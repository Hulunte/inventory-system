"""add product snapshot fields to harvest_entries

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4d5e6f7a8b9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "harvest_entries",
        sa.Column("product_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "harvest_entries",
        sa.Column("product_name_snapshot", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "harvest_entries",
        sa.Column(
            "rate_per_kg_snapshot", sa.Numeric(precision=8, scale=2), nullable=True
        ),
    )
    op.add_column(
        "harvest_entries",
        sa.Column("amount_mxn", sa.Numeric(precision=12, scale=2), nullable=True),
    )

    op.create_foreign_key(
        "fk_harvest_entries_product_id",
        "harvest_entries",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_check_constraint(
        "ck_harvest_entries_rate_snapshot_non_negative",
        "harvest_entries",
        "rate_per_kg_snapshot IS NULL OR rate_per_kg_snapshot >= 0",
    )
    op.create_check_constraint(
        "ck_harvest_entries_amount_non_negative",
        "harvest_entries",
        "amount_mxn IS NULL OR amount_mxn >= 0",
    )
    op.create_check_constraint(
        "ck_harvest_entries_product_snapshot_consistency",
        "harvest_entries",
        "(product_id IS NULL AND product_name_snapshot IS NULL "
        "AND rate_per_kg_snapshot IS NULL AND amount_mxn IS NULL) OR "
        "(product_id IS NOT NULL AND product_name_snapshot IS NOT NULL "
        "AND rate_per_kg_snapshot IS NOT NULL AND amount_mxn IS NOT NULL)",
    )

    op.create_index(
        "ix_harvest_entries_product_id",
        "harvest_entries",
        ["product_id"],
    )


def downgrade():
    op.drop_index("ix_harvest_entries_product_id", table_name="harvest_entries")
    op.drop_constraint(
        "ck_harvest_entries_product_snapshot_consistency",
        "harvest_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_harvest_entries_amount_non_negative",
        "harvest_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_harvest_entries_rate_snapshot_non_negative",
        "harvest_entries",
        type_="check",
    )
    op.drop_constraint(
        "fk_harvest_entries_product_id",
        "harvest_entries",
        type_="foreignkey",
    )
    op.drop_column("harvest_entries", "amount_mxn")
    op.drop_column("harvest_entries", "rate_per_kg_snapshot")
    op.drop_column("harvest_entries", "product_name_snapshot")
    op.drop_column("harvest_entries", "product_id")
