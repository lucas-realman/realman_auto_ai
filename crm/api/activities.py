from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from crm.database import get_session
from crm.models.activity import Activity
from crm.schemas.activity import (
    ActivityCreate,
    ActivityResponse,
    ActivityListResponse,
)
from crm.services.audit import log_audit

router = APIRouter(prefix="/api/v1/activities", tags=["Activities"])


@router.post("/", response_model=ActivityResponse, status_code=201)
async def create_activity(
    body: ActivityCreate,
    session: AsyncSession = Depends(get_session),
):
    """创建一条活动记录，并写入审计日志。"""

    activity = Activity(**body.model_dump())
    session.add(activity)
    await session.flush()

    await log_audit(
        session=session,
        entity_type="activities",
        entity_id=activity.id,
        action="create",
        old_values=None,
        new_values=body.model_dump(mode="json"),
    )

    await session.commit()
    await session.refresh(activity)

    return activity


@router.get("/", response_model=ActivityListResponse)
async def list_activities(
    customer_id: Optional[UUID] = Query(None, description="按客户 ID 过滤"),
    opportunity_id: Optional[UUID] = Query(None, description="按商机 ID 过滤"),
    lead_id: Optional[UUID] = Query(None, description="按线索 ID 过滤"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    session: AsyncSession = Depends(get_session),
):
    """分页查询活动列表，支持按关联实体过滤。"""

    base_query = select(Activity)
    count_query = select(func.count()).select_from(Activity)

    if customer_id is not None:
        base_query = base_query.where(Activity.customer_id == customer_id)
        count_query = count_query.where(Activity.customer_id == customer_id)

    if opportunity_id is not None:
        base_query = base_query.where(Activity.opportunity_id == opportunity_id)
        count_query = count_query.where(Activity.opportunity_id == opportunity_id)

    if lead_id is not None:
        base_query = base_query.where(Activity.lead_id == lead_id)
        count_query = count_query.where(Activity.lead_id == lead_id)

    total = (await session.execute(count_query)).scalar() or 0

    offset = (page - 1) * size
    rows_query = (
        base_query
        .order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    items = (await session.execute(rows_query)).scalars().all()

    return ActivityListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )
