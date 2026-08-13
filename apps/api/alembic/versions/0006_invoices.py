"""Tax invoices

Every completed sale between two organizations is a B2B supply requiring a
cleared tax invoice. Nothing recorded one.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=60), nullable=False),
        sa.Column("invoice_uuid", sa.String(length=36), nullable=False),
        sa.Column("icv", sa.Integer(), nullable=False),
        sa.Column("previous_hash", sa.Text(), nullable=False),
        sa.Column("invoice_hash", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_with_vat", sa.Numeric(12, 2), nullable=False),
        sa.Column("xml_content", sa.Text(), nullable=False),
        sa.Column("qr_code", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("clearance_response", sa.Text(), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["seller_organization_id"], ["pharmacy_organizations.id"]),
        sa.ForeignKeyConstraint(["buyer_organization_id"], ["pharmacy_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_invoices_seller_organization_id", "invoices", ["seller_organization_id"])
    op.create_index("ix_invoices_buyer_organization_id", "invoices", ["buyer_organization_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    # The counter must be gapless and unique per seller.
    op.create_index("uq_invoices_seller_icv", "invoices", ["seller_organization_id", "icv"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_invoices_seller_icv", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_buyer_organization_id", table_name="invoices")
    op.drop_index("ix_invoices_seller_organization_id", table_name="invoices")
    op.drop_table("invoices")
