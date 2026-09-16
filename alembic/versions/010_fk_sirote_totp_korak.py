"""Čiščenje osirotelih vrstic (pred vklopom PRAGMA foreign_keys) + uporabniki.totp_zadnji_korak

Revision ID: 010
Revises: 009
Create Date: 2026-09-17
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aplikacija od v1.29 uveljavlja tuje ključe (PRAGMA foreign_keys=ON); obstoječe
    # osirotele vrstice bi ob nadaljnjih operacijah povzročile IntegrityError.
    op.execute("DELETE FROM clanarine WHERE clan_id NOT IN (SELECT id FROM clani)")
    op.execute("DELETE FROM aktivnosti WHERE clan_id NOT IN (SELECT id FROM clani)")
    op.execute("DELETE FROM clan_vloge WHERE clan_id NOT IN (SELECT id FROM clani)")
    op.execute("DELETE FROM clan_skupina WHERE clan_id NOT IN (SELECT id FROM clani) "
               "OR skupina_id NOT IN (SELECT id FROM skupine)")
    op.execute("DELETE FROM zaupljive_naprave WHERE uporabnik_id NOT IN (SELECT id FROM uporabniki)")

    with op.batch_alter_table("uporabniki") as batch_op:
        batch_op.add_column(sa.Column("totp_zadnji_korak", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("uporabniki") as batch_op:
        batch_op.drop_column("totp_zadnji_korak")
