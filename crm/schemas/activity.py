from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from crm.schemas.base import CamelModel

ActivityTypeEnum = Literal["call", "visit", "email", "meeting", "note"]


class ActivityCreate(CamelModel):
    type: ActivityTypeEnum
    subject: str = Field(..., max_length=200)
    content: Optional[str] = None
    customer_id: Optional[uuid.UUID] = None
    opportunity_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    scheduled_at: Optional[datetime] = None


class ActivityResponse(CamelModel):
    id: uuid.UUID
    type: ActivityTypeEnum
    subject: str
    content: Optional[str] = None
    customer_id: Optional[uuid.UUID] = None
    opportunity_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    scheduled_at: Optional[datetime] = None
    user_id: Optional[uuid.UUID] = None
    ai_summary: Optional[str] = None
    created_at: datetime


class ActivityListResponse(CamelModel):
    items: list[ActivityResponse]
    total: int
    page: int
    size: int
    pages: int
