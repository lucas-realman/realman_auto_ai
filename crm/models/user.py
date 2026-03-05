import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    sales = "sales"
    readonly = "readonly"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    dingtalk_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, comment="钉钉 userid",
    )

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="姓名",
    )

    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )

    department: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(50), default=UserRole.sales.value, server_default="sales",
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String, nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
