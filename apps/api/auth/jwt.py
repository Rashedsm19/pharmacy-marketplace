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

    # ── Impersonation ─────────────────────────────────────────────────────
    # Set only when support is operating inside a customer's account. Absent on
    # every ordinary token, so tokens issued before this existed still decode.
    act_sub: str | None = None      # the real administrator's user id
    act_email: str | None = None    # carried so audit and UI need no extra query
    imp_sid: str | None = None      # impersonation session id — the kill switch


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    role: str,
    org_id: uuid.UUID | None = None,
    *,
    impersonator_id: uuid.UUID | None = None,
    impersonator_email: str | None = None,
    session_id: uuid.UUID | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Mint an access token.

    The impersonation arguments are keyword-only with defaults so every existing
    caller is unaffected, and the claims are added only when support is actually
    acting as someone — an absent claim is what "not impersonating" looks like.
    """
    now = datetime.now(timezone.utc)
    minutes = expires_minutes or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    expire = now + timedelta(minutes=minutes)
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
    if impersonator_id is not None:
        payload["act_sub"] = str(impersonator_id)
        payload["act_email"] = impersonator_email
        payload["imp_sid"] = str(session_id) if session_id else None
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
        act_sub=payload.get("act_sub"),
        act_email=payload.get("act_email"),
        imp_sid=payload.get("imp_sid"),
    )
