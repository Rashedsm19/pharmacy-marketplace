"""Support console: released emails and hashed reset tokens

Two changes, both about accounts.

`former_email` lets a deletion release the address. `users.email` is UNIQUE and
the constraint counts soft-deleted rows, so without this a pharmacist who leaves
can never be registered again on the same corporate address.

The reset token column now holds a SHA-256 digest rather than the token itself.
Any token in flight at deploy time stops working — which is correct: they were
stored in a form that anyone with read access to the table could have used to
take over the account, and an hour's inconvenience is the right price for
closing that. Existing values are cleared rather than migrated, because a
plaintext token cannot be turned into its own digest without being read first.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-14 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("former_email", sa.String(length=255), nullable=True))

    # Invalidate anything issued under the old plaintext scheme.
    op.execute(
        sa.text(
            "UPDATE users SET password_reset_token = NULL, "
            "password_reset_expires = NULL WHERE password_reset_token IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE users SET password_reset_token = NULL, "
            "password_reset_expires = NULL WHERE password_reset_token IS NOT NULL"
        )
    )
    op.drop_column("users", "former_email")
