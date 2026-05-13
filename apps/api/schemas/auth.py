"""
Auth request/response schemas.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    role: str
    org_id: uuid.UUID | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    # User info
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=9, max_length=20)
    password: str = Field(min_length=8, max_length=128)

    # Organization info
    org_name: str = Field(min_length=2, max_length=255)
    org_name_ar: str | None = None
    commercial_registration_number: str = Field(min_length=5, max_length=100)
    license_number: str | None = None
    org_email: EmailStr
    org_phone: str = Field(min_length=9, max_length=20)
    org_address: str | None = None
    org_city: str | None = None
    org_region: str | None = None

    # First branch info
    branch_name: str = Field(min_length=2, max_length=255)
    branch_name_ar: str | None = None
    branch_address: str | None = None
    branch_city: str | None = None
    branch_phone: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
