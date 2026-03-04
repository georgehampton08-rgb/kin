"""Add matched_routes table

Revision ID: d4b7f2a91e3c
Revises: c9a1e3b72d4f
Create Date: 2026-03-04 09:10:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = 'd4b7f2a91e3c'
down_revision: Union[str, None] = 'c9a1e3b72d4f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'matched_routes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('trip_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trip_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_point_count', sa.Integer(), nullable=False),
        sa.Column('matched_path', geoalchemy2.types.Geography(
            geometry_type='LINESTRING', srid=4326, nullable=False
        )),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('provider', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_matched_routes_device_id', 'matched_routes', ['device_id'])


def downgrade() -> None:
    op.drop_index('ix_matched_routes_device_id', table_name='matched_routes')
    op.drop_table('matched_routes')
