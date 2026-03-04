"""Add zones and geofence_events tables

Revision ID: c9a1e3b72d4f
Revises: b7642bb95c6b
Create Date: 2026-03-04 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = 'c9a1e3b72d4f'
down_revision: Union[str, None] = 'b7642bb95c6b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'zones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('center', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, nullable=False)),
        sa.Column('radius_meters', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'geofence_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=False),
        sa.Column('zone_name', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['zone_id'], ['zones.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_geofence_events_device_id', 'geofence_events', ['device_id'])


def downgrade() -> None:
    op.drop_index('ix_geofence_events_device_id', table_name='geofence_events')
    op.drop_table('geofence_events')
    op.drop_table('zones')
