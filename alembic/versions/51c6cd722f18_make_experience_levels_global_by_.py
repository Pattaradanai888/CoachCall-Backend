"""make experience levels global by dropping user_id

Revision ID: 51c6cd722f18
Revises: 4bd8da772649
Create Date: 2025-10-30 22:12:36.388324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51c6cd722f18'
down_revision: Union[str, None] = '4bd8da772649'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - make experience levels global."""
    # Drop the foreign key constraint first
    op.drop_constraint('experience_levels_user_id_fkey', 'experience_levels', type_='foreignkey')
    
    # Drop the user_id column
    op.drop_column('experience_levels', 'user_id')


def downgrade() -> None:
    """Downgrade schema - restore per-user experience levels."""
    # Re-add user_id column
    op.add_column('experience_levels', 
                  sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False))
    
    # Re-create foreign key constraint
    op.create_foreign_key('experience_levels_user_id_fkey', 
                          'experience_levels', 'users', 
                          ['user_id'], ['id'])
