"""
Organization and membership schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from models.organization import MembershipRole, OrganizationStatus


class OrganizationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    name_ar: str | None = None
    commercial_registration_number: str
    license_number: str | None = None
    email: EmailStr
    phone: str
    address: str | None = None
    city: str | None = None
    region: str | None = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: str | None = None
    name_ar: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    logo_url: str | None = None
    allow_auto_listing: bool | None = None
    notes: str | None = None


class OrganizationOut(OrganizationBase):
    id: uuid.UUID
    is_licensed: bool
    status: OrganizationStatus
    logo_url: str | None = None
    allow_auto_listing: bool
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationApprove(BaseModel):
    notes: str | None = None


class OrganizationReject(BaseModel):
    reason: str


class OrganizationSuspend(BaseModel):
    reason: str


class MembershipBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: MembershipRole
    is_active: bool


class MembershipCreate(BaseModel):
    user_email: EmailStr
    role: MembershipRole = MembershipRole.PHARMACIST


class MembershipOut(MembershipBase):
    id: uuid.UUID
    user_full_name: str | None = None
    user_email: str | None = None
    joined_at: datetime | None = None
    created_at: datetime
