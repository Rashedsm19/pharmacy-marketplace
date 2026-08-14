"""Products can belong to one pharmacy

The catalogue is curated by the platform and holds 44 products. A customer
importing ten thousand medicines would match almost none of them, and could not
create the rest: sku was globally unique and only a platform admin could add a
product.

This makes ownership explicit. NULL owner means the shared catalogue, as before.
A set owner means the product is private to that pharmacy — its own stock, its
own codes, invisible to the rest of the market.

Uniqueness moves with it: two pharmacies may legitimately use the same internal
code for different medicines, so sku is unique per owner rather than globally.
NULLS NOT DISTINCT keeps the shared catalogue itself free of duplicate codes.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("owner_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "products",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="catalog"),
    )
    op.create_foreign_key(
        "fk_products_owner_organization_id",
        "products",
        "pharmacy_organizations",
        ["owner_organization_id"],
        ["id"],
    )
    op.create_index(
        "ix_products_owner_organization_id", "products", ["owner_organization_id"]
    )

    # Existing rows are the shared catalogue: owner stays NULL, which the new
    # index already treats as a single namespace.
    op.drop_constraint("products_sku_key", "products", type_="unique")
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_products_owner_sku "
            "ON products (owner_organization_id, sku) NULLS NOT DISTINCT"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_products_owner_sku"))
    # Only rows in the shared catalogue can satisfy a global unique constraint.
    op.execute(sa.text("DELETE FROM products WHERE owner_organization_id IS NOT NULL"))
    op.create_unique_constraint("products_sku_key", "products", ["sku"])
    op.drop_index("ix_products_owner_organization_id", table_name="products")
    op.drop_constraint("fk_products_owner_organization_id", "products", type_="foreignkey")
    op.drop_column("products", "source")
    op.drop_column("products", "is_draft")
    op.drop_column("products", "owner_organization_id")
