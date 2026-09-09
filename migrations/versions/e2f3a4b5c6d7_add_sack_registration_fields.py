"""Add explicit sack registration fields.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""
from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("average_sack_weight_kg", sa.Numeric(10, 3), nullable=True))
    op.create_check_constraint(
        "ck_products_average_sack_weight_positive",
        "products",
        "average_sack_weight_kg IS NULL OR average_sack_weight_kg > 0",
    )
    op.add_column(
        "harvest_entries",
        sa.Column("registration_type", sa.String(10), nullable=False, server_default="scale"),
    )
    op.add_column("harvest_entries", sa.Column("sack_count", sa.Integer(), nullable=True))
    op.add_column(
        "harvest_entries",
        sa.Column("average_sack_weight_kg_snapshot", sa.Numeric(10, 3), nullable=True),
    )
    op.create_check_constraint(
        "ck_harvest_entries_registration_type_consistency",
        "harvest_entries",
        "(registration_type = 'scale' AND sack_count IS NULL AND average_sack_weight_kg_snapshot IS NULL) OR "
        "(registration_type = 'sacks' AND sack_count > 0 AND average_sack_weight_kg_snapshot > 0)",
    )


def downgrade():
    op.drop_constraint("ck_harvest_entries_registration_type_consistency", "harvest_entries", type_="check")
    op.drop_column("harvest_entries", "average_sack_weight_kg_snapshot")
    op.drop_column("harvest_entries", "sack_count")
    op.drop_column("harvest_entries", "registration_type")
    op.drop_constraint("ck_products_average_sack_weight_positive", "products", type_="check")
    op.drop_column("products", "average_sack_weight_kg")
