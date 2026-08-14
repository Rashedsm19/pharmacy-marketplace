"""Durable file storage

The instance disk is wiped on every deploy and there is no persistent volume, so
pharmacy licences, commercial-register extracts, cold-chain temperature logs and
dispute evidence were all lost while the rows pointing at them survived — the
record kept asserting a licence had been submitted and the download answered
"file not found".

Regulated evidence has to outlive a deploy, so the bytes now live beside the
record. Files already uploaded cannot be recovered; this stops the loss from here.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-15 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["pharmacy_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_stored_files_path", "stored_files", ["path"], unique=True)
    op.create_index("ix_stored_files_organization_id", "stored_files", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_stored_files_organization_id", table_name="stored_files")
    op.drop_index("uq_stored_files_path", table_name="stored_files")
    op.drop_table("stored_files")
