from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from crm.database import get_session
from crm.models.lead import Lead, LeadStatus
from crm.models.customer import Customer, CustomerLevel
from crm.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
    LeadStatusEnum,
)
from crm.services.audit import log_audit

router = APIRouter(prefix="/api/v1/leads", tags=["Leads"])


@router.post("/", response_model=LeadResponse, status_code=201)
async def create_lead(
    payload: LeadCreate,
    session: AsyncSession = Depends(get_session),
):
    lead = Lead(**payload.model_dump())
    session.add(lead)
    await session.flush()

    await log_audit(
        session,
        "leads",
        lead.id,
        "create",
        None,
        payload.model_dump(mode="json"),
        None,
    )
    await session.commit()
    await session.refresh(lead)
    return lead


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[LeadStatusEnum] = Query(None),
    assigned_to: Optional[UUID] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    base = select(Lead)
    count_base = select(func.count(Lead.id))

    if status is not None:
        base = base.where(Lead.status == status)
        count_base = count_base.where(Lead.status == status)
    if assigned_to is not None:
        base = base.where(Lead.assigned_to == assigned_to)
        count_base = count_base.where(Lead.assigned_to == assigned_to)

    total = (await session.execute(count_base)).scalar() or 0

    offset = (page - 1) * size
    query = base.order_by(Lead.created_at.desc()).offset(offset).limit(size)
    rows = (await session.execute(query)).scalars().all()

    return LeadListResponse(items=rows, total=total, page=page, size=size)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    session: AsyncSession = Depends(get_session),
):
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    old_values = {
        c.key: getattr(lead, c.key)
        for c in Lead.__table__.columns
    }

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    await session.flush()

    new_values = {
        c.key: getattr(lead, c.key)
        for c in Lead.__table__.columns
    }

    await log_audit(
        session,
        "leads",
        lead.id,
        "update",
        old_values,
        new_values,
        None,
    )
    await session.commit()
    await session.refresh(lead)
    return lead


@router.post("/{lead_id}/convert", response_model=LeadResponse, status_code=201)
async def convert_lead(
    lead_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.status == LeadStatus.converted:
        raise HTTPException(status_code=400, detail="Lead already converted")

    customer = Customer(
        name=lead.company or lead.contact_name,
        level=CustomerLevel.C,
        industry=getattr(lead, "industry", None),
        source=lead.source,
    )
    session.add(customer)
    await session.flush()

    old_status = lead.status
    lead.status = LeadStatus.converted
    lead.customer_id = customer.id
    await session.flush()

    await log_audit(
        session,
        "leads",
        lead.id,
        "convert",
        {"status": old_status},
        {"status": lead.status, "customer_id": str(customer.id)},
        None,
    )
    await log_audit(
        session,
        "customers",
        customer.id,
        "create",
        None,
        {"name": customer.name, "level": customer.level, "source": customer.source},
        None,
    )
    await session.commit()
    await session.refresh(lead)
    return lead
