import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ActivityType(str, enum.Enum):
    call = "call"
    visit = "visit"
    email = "email"
    meeting = "meeting"
    note = "note"


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )

    type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="call/visit/email/meeting/note",
    )

    subject: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )

    content: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True,
    )

    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True,
    )

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    ai_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 活动摘要",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ---- relationships ----
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    customer = relationship("Customer", foreign_keys=[customer_id], lazy="selectin")
    opportunity = relationship("Opportunity", foreign_keys=[opportunity_id], lazy="selectin")
    lead = relationship("Lead", foreign_keys=[lead_id], lazy="selectin")
