"""replace products/inventory with workers/harvest

Revision ID: a1b2c3d4e5f6
Revises: 7c028815dd1b
Create Date: 2026-08-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '7c028815dd1b'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('inventory_movements')
    op.drop_table('products')

    op.create_table('workers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('barcode', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('workers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workers_barcode'), ['barcode'], unique=True)

    op.create_table('harvest_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('worker_id', sa.Integer(), nullable=False),
    sa.Column('weight_kg', sa.Numeric(precision=10, scale=3), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.CheckConstraint('weight_kg > 0', name='ck_harvest_entries_weight_positive')
    )
    with op.batch_alter_table('harvest_entries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_harvest_entries_worker_id'), ['worker_id'], unique=False)


def downgrade():
    with op.batch_alter_table('harvest_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_harvest_entries_worker_id'))

    op.drop_table('harvest_entries')

    with op.batch_alter_table('workers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workers_barcode'))

    op.drop_table('workers')

    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('barcode', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_products_barcode'), ['barcode'], unique=True)

    op.create_table('inventory_movements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('movement_type', sa.String(length=20), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('inventory_movements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inventory_movements_product_id'), ['product_id'], unique=False)
