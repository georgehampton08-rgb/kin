"""Initial Postgis schema

Revision ID: b7642bb95c6b
Revises: 
Create Date: 2026-03-04 07:58:38.660412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = 'b7642bb95c6b'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure postgis extension exists
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')

    # Drop explicitly if exists depending on cleanup
    op.execute('DROP TABLE IF EXISTS current_status CASCADE')
    op.execute('DROP TABLE IF EXISTS location_history CASCADE')

    op.create_table('current_status',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(), nullable=False),
    sa.Column('coordinates', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, dimension=2, nullable=False)),
    sa.Column('altitude', sa.Float(), nullable=True),
    sa.Column('speed', sa.Float(), nullable=True),
    sa.Column('battery_level', sa.Float(), nullable=True),
    sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_current_status_device_id'), 'current_status', ['device_id'], unique=True)
    
    op.create_table('location_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(), nullable=False),
    sa.Column('coordinates', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, dimension=2, nullable=False)),
    sa.Column('altitude', sa.Float(), nullable=True),
    sa.Column('speed', sa.Float(), nullable=True),
    sa.Column('battery_level', sa.Float(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_location_history_device_id'), 'location_history', ['device_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_location_history_device_id'), table_name='location_history')
    op.drop_table('location_history')
    op.drop_index(op.f('ix_current_status_device_id'), table_name='current_status')
    op.drop_table('current_status')
