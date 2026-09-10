"""Separate scale and sack pricing constraints without rewriting history.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
"""
from alembic import op


revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


OLD_SNAPSHOT_CHECK = (
    "(product_id IS NULL AND product_name_snapshot IS NULL "
    "AND rate_per_kg_snapshot IS NULL AND amount_mxn IS NULL) OR "
    "(product_id IS NOT NULL AND product_name_snapshot IS NOT NULL "
    "AND rate_per_kg_snapshot IS NOT NULL AND amount_mxn IS NOT NULL)"
)

NEW_SNAPSHOT_CHECK = (
    "(product_id IS NULL AND product_name_snapshot IS NULL "
    "AND rate_per_kg_snapshot IS NULL AND rate_per_sack_snapshot IS NULL "
    "AND amount_mxn IS NULL) OR "
    "(product_id IS NOT NULL AND product_name_snapshot IS NOT NULL "
    "AND amount_mxn IS NOT NULL AND ("
    "(registration_type = 'scale' AND rate_per_kg_snapshot IS NOT NULL "
    "AND rate_per_sack_snapshot IS NULL) OR "
    "(registration_type = 'sacks' AND "
    "(rate_per_sack_snapshot IS NOT NULL OR rate_per_kg_snapshot IS NOT NULL))))"
)


def upgrade():
    op.drop_constraint(
        "ck_harvest_entries_product_snapshot_consistency",
        "harvest_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_harvest_entries_product_snapshot_consistency",
        "harvest_entries",
        NEW_SNAPSHOT_CHECK,
    )


def downgrade():
    op.drop_constraint(
        "ck_harvest_entries_product_snapshot_consistency",
        "harvest_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_harvest_entries_product_snapshot_consistency",
        "harvest_entries",
        OLD_SNAPSHOT_CHECK,
    )
