"""
Internal API routes — called only by the worker/bot services.
Not exposed to admin panel users directly.
These endpoints have no JWT auth (they rely on internal Docker network isolation).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.db.session import get_db
from app.models.job import MonitoringJob, JobStatus
from app.models.otp_request import OTPRequest, OTPStatus, Log, LogLevel, Notification
from app.core.redis import publish_event

router = APIRouter()


# ── Job status update ──────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: JobStatus


@router.patch("/jobs/internal/{job_id}/status")
async def update_job_status(job_id: int, body: StatusUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = body.status
    job.updated_at = datetime.now(timezone.utc)
    await db.commit()

    await publish_event(f"job:{job_id}", "job_update", {
        "job_id": job_id,
        "status": body.status,
    })
    return {"ok": True}


class CheckUpdate(BaseModel):
    check_count: int


@router.patch("/jobs/internal/{job_id}/check")
async def update_check_count(job_id: int, body: CheckUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return {"ok": False}
    job.check_count = body.check_count
    job.last_check_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


class ErrorUpdate(BaseModel):
    error_message: str


@router.patch("/jobs/internal/{job_id}/error")
async def update_job_error(job_id: int, body: ErrorUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return {"ok": False}
    job.error_message = body.error_message
    job.error_count += 1
    await db.commit()
    return {"ok": True}


# ── Appointment found notification ────────────────────────────

class FoundPayload(BaseModel):
    job_id: int
    screenshot_path: Optional[str] = None


@router.post("/jobs/internal/found")
async def appointment_found(body: FoundPayload, db: AsyncSession = Depends(get_db)):
    """Called when worker finds an available appointment slot."""
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == body.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = JobStatus.FOUND
    job.found_at = datetime.now(timezone.utc)
    job.screenshot_path = body.screenshot_path
    await db.commit()

    # Publish WebSocket event
    await publish_event("system:appointments", "appointment_found", {
        "job_id": body.job_id,
        "user_id": job.user_id,
        "screenshot_path": body.screenshot_path,
        "found_at": job.found_at.isoformat(),
    })

    # Trigger Telegram notification (via Redis pub/sub)
    await publish_event("notifications:telegram", "appointment_found", {
        "job_id": body.job_id,
        "user_id": job.user_id,
        "profile_id": job.profile_id,
        "screenshot_path": body.screenshot_path,
    })

    return {"ok": True}


# ── Start job (from bot after profile creation) ────────────────

class StartJobPayload(BaseModel):
    profile_id: int
    user_id: int


@router.post("/jobs/internal/start")
async def start_job(body: StartJobPayload, db: AsyncSession = Depends(get_db)):
    job = MonitoringJob(
        user_id=body.user_id,
        profile_id=body.profile_id,
        status=JobStatus.QUEUED,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await publish_event("jobs:queue", "job_queued", {
        "job_id": job.id,
        "user_id": body.user_id,
        "profile_id": body.profile_id,
    })
    return {"job_id": job.id}


# ── OTP create (from worker) ────────────────────────────────────

class OTPCreatePayload(BaseModel):
    job_id: int
    screenshot_path: Optional[str] = None
    context_data: Optional[str] = None


@router.post("/otp/internal/create")
async def create_otp_request(body: OTPCreatePayload, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == body.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    otp = OTPRequest(
        user_id=job.user_id,
        job_id=body.job_id,
        status=OTPStatus.PENDING,
        screenshot_path=body.screenshot_path,
        context_data=body.context_data,
    )
    db.add(otp)
    await db.commit()
    await db.refresh(otp)

    # Notify admin via WebSocket
    await publish_event("otp:pending", "otp_required", {
        "otp_id": otp.id,
        "job_id": body.job_id,
        "user_id": job.user_id,
        "screenshot_path": body.screenshot_path,
        "created_at": otp.created_at.isoformat(),
    })

    # Notify admin via Telegram
    await publish_event("notifications:telegram", "otp_required", {
        "otp_id": otp.id,
        "job_id": body.job_id,
        "user_id": job.user_id,
        "screenshot_path": body.screenshot_path,
    })

    return {"id": otp.id, "status": "pending"}


@router.get("/otp/{otp_id}")
async def get_otp(otp_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OTPRequest).where(OTPRequest.id == otp_id))
    otp = result.scalar_one_or_none()
    if not otp:
        raise HTTPException(status_code=404, detail="OTP not found")
    return {"id": otp.id, "status": otp.status, "otp_value": otp.otp_value}


# ── Internal log write ─────────────────────────────────────────

class LogPayload(BaseModel):
    job_id: Optional[int] = None
    level: LogLevel = LogLevel.INFO
    source: str
    message: str
    extra: Optional[str] = None


@router.post("/logs/internal")
async def write_log(body: LogPayload, db: AsyncSession = Depends(get_db)):
    log = Log(**body.model_dump())
    db.add(log)
    await db.commit()
    return {"ok": True}
