from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.audit_log import AuditLog


async def log_audit(
    session: AsyncSession,
    table_name: str,
    record_id: UUID,
    action: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    user_id: UUID | None = None,
) -> AuditLog:
    """创建一条审计日志记录并刷写到数据库（不提交事务）。"""
    audit = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        user_id=user_id,
    )
    session.add(audit)
    await session.flush()
    return audit
