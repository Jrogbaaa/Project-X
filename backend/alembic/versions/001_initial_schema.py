"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create influencers table
    op.create_table(
        'influencers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('platform_type', sa.String(20), nullable=False, server_default='instagram'),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('username_encrypted', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('profile_picture_url', sa.Text, nullable=True),
        sa.Column('bio', sa.Text, nullable=True),
        sa.Column('profile_url', sa.Text, nullable=True),
        sa.Column('is_verified', sa.Boolean, server_default='false'),
        sa.Column('follower_count', sa.BigInteger, nullable=True),
        sa.Column('following_count', sa.Integer, nullable=True),
        sa.Column('post_count', sa.Integer, nullable=True),
        sa.Column('credibility_score', sa.Float, nullable=True),
        sa.Column('engagement_rate', sa.Float, nullable=True),
        sa.Column('follower_growth_rate_6m', sa.Float, nullable=True),
        sa.Column('avg_likes', sa.Integer, nullable=True),
        sa.Column('avg_comments', sa.Integer, nullable=True),
        sa.Column('avg_views', sa.Integer, nullable=True),
        sa.Column('audience_genders', postgresql.JSONB, nullable=True),
        sa.Column('audience_age_distribution', postgresql.JSONB, nullable=True),
        sa.Column('audience_geography', postgresql.JSONB, nullable=True),
        sa.Column('female_audience_age_distribution', postgresql.JSONB, nullable=True),
        sa.Column('primetag_raw_response', postgresql.JSONB, nullable=True),
        sa.Column('cached_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('cache_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_index('idx_influencers_platform_username', 'influencers', ['platform_type', 'username'], unique=True)
    op.create_index('idx_influencers_credibility', 'influencers', ['credibility_score'])
    op.create_index('idx_influencers_engagement', 'influencers', ['engagement_rate'])
    op.create_index('idx_influencers_growth', 'influencers', ['follower_growth_rate_6m'])
    op.create_index('idx_influencers_cache_expiry', 'influencers', ['cache_expires_at'])

    # Create searches table
    op.create_table(
        'searches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('raw_query', sa.Text, nullable=False),
        sa.Column('parsed_query', postgresql.JSONB, nullable=True),
        sa.Column('target_count', sa.Integer, nullable=True),
        sa.Column('gender_filter', sa.String(20), nullable=True),
        sa.Column('brand_context', sa.String(255), nullable=True),
        sa.Column('min_credibility_score', sa.Float, nullable=True),
        sa.Column('min_engagement_rate', sa.Float, nullable=True),
        sa.Column('min_spain_audience_pct', sa.Float, nullable=True),
        sa.Column('min_follower_growth_rate', sa.Float, nullable=True),
        sa.Column('ranking_weights', postgresql.JSONB, nullable=True),
        sa.Column('result_count', sa.Integer, nullable=True),
        sa.Column('result_influencer_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('is_saved', sa.Boolean, server_default='false'),
        sa.Column('saved_name', sa.String(255), nullable=True),
        sa.Column('saved_description', sa.Text, nullable=True),
        sa.Column('user_identifier', sa.String(255), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_index('idx_searches_saved', 'searches', ['is_saved'])
    op.create_index('idx_searches_user', 'searches', ['user_identifier'])
    op.create_index('idx_searches_executed', 'searches', ['executed_at'])

    # Create search_results table
    op.create_table(
        'search_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('search_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('searches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('influencer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('influencers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rank_position', sa.Integer, nullable=False),
        sa.Column('relevance_score', sa.Float, nullable=True),
        sa.Column('credibility_score_normalized', sa.Float, nullable=True),
        sa.Column('engagement_score_normalized', sa.Float, nullable=True),
        sa.Column('audience_match_score', sa.Float, nullable=True),
        sa.Column('growth_score_normalized', sa.Float, nullable=True),
        sa.Column('geography_score', sa.Float, nullable=True),
        sa.Column('metrics_snapshot', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_index('idx_search_results_search', 'search_results', ['search_id'])
    op.create_index('idx_search_results_rank', 'search_results', ['search_id', 'rank_position'])

    # Create api_audit_log table
    op.create_table(
        'api_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('request_params', postgresql.JSONB, nullable=True),
        sa.Column('response_status', sa.Integer, nullable=True),
        sa.Column('response_time_ms', sa.Integer, nullable=True),
        sa.Column('response_size_bytes', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('search_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('searches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.create_index('idx_api_audit_created', 'api_audit_log', ['created_at'])
    op.create_index('idx_api_audit_endpoint', 'api_audit_log', ['endpoint'])

    # Create ranking_presets table
    op.create_table(
        'ranking_presets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('credibility_weight', sa.Float, server_default='0.25'),
        sa.Column('engagement_weight', sa.Float, server_default='0.30'),
        sa.Column('audience_match_weight', sa.Float, server_default='0.25'),
        sa.Column('growth_weight', sa.Float, server_default='0.10'),
        sa.Column('geography_weight', sa.Float, server_default='0.10'),
        sa.Column('is_default', sa.Boolean, server_default='false'),
        sa.Column('is_system', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # Insert default presets
    op.execute("""
        INSERT INTO ranking_presets (name, description, credibility_weight, engagement_weight, audience_match_weight, growth_weight, geography_weight, is_default, is_system) VALUES
        ('Balanced', 'Equal emphasis on all factors', 0.25, 0.30, 0.25, 0.10, 0.10, TRUE, TRUE),
        ('Engagement Focus', 'Prioritizes high engagement rates', 0.15, 0.50, 0.20, 0.10, 0.05, FALSE, TRUE),
        ('Quality First', 'Prioritizes credibility and audience quality', 0.40, 0.20, 0.30, 0.05, 0.05, FALSE, TRUE),
        ('Growth Oriented', 'Prioritizes growing accounts', 0.15, 0.25, 0.20, 0.35, 0.05, FALSE, TRUE),
        ('Local Reach', 'Prioritizes Spanish audience percentage', 0.20, 0.20, 0.20, 0.10, 0.30, FALSE, TRUE)
    """)


def downgrade() -> None:
    op.drop_table('ranking_presets')
    op.drop_table('api_audit_log')
    op.drop_table('search_results')
    op.drop_table('searches')
    op.drop_table('influencers')
