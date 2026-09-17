"""Team screen schemas: permissions, roles, members and invitations."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.rbac import InviteStatus


# ── Permissions ───────────────────────────────────────────────────────────────

class PermissionOut(BaseModel):
    key: str
    label_ar: str
    label_en: str


class PermissionGroupOut(BaseModel):
    group_ar: str
    group_en: str
    permissions: list[PermissionOut]


# ── Roles ─────────────────────────────────────────────────────────────────────

class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    key: str
    name_ar: str
    name: str
    description_ar: str | None = None
    is_system: bool
    permissions: list[str]
    member_count: int = 0
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    name_ar: str = Field(min_length=2, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    description_ar: str | None = Field(default=None, max_length=1000)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name_ar: str | None = Field(default=None, min_length=2, max_length=120)
    name: str | None = Field(default=None, max_length=120)
    description_ar: str | None = Field(default=None, max_length=1000)
    permissions: list[str] | None = None


# ── Members ───────────────────────────────────────────────────────────────────

class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None = None
    role_id: uuid.UUID | None = None
    role_key: str
    role_name_ar: str
    is_active: bool
    is_self: bool = False
    joined_at: datetime | None = None
    last_login_at: datetime | None = None


class MemberUpdate(BaseModel):
    role_id: uuid.UUID | None = None
    is_active: bool | None = None


# ── Invites ───────────────────────────────────────────────────────────────────

class InviteCreate(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    role_id: uuid.UUID


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    role_id: uuid.UUID
    role_name_ar: str
    invited_by_name: str | None = None
    status: InviteStatus
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime


class InviteCreated(InviteOut):
    """Returned once, on creation, with the link the email carries."""

    invite_link: str


class InvitePreview(BaseModel):
    org_name: str
    role_name_ar: str
    email: str
    full_name: str | None = None
    expires_at: datetime
    status: InviteStatus
    # True when the address already belongs to an account: the accept form
    # then needs no password, only a sign-in afterwards.
    existing_account: bool = False


class InviteAccept(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
