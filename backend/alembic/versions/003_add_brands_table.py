"""Add brands table for brand knowledge base

Revision ID: 003
Revises: 002
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create brands table for Spanish brand knowledge base
    op.create_table(
        'brands',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('name_normalized', sa.String(255), nullable=False),  # lowercase, no accents for deduplication
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(100), nullable=True),  # e.g., "fashion", "food_beverage", "banking"
        sa.Column('subcategory', sa.String(100), nullable=True),  # e.g., "fast_fashion", "beer", "retail_banking"
        sa.Column('industry', sa.String(100), nullable=True),  # broader sector
        sa.Column('headquarters', sa.String(100), nullable=True),  # city/region in Spain
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('instagram_handle', sa.String(100), nullable=True),  # optional Instagram handle if known
        sa.Column('source', sa.String(100), nullable=True),  # where we got the data (e.g., "kantar_brandz", "ibex35")
        sa.Column('source_rank', sa.Integer, nullable=True),  # ranking in source list (if applicable)
        sa.Column('brand_value_eur', sa.BigInteger, nullable=True),  # brand value in euros if available
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('extra_data', postgresql.JSONB, nullable=True),  # flexible storage for additional data
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # Unique constraint on normalized name for deduplication
    op.create_index(
        'idx_brands_name_normalized',
        'brands',
        ['name_normalized'],
        unique=True
    )

    # Index on category for filtering
    op.create_index(
        'idx_brands_category',
        'brands',
        ['category']
    )

    # Index on industry for broader filtering
    op.create_index(
        'idx_brands_industry',
        'brands',
        ['industry']
    )

    # Index on source for tracking data provenance
    op.create_index(
        'idx_brands_source',
        'brands',
        ['source']
    )

    # GIN index on extra_data for flexible JSONB queries
    op.create_index(
        'idx_brands_extra_data',
        'brands',
        ['extra_data'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_index('idx_brands_extra_data', table_name='brands')
    op.drop_index('idx_brands_source', table_name='brands')
    op.drop_index('idx_brands_industry', table_name='brands')
    op.drop_index('idx_brands_category', table_name='brands')
    op.drop_index('idx_brands_name_normalized', table_name='brands')
    op.drop_table('brands')
