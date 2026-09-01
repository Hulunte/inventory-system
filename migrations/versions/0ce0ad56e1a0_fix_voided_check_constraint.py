"""fix voided check constraint

Revision ID: 0ce0ad56e1a0
Revises: 84dac1bb632d
Create Date: 2026-09-01 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0ce0ad56e1a0'
down_revision = '84dac1bb632d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('harvest_entries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_harvest_entries_voided_consistency', type_='check')
        batch_op.create_check_constraint(
            'ck_harvest_entries_voided_consistency',
            '(NOT voided AND voided_at IS NULL AND void_reason IS NULL) OR '
            '(voided AND voided_at IS NOT NULL AND void_reason IS NOT NULL AND LENGTH(TRIM(void_reason)) > 0)'
        )


def downgrade():
    with op.batch_alter_table('harvest_entries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_harvest_entries_voided_consistency', type_='check')
        batch_op.create_check_constraint(
            'ck_harvest_entries_voided_consistency',
            'NOT voided OR '
            '(voided AND voided_at IS NOT NULL AND void_reason IS NOT NULL AND LENGTH(TRIM(void_reason)) > 0)'
        )
