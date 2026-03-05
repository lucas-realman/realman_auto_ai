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
    entity_type: str = Query(..., description="关联实体类型，如 customer / lead / opportunity"),
    entity_id: UUID = Query(..., description="关联实体 ID"),
    body: ActivityCreate = ...,
    session: AsyncSession = Depends(get_session),
):
    """创建一条活动记录，并写入审计日志。"""

    activity = Activity(
        entity_type=entity_type,
        entity_id=entity_id,
        **body.model_dump(),
    )
    session.add(activity)
    await session.flush()

    await log_audit(
        session=session,
        table_name="activities",
        record_id=activity.id,
        action="create",
        old_values=None,
        new_values={
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            **body.model_dump(mode="json"),
        },
    )

    await session.commit()
    await session.refresh(activity)

    return activity


@router.get("/", response_model=ActivityListResponse)
async def list_activities(
    entity_type: str | None = Query(None, description="按实体类型过滤"),
    entity_id: UUID | None = Query(None, description="按实体 ID 过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    session: AsyncSession = Depends(get_session),
):
    """分页查询活动列表，支持按 entity_type 和 entity_id 过滤。"""

    base_query = select(Activity)
    count_query = select(func.count()).select_from(Activity)

    if entity_type is not None:
        base_query = base_query.where(Activity.entity_type == entity_type)
        count_query = count_query.where(Activity.entity_type == entity_type)

    if entity_id is not None:
        base_query = base_query.where(Activity.entity_id == entity_id)
        count_query = count_query.where(Activity.entity_id == entity_id)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    rows_query = (
        base_query
        .order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(rows_query)
    items = result.scalars().all()

    return ActivityListResponse(
        items=[ActivityResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
