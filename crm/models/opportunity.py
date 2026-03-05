import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class OpportunityStage(str, enum.Enum):
    initial_contact = "initial_contact"
    needs_confirmed = "needs_confirmed"
    solution_review = "solution_review"
    negotiation = "negotiation"
    won = "won"
    lost = "lost"


class ProductType(str, enum.Enum):
    standard = "standard"
    custom = "custom"


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"

    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False,
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, server_default="0",
    )

    stage: Mapped[str] = mapped_column(
        String(30),
        default=OpportunityStage.initial_contact.value,
        server_default="initial_contact",
    )

    product_type: Mapped[str] = mapped_column(
        String(20),
        default=ProductType.standard.value,
        server_default="standard",
    )

    expected_close_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
    )

    win_rate: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True, comment="AI 预测赢率",
    )

    lost_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    # ---- relationships ----
    customer = relationship("Customer", foreign_keys=[customer_id], lazy="selectin")
    owner = relationship("User", foreign_keys=[owner_id], lazy="selectin")
