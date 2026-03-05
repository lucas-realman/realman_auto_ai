from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import Field, computed_field

from crm.schemas.base import CamelModel

OpportunityStageEnum = Literal[
    "initial_contact",
    "needs_confirmed",
    "solution_review",
    "negotiation",
    "won",
    "lost",
]

ProductTypeEnum = Literal["standard", "custom"]


class OpportunityCreate(CamelModel):
    name: str = Field(..., max_length=200)
    customer_id: uuid.UUID
    amount: Optional[float] = Field(None, ge=0)
    stage: Optional[OpportunityStageEnum] = "initial_contact"
    expected_close_date: Optional[date] = None
    product_type: Optional[ProductTypeEnum] = "standard"
    notes: Optional[str] = None


class OpportunityUpdate(CamelModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    stage: Optional[OpportunityStageEnum] = None
    expected_close_date: Optional[date] = None
    win_rate: Optional[float] = Field(None, ge=0, le=100)
    lost_reason: Optional[str] = None
    notes: Optional[str] = None


class OpportunityResponse(CamelModel):
    id: uuid.UUID
    name: str
    customer_id: uuid.UUID
    amount: Optional[float] = None
    stage: OpportunityStageEnum = "initial_contact"
    expected_close_date: Optional[date] = None
    product_type: Optional[ProductTypeEnum] = "standard"
    notes: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None
    win_rate: Optional[float] = None
    lost_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(CamelModel):
    items: list[OpportunityResponse]
    total: int
    page: int
    size: int

    @computed_field
    @property
    def pages(self) -> int:
        return -(-self.total // self.size) if self.size > 0 else 0
