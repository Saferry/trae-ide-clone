"""API Key 鉴权。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status

from ..config import get_config


@dataclass
class APIKeyContext:
    key: str
    name: str
    user_id: str
    quota: dict


async def authenticate_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None),
) -> APIKeyContext:
    """FastAPI Depends 钩子：从 Header 中提取并校验 API Key。"""
    cfg = get_config()

    raw = ""
    if x_api_key:
        raw = x_api_key
    elif authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:]

    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")

    for entry in cfg.auth.api_keys:
        if entry.key == raw:
            return APIKeyContext(
                key=entry.key,
                name=entry.name,
                user_id=f"apikey:{entry.name}",
                quota=entry.quota,
            )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")


def issue_jwt(user_id: str) -> str:
    """签发 JWT（仅在 cfg.auth.jwt.enabled 时使用）。"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    cfg = get_config()
    if not cfg.auth.jwt.enabled:
        raise RuntimeError("JWT is not enabled in config")

    payload = {
        "sub": user_id,
        "iat": datetime.now(tz=timezone.utc),
        "exp": datetime.now(tz=timezone.utc) + timedelta(seconds=cfg.auth.jwt.expires_seconds),
    }
    return jwt.encode(payload, cfg.auth.jwt.secret, algorithm=cfg.auth.jwt.algorithm)