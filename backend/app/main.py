import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine, SessionLocal
from . import models, seed
from .config import ENVIRONMENT
from .routes import auth_routes, diagnostic, reports, dashboard, insights

Base.metadata.create_all(bind=engine)

# Auto-seed initial demo accounts on first run if database is empty
try:
    with SessionLocal() as _db:
        if _db.query(models.User).count() == 0:
            seed.run(reset=False)
except Exception:
    pass

app = FastAPI(title="AI Pulse API")

cors_origins_raw = os.getenv("CORS_ORIGINS", "").strip()
if cors_origins_raw:
    origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
elif ENVIRONMENT == "production":
    origins = ["https://ai-pulse-rho-one.vercel.app"]
else:
    origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

# If wildcard origin is explicitly requested, credentials must be disabled per CORS specification
allow_creds = origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(diagnostic.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
app.include_router(insights.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/seed")
def trigger_seed():
    """Idempotently seed demo accounts if the database is empty in non-production environments."""
    if ENVIRONMENT == "production":
        raise HTTPException(status_code=403, detail="Seeding is disabled in production environments")

    with SessionLocal() as db:
        user_count = db.query(models.User).count()
        if user_count == 0:
            seed.run(reset=False)
            return {"status": "seeded", "message": "Demo data seeded successfully"}
        return {"status": "already_seeded", "users": user_count}
