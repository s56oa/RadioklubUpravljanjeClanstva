"""clan_vloge – evidenca vlog in funkcij člana z zgodovino

Revision ID: 004
Revises: 003
Create Date: 2026-03-02
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clan_vloge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clan_id", sa.Integer(), nullable=False),
        sa.Column("naziv", sa.String(), nullable=False),
        sa.Column("datum_od", sa.Date(), nullable=False),
        sa.Column("datum_do", sa.Date(), nullable=True),
        sa.Column("opombe", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["clan_id"], ["clani.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clan_vloge_id", "clan_vloge", ["id"], unique=False)
    op.create_index("ix_clan_vloge_clan_id", "clan_vloge", ["clan_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clan_vloge_clan_id", table_name="clan_vloge")
    op.drop_index("ix_clan_vloge_id", table_name="clan_vloge")
    op.drop_table("clan_vloge")
