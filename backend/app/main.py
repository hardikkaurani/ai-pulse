import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routes import auth_routes, diagnostic, reports, dashboard

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Pulse API")

cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()] if cors_origins_raw != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(diagnostic.router)
app.include_router(reports.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}
