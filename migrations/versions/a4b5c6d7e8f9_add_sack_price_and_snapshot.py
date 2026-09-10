"""Add independent sack price and historical snapshot.

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
"""
from alembic import op
import sqlalchemy as sa


revision = "a4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("rate_per_sack", sa.Numeric(8, 2), nullable=True))
    op.create_check_constraint(
        "ck_products_rate_per_sack_non_negative",
        "products",
        "rate_per_sack IS NULL OR rate_per_sack >= 0",
    )
    op.add_column(
        "harvest_entries",
        sa.Column("rate_per_sack_snapshot", sa.Numeric(8, 2), nullable=True),
    )
    op.create_check_constraint(
        "ck_harvest_entries_sack_rate_snapshot_non_negative",
        "harvest_entries",
        "rate_per_sack_snapshot IS NULL OR rate_per_sack_snapshot >= 0",
    )


def downgrade():
    op.drop_constraint(
        "ck_harvest_entries_sack_rate_snapshot_non_negative",
        "harvest_entries",
        type_="check",
    )
    op.drop_column("harvest_entries", "rate_per_sack_snapshot")
    op.drop_constraint("ck_products_rate_per_sack_non_negative", "products", type_="check")
    op.drop_column("products", "rate_per_sack")
