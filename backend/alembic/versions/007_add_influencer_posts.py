"""Add influencer_posts table and post_content_aggregated column

Revision ID: 007_add_influencer_posts
Revises: 006_add_primetag_identifiers
Create Date: 2026-01-29

Adds support for storing scraped Instagram post content from Apify
for enhanced niche detection based on actual post captions and hashtags.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create influencer_posts table
    op.create_table(
        'influencer_posts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('influencer_id', UUID(as_uuid=True), sa.ForeignKey('influencers.id', ondelete='CASCADE'), nullable=False),

        # Post identifiers
        sa.Column('instagram_post_id', sa.String(100), nullable=False),
        sa.Column('shortcode', sa.String(50), nullable=True),
        sa.Column('post_url', sa.Text(), nullable=True),

        # Content
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('hashtags', JSONB(), nullable=True),  # ["padel", "fitness"]
        sa.Column('mentions', JSONB(), nullable=True),  # ["nike", "bullpadel"]

        # Post metadata
        sa.Column('post_type', sa.String(20), nullable=True),  # Image, Video, Sidecar, Reel
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),

        # Engagement metrics
        sa.Column('likes_count', sa.Integer(), nullable=True),
        sa.Column('comments_count', sa.Integer(), nullable=True),
        sa.Column('views_count', sa.Integer(), nullable=True),

        # Media
        sa.Column('thumbnail_url', sa.Text(), nullable=True),
        sa.Column('is_sponsored', sa.Boolean(), default=False),

        # Apify metadata
        sa.Column('apify_scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('apify_run_id', sa.String(100), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create unique constraint on influencer_id + instagram_post_id
    op.create_unique_constraint(
        'uq_influencer_post',
        'influencer_posts',
        ['influencer_id', 'instagram_post_id']
    )

    # Create indexes for efficient querying
    op.create_index('idx_posts_influencer', 'influencer_posts', ['influencer_id'])
    op.create_index('idx_posts_posted_at', 'influencer_posts', ['posted_at'])
    op.create_index('idx_posts_hashtags', 'influencer_posts', ['hashtags'], postgresql_using='gin')
    op.create_index('idx_posts_mentions', 'influencer_posts', ['mentions'], postgresql_using='gin')

    # Add post_content_aggregated column to influencers table
    # This stores pre-computed niche signals for fast queries
    op.add_column(
        'influencers',
        sa.Column('post_content_aggregated', JSONB(), nullable=True)
    )


def downgrade() -> None:
    # Drop post_content_aggregated column from influencers
    op.drop_column('influencers', 'post_content_aggregated')

    # Drop indexes
    op.drop_index('idx_posts_mentions', table_name='influencer_posts')
    op.drop_index('idx_posts_hashtags', table_name='influencer_posts')
    op.drop_index('idx_posts_posted_at', table_name='influencer_posts')
    op.drop_index('idx_posts_influencer', table_name='influencer_posts')

    # Drop unique constraint
    op.drop_constraint('uq_influencer_post', 'influencer_posts', type_='unique')

    # Drop table
    op.drop_table('influencer_posts')
