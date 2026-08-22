"""Vercel serverless entry — imports the FastAPI app.

SQLite is used at runtime (stored in /tmp on Vercel, ephemeral per instance).
For a persistent deployment point DATABASE_URL at a hosted Postgres.
"""
from app.main import app

# Vercel expects a module-level `app` (FastAPI) — handled above.
# In production, make sure the DB is initialized before first request.
from app.database import Base, engine

Base.metadata.create_all(bind=engine)
