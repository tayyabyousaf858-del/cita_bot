"""Logs routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.otp_request import Log, LogLevel
from app.api.routes.auth import get_current_admin

router = APIRouter()


class LogOut(BaseModel):
    id: int
    job_id: Optional[int]
    level: LogLevel
    source: str
    message: str
    extra: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[LogOut])
async def list_logs(
    job_id: Optional[int] = None,
    level: Optional[LogLevel] = None,
    source: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_admin),
):
    query = select(Log).order_by(desc(Log.created_at)).offset(skip).limit(limit)
    if job_id:
        query = query.where(Log.job_id == job_id)
    if level:
        query = query.where(Log.level == level)
    if source:
        query = query.where(Log.source == source)
    result = await db.execute(query)
    return result.scalars().all()
