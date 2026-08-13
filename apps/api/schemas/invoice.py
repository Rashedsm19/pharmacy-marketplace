"""Invoice schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.invoice import InvoiceStatus


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    seller_organization_id: uuid.UUID
    buyer_organization_id: uuid.UUID
    invoice_number: str
    invoice_uuid: str
    icv: int
    issued_at: datetime
    subtotal: float
    vat_rate: float
    vat_amount: float
    total_with_vat: float
    qr_code: str
    status: InvoiceStatus
    cleared_at: datetime | None = None
    attempts: int
    last_error: str | None = None
    created_at: datetime

    # Labels for the invoice table; the XML itself is a separate download.
    seller_name: str | None = None
    buyer_name: str | None = None
    transaction_reference: str | None = None
