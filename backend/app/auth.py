from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.config import EnvironmentSettings


PASSWORD_CONTEXT = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return PASSWORD_CONTEXT.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return PASSWORD_CONTEXT.verify(password, hashed_password)


def create_access_token(
    *,
    subject: str,
    role: str,
    env_settings: EnvironmentSettings,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    expire_at = now + (expires_delta or timedelta(minutes=env_settings.access_token_ttl_minutes))
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
    }
    return jwt.encode(payload, env_settings.secret_key, algorithm="HS256")


def decode_access_token(token: str, env_settings: EnvironmentSettings) -> dict[str, str]:
    try:
        payload = jwt.decode(token, env_settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访问令牌无效或已过期",
        ) from exc
    return payload
