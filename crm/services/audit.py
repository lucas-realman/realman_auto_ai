from datetime import date, datetime
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from crm.models.audit_log import AuditLog


def _json_safe(d: Optional[dict]) -> Optional[dict]:
    """Make dict values JSON-serializable (datetime, UUID, enum → str)."""
    if d is None:
        return None
    out = {}
    for k, v in d.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, UUID):
            out[k] = str(v)
        elif hasattr(v, "value"):  # Enum
            out[k] = v.value
        else:
            out[k] = v
    return out


async def log_audit(
    session: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    action: str,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    user_id: Optional[UUID] = None,
) -> AuditLog:
    """创建一条审计日志记录并刷写到数据库（不提交事务）。"""
    audit = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_values=_json_safe(old_values),
        new_values=_json_safe(new_values),
        user_id=user_id,
    )
    session.add(audit)
    await session.flush()
    return audit
