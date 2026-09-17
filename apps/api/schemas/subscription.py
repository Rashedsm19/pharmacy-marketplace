"""
Subscription API schemas — plans, lifecycle requests, billing history.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    version: int
    name_ar: str
    name_en: str
    description_ar: str | None
    description_en: str | None
    monthly_price: Decimal
    annual_price: Decimal
    currency: str
    trial_days: int
    limits: dict
    is_active: bool
    is_public: bool
    sort_order: int


class PlanCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name_ar: str = Field(min_length=1, max_length=255)
    name_en: str = Field(min_length=1, max_length=255)
    description_ar: str | None = None
    description_en: str | None = None
    monthly_price: Decimal = Decimal("0.00")
    annual_price: Decimal = Decimal("0.00")
    currency: str = Field(default="SAR", min_length=3, max_length=3)
    trial_days: int = Field(default=0, ge=0, le=365)
    limits: dict = Field(default_factory=dict)
    is_active: bool = True
    is_public: bool = True
    sort_order: int = 0


class PlanUpdate(BaseModel):
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    monthly_price: Decimal | None = None
    annual_price: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    trial_days: int | None = Field(default=None, ge=0, le=365)
    limits: dict | None = None
    is_active: bool | None = None
    is_public: bool | None = None
    sort_order: int | None = None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    plan_id: uuid.UUID
    plan_snapshot: dict
    status: str
    billing_cycle: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_start: datetime | None
    trial_end: datetime | None
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    grace_until: datetime | None
    pending_plan_id: uuid.UUID | None
    proration_credit: Decimal
    last_payment_at: datetime | None


class TrialStartRequest(BaseModel):
    plan_id: uuid.UUID


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|annual)$")


class ChangePlanRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: str | None = Field(default=None, pattern="^(monthly|annual)$")


class ReactivateRequest(BaseModel):
    plan_id: uuid.UUID | None = None
    billing_cycle: str | None = Field(default=None, pattern="^(monthly|annual)$")


class CheckoutResponse(BaseModel):
    subscription_id: uuid.UUID
    invoice_id: uuid.UUID
    provider: str
    provider_ref: str
    redirect_url: str
    amount: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    sandbox: bool


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    subscription_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    amount: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    status: str
    provider: str | None
    provider_ref: str | None
    paid_at: datetime | None
    created_at: datetime


class AddonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    quantity: int
    price: Decimal
    currency: str
    valid_from: datetime | None
    valid_until: datetime | None
    status: str
    created_at: datetime


class AddonPurchaseRequest(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    quantity: int = Field(default=1, ge=1, le=100)


class SimulatePaymentRequest(BaseModel):
    provider_ref: str = Field(min_length=1, max_length=120)
    status: str = Field(default="paid", pattern="^(paid|failed)$")


class CurrentSubscriptionResponse(BaseModel):
    subscription: SubscriptionOut | None
    plan: PlanOut | None
    entitlements: dict
    usage: dict
    sandbox: bool


class AdminSubscriptionRow(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_status: str
    subscription: SubscriptionOut | None
    plan: PlanOut | None
