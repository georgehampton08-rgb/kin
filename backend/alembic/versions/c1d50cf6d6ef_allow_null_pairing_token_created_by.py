"""allow_null_pairing_token_created_by

Revision ID: c1d50cf6d6ef
Revises: f1a2b3c4d5e6
Create Date: 2026-03-05 16:06:04.198200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1d50cf6d6ef'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow pairing tokens to be created without an associated user."""
    op.alter_column('pairing_tokens', 'created_by',
               existing_type=sa.UUID(),
               nullable=True)


def downgrade() -> None:
    """Revert: make created_by required again."""
    op.alter_column('pairing_tokens', 'created_by',
               existing_type=sa.UUID(),
               nullable=False)
