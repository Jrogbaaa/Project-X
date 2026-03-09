"""Add idea match tables: campaign_examples and idea_briefs

Revision ID: 012_add_idea_match_tables
Revises: 011_add_influencer_gender
Create Date: 2026-03-09

campaign_examples — curated knowledge base of real campaigns, seeded manually.
  Each row represents one campaign/brand example tagged with category, audience,
  archetype, framework used, and what made it work. Used for content-based
  retrieval before LLM generation.

idea_briefs — persisted output of each Idea Match generation run, for history.

After migrating, seed the knowledge base:
    cd backend && python -m app.services.seed_campaign_examples
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB


revision = "012_add_idea_match_tables"
down_revision = "011_add_influencer_gender"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── campaign_examples ─────────────────────────────────────────────────────
    op.create_table(
        "campaign_examples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_name", sa.Text, nullable=False),
        sa.Column("campaign_title", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=False),        # sports, beauty, food, beverage, tech, fashion...
        sa.Column("audience", sa.Text, nullable=True),          # young_male, broad_female, gen_z, family...
        sa.Column("positioning", sa.Text, nullable=True),       # challenger, premium, mass, lifestyle, purpose
        sa.Column("price_tier", sa.Text, nullable=True),        # budget, mid, premium, luxury
        sa.Column("platform", ARRAY(sa.Text), nullable=True),   # ['instagram', 'tiktok', 'youtube', 'tv']
        sa.Column("format", sa.Text, nullable=True),            # challenge, documentary, testimonial, stunt, ugc
        sa.Column("tone", ARRAY(sa.Text), nullable=True),       # ['authentic', 'inspirational', 'humorous', 'bold']
        sa.Column("archetype", sa.Text, nullable=True),         # hero, explorer, caregiver, everyman, creator, ruler, lover
        sa.Column("growth_goal", sa.Text, nullable=True),       # awareness, engagement, persuasion, brand_personality
        sa.Column("framework_used", sa.Text, nullable=False),   # goldenberg_extreme_consequence | repetition_break | ...
        sa.Column("creative_angle", sa.Text, nullable=True),    # 1-2 sentence description of what made this work
        sa.Column("success_signals", sa.Text, nullable=True),   # why it worked
        sa.Column("tags", ARRAY(sa.Text), nullable=True),       # searchable tags
    )

    op.create_index("idx_campaign_examples_category", "campaign_examples", ["category"])
    op.create_index("idx_campaign_examples_growth_goal", "campaign_examples", ["growth_goal"])
    op.create_index("idx_campaign_examples_archetype", "campaign_examples", ["archetype"])
    op.create_index("idx_campaign_examples_framework", "campaign_examples", ["framework_used"])

    # ── idea_briefs ───────────────────────────────────────────────────────────
    op.create_table(
        "idea_briefs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_input", sa.Text, nullable=False),
        sa.Column("brand_attributes", JSONB, nullable=True),      # extracted brand profile
        sa.Column("frameworks_selected", ARRAY(sa.Text), nullable=True),
        sa.Column("retrieved_example_ids", ARRAY(sa.Text), nullable=True),  # UUIDs as strings
        sa.Column("brief", JSONB, nullable=True),                  # full structured output
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("idea_briefs")
    op.drop_index("idx_campaign_examples_framework", table_name="campaign_examples")
    op.drop_index("idx_campaign_examples_archetype", table_name="campaign_examples")
    op.drop_index("idx_campaign_examples_growth_goal", table_name="campaign_examples")
    op.drop_index("idx_campaign_examples_category", table_name="campaign_examples")
    op.drop_table("campaign_examples")
