"""login_poskusi – persistentni rate limiting

Revision ID: 003
Revises: 002
Create Date: 2026-02-26
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_poskusi",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("cas", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_poskusi_ip_cas", "login_poskusi", ["ip", "cas"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_login_poskusi_ip_cas", table_name="login_poskusi")
    op.drop_table("login_poskusi")
