"""add_communications_tables

Revision ID: 12def9e7f486
Revises: c1d50cf6d6ef
Create Date: 2026-03-05 17:44:43.075973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '12def9e7f486'
down_revision: Union[str, Sequence[str], None] = 'c1d50cf6d6ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('call_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(), nullable=False),
    sa.Column('number', sa.String(), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_call_logs_device_id'), 'call_logs', ['device_id'], unique=False)

    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(), nullable=False),
    sa.Column('package_name', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=True),
    sa.Column('text', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_device_id'), 'notifications', ['device_id'], unique=False)

    op.create_table('sms_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(), nullable=False),
    sa.Column('sender', sa.String(), nullable=False),
    sa.Column('body', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_incoming', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sms_messages_device_id'), 'sms_messages', ['device_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_sms_messages_device_id'), table_name='sms_messages')
    op.drop_table('sms_messages')
    op.drop_index(op.f('ix_notifications_device_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_call_logs_device_id'), table_name='call_logs')
    op.drop_table('call_logs')

