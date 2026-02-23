"""Add influencer_tier column for size-based classification

Revision ID: 009_add_influencer_tier
Revises: 008
Create Date: 2026-02-23

Adds influencer_tier VARCHAR column to enable fast tier-based filtering and
display without recomputing follower ranges on every query.

Tier definitions:
  micro  — < 50K followers
  mid    — 50K–500K followers
  macro  — 500K–2M followers
  mega   — > 2M followers

Populated by: backend/app/services/compute_tiers.py
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'influencers',
        sa.Column(
            'influencer_tier',
            sa.String(10),
            nullable=True,
            comment='Size tier: micro (<50K), mid (50K-500K), macro (500K-2M), mega (>2M)',
        )
    )
    op.create_index('idx_influencers_tier', 'influencers', ['influencer_tier'])


def downgrade() -> None:
    op.drop_index('idx_influencers_tier', table_name='influencers')
    op.drop_column('influencers', 'influencer_tier')
