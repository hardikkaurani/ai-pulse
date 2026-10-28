import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine, SessionLocal
from . import models, seed
from .routes import auth_routes, diagnostic, reports, dashboard

Base.metadata.create_all(bind=engine)

# Auto-seed initial demo accounts on first run if database is empty
try:
    with SessionLocal() as _db:
        if _db.query(models.User).count() == 0:
            seed.run()
except Exception:
    pass

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


@app.get("/seed")
def trigger_seed():
    """Idempotently seed demo accounts if the database is empty."""
    with SessionLocal() as db:
        user_count = db.query(models.User).count()
        if user_count == 0:
            seed.run()
            return {"status": "seeded", "message": "Demo data seeded successfully"}
        return {"status": "already_seeded", "users": user_count}
