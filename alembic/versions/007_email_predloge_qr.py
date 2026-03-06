"""email_predloge: dodaj vkljuci_qr

Revision ID: 007
Revises: 006
Create Date: 2026-03-06
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "email_predloge",
        sa.Column("vkljuci_qr", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("email_predloge", "vkljuci_qr")
