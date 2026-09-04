"""add products table

Revision ID: b2c3d4e5f6a7
Revises: 0ce0ad56e1a0
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = '0ce0ad56e1a0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('rate_per_kg', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_check_constraint(
        'ck_products_rate_non_negative',
        'products',
        'rate_per_kg >= 0',
    )
    op.create_index(
        'ux_products_name_lower',
        'products',
        [sa.text('lower(name)')],
        unique=True,
    )


def downgrade():
    op.drop_index('ux_products_name_lower', table_name='products')
    op.drop_constraint('ck_products_rate_non_negative', 'products', type_='check')
    op.drop_table('products')
