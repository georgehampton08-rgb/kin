"""Add trips and device_status tables

Revision ID: f1a2b3c4d5e6
Revises: e1a2b3c4d5f6
Create Date: 2026-03-05 10:20:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e1a2b3c4d5f6'
branch_labels = None
depends_on = None

TRIP_STATUSES = ('ACCUMULATING', 'TRIP_OPEN', 'TRIP_PAUSED', 'TRIP_CLOSED')
DEVICE_STATUSES = ('ONLINE', 'STALE', 'OFFLINE')


def upgrade() -> None:
    # ── trips ────────────────────────────────────────────────
    op.create_table(
        'trips',
        sa.Column('id', UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False,
                  server_default='ACCUMULATING'),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('point_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.CheckConstraint(
            "status IN ('ACCUMULATING','TRIP_OPEN','TRIP_PAUSED','TRIP_CLOSED')",
            name='chk_trip_status',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_trips_device_status', 'trips', ['device_id', 'status'])
    op.create_index('ix_trips_device_id', 'trips', ['device_id'])

    # ── device_status ─────────────────────────────────────────
    op.create_table(
        'device_status',
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('family_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(10), nullable=False,
                  server_default='ONLINE'),
        sa.Column('battery_level', sa.Float(), nullable=True),
        sa.Column('gps_accuracy', sa.Float(), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'),
                  onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.CheckConstraint(
            "status IN ('ONLINE','STALE','OFFLINE')",
            name='chk_device_status',
        ),
        sa.PrimaryKeyConstraint('device_id'),
    )


def downgrade() -> None:
    op.drop_table('device_status')
    op.drop_index('ix_trips_device_id', table_name='trips')
    op.drop_index('ix_trips_device_status', table_name='trips')
    op.drop_table('trips')
