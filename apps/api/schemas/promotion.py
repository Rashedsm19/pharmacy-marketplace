"""
Promotion request and response schemas.

The rule body differs per promotion type, so it is a discriminated union: the
`type` field picks the rule model, and every model checks its own numbers so a
tier that gives 150% off or a bundle that costs more than the list price is
refused before it is stored. Messages are Arabic because they are shown as-is.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.promotion import PromotionType


class QuantityTier(BaseModel):
    min_qty: int = Field(ge=1)
    discount_pct: float = Field(gt=0, le=100)


class QuantityTierRules(BaseModel):
    type: Literal["quantity_tier"]
    tiers: list[QuantityTier] = Field(min_length=1, max_length=10)

    @field_validator("tiers")
    @classmethod
    def _sorted_and_distinct(cls, tiers: list[QuantityTier]) -> list[QuantityTier]:
        tiers = sorted(tiers, key=lambda t: t.min_qty)
        for prev, cur in zip(tiers, tiers[1:]):
            if cur.min_qty == prev.min_qty:
                raise ValueError("لا يمكن تكرار الحد الأدنى للكمية في أكثر من شريحة")
            if cur.discount_pct <= prev.discount_pct:
                raise ValueError("نسبة الخصم يجب أن تزيد مع زيادة الكمية")
        return tiers


class ThresholdDiscountRules(BaseModel):
    type: Literal["threshold_discount"]
    min_amount: float = Field(gt=0)
    discount_pct: float = Field(gt=0, le=100)


class BogoRules(BaseModel):
    type: Literal["bogo"]
    buy: int = Field(ge=1)
    get: int = Field(ge=1)

    @model_validator(mode="after")
    def _sane(self) -> "BogoRules":
        if self.get > self.buy:
            raise ValueError("عدد الوحدات المجانية لا يمكن أن يتجاوز عدد الوحدات المشتراة")
        return self


class BundleRules(BaseModel):
    type: Literal["bundle"]
    min_qty: int = Field(ge=2)
    bundle_price: float = Field(gt=0)


class ExpiryDynamicRules(BaseModel):
    type: Literal["expiry_dynamic"]
    yellow_pct: float = Field(ge=0, le=100)
    orange_pct: float = Field(ge=0, le=100)
    red_pct: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _escalates(self) -> "ExpiryDynamicRules":
        if not (self.yellow_pct <= self.orange_pct <= self.red_pct):
            raise ValueError("نسبة الخصم يجب أن ترتفع كلما اقترب تاريخ الانتهاء")
        if self.red_pct == 0:
            raise ValueError("يجب تحديد نسبة خصم واحدة على الأقل")
        return self


PromotionRules = Annotated[
    QuantityTierRules | ThresholdDiscountRules | BogoRules | BundleRules | ExpiryDynamicRules,
    Field(discriminator="type"),
]


def validate_rules(ptype: str, rules: dict) -> dict:
    """Validate a raw rule body for the given type and return its clean form."""
    from pydantic import TypeAdapter

    body = {**(rules or {}), "type": ptype}
    parsed = TypeAdapter(PromotionRules).validate_python(body)
    clean = parsed.model_dump()
    clean.pop("type", None)
    return clean


class PromotionBase(BaseModel):
    listing_id: uuid.UUID | None = None
    type: PromotionType
    name_ar: str = Field(min_length=2, max_length=200)
    description_ar: str | None = Field(None, max_length=2000)
    rules: dict
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    max_redemptions: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _check(self) -> "PromotionBase":
        try:
            self.rules = validate_rules(self.type.value, self.rules)
        except ValueError as exc:  # pydantic ValidationError is a ValueError
            raise ValueError(_first_message(exc)) from None
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("تاريخ انتهاء العرض يجب أن يكون بعد تاريخ بدايته")
        return self


def _first_message(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        for err in errors():
            msg = str(err.get("msg", ""))
            loc = [str(p) for p in err.get("loc", ()) if p != "type"]
            # Strip pydantic's "Value error, " prefix so the sentence stands alone.
            msg = msg.removeprefix("Value error, ")
            if loc and not any("؀" <= ch <= "ۿ" for ch in msg):
                return f"قواعد العرض غير صالحة: الحقل {'.'.join(loc)} — {msg}"
            return msg or "قواعد العرض غير صالحة"
    return "قواعد العرض غير صالحة"


class PromotionCreate(PromotionBase):
    pass


class PromotionUpdate(BaseModel):
    listing_id: uuid.UUID | None = None
    name_ar: str | None = Field(None, min_length=2, max_length=200)
    description_ar: str | None = Field(None, max_length=2000)
    rules: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    max_redemptions: int | None = Field(None, ge=1)


class PromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    listing_id: uuid.UUID | None
    type: PromotionType
    name_ar: str
    description_ar: str | None
    rules: dict
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    max_redemptions: int | None
    redemption_count: int
    created_at: datetime
    updated_at: datetime
    # Derived: active | scheduled | expired | paused | exhausted
    computed_status: str | None = None
    listing_title: str | None = None


class ActivePromotionSummary(BaseModel):
    id: uuid.UUID
    type: PromotionType
    name_ar: str


class QuoteOut(BaseModel):
    unit_price: float
    quantity: int
    subtotal: float
    discount: float
    total: float
    free_units: int = 0
    promotion_id: uuid.UUID | None = None
    promotion_name_ar: str | None = None
    lines_ar: list[str] = []


class SeriesPoint(BaseModel):
    day: str
    redemptions: int
    discount: float


class PromotionStats(BaseModel):
    promotion_id: uuid.UUID
    redemptions: int
    total_discount: float
    series: list[SeriesPoint]
