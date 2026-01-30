"""
Pytest fixtures for backend testing.

Provides database sessions, service instances, and test data factories.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import Base
from app.models.influencer import Influencer
from app.models.search import Search, SearchResult
from app.services.search_service import SearchService
from app.services.filter_service import FilterService
from app.services.ranking_service import RankingService
from app.services.cache_service import CacheService
from app.schemas.search import SearchRequest, FilterConfig, RankingWeights
from app.schemas.llm import ParsedSearchQuery, GenderFilter


# ============================================================
# Database Fixtures
# ============================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh database session for each test.
    
    Uses the real database connection from environment.
    Tests should not rely on clean state - use explicit cleanup if needed.
    """
    from app.config import get_settings
    
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        # Rollback any uncommitted changes
        await session.rollback()
    
    await engine.dispose()


# ============================================================
# Service Fixtures
# ============================================================

@pytest_asyncio.fixture
async def search_service(db_session: AsyncSession) -> SearchService:
    """Create a SearchService instance with a database session."""
    return SearchService(db_session)


@pytest.fixture
def filter_service() -> FilterService:
    """Create a FilterService instance."""
    return FilterService()


@pytest.fixture
def ranking_service() -> RankingService:
    """Create a RankingService instance."""
    return RankingService()


@pytest_asyncio.fixture
async def cache_service(db_session: AsyncSession) -> CacheService:
    """Create a CacheService instance."""
    return CacheService(db_session)


# ============================================================
# Test Data Factories
# ============================================================

