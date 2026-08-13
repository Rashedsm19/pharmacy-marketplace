"""Regulatory identity on organizations

A ZATCA tax invoice cannot be issued without the seller's VAT number, and RSD
reports are filed against a GS1 Global Location Number — neither of which the
model carried. Licence expiry and verification state are added alongside so the
licence can be re-checked rather than trusted indefinitely.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pharmacy_organizations", sa.Column("vat_number", sa.String(length=15), nullable=True)
    )
    op.add_column("pharmacy_organizations", sa.Column("gln", sa.String(length=13), nullable=True))
    op.add_column(
        "pharmacy_organizations", sa.Column("license_expires_at", sa.Date(), nullable=True)
    )
    op.add_column(
        "pharmacy_organizations",
        sa.Column("license_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pharmacy_organizations",
        sa.Column(
            "license_verification_status",
            sa.String(length=20),
            nullable=False,
            server_default="unverified",
        ),
    )

    op.create_index(
        "ix_pharmacy_organizations_vat_number", "pharmacy_organizations", ["vat_number"]
    )
    op.create_index("ix_pharmacy_organizations_gln", "pharmacy_organizations", ["gln"])
    op.create_index(
        "ix_pharmacy_organizations_license_expires_at",
        "pharmacy_organizations",
        ["license_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pharmacy_organizations_license_expires_at", table_name="pharmacy_organizations")
    op.drop_index("ix_pharmacy_organizations_gln", table_name="pharmacy_organizations")
    op.drop_index("ix_pharmacy_organizations_vat_number", table_name="pharmacy_organizations")
    op.drop_column("pharmacy_organizations", "license_verification_status")
    op.drop_column("pharmacy_organizations", "license_verified_at")
    op.drop_column("pharmacy_organizations", "license_expires_at")
    op.drop_column("pharmacy_organizations", "gln")
    op.drop_column("pharmacy_organizations", "vat_number")
