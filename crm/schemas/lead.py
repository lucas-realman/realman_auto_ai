from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import Field

from crm.schemas.base import CamelModel


# ── 枚举值以 Literal 约束，保持与 crm-api.yaml 一致 ──
from typing import Literal

LeadSourceEnum = Literal[
    "website", "exhibition", "referral", "cold_call", "dingtalk", "other"
]
LeadStatusEnum = Literal[
    "new", "contacted", "qualified", "converted", "closed"
]


class LeadCreate(CamelModel):
    company_name: str = Field(..., max_length=200)
    contact_name: str = Field(..., max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = None
    source: Optional[LeadSourceEnum] = None
    industry: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class LeadUpdate(CamelModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[LeadStatusEnum] = None
    owner_id: Optional[uuid.UUID] = None
    ai_score: Optional[float] = Field(None, ge=0, le=100)
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class LeadResponse(CamelModel):
    id: uuid.UUID
    company_name: str
    contact_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    source: Optional[LeadSourceEnum] = None
    industry: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    status: LeadStatusEnum = "new"
    owner_id: Optional[uuid.UUID] = None
    ai_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class LeadListResponse(CamelModel):
    items: list[LeadResponse]
    total: int
    page: int
    size: int
    pages: int
