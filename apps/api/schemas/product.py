"""
Product and product category schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductCategoryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    name_ar: str
    code: str
    description: str | None = None
    is_exchange_allowed_default: bool = True
    requires_cold_chain: bool = False
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryUpdate(BaseModel):
    name: str | None = None
    name_ar: str | None = None
    description: str | None = None
    is_exchange_allowed_default: bool | None = None
    requires_cold_chain: bool | None = None
    sort_order: int | None = None


class ProductCategoryOut(ProductCategoryBase):
    id: uuid.UUID
    created_at: datetime


class ProductBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: uuid.UUID
    name: str
    name_ar: str
    sku: str
    barcode: str | None = None
    manufacturer: str | None = None
    manufacturer_ar: str | None = None
    description: str | None = None
    unit: str = "unit"
    unit_ar: str = "وحدة"
    standard_price: float | None = None
    is_restricted: bool = False
    is_controlled: bool = False
    requires_prescription: bool = False
    notes: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    name_ar: str | None = None
    category_id: uuid.UUID | None = None
    barcode: str | None = None
    manufacturer: str | None = None
    manufacturer_ar: str | None = None
    description: str | None = None
    unit: str | None = None
    unit_ar: str | None = None
    standard_price: float | None = None
    is_active: bool | None = None
    is_restricted: bool | None = None
    is_controlled: bool | None = None
    requires_prescription: bool | None = None
    image_url: str | None = None
    notes: str | None = None


class ProductOut(ProductBase):
    id: uuid.UUID
    is_active: bool
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime
    category: ProductCategoryOut | None = None