class InfluencerFactory:
    """Factory for creating test influencer data."""
    
    @staticmethod
    def create(
        username: str = None,
        follower_count: int = 100000,
        engagement_rate: float = 3.5,
        credibility_score: float = 85.0,
        country: str = "Spain",
        primary_niche: str = None,
        interests: List[str] = None,
        audience_geography: Dict[str, float] = None,
        audience_genders: Dict[str, float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a test influencer data dict."""
        username = username or f"test_user_{uuid4().hex[:8]}"
        
        return {
            "id": str(uuid4()),
            "username": username,
            "display_name": username.replace("_", " ").title(),
            "follower_count": follower_count,
            "engagement_rate": engagement_rate,
            "credibility_score": credibility_score,
            "country": country,
            "primary_niche": primary_niche,
            "niche_confidence": 0.85 if primary_niche else None,
            "interests": interests or ["Lifestyle"],
            "audience_geography": audience_geography or {"ES": 75.0, "MX": 10.0, "AR": 5.0},
            "audience_genders": audience_genders or {"male": 45.0, "female": 55.0},
            "audience_age_distribution": {"18-24": 30, "25-34": 40, "35-44": 20},
            "bio": f"Test bio for {username}",
            "platform_type": "instagram",
            "cache_expires_at": datetime.utcnow() + timedelta(hours=24),
            **kwargs
        }
    
    @staticmethod
    def create_model(db_session: AsyncSession = None, **kwargs) -> Influencer:
        """Create an Influencer model instance."""
        data = InfluencerFactory.create(**kwargs)
        influencer = Influencer(
            id=data["id"],
            username=data["username"],
            display_name=data["display_name"],
            follower_count=data["follower_count"],
            engagement_rate=data["engagement_rate"],
            credibility_score=data["credibility_score"],
            country=data["country"],
            primary_niche=data["primary_niche"],
            niche_confidence=data["niche_confidence"],
            interests=data["interests"],
            audience_geography=data["audience_geography"],
            audience_genders=data["audience_genders"],
            audience_age_distribution=data["audience_age_distribution"],
            bio=data["bio"],
            platform_type=data["platform_type"],
            cache_expires_at=data["cache_expires_at"],
        )
        return influencer


@pytest.fixture
def influencer_factory() -> InfluencerFactory:
    """Provide the InfluencerFactory class."""
    return InfluencerFactory()


class ParsedQueryFactory:
    """Factory for creating test ParsedSearchQuery instances."""
    
    @staticmethod
    def create(
        brand_name: str = None,
        campaign_niche: str = None,
        creative_concept: str = None,
        creative_tone: List[str] = None,
        creative_themes: List[str] = None,
        exclude_niches: List[str] = None,
        target_count: int = 5,
        **kwargs
    ) -> ParsedSearchQuery:
        """Create a test ParsedSearchQuery."""
        return ParsedSearchQuery(
            target_count=target_count,
            brand_name=brand_name,
            campaign_niche=campaign_niche,
            creative_concept=creative_concept,
            creative_tone=creative_tone or [],
            creative_themes=creative_themes or [],
            exclude_niches=exclude_niches or [],
            search_keywords=kwargs.pop("search_keywords", []),
            campaign_topics=kwargs.pop("campaign_topics", []),
            parsing_confidence=kwargs.pop("parsing_confidence", 1.0),
            reasoning=kwargs.pop("reasoning", "Test query"),
            **kwargs
        )


@pytest.fixture
def parsed_query_factory() -> ParsedQueryFactory:
    """Provide the ParsedQueryFactory class."""
    return ParsedQueryFactory()


# ============================================================
# Test Brief Templates
# ============================================================

TEST_BRIEFS = {
    # Niche Precision Tests
    "padel_brand": {
        "query": """Find 5 influencers for Bullpadel, a premium padel equipment brand. 
        We're launching a new racket line targeting serious padel players in Spain.
        Looking for authentic padel content creators who post regularly about the sport.
        IMPORTANT: No football or soccer influencers - this is strictly for padel.""",
        "expected_niche": "padel",
        "excluded_niches": ["football", "soccer"],
        "expected_brand": "Bullpadel",
    },
    
    "home_furniture": {
        "query": """Campaign for IKEA Spain - we need 5 home and lifestyle influencers
        who create content about interior design, home decor, and living spaces.
        Target audience is young couples (25-34) furnishing their first homes.
        Prefer influencers with authentic, relatable content style.""",
        "expected_niche": "home_decor",
        "expected_brand": "IKEA",
    },
    
    "fitness_supplement": {
        "query": """Looking for 5 fitness influencers for MyProtein campaign.
        Need content creators who focus on gym workouts, nutrition, and healthy lifestyle.
        Prefer macro-influencers (100K-500K followers) with high engagement.
        Authentic fitness journeys, not just flexing.""",
        "expected_niche": "fitness",
        "expected_brand": "MyProtein",
    },
    
    # Brand Matching Tests
    "unknown_brand": {
        "query": """Find influencers for VIPS restaurant chain in Spain.
        Looking for food and lifestyle content creators who enjoy casual dining.
        Family-friendly content preferred, target audience 25-45 years old.""",
        "expected_niche": "food",
        "expected_brand": "VIPS",
    },
    
    "competitor_exclusion": {
        "query": """Nike Spain campaign for new running shoes.
        Need 5 fitness/running influencers who are NOT affiliated with Adidas.
        Focus on authentic runners, marathon trainers, trail runners.
        Documentary-style content showing real training journeys.""",
        "expected_niche": "running",
        "expected_brand": "Nike",
        "exclude_competitors": ["Adidas"],
    },
    
    # Creative Fit Tests
    "documentary_style": {
        "query": """Documentary-style campaign for Red Bull Spain.
        Looking for adventure and extreme sports content creators.
        Raw, authentic storytelling showing real athletic journeys.
        Gritty, inspirational tone - not polished commercial content.""",
        "expected_niche": "sports",
        "creative_format": "documentary",
        "creative_tone": ["authentic", "gritty", "inspirational"],
    },
    
    "luxury_brand": {
        "query": """Luxury campaign for Loewe fashion brand.
        Need 5 fashion influencers with premium, high-end aesthetic.
        Polished, sophisticated content style. Targeting affluent audience.
        Prefer influencers who have worked with luxury brands before.""",
        "expected_niche": "fashion",
        "expected_brand": "Loewe",
        "creative_tone": ["luxury", "polished"],
    },
    
    "humorous_casual": {
        "query": """Campaign for Mahou beer - fun, casual summer campaign.
        Looking for lifestyle/comedy influencers who create humorous content.
        Relatable, funny, engaging - celebrating good times with friends.
        NOT looking for fitness influencers or health-focused content.""",
        "expected_niche": "lifestyle",
        "expected_brand": "Mahou",
        "creative_tone": ["humorous", "casual"],
        "excluded_niches": ["fitness", "wellness"],
    },
    
    # Edge Cases
    "gender_split": {
        "query": """Fashion campaign needs 3 male and 3 female influencers.
        Mix of street style and casual fashion content.
        Followers between 50K-300K, high engagement required.""",
        "expected_niche": "fashion",
        "target_male_count": 3,
        "target_female_count": 3,
    },
    
    "size_preferences": {
        "query": """Looking for micro-influencers (10K-100K followers) for local
        restaurant promotion. Food and lifestyle content creators in Spain.
        Prefer high engagement over follower count. Authentic food lovers.""",
        "expected_niche": "food",
        "preferred_follower_min": 10000,
        "preferred_follower_max": 100000,
    },
    
    "multi_niche": {
        "query": """Sports nutrition brand campaign - need influencers who combine
        fitness AND nutrition content. Workout routines plus healthy eating.
        Athletes who care about what they eat. Gym and kitchen content.""",
        "expected_niche": "fitness",
        "additional_niches": ["nutrition"],
    },
}


@pytest.fixture
def test_briefs() -> Dict[str, Dict[str, Any]]:
    """Provide test brief templates."""
    return TEST_BRIEFS


# ============================================================
# Helper Fixtures
# ============================================================

@pytest.fixture
def default_filters() -> FilterConfig:
    """Provide default filter configuration."""
    return FilterConfig(
        min_credibility_score=70.0,
        min_spain_audience_pct=60.0,
        min_engagement_rate=None,
        max_follower_count=2_500_000,
    )


@pytest.fixture
def default_weights() -> RankingWeights:
    """Provide default ranking weights."""
    return RankingWeights(
        credibility=0.00,
        engagement=0.00,
        audience_match=0.00,
        growth=0.00,
        geography=0.00,
        brand_affinity=0.25,
        creative_fit=0.35,
        niche_match=0.40,
    )
