import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pgvector 包未安装时不阻断导入
    Vector = None


class CustomerLevel(str, enum.Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    company_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )

    region: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )

    level: Mapped[str] = mapped_column(
        String(1), default=CustomerLevel.C.value, server_default="C",
    )

    address: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True, comment="转化来源",
    )

    ai_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 客户画像",
    )

    # pgvector 1024 维向量；若 pgvector 未安装则跳过列定义
    if Vector is not None:
        ai_embedding = mapped_column(
            Vector(1024), nullable=True, comment="客户向量",
        )

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), server_default="{}",
    )

    # ---- relationships ----
    owner = relationship("User", foreign_keys=[owner_id], lazy="selectin")
    lead = relationship("Lead", foreign_keys=[lead_id], lazy="selectin")
    contacts = relationship("Contact", back_populates="customer", lazy="selectin")


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
    )

    title: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )

    department: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )

    is_decision_maker: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
    )

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    # ---- relationships ----
    customer = relationship("Customer", back_populates="contacts", lazy="selectin")
