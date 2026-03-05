import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    convert = "convert"
    stage_change = "stage_change"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="create/update/delete/convert/stage_change",
    )

    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="lead/customer/opportunity/activity",
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )

    old_values: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )

    new_values: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
