"""
API key schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=1)
    expires_at: datetime | None = None


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    request_count: int
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    """The one response that carries the key itself."""

    key: str
    warning: str = (
        "احفظ هذا المفتاح الآن — لن يعرض مرة أخرى. "
        "إذا فقدته أنشئ مفتاحا جديدا وألغ القديم."
    )


class ApiKeyScopeOut(BaseModel):
    value: str
    label_ar: str
    description_ar: str
