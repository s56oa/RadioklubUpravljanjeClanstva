"""Dodaj tabelo zaupljive_naprave za 2FA "zapomni si napravo"

Revision ID: 002
Revises: 001
Create Date: 2026-02-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zaupljive_naprave",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uporabnik_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["uporabnik_id"], ["uporabniki.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_zaupljive_naprave_uporabnik_id",
        "zaupljive_naprave",
        ["uporabnik_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_zaupljive_naprave_uporabnik_id", table_name="zaupljive_naprave")
    op.drop_table("zaupljive_naprave")
