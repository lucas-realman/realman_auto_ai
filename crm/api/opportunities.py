from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from crm.database import get_session
from crm.models.activity import Activity
from crm.models.opportunity import Opportunity, OpportunityStage
from crm.schemas.activity import ActivityListResponse, ActivityResponse
from crm.schemas.opportunity import (
    OpportunityCreate,
    OpportunityListResponse,
    OpportunityResponse,
    OpportunityUpdate,
)
from crm.services.audit import log_audit
from crm.services.event_publisher import publish_event

router = APIRouter(prefix="/api/v1/opportunities", tags=["Opportunities"])


def _opportunity_to_dict(opp: Opportunity) -> dict:
    return {
        c.name: (str(v) if isinstance(v, UUID) else v)
        for c in Opportunity.__table__.columns
        if (v := getattr(opp, c.name, None)) is not None
    }


# ---------- POST / ----------
@router.post(
    "/",
    response_model=OpportunityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_opportunity(
    body: OpportunityCreate,
    session: AsyncSession = Depends(get_session),
):
    opp = Opportunity(**body.model_dump())
    session.add(opp)
    await session.flush()

    await log_audit(
        session=session,
        entity_type="opportunities",
        entity_id=opp.id,
        action="create",
        new_values=_opportunity_to_dict(opp),
    )

    await session.commit()
    await session.refresh(opp)
    return opp


# ---------- GET / ----------
@router.get("/", response_model=OpportunityListResponse)
async def list_opportunities(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    stage: Optional[str] = Query(None),
    customer_id: Optional[UUID] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Opportunity)
    count_stmt = select(func.count()).select_from(Opportunity)

    if stage is not None:
        stmt = stmt.where(Opportunity.stage == stage)
        count_stmt = count_stmt.where(Opportunity.stage == stage)

    if customer_id is not None:
        stmt = stmt.where(Opportunity.customer_id == customer_id)
        count_stmt = count_stmt.where(Opportunity.customer_id == customer_id)

    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size)
    rows = (await session.execute(stmt)).scalars().all()

    return OpportunityListResponse(items=rows, total=total, page=page, size=size)


# ---------- GET /{opp_id} ----------
@router.get("/{opp_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opp_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    opp = await session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


# ---------- PUT /{opp_id} ----------
@router.put("/{opp_id}", response_model=OpportunityResponse)
async def update_opportunity(
    opp_id: UUID,
    body: OpportunityUpdate,
    session: AsyncSession = Depends(get_session),
):
    opp = await session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    old_values = _opportunity_to_dict(opp)
    old_stage = opp.stage

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(opp, field, value)

    await session.flush()

    new_values = _opportunity_to_dict(opp)

    await log_audit(
        session=session,
        entity_type="opportunities",
        entity_id=opp.id,
        action="update",
        old_values=old_values,
        new_values=new_values,
    )

    # 若 stage 发生变更，发布事件
    new_stage = opp.stage
    if old_stage != new_stage:
        await publish_event(
            "crm.opportunity.stage_changed",
            {
                "opportunity_id": str(opp.id),
                "old_stage": old_stage.value if isinstance(old_stage, OpportunityStage) else old_stage,
                "new_stage": new_stage.value if isinstance(new_stage, OpportunityStage) else new_stage,
            },
        )

    await session.commit()
    await session.refresh(opp)
    return opp


# ---------- GET /{opp_id}/activities ----------
@router.get("/{opp_id}/activities", response_model=ActivityListResponse)
async def list_opportunity_activities(
    opp_id: UUID,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    # 先确认 opportunity 存在
    opp = await session.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    stmt = select(Activity).where(Activity.opportunity_id == opp_id)
    count_stmt = (
        select(func.count())
        .select_from(Activity)
        .where(Activity.opportunity_id == opp_id)
    )

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * size).limit(size)
    rows = (await session.execute(stmt)).scalars().all()

    return ActivityListResponse(items=rows, total=total, page=page, size=size)
