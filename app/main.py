"""FastAPI application entry — wires everything together."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import admin, auth, categories, complaints, officers, stats
from .security import limiter

settings = get_settings()

app = FastAPI(
    title="Shikayat API",
    description="Civic complaint & issue tracker for Pakistani cities.",
    version=settings.APP_VERSION,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tables are created at startup (SQLite dev convenience; Postgres via Alembic/migrations)
Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(complaints.router)
app.include_router(officers.router)
app.include_router(admin.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Slow down!"})


# Serve the SPA (mounted last so /api routes win; html=True serves static/index.html at /)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
