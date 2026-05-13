"""
User schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from models.user import UserRole


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    phone: str | None = None
    full_name: str
    role: UserRole
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    phone: str | None = None
    full_name: str
    password: str
    role: UserRole = UserRole.PHARMACIST


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    is_active: bool | None = None


class UserOut(UserBase):
    id: uuid.UUID
    is_email_verified: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserWithOrg(UserOut):
    org_id: uuid.UUID | None = None
    org_name: str | None = None
    org_status: str | None = None
