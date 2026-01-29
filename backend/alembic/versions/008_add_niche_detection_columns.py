"""Add niche detection and content themes columns

Revision ID: 008_add_niche_detection_columns
Revises: 007_add_influencer_posts
Create Date: 2026-01-29

Adds columns for storing inferred niche and content theme data from Apify post scraping.
These columns enable fast filtering and matching based on:
- Primary niche (e.g., "padel", "football", "fitness")
- Detected brand mentions from posts
- Content themes for creative matching
- Language detection
- Sponsored content ratio
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add niche detection columns
    op.add_column(
        'influencers',
        sa.Column('primary_niche', sa.String(50), nullable=True,
                  comment='Inferred primary content niche (e.g., padel, football, fitness)')
    )
    op.add_column(
        'influencers',
        sa.Column('niche_confidence', sa.Float(), nullable=True,
                  comment='Confidence score for niche detection (0.0-1.0)')
    )
    op.add_column(
        'influencers',
        sa.Column('detected_brands', JSONB(), nullable=True,
                  comment='Brands detected from post mentions/hashtags')
    )
    op.add_column(
        'influencers',
        sa.Column('sponsored_ratio', sa.Float(), nullable=True,
                  comment='Ratio of sponsored posts (0.0-1.0)')
    )
    op.add_column(
        'influencers',
        sa.Column('content_language', sa.String(10), nullable=True,
                  comment='Primary content language (es, en, ca, etc.)')
    )
    op.add_column(
        'influencers',
        sa.Column('content_themes', JSONB(), nullable=True,
                  comment='Detected content themes for creative matching')
    )

    # Create indexes for efficient querying
    op.create_index('idx_influencers_primary_niche', 'influencers', ['primary_niche'])
    op.create_index('idx_influencers_niche_confidence', 'influencers', ['niche_confidence'])
    op.create_index('idx_influencers_detected_brands', 'influencers', ['detected_brands'], postgresql_using='gin')
    op.create_index('idx_influencers_content_language', 'influencers', ['content_language'])
    op.create_index('idx_influencers_content_themes', 'influencers', ['content_themes'], postgresql_using='gin')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_influencers_content_themes', table_name='influencers')
    op.drop_index('idx_influencers_content_language', table_name='influencers')
    op.drop_index('idx_influencers_detected_brands', table_name='influencers')
    op.drop_index('idx_influencers_niche_confidence', table_name='influencers')
    op.drop_index('idx_influencers_primary_niche', table_name='influencers')

    # Drop columns
    op.drop_column('influencers', 'content_themes')
    op.drop_column('influencers', 'content_language')
    op.drop_column('influencers', 'sponsored_ratio')
    op.drop_column('influencers', 'detected_brands')
    op.drop_column('influencers', 'niche_confidence')
    op.drop_column('influencers', 'primary_niche')
