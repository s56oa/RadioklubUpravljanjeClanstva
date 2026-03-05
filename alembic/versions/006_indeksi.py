"""indeksi – Clan.aktiven, Clanarina.leto, Aktivnost.leto

Revision ID: 006
Revises: 005
Create Date: 2026-03-05
"""
from typing import Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_clani_aktiven", "clani", ["aktiven"], unique=False)
    op.create_index("ix_clanarine_leto", "clanarine", ["leto"], unique=False)
    op.create_index("ix_aktivnosti_leto", "aktivnosti", ["leto"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_aktivnosti_leto", table_name="aktivnosti")
    op.drop_index("ix_clanarine_leto", table_name="clanarine")
    op.drop_index("ix_clani_aktiven", table_name="clani")
