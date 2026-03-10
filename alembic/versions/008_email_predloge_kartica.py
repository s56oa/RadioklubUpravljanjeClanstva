"""email_predloge: dodaj prilozi_kartico

Revision ID: 008
Revises: 007
Create Date: 2026-03-10
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "email_predloge",
        sa.Column("prilozi_kartico", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("email_predloge", "prilozi_kartico")
