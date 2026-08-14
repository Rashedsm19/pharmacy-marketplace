"""Impersonation sessions

The session row is what makes ending a support session real. Without it,
leaving a customer's account would be a gesture in the browser while the token
kept working until it expired.

The foreign keys are nullable and the names are duplicated as text so that
purging an organization can detach the row rather than destroy the evidence
that support was inside that account.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "impersonation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("admin_email", sa.String(length=255), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_email", sa.String(length=255), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_reason", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["pharmacy_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_impersonation_sessions_admin_user_id", "impersonation_sessions", ["admin_user_id"])
    op.create_index("ix_impersonation_sessions_target_user_id", "impersonation_sessions", ["target_user_id"])
    op.create_index("ix_impersonation_open", "impersonation_sessions", ["ended_at"])


def downgrade() -> None:
    op.drop_index("ix_impersonation_open", table_name="impersonation_sessions")
    op.drop_index("ix_impersonation_sessions_target_user_id", table_name="impersonation_sessions")
    op.drop_index("ix_impersonation_sessions_admin_user_id", table_name="impersonation_sessions")
    op.drop_table("impersonation_sessions")
