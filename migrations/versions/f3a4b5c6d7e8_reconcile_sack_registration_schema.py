"""Reconcile Phase 3 sack-registration columns.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7

This repairs databases that were stamped at the previous head without the
corresponding DDL.  Every operation is conditional so normally migrated
databases remain unchanged.
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name):
    return {column["name"] for column in inspector.get_columns(table_name)}


def _check_names(inspector, table_name):
    return {constraint["name"] for constraint in inspector.get_check_constraints(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    product_columns = _column_names(inspector, "products")
    if "average_sack_weight_kg" not in product_columns:
        op.add_column(
            "products",
            sa.Column("average_sack_weight_kg", sa.Numeric(10, 3), nullable=True),
        )

    inspector = sa.inspect(bind)
    if "ck_products_average_sack_weight_positive" not in _check_names(inspector, "products"):
        op.create_check_constraint(
            "ck_products_average_sack_weight_positive",
            "products",
            "average_sack_weight_kg IS NULL OR average_sack_weight_kg > 0",
        )

    entry_columns = _column_names(inspector, "harvest_entries")
    if "registration_type" not in entry_columns:
        op.add_column(
            "harvest_entries",
            sa.Column(
                "registration_type",
                sa.String(10),
                nullable=False,
                server_default="scale",
            ),
        )
    if "sack_count" not in entry_columns:
        op.add_column("harvest_entries", sa.Column("sack_count", sa.Integer(), nullable=True))
    if "average_sack_weight_kg_snapshot" not in entry_columns:
        op.add_column(
            "harvest_entries",
            sa.Column("average_sack_weight_kg_snapshot", sa.Numeric(10, 3), nullable=True),
        )

    inspector = sa.inspect(bind)
    if (
        "ck_harvest_entries_registration_type_consistency"
        not in _check_names(inspector, "harvest_entries")
    ):
        op.create_check_constraint(
            "ck_harvest_entries_registration_type_consistency",
            "harvest_entries",
            "(registration_type = 'scale' AND sack_count IS NULL "
            "AND average_sack_weight_kg_snapshot IS NULL) OR "
            "(registration_type = 'sacks' AND sack_count > 0 "
            "AND average_sack_weight_kg_snapshot > 0)",
        )


def downgrade():
    # The preceding revision declares these columns as its canonical schema.
    # Removing them here would corrupt a valid e2f3a4b5c6d7 database.  A
    # downgrade through e2's own downgrade remains fully reversible, while
    # this reconciliation step is intentionally non-destructive.
    pass
