"""add void fields to harvest_entries

Revision ID: 84dac1bb632d
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01 14:06:09.430021

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '84dac1bb632d'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('harvest_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voided', sa.Boolean(), nullable=False, server_default='false'))
        batch_op.add_column(sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('void_reason', sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f('ix_harvest_entries_voided'), ['voided'], unique=False)
        batch_op.create_check_constraint('ck_harvest_entries_voided_consistency', 'NOT voided OR (voided AND voided_at IS NOT NULL AND void_reason IS NOT NULL AND LENGTH(TRIM(void_reason)) > 0)')


def downgrade():
    with op.batch_alter_table('harvest_entries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_harvest_entries_voided_consistency', type_='check')
        batch_op.drop_index(batch_op.f('ix_harvest_entries_voided'))
        batch_op.drop_column('void_reason')
        batch_op.drop_column('voided_at')
        batch_op.drop_column('voided')
