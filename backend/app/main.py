import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import config
from .db import engine
from .routes import auth_routes, dashboard, diagnostic, reports

app = FastAPI(title="AI Pulse API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


class BodyLimit:
    """Bound the body even when Content-Length is absent or untruthful."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        messages, size = [], 0
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            size += len(msg.get("body", b""))
            if size > 65536:
                return await JSONResponse(
                    {"detail": "Request is too large."}, status_code=413
                )(scope, receive, send)
            messages.append(msg)
            if not msg.get("more_body"):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)


app.add_middleware(BodyLimit)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic errors can echo submitted passwords/answers. Return only a generic safe message.
    return JSONResponse(
        status_code=422,
        content={"detail": "Please check the required fields and answer lengths."},
    )


app.include_router(auth_routes.router)
app.include_router(diagnostic.router)
app.include_router(reports.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok", "ai_mode": config.AI_MODE}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "healthy", "ai_mode": config.AI_MODE}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "unreachable",
                "ai_mode": config.AI_MODE,
            },
        )


# API routes must precede this mount. Only the built frontend is served, never
# the backend directory containing configuration or the persistent database.
if config.STATIC_DIR:
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="web")
