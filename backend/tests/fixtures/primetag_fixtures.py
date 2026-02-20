"""
Deterministic PrimeTag fixture factory.

All tests that exercise extract_metrics(), Spain-filter, or retry logic
should import from here so fixture data has a single source of truth.

Real PrimeTag schema for average_age items:
    {"label": "18-24", "female": 18.5, "male": 16.3}
"""
from typing import Any, Dict, List, Optional

from app.schemas.primetag import (
    AudienceData,
    AudienceDataSection,
    MediaKit,
    MediaKitSummary,
)


# ---------------------------------------------------------------------------
# Default values used by make_media_kit() — override per-test as needed
# ---------------------------------------------------------------------------

_DEFAULT_LOCATION_BY_COUNTRY: List[Dict[str, Any]] = [
    {"name": "Spain",   "percentage": 65.0},
    {"name": "Mexico",  "percentage": 12.0},
    {"name": "France",  "percentage": 8.0},
    {"name": "Germany", "percentage": 5.0},
]

_DEFAULT_GENDERS: Dict[str, float] = {"female": 55.0, "male": 45.0}

# Uses real PrimeTag schema: label / female / male
_DEFAULT_AVERAGE_AGE: List[Dict[str, Any]] = [
    {"label": "13-17", "female": 2.0,  "male": 1.5},
    {"label": "18-24", "female": 18.5, "male": 16.3},
    {"label": "25-34", "female": 22.0, "male": 20.1},
    {"label": "35-44", "female": 8.5,  "male": 7.2},
    {"label": "45-54", "female": 2.5,  "male": 0.9},
    {"label": "55+",   "female": 1.5,  "male": 0.0},
]


def make_audience_section(
    credibility: Optional[float] = 82.0,
    genders: Optional[Dict[str, float]] = None,
    average_age: Optional[List[Dict[str, Any]]] = None,
    location_by_country: Optional[List[Dict[str, Any]]] = None,
) -> AudienceDataSection:
    """Build an AudienceDataSection with sensible defaults."""
    return AudienceDataSection(
        audience_credibility_percentage=credibility,
        genders=genders if genders is not None else _DEFAULT_GENDERS.copy(),
        average_age=average_age if average_age is not None else [
            dict(item) for item in _DEFAULT_AVERAGE_AGE
        ],
        location_by_country=location_by_country if location_by_country is not None else [
            dict(item) for item in _DEFAULT_LOCATION_BY_COUNTRY
        ],
    )


def make_media_kit(
    username: str = "test_influencer",
    platform_type: int = 2,          # 2 = Instagram
    avg_engagement_rate: float = 0.034,
    followers: int = 150_000,
    avg_likes: int = 5_100,
    avg_comments: int = 210,
    credibility: Optional[float] = 82.0,
    genders: Optional[Dict[str, float]] = None,
    average_age: Optional[List[Dict[str, Any]]] = None,
    location_by_country: Optional[List[Dict[str, Any]]] = None,
    audience_data: Optional[AudienceData] = None,
    **extra,
) -> MediaKit:
    """
    Return a fully populated MediaKit Pydantic object.

    All audience-data defaults produce a passing influencer:
      - Spain 65% → passes 60% threshold
      - female=55 / male=45 → sums to 100
      - age bands have no None values
      - credibility=82 → present for Instagram, None returned for TikTok by extract_metrics()
      - ER=0.034
    """
    if audience_data is None:
        audience_data = AudienceData(
            followers=make_audience_section(
                credibility=credibility,
                genders=genders,
                average_age=average_age,
                location_by_country=location_by_country,
            )
        )
    return MediaKit(
        username=username,
        platform_type=platform_type,
        avg_engagement_rate=avg_engagement_rate,
        followers=followers,
        avg_likes=avg_likes,
        avg_comments=avg_comments,
        fullname=username.replace("_", " ").title(),
        audience_data=audience_data,
        **extra,
    )


def make_media_kit_summary(
    username: str = "test_influencer",
    platform_type: int = 2,
    audience_size: int = 150_000,
    external_social_profile_id: Optional[str] = None,
    mediakit_url: Optional[str] = None,
) -> MediaKitSummary:
    """Return a minimal MediaKitSummary (as returned by the search endpoint)."""
    encrypted = "Z0FBQUFBQm1PckVxX3Rlc3RfdG9rZW4"  # deterministic fake token
    return MediaKitSummary(
        username=username,
        platform_type=platform_type,
        audience_size=audience_size,
        external_social_profile_id=external_social_profile_id or f"ext_{username}",
        mediakit_url=mediakit_url or f"https://mediakit.primetag.com/instagram/{encrypted}",
    )
