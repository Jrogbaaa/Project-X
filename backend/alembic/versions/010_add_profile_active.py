"""Add profile_active column for Instagram handle validity tracking

Revision ID: 010_add_profile_active
Revises: 009
Create Date: 2026-02-24

Adds profile_active BOOLEAN column (default TRUE) to allow marking influencers
whose Instagram handles no longer resolve (renamed, deleted, or scraped incorrectly).

- True  (default): handle assumed active, included in search results
- False: handle confirmed gone; excluded from all discovery queries
"""

from alembic import op
import sqlalchemy as sa


revision = "010_add_profile_active"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "influencers",
        sa.Column(
            "profile_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.create_index(
        "idx_influencers_profile_active",
        "influencers",
        ["profile_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_influencers_profile_active", table_name="influencers")
    op.drop_column("influencers", "profile_active")
