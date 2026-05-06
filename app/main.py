"""CitaMonitor - FastAPI Backend Main"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import structlog

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import init_db
from app.api.routes import auth, users, jobs, otp, logs, system, ws
from app.api.routes.internal import router as internal_router
from app.core.redis import init_redis, get_redis
from app.services.notifications import run_notification_service
from app.api.routes.ws import start_subscriber

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting CitaMonitor backend", version="1.0.0")
    await init_db()
    await init_redis()
    redis = get_redis()
    asyncio.create_task(run_notification_service(redis))
    start_subscriber()
    logger.info("Backend ready")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="CitaMonitor API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/screenshots", StaticFiles(directory="/app/screenshots"), name="screenshots")

app.include_router(auth.router,       prefix="/api/auth",   tags=["auth"])
app.include_router(users.router,      prefix="/api/users",  tags=["users"])
app.include_router(jobs.router,       prefix="/api/jobs",   tags=["jobs"])
app.include_router(otp.router,        prefix="/api/otp",    tags=["otp"])
app.include_router(logs.router,       prefix="/api/logs",   tags=["logs"])
app.include_router(system.router,     prefix="/api/system", tags=["system"])
app.include_router(ws.router,         prefix="/ws",         tags=["websocket"])
app.include_router(internal_router,   prefix="/api",        tags=["internal"])


@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "citamonitor-backend"}
