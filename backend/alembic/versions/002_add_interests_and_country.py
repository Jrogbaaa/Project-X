"""Add interests, brand_mentions, and country columns

Revision ID: 002
Revises: 001
Create Date: 2026-01-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add interests column for niche matching
    op.add_column(
        'influencers',
        sa.Column('interests', postgresql.JSONB, nullable=True)
    )
    
    # Add brand_mentions column for creative fit scoring
    op.add_column(
        'influencers',
        sa.Column('brand_mentions', postgresql.JSONB, nullable=True)
    )
    
    # Add country column for geography-based search
    op.add_column(
        'influencers',
        sa.Column('country', sa.String(100), nullable=True)
    )
    
    # Create GIN index on interests for efficient JSONB array searching
    op.create_index(
        'idx_influencers_interests',
        'influencers',
        ['interests'],
        postgresql_using='gin'
    )
    
    # Create index on country for filtering
    op.create_index(
        'idx_influencers_country',
        'influencers',
        ['country']
    )


def downgrade() -> None:
    op.drop_index('idx_influencers_country', table_name='influencers')
    op.drop_index('idx_influencers_interests', table_name='influencers')
    op.drop_column('influencers', 'country')
    op.drop_column('influencers', 'brand_mentions')
    op.drop_column('influencers', 'interests')
