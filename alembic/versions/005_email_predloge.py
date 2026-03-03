"""email_predloge – predloge za e-poštna obvestila

Revision ID: 005
Revises: 004
Create Date: 2026-03-03
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_predloge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("naziv", sa.String(), nullable=False),
        sa.Column("zadeva", sa.String(), nullable=False),
        sa.Column("telo_html", sa.Text(), nullable=False),
        sa.Column("je_privzeta", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_predloge_id", "email_predloge", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_email_predloge_id", table_name="email_predloge")
    op.drop_table("email_predloge")
