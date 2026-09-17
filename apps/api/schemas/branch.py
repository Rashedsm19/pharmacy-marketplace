"""
Branch schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.branch import StorageConditionStatus


class _CoordinatesMixin(BaseModel):
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def _both_or_neither(self):
        fields_set = self.model_fields_set
        lat_given = "latitude" in fields_set
        lng_given = "longitude" in fields_set
        # Only enforce pairing when the caller is actually touching coordinates.
        if lat_given or lng_given:
            if (self.latitude is None) != (self.longitude is None):
                raise ValueError("يجب ادخال خط العرض وخط الطول معا او تركهما فارغين")
        return self


class BranchBase(_CoordinatesMixin):
    model_config = ConfigDict(from_attributes=True)

    name: str
    name_ar: str | None = None
    branch_code: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    phone: str | None = None
    manager_name: str | None = None
    cold_chain_available: bool = False
    narcotics_license: bool = False


class BranchCreate(BranchBase):
    organization_id: uuid.UUID | None = None  # injected from token if omitted


class BranchUpdate(_CoordinatesMixin):
    name: str | None = None
    name_ar: str | None = None
    branch_code: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    phone: str | None = None
    manager_name: str | None = None
    is_active: bool | None = None
    cold_chain_available: bool | None = None
    narcotics_license: bool | None = None
    storage_condition_status: StorageConditionStatus | None = None
    storage_notes: str | None = None


class BranchOut(BranchBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    storage_condition_status: StorageConditionStatus
    storage_notes: str | None = None
    created_at: datetime
    updated_at: datetime
