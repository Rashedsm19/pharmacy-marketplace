"""
JWT token creation and validation utilities.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from pydantic import BaseModel

from config import settings


class TokenData(BaseModel):
    sub: str          # user ID as string
    email: str
    role: str
    org_id: str | None = None
    token_type: Literal["access", "refresh"] = "access"
    jti: str = ""     # unique token ID (for revocation)


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    role: str,
    org_id: uuid.UUID | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "org_id": str(org_id) if org_id else None,
        "token_type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    email: str,
    role: str,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "org_id": None,
        "token_type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> TokenData:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return TokenData(
        sub=payload["sub"],
        email=payload["email"],
        role=payload["role"],
        org_id=payload.get("org_id"),
        token_type=payload.get("token_type", "access"),
        jti=payload.get("jti", ""),
    )
