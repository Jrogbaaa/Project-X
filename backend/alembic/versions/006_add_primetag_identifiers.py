"""Add PrimeTag identifier fields for optimized API calls

Revision ID: 006_add_primetag_identifiers
Revises: 005_cleanup_unused_columns
Create Date: 2026-01-28

These fields store PrimeTag identifiers to enable direct API calls
without needing to search first, reducing API calls from 2 to 1 per verification.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add external_social_profile_id column
    op.add_column(
        'influencers',
        sa.Column('external_social_profile_id', sa.String(100), nullable=True)
    )
    
    # Add primetag_encrypted_username column
    op.add_column(
        'influencers',
        sa.Column('primetag_encrypted_username', sa.Text(), nullable=True)
    )
    
    # Add index on external_social_profile_id for lookups
    op.create_index(
        'idx_influencers_external_id',
        'influencers',
        ['external_social_profile_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('idx_influencers_external_id', table_name='influencers')
    op.drop_column('influencers', 'primetag_encrypted_username')
    op.drop_column('influencers', 'external_social_profile_id')
