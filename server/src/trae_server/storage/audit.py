"""审计日志工具。"""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from .models import AuditLog, to_json_safe


def write_audit(
    db: DbSession,
    user_id: str,
    action: str,
    resource: str = "",
    payload: dict | None = None,
    api_key_name: str = "",
    ip: str = "",
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        api_key_name=api_key_name,
        action=action,
        resource=resource,
        payload=to_json_safe(payload) if payload else None,
        ip=ip,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry