"""
Inventory import jobs.

Ten thousand rows cannot be processed inside an HTTP request, and an in-memory
background task would die with the next deploy — on a free instance that is
often. The job therefore lives in the database: the upload records it, a worker
picks it up, and the customer polls it.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.organization import PharmacyOrganization
    from models.user import User


class ImportStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    # Some rows landed, some did not — the common outcome on a first import.
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class ImportSource(str, enum.Enum):
    EXCEL = "excel"
    CSV = "csv"
    API = "api"


class ImportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "import_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[ImportSource] = mapped_column(
        String(20), nullable=False, default=ImportSource.EXCEL
    )
    status: Mapped[ImportStatus] = mapped_column(
        String(30), nullable=False, default=ImportStatus.QUEUED, index=True
    )

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_batches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_batches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_products: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_products: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Kept to a bounded number of entries; the full set goes to the errors file.
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    organization: Mapped["PharmacyOrganization"] = relationship(
        "PharmacyOrganization", foreign_keys=[organization_id], lazy="selectin"
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id], lazy="selectin"
    )
