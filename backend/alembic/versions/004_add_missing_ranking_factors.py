"""Add missing ranking factors (brand_affinity, creative_fit, niche_match)

Revision ID: 004
Revises: 003
Create Date: 2026-01-28

Changes:
- Add brand_affinity_score, creative_fit_score, niche_match_score to search_results
- Add brand_affinity_weight, creative_fit_weight, niche_match_weight to ranking_presets
- Update CHECK constraint for weights sum (now 8 factors)
- Update default presets with new weights
- Drop redundant result_influencer_ids from searches
- Add GIN index on brand_mentions in influencers

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # 1. Add missing score columns to search_results
    # ===========================================
    op.add_column(
        'search_results',
        sa.Column('brand_affinity_score', sa.Float, nullable=True)
    )
    op.add_column(
        'search_results',
        sa.Column('creative_fit_score', sa.Float, nullable=True)
    )
    op.add_column(
        'search_results',
        sa.Column('niche_match_score', sa.Float, nullable=True)
    )

    # ===========================================
    # 2. Add missing weight columns to ranking_presets
    # ===========================================
    op.add_column(
        'ranking_presets',
        sa.Column('brand_affinity_weight', sa.Float, server_default='0.0')
    )
    op.add_column(
        'ranking_presets',
        sa.Column('creative_fit_weight', sa.Float, server_default='0.0')
    )
    op.add_column(
        'ranking_presets',
        sa.Column('niche_match_weight', sa.Float, server_default='0.0')
    )

    # Drop old CHECK constraint if exists, then add new one with 8 factors
    # Using raw SQL to handle case where constraint doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            ALTER TABLE ranking_presets DROP CONSTRAINT IF EXISTS weights_sum_check;
        EXCEPTION WHEN undefined_object THEN
            -- Constraint doesn't exist, ignore
        END $$;
    """)
    op.create_check_constraint(
        'weights_sum_check',
        'ranking_presets',
        'credibility_weight + engagement_weight + audience_match_weight + growth_weight + geography_weight + brand_affinity_weight + creative_fit_weight + niche_match_weight BETWEEN 0.99 AND 1.01'
    )

    # Update default presets with balanced weights across 8 factors
    # New distribution: credibility=0.15, engagement=0.20, audience=0.15, growth=0.10, 
    #                   geography=0.10, brand_affinity=0.10, creative_fit=0.10, niche_match=0.10
    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.15,
            engagement_weight = 0.20,
            audience_match_weight = 0.15,
            growth_weight = 0.10,
            geography_weight = 0.10,
            brand_affinity_weight = 0.10,
            creative_fit_weight = 0.10,
            niche_match_weight = 0.10
        WHERE name = 'Balanced'
    """)

    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.10,
            engagement_weight = 0.40,
            audience_match_weight = 0.15,
            growth_weight = 0.10,
            geography_weight = 0.05,
            brand_affinity_weight = 0.05,
            creative_fit_weight = 0.10,
            niche_match_weight = 0.05
        WHERE name = 'Engagement Focus'
    """)

    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.30,
            engagement_weight = 0.15,
            audience_match_weight = 0.20,
            growth_weight = 0.05,
            geography_weight = 0.05,
            brand_affinity_weight = 0.10,
            creative_fit_weight = 0.05,
            niche_match_weight = 0.10
        WHERE name = 'Quality First'
    """)

    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.10,
            engagement_weight = 0.15,
            audience_match_weight = 0.15,
            growth_weight = 0.30,
            geography_weight = 0.05,
            brand_affinity_weight = 0.05,
            creative_fit_weight = 0.10,
            niche_match_weight = 0.10
        WHERE name = 'Growth Oriented'
    """)

    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.15,
            engagement_weight = 0.15,
            audience_match_weight = 0.15,
            growth_weight = 0.05,
            geography_weight = 0.25,
            brand_affinity_weight = 0.10,
            creative_fit_weight = 0.05,
            niche_match_weight = 0.10
        WHERE name = 'Local Reach'
    """)

    # Add new preset focused on brand partnerships
    op.execute("""
        INSERT INTO ranking_presets (
            name, description, 
            credibility_weight, engagement_weight, audience_match_weight, 
            growth_weight, geography_weight, brand_affinity_weight, 
            creative_fit_weight, niche_match_weight, 
            is_default, is_system
        ) VALUES (
            'Brand Partnership', 
            'Optimized for brand collaboration fit - prioritizes brand affinity and creative alignment',
            0.10, 0.15, 0.15, 0.05, 0.05, 0.20, 0.20, 0.10,
            FALSE, TRUE
        )
        ON CONFLICT (name) DO NOTHING
    """)

    # ===========================================
    # 3. Drop redundant result_influencer_ids from searches
    # ===========================================
    op.drop_column('searches', 'result_influencer_ids')

    # ===========================================
    # 4. Add GIN index on brand_mentions for efficient querying
    # ===========================================
    op.create_index(
        'idx_influencers_brand_mentions',
        'influencers',
        ['brand_mentions'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    # Drop brand_mentions index
    op.drop_index('idx_influencers_brand_mentions', table_name='influencers')

    # Re-add result_influencer_ids to searches
    op.add_column(
        'searches',
        sa.Column('result_influencer_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True)
    )

    # Delete new preset
    op.execute("DELETE FROM ranking_presets WHERE name = 'Brand Partnership'")

    # Restore old preset values (5 factors summing to 1.0)
    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.25, engagement_weight = 0.30, 
            audience_match_weight = 0.25, growth_weight = 0.10, geography_weight = 0.10
        WHERE name = 'Balanced'
    """)
    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.15, engagement_weight = 0.50, 
            audience_match_weight = 0.20, growth_weight = 0.10, geography_weight = 0.05
        WHERE name = 'Engagement Focus'
    """)
    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.40, engagement_weight = 0.20, 
            audience_match_weight = 0.30, growth_weight = 0.05, geography_weight = 0.05
        WHERE name = 'Quality First'
    """)
    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.15, engagement_weight = 0.25, 
            audience_match_weight = 0.20, growth_weight = 0.35, geography_weight = 0.05
        WHERE name = 'Growth Oriented'
    """)
    op.execute("""
        UPDATE ranking_presets SET
            credibility_weight = 0.20, engagement_weight = 0.20, 
            audience_match_weight = 0.20, growth_weight = 0.10, geography_weight = 0.30
        WHERE name = 'Local Reach'
    """)

    # Drop new CHECK constraint and restore old one (5 factors)
    op.execute("""
        DO $$ 
        BEGIN
            ALTER TABLE ranking_presets DROP CONSTRAINT IF EXISTS weights_sum_check;
        EXCEPTION WHEN undefined_object THEN
            -- Constraint doesn't exist, ignore
        END $$;
    """)
    op.create_check_constraint(
        'weights_sum_check',
        'ranking_presets',
        'credibility_weight + engagement_weight + audience_match_weight + growth_weight + geography_weight BETWEEN 0.99 AND 1.01'
    )

    # Drop new weight columns from ranking_presets
    op.drop_column('ranking_presets', 'niche_match_weight')
    op.drop_column('ranking_presets', 'creative_fit_weight')
    op.drop_column('ranking_presets', 'brand_affinity_weight')

    # Drop new score columns from search_results
    op.drop_column('search_results', 'niche_match_score')
    op.drop_column('search_results', 'creative_fit_score')
    op.drop_column('search_results', 'brand_affinity_score')
