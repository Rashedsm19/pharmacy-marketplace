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


class ImpersonateIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)
    minutes: int = Field(default=30, ge=5, le=120)


class ImpersonateOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    session_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_name: str
    organization_id: uuid.UUID
    organization_name: str
    notice: str


class ImpersonationRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_email: str
    target_email: str
    organization_name: str | None = None
    reason: str
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None = None
    ended_reason: str | None = None


class CustomerRow(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    city: str | None = None
    commercial_registration_number: str | None = None
    is_licensed: bool = False
    created_at: datetime
    approved_at: datetime | None = None

    users: int = 0
    active_users: int = 0
    branches: int = 0
    batches: int = 0
    units: int = 0
    stock_value: float = 0.0
    near_expiry: int = 0
    expired: int = 0
    active_listings: int = 0
    imports: int = 0
    sales: int = 0
    purchases: int = 0
    open_disputes: int = 0
    api_keys: int = 0
    last_activity_at: datetime | None = None


class CustomerList(BaseModel):
    items: list[CustomerRow]
    total: int
    page: int
    page_size: int
    pages: int


class CustomerDetail(BaseModel):
    organization: dict
    summary: CustomerRow
    users: list[AdminUserRow]
    branches: list[dict]
    inventory_by_zone: dict
    recent_imports: list[dict]
    listings: dict
    api_keys: list[dict]


class PurgeIn(BaseModel):
    """Deleting a pharmacy for good asks for its name, in full."""

    confirm_name: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=10, max_length=500)


class PurgeOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    deleted: dict[str, int]
    audit_log_id: uuid.UUID
    message: str
