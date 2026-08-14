"""
Files kept in the database rather than on the instance's disk.

The disk on this deployment is ephemeral: it is wiped on every deploy and every
restart, and there is no persistent volume. Everything written to it was lost —
pharmacy licences, commercial-register extracts, cold-chain temperature logs,
dispute evidence — while the row that pointed at the file survived. So the record
went on asserting that a licence had been submitted, and the download answered
"file not found". For an already-approved pharmacy the evidence behind the
approval was simply gone.

Regulated evidence has to outlive a deploy. The database does; the disk does not.
These files are small and few — a licence scan, a temperature chart — so holding
the bytes alongside the record they belong to is the honest trade: a little
storage in exchange for the document still being there when an inspector asks.
"""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StoredFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "stored_files"
    __table_args__ = (
        # Lookups are always by the path already recorded on the owning row.
        Index("uq_stored_files_path", "path", unique=True),
    )

    # The same reference the owning row stores, e.g. "<org>/licence-<uuid>.pdf".
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_organizations.id"), nullable=True, index=True
    )
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
