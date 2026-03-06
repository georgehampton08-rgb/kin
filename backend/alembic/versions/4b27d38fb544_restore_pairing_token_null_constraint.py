"""restore pairing token null constraint

Revision ID: 4b27d38fb544
Revises: 12def9e7f486
Create Date: 2026-03-05 17:51:05.649639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b27d38fb544'
down_revision: Union[str, Sequence[str], None] = '12def9e7f486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE pairing_tokens SET created_by = (SELECT id FROM users LIMIT 1) WHERE created_by IS NULL;")
    op.execute("ALTER TABLE pairing_tokens ALTER COLUMN created_by SET NOT NULL;")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE pairing_tokens ALTER COLUMN created_by DROP NOT NULL;")
