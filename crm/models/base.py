"""SQLAlchemy 声明式基类及公共 Mixin。

所有业务模型继承 Base，并可选混入 TimestampMixin 获取 id / created_at / updated_at / deleted_at。
"""

from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """声明式基类，所有 ORM 模型都需继承此类。"""

    pass


class TimestampMixin:
    """提供 id / created_at / updated_at / deleted_at 公共列。

    约定:
        - id: UUID 主键，由数据库自动生成
        - created_at / updated_at: 自动维护时间戳
        - deleted_at: 软删除标记，NULL 表示未删除
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.uuid_generate_v4(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
