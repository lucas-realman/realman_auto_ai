from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crm.database import get_session
from crm.models.customer import Customer, Contact
from crm.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerDetailResponse,
    CustomerListResponse,
    ContactCreate,
    ContactResponse,
)
from crm.services.audit import log_audit

router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


# ---------- POST / ----------
@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    body: CustomerCreate,
    session: AsyncSession = Depends(get_session),
):
    customer = Customer(**body.model_dump())
    session.add(customer)
    await session.flush()

    await log_audit(
        session=session,
        entity_type="customers",
        entity_id=customer.id,
        action="create",
        new_values=body.model_dump(mode="json"),
    )

    await session.commit()
    await session.refresh(customer)
    return customer


# ---------- GET / ----------
@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    tier: Optional[str] = Query(None, description="客户等级筛选"),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Customer)

    if tier is not None:
        stmt = stmt.where(Customer.level == tier)

    # total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    # pagination
    offset = (page - 1) * size
    stmt = stmt.order_by(Customer.created_at.desc()).offset(offset).limit(size)
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return CustomerListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


# ---------- GET /{customer_id} ----------
@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.contacts))
    )
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return customer


# ---------- PUT /{customer_id} ----------
@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    body: CustomerUpdate,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Customer).where(Customer.id == customer_id)
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    old_values = {
        c.key: getattr(customer, c.key)
        for c in Customer.__table__.columns
    }

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    await session.flush()

    new_values = {
        c.key: getattr(customer, c.key)
        for c in Customer.__table__.columns
    }

    await log_audit(
        session=session,
        entity_type="customers",
        entity_id=customer.id,
        action="update",
        old_values={k: str(v) for k, v in old_values.items()},
        new_values={k: str(v) for k, v in new_values.items()},
    )

    await session.commit()
    await session.refresh(customer)
    return customer


# ---------- POST /{customer_id}/contacts ----------
@router.post(
    "/{customer_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    customer_id: UUID,
    body: ContactCreate,
    session: AsyncSession = Depends(get_session),
):
    # 确认客户存在
    stmt = select(Customer).where(Customer.id == customer_id)
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    contact = Contact(**body.model_dump(), customer_id=customer_id)
    session.add(contact)
    await session.flush()

    await log_audit(
        session=session,
        entity_type="contacts",
        entity_id=contact.id,
        action="create",
        new_values={**body.model_dump(mode="json"), "customer_id": str(customer_id)},
    )

    await session.commit()
    await session.refresh(contact)
    return contact
