"""Inventory import jobs

A ten thousand row file cannot be processed inside an HTTP request, and an
in-memory task would die with the next deploy. The job is a database row: the
upload records it, a worker picks it up, the customer polls it.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="excel"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_batches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_batches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_products", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_products", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_file_path", sa.String(length=500), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["pharmacy_organizations.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_organization_id", "import_jobs", ["organization_id"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])

    # The worker claims the oldest queued job; this is the index it runs on.
    op.create_index(
        "ix_import_jobs_queue", "import_jobs", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_import_jobs_queue", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_organization_id", table_name="import_jobs")
    op.drop_table("import_jobs")
