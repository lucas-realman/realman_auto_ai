import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class LeadSource(str, enum.Enum):
    website = "website"
    exhibition = "exhibition"
    referral = "referral"
    cold_call = "cold_call"
    dingtalk = "dingtalk"
    other = "other"


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    converted = "converted"
    closed = "closed"


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"

    company_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )

    contact_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(20), default=LeadSource.other.value, server_default="other",
    )

    industry: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), default=LeadStatus.new.value, server_default="new",
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    pool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="所属线索池",
    )

    ai_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="AI 评分 0-100",
    )

    ai_score_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 评分理由",
    )

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), server_default="{}",
    )

    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="转化时间",
    )

    # ---- relationships ----
    owner = relationship("User", foreign_keys=[owner_id], lazy="selectin")
