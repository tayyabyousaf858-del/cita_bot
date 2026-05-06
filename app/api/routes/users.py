"""Users management routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.job import MonitoringJob, JobStatus
from app.api.routes.auth import get_current_admin

router = APIRouter()


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    is_active: bool
    is_banned: bool
    created_at: datetime
    last_seen: Optional[datetime]
    job_count: int = 0

    class Config:
        from_attributes = True


@router.get("/", response_model=List[UserOut])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    query = select(User).order_by(desc(User.created_at)).offset(skip).limit(limit)
    if search:
        query = query.where(
            (User.username.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%"))
        )
    result = await db.execute(query)
    users = result.scalars().all()

    out = []
    for u in users:
        job_count_result = await db.execute(
            select(func.count()).where(MonitoringJob.user_id == u.id)
        )
        out.append(UserOut(
            **{c.name: getattr(u, c.name) for c in u.__table__.columns},
            job_count=job_count_result.scalar() or 0
        ))
    return out


@router.get("/stats")
async def user_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    total = await db.execute(select(func.count()).select_from(User))
    active = await db.execute(select(func.count()).where(User.is_active == True))
    banned = await db.execute(select(func.count()).where(User.is_banned == True))
    return {
        "total": total.scalar(),
        "active": active.scalar(),
        "banned": banned.scalar(),
    }


@router.patch("/{user_id}/ban")
async def ban_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = not user.is_banned
    await db.commit()
    return {"id": user_id, "is_banned": user.is_banned}
