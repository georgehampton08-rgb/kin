""""add parent dashboard device fields"

Revision ID: 3c8553b760e5
Revises: 4b27d38fb544
Create Date: 2026-03-05 21:23:18.917178

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3c8553b760e5'
down_revision = '4b27d38fb544'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('devices', sa.Column('nickname', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('os_info', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('app_version', sa.String(length=50), nullable=True))
    
    op.add_column('call_logs', sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('notifications', sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sms_messages', sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('sms_messages', 'is_read')
    op.drop_column('notifications', 'is_read')
    op.drop_column('call_logs', 'is_read')
    op.drop_column('devices', 'app_version')
    op.drop_column('devices', 'os_info')
    op.drop_column('devices', 'nickname')
