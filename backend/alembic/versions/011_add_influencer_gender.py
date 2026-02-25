"""Add influencer_gender column for pre-computed gender classification

Revision ID: 011_add_influencer_gender
Revises: 010
Create Date: 2026-02-25

Adds influencer_gender VARCHAR(10) column (nullable) to store the result of
name/bio/audience gender inference so it is computed once at import time
rather than re-inferred on every search query.

Values: 'male', 'female', or NULL (indeterminate).

Run compute_gender.py after migrating to bulk-populate existing rows:
    cd backend && python -m app.services.compute_gender
"""

from alembic import op
import sqlalchemy as sa


revision = "011_add_influencer_gender"
down_revision = "010_add_profile_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "influencers",
        sa.Column("influencer_gender", sa.String(10), nullable=True),
    )
    op.create_index(
        "idx_influencers_influencer_gender",
        "influencers",
        ["influencer_gender"],
    )


def downgrade() -> None:
    op.drop_index("idx_influencers_influencer_gender", table_name="influencers")
    op.drop_column("influencers", "influencer_gender")
