"""
Organization and membership schemas.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from models.organization import (
    LicenseVerificationStatus,
    MembershipRole,
    OrganizationStatus,
)
from schemas.validators import validate_gln, validate_vat_number


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

    # Regulatory identity — editable by the organization, checked on the way in.
    vat_number: str | None = None
    gln: str | None = None
    license_expires_at: date | None = None

    _vat = field_validator("vat_number")(lambda cls, v: validate_vat_number(v))
    _gln = field_validator("gln")(lambda cls, v: validate_gln(v))


class OrganizationOut(OrganizationBase):
    id: uuid.UUID
    is_licensed: bool
    status: OrganizationStatus
    logo_url: str | None = None
    allow_auto_listing: bool
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Stored references, not public URLs — the file is served through the
    # authenticated download endpoint. Exposed so the UI knows what exists.
    cr_doc_url: str | None = None
    license_doc_url: str | None = None
    rejection_reason: str | None = None
    suspension_reason: str | None = None

    vat_number: str | None = None
    gln: str | None = None
    license_expires_at: date | None = None
    license_verified_at: datetime | None = None
    license_verification_status: LicenseVerificationStatus = (
        LicenseVerificationStatus.UNVERIFIED
    )


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
