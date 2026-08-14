"""
Schemas for the platform support console.

Support acts on other people's accounts, so every request here carries a reason
and every response says plainly what happened. The reason is not decoration: it
lands in the audit trail, which is what makes an action on a customer's data
answerable afterwards.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminUserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None = None
    role: str
    is_active: bool
    is_deleted: bool = False
    is_email_verified: bool = False
    last_login_at: datetime | None = None
    created_at: datetime

    organization_id: uuid.UUID | None = None
    organization_name: str | None = None
    organization_status: str | None = None
    membership_role: str | None = None


class AdminUserList(BaseModel):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int
    pages: int


class ReasonIn(BaseModel):
    """Every support action that changes something asks why."""

    reason: str = Field(min_length=5, max_length=500)


class UserPatchIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    role: str | None = None
    reason: str = Field(min_length=5, max_length=500)


class ResetLinkOut(BaseModel):
    """The one response that carries a live reset link."""

    reset_url: str
    expires_at: datetime
    email_sent: bool
    notice: str


class BatchDeleteOut(BaseModel):
    id: uuid.UUID
    batch_number: str
    organization_name: str
    deleted: bool
    message: str


class ListingRemoveIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
