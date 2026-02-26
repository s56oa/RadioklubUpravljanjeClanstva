"""Initial schema – vse tabele do v1.12 (brez zaupljive_naprave)

Revision ID: 001
Revises:
Create Date: 2026-02-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clani",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("priimek", sa.String(), nullable=False),
        sa.Column("ime", sa.String(), nullable=False),
        sa.Column("klicni_znak", sa.String(), nullable=True),
        sa.Column("naslov_ulica", sa.String(), nullable=True),
        sa.Column("naslov_posta", sa.String(), nullable=True),
        sa.Column("tip_clanstva", sa.String(), nullable=False),
        sa.Column("klicni_znak_nosilci", sa.String(), nullable=True),
        sa.Column("operaterski_razred", sa.String(), nullable=True),
        sa.Column("mobilni_telefon", sa.String(), nullable=True),
        sa.Column("telefon_doma", sa.String(), nullable=True),
        sa.Column("elektronska_posta", sa.String(), nullable=True),
        sa.Column("soglasje_op", sa.String(), nullable=True),
        sa.Column("izjava", sa.String(), nullable=True),
        sa.Column("veljavnost_rd", sa.Date(), nullable=True),
        sa.Column("es_stevilka", sa.Integer(), nullable=True),
        sa.Column("aktiven", sa.Boolean(), nullable=False),
        sa.Column("opombe", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clani_klicni_znak", "clani", ["klicni_znak"], unique=False)

    op.create_table(
        "skupine",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ime", sa.String(), nullable=False),
        sa.Column("opis", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "nastavitve",
        sa.Column("kljuc", sa.String(), nullable=False),
        sa.Column("vrednost", sa.String(), nullable=True),
        sa.Column("opis", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("kljuc"),
    )

    op.create_table(
        "uporabniki",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uporabnisko_ime", sa.String(), nullable=False),
        sa.Column("geslo_hash", sa.String(), nullable=False),
        sa.Column("vloga", sa.String(), nullable=False),
        sa.Column("ime_priimek", sa.String(), nullable=True),
        sa.Column("aktiven", sa.Boolean(), nullable=False),
        sa.Column("totp_skrivnost", sa.String(), nullable=True),
        sa.Column("totp_aktiven", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uporabniki_uporabnisko_ime", "uporabniki",
                    ["uporabnisko_ime"], unique=True)

    op.create_table(
        "clanarine",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clan_id", sa.Integer(), nullable=False),
        sa.Column("leto", sa.Integer(), nullable=False),
        sa.Column("datum_placila", sa.Date(), nullable=True),
        sa.Column("znesek", sa.String(), nullable=True),
        sa.Column("opombe", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["clan_id"], ["clani.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "aktivnosti",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clan_id", sa.Integer(), nullable=False),
        sa.Column("leto", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=True),
        sa.Column("opis", sa.String(1000), nullable=False),
        sa.Column("delovne_ure", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["clan_id"], ["clani.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "clan_skupina",
        sa.Column("clan_id", sa.Integer(), nullable=False),
        sa.Column("skupina_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["clan_id"], ["clani.id"]),
        sa.ForeignKeyConstraint(["skupina_id"], ["skupine.id"]),
        sa.PrimaryKeyConstraint("clan_id", "skupina_id"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cas", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("uporabnik", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("akcija", sa.String(), nullable=False),
        sa.Column("opis", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_akcija", "audit_log", ["akcija"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("clan_skupina")
    op.drop_table("aktivnosti")
    op.drop_table("clanarine")
    op.drop_index("ix_uporabniki_uporabnisko_ime", table_name="uporabniki")
    op.drop_table("uporabniki")
    op.drop_table("nastavitve")
    op.drop_table("skupine")
    op.drop_index("ix_clani_klicni_znak", table_name="clani")
    op.drop_table("clani")
