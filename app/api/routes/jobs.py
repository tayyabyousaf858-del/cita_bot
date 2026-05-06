"""Monitoring jobs routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.job import MonitoringJob, JobStatus
from app.models.user import User
from app.models.profile import Profile
from app.api.routes.auth import get_current_admin
from app.core.redis import publish_event

router = APIRouter()


class JobOut(BaseModel):
    id: int
    user_id: int
    profile_id: int
    status: JobStatus
    worker_id: Optional[str]
    check_count: int
    last_check_at: Optional[datetime]
    found_at: Optional[datetime]
    screenshot_path: Optional[str]
    error_message: Optional[str]
    error_count: int
    created_at: datetime
    updated_at: datetime
    # Joined
    user_name: Optional[str] = None
    province_name: Optional[str] = None
    tramite_name: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[JobOut])
async def list_jobs(
    status: Optional[JobStatus] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    query = select(MonitoringJob).order_by(desc(MonitoringJob.created_at)).offset(skip).limit(limit)
    if status:
        query = query.where(MonitoringJob.status == status)
    result = await db.execute(query)
    jobs = result.scalars().all()

    out = []
    for j in jobs:
        user_res = await db.execute(select(User).where(User.id == j.user_id))
        user = user_res.scalar_one_or_none()
        profile_res = await db.execute(select(Profile).where(Profile.id == j.profile_id))
        profile = profile_res.scalar_one_or_none()

        out.append(JobOut(
            **{c.name: getattr(j, c.name) for c in j.__table__.columns},
            user_name=user.first_name if user else None,
            province_name=profile.province_name if profile else None,
            tramite_name=profile.tramite_name if profile else None,
        ))
    return out


@router.get("/stats")
async def job_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    stats = {}
    for status in JobStatus:
        res = await db.execute(
            select(func.count()).where(MonitoringJob.status == status)
        )
        stats[status.value] = res.scalar()
    return stats


@router.post("/{job_id}/stop")
async def stop_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.STOPPED
    await db.commit()
    # Signal worker via Redis
    await publish_event(f"job:{job_id}", "job_stop", {"job_id": job_id})
    return {"job_id": job_id, "status": "stopped"}


@router.post("/{job_id}/restart")
async def restart_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.QUEUED
    job.error_count = 0
    job.error_message = None
    await db.commit()
    await publish_event("jobs:queue", "job_queued", {"job_id": job_id})
    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}")
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    result = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
