"""Cleanup unused columns from influencers table

Revision ID: 005
Revises: 004
Create Date: 2026-01-28

Removes columns not required for the discovery/caching workflow:
- username_encrypted: Never used
- following_count: Not in requirements
- post_count: Not in requirements
- primetag_raw_response: Debug bloat
- profile_url: Derivable from username

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove unused columns from influencers table
    op.drop_column('influencers', 'username_encrypted')
    op.drop_column('influencers', 'following_count')
    op.drop_column('influencers', 'post_count')
    op.drop_column('influencers', 'primetag_raw_response')
    op.drop_column('influencers', 'profile_url')


def downgrade() -> None:
    # Re-add columns if needed
    op.add_column(
        'influencers',
        sa.Column('profile_url', sa.Text, nullable=True)
    )
    op.add_column(
        'influencers',
        sa.Column('primetag_raw_response', postgresql.JSONB, nullable=True)
    )
    op.add_column(
        'influencers',
        sa.Column('post_count', sa.Integer, nullable=True)
    )
    op.add_column(
        'influencers',
        sa.Column('following_count', sa.Integer, nullable=True)
    )
    op.add_column(
        'influencers',
        sa.Column('username_encrypted', sa.String(255), nullable=True)
    )
