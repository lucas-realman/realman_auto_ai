from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import Field, computed_field

from crm.schemas.base import CamelModel

CustomerLevelEnum = Literal["S", "A", "B", "C", "D"]


# ── Contact ──


class ContactCreate(CamelModel):
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_decision_maker: bool = False


class ContactResponse(CamelModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_decision_maker: bool = False
    created_at: datetime
    updated_at: datetime


# ── Customer ──


class CustomerCreate(CamelModel):
    company_name: str = Field(..., max_length=200)
    industry: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    level: Optional[CustomerLevelEnum] = "C"
    address: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class CustomerUpdate(CamelModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    level: Optional[CustomerLevelEnum] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class CustomerResponse(CamelModel):
    id: uuid.UUID
    company_name: str
    industry: Optional[str] = None
    region: Optional[str] = None
    level: Optional[CustomerLevelEnum] = "C"
    address: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    owner_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    ai_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


if TYPE_CHECKING:
    from crm.schemas.lead import LeadResponse
    from crm.schemas.opportunity import OpportunityResponse
    from crm.schemas.activity import ActivityResponse


class CustomerDetailResponse(CustomerResponse):
    """客户 360 视图，包含关联的联系人、线索、商机、活动。"""

    contacts: list[ContactResponse] = []
    recent_leads: list[LeadResponse] = []
    opportunities: list[OpportunityResponse] = []
    recent_activities: list[ActivityResponse] = []


class CustomerListResponse(CamelModel):
    items: list[CustomerResponse]
    total: int
    page: int
    size: int

    @computed_field
    @property
    def pages(self) -> int:
        return -(-self.total // self.size) if self.size > 0 else 0
