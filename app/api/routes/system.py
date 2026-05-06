"""System routes: health, stats."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta

from app.db.session import get_db
from app.models.user import User
from app.models.job import MonitoringJob, JobStatus
from app.models.otp_request import OTPRequest, OTPStatus
from app.api.routes.auth import get_current_admin
from app.core.redis import get_redis

router = APIRouter()


@router.get("/stats")
async def system_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    # Jobs
    active_jobs = await db.execute(
        select(func.count()).where(MonitoringJob.status == JobStatus.SEARCHING)
    )
    found_jobs = await db.execute(
        select(func.count()).where(MonitoringJob.status == JobStatus.FOUND)
    )
    total_jobs = await db.execute(select(func.count()).select_from(MonitoringJob))

    # OTP
    pending_otp = await db.execute(
        select(func.count()).where(OTPRequest.status == OTPStatus.PENDING)
    )

    # Users
    total_users = await db.execute(select(func.count()).select_from(User))

    # Success rate (found / total)
    total = total_jobs.scalar() or 1
    found = found_jobs.scalar() or 0

    return {
        "active_jobs": active_jobs.scalar(),
        "found_jobs": found,
        "total_jobs": total_jobs.scalar(),
        "pending_otp": pending_otp.scalar(),
        "total_users": total_users.scalar(),
        "success_rate": round(found / total * 100, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(func.now()))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        r = get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "status": "healthy" if (db_ok and redis_ok) else "degraded",
    }
