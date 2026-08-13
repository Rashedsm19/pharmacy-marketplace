"""Disputes on transactions

The cycle ended at "receipt confirmed" with no way to report a short, damaged or
suspect delivery. TransactionStatus already carried DISPUTED and REFUNDED with
nothing able to set them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raised_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raised_by_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("disputed_quantity", sa.Integer(), nullable=True),
        sa.Column("evidence_url", sa.String(length=500), nullable=True),
        sa.Column("seller_response", sa.Text(), nullable=True),
        sa.Column("seller_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refund_amount", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["raised_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["raised_by_organization_id"], ["pharmacy_organizations.id"]),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_disputes_transaction_id", "disputes", ["transaction_id"])
    op.create_index("ix_disputes_raised_by_organization_id", "disputes", ["raised_by_organization_id"])
    op.create_index("ix_disputes_status", "disputes", ["status"])

    # Only one live case per transaction; closed ones may repeat.
    op.create_index(
        "uq_disputes_open_per_transaction",
        "disputes",
        ["transaction_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'seller_responded')"),
    )


def downgrade() -> None:
    op.drop_index("uq_disputes_open_per_transaction", table_name="disputes")
    op.drop_index("ix_disputes_status", table_name="disputes")
    op.drop_index("ix_disputes_raised_by_organization_id", table_name="disputes")
    op.drop_index("ix_disputes_transaction_id", table_name="disputes")
    op.drop_table("disputes")
