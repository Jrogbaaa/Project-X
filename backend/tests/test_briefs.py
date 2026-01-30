"""
Comprehensive test briefs for search pipeline testing.

Each brief includes:
- query: The natural language search query
- expected: Expected behaviors and extractions
- assertions: Specific things to verify in results
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class TestBriefExpectations:
    """Expected behaviors for a test brief."""
    # Query parsing expectations
    expected_brand: Optional[str] = None
    expected_niche: Optional[str] = None
    expected_topics: List[str] = field(default_factory=list)
    excluded_niches: List[str] = field(default_factory=list)
    
    # Creative expectations
    expected_format: Optional[str] = None
    expected_tones: List[str] = field(default_factory=list)
    expected_themes: List[str] = field(default_factory=list)
    
    # Count expectations
    target_count: int = 5
    target_male_count: Optional[int] = None
    target_female_count: Optional[int] = None
    
    # Size expectations
    preferred_follower_min: Optional[int] = None
    preferred_follower_max: Optional[int] = None
    
    # Result quality expectations
    min_niche_alignment: float = 0.6  # Minimum acceptable niche alignment score
    min_brand_fit: float = 0.5  # Minimum acceptable brand fit
    min_creative_fit: float = 0.4  # Minimum acceptable creative fit
    
    # Strict checks
    must_not_have_niches: List[str] = field(default_factory=list)  # Hard fail if these niches appear
    must_not_have_brands: List[str] = field(default_factory=list)  # Hard fail if competitor brands
    
    # Success criteria
    min_overall_quality: str = "acceptable"  # Minimum acceptable reflection verdict


@dataclass
class TestBrief:
    """A test brief with query and expectations."""
    name: str
    category: str  # niche_precision, brand_matching, creative_fit, edge_case
    query: str
    expectations: TestBriefExpectations
    description: str = ""


# ============================================================
# NICHE PRECISION TESTS
# These test that the search correctly identifies and matches niches
# ============================================================

NICHE_PRECISION_BRIEFS = [
    TestBrief(
        name="padel_brand_strict",
        category="niche_precision",
        description="Padel brand with strict exclusion of football - CRITICAL TEST",
        query="""Find 5 influencers for Bullpadel, a premium padel equipment brand. 
        We're launching a new racket line targeting serious padel players in Spain.
        Looking for authentic padel content creators who post regularly about the sport.
        IMPORTANT: Absolutely NO football or soccer influencers - this campaign is 
        strictly for padel content. We don't want famous soccer players who play 
        padel casually, we want dedicated padel creators.""",
        expectations=TestBriefExpectations(
            expected_brand="Bullpadel",
            expected_niche="padel",
            excluded_niches=["football", "soccer"],
            must_not_have_niches=["football", "soccer"],
            min_niche_alignment=0.7,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="home_furniture_ikea",
        category="niche_precision",
        description="Home furniture brand targeting home decor niche",
        query="""Campaign for IKEA Spain - we need 5 home and lifestyle influencers
        who create content about interior design, home decor, and living spaces.
        Target audience is young couples (25-34) furnishing their first homes.
        Prefer influencers with authentic, relatable content showing real homes,
        not just staged photoshoots. DIY and renovation content is a plus.""",
        expectations=TestBriefExpectations(
            expected_brand="IKEA",
            expected_niche="home_decor",
            expected_topics=["interior design", "home decor", "living spaces", "diy"],
            min_niche_alignment=0.6,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="fitness_supplement_protein",
        category="niche_precision",
        description="Fitness supplement brand targeting gym/nutrition niche",
        query="""Looking for 5 fitness influencers for MyProtein campaign.
        Need content creators who focus on gym workouts, nutrition, and healthy lifestyle.
        Prefer macro-influencers (100K-500K followers) with high engagement.
        Authentic fitness journeys, not just flexing and showing off.
        Content about meal prep, supplements, workout routines.""",
        expectations=TestBriefExpectations(
            expected_brand="MyProtein",
            expected_niche="fitness",
            expected_topics=["gym", "nutrition", "workout"],
            preferred_follower_min=100000,
            preferred_follower_max=500000,
            min_niche_alignment=0.7,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="tennis_racket_brand",
        category="niche_precision",
        description="Tennis equipment brand - should match tennis/racket sports",
        query="""Babolat tennis campaign in Spain. Looking for 5 tennis players 
        and coaches who create tennis content. Focus on technique, training, 
        and tournament coverage. Both professional and amateur content creators.
        No football, padel should be OK as related racket sport.""",
        expectations=TestBriefExpectations(
            expected_brand="Babolat",
            expected_niche="tennis",
            excluded_niches=["football"],
            must_not_have_niches=["football", "soccer"],
            min_niche_alignment=0.7,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="running_shoes_brand",
        category="niche_precision",
        description="Running shoes - should match running/fitness niche",
        query="""ASICS running campaign for marathon season. Need 5 runners -
        marathon trainers, trail runners, ultrarunners. Real runners who 
        document their training, not just fitness models. Show me people
        who actually compete in races. NO football, basketball, etc.""",
        expectations=TestBriefExpectations(
            expected_brand="ASICS",
            expected_niche="running",
            expected_topics=["marathon", "trail running", "training"],
            excluded_niches=["football", "basketball"],
            must_not_have_niches=["football", "basketball", "soccer"],
            min_niche_alignment=0.7,
            target_count=5,
        )
    ),
]

# ============================================================
# BRAND MATCHING TESTS
# These test brand recognition, competitor exclusion, and brand context
# ============================================================

BRAND_MATCHING_BRIEFS = [
    TestBrief(
        name="unknown_restaurant_brand",
        category="brand_matching",
        description="Unknown brand that requires LLM lookup",
        query="""Find influencers for VIPS restaurant chain in Spain.
        Looking for food and lifestyle content creators who enjoy casual dining.
        Family-friendly content preferred, target audience 25-45 years old.
        Show me foodies who do restaurant reviews and food content.""",
        expectations=TestBriefExpectations(
            expected_brand="VIPS",
            expected_niche="food",
            expected_topics=["restaurant", "dining", "food"],
            min_niche_alignment=0.5,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="nike_exclude_adidas",
        category="brand_matching",
        description="Nike campaign with Adidas competitor exclusion",
        query="""Nike Spain campaign for new running shoes.
        Need 5 fitness/running influencers who are NOT affiliated with Adidas.
        Focus on authentic runners, marathon trainers, trail runners.
        Documentary-style content showing real training journeys.
        NO Adidas ambassadors or influencers who frequently post Adidas content.""",
        expectations=TestBriefExpectations(
            expected_brand="Nike",
            expected_niche="running",
            must_not_have_brands=["Adidas", "adidas"],
            expected_format="documentary",
            min_niche_alignment=0.6,
            min_brand_fit=0.7,  # Higher standard due to competitor exclusion
            target_count=5,
        )
    ),
    
    TestBrief(
        name="adidas_exclude_nike",
        category="brand_matching",
        description="Adidas campaign with Nike competitor exclusion",
        query="""Adidas Originals streetwear campaign. Looking for 5 fashion/lifestyle
        influencers with street style aesthetic. No Nike ambassadors.
        Urban, trendy, authentic style. Sneaker culture content.""",
        expectations=TestBriefExpectations(
            expected_brand="Adidas",
            expected_niche="fashion",
            expected_topics=["streetwear", "sneakers", "street style"],
            must_not_have_brands=["Nike", "nike"],
            min_brand_fit=0.7,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="local_spanish_brand",
        category="brand_matching",
        description="Local Spanish brand test",
        query="""Campaign for Desigual, Spanish fashion brand.
        Need 5 colorful, creative fashion influencers.
        Artistic, bold, unconventional style. Not minimal aesthetic.
        Spanish creators preferred, authentic personal style.""",
        expectations=TestBriefExpectations(
            expected_brand="Desigual",
            expected_niche="fashion",
            expected_tones=["creative", "bold", "artistic"],
            min_niche_alignment=0.6,
            target_count=5,
        )
    ),
]

# ============================================================
# CREATIVE FIT TESTS
# These test creative concept matching (format, tone, themes)
# ============================================================

CREATIVE_FIT_BRIEFS = [
    TestBrief(
        name="documentary_adventure",
        category="creative_fit",
        description="Documentary-style adventure content",
        query="""Documentary-style campaign for Red Bull Spain.
        Looking for adventure and extreme sports content creators.
        Raw, authentic storytelling showing real athletic journeys.
        Gritty, inspirational tone - not polished commercial content.
        Athletes pushing their limits, behind-the-scenes training.""",
        expectations=TestBriefExpectations(
            expected_brand="Red Bull",
            expected_niche="sports",
            expected_format="documentary",
            expected_tones=["authentic", "gritty", "inspirational", "raw"],
            expected_themes=["adventure", "athletic journeys", "pushing limits"],
            min_creative_fit=0.6,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="luxury_fashion_polished",
        category="creative_fit",
        description="Luxury brand requiring polished aesthetic",
        query="""Luxury campaign for Loewe fashion brand.
        Need 5 fashion influencers with premium, high-end aesthetic.
        Polished, sophisticated content style. Targeting affluent audience.
        Prefer influencers who have worked with luxury brands before.
        Editorial quality, artistic vision, aspirational content.""",
        expectations=TestBriefExpectations(
            expected_brand="Loewe",
            expected_niche="fashion",
            expected_tones=["luxury", "polished", "sophisticated"],
            expected_themes=["aspirational", "editorial", "artistic"],
            min_creative_fit=0.6,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="humorous_beer_campaign",
        category="creative_fit",
        description="Humorous casual campaign",
        query="""Campaign for Mahou beer - fun, casual summer campaign.
        Looking for lifestyle/comedy influencers who create humorous content.
        Relatable, funny, engaging - celebrating good times with friends.
        NOT looking for fitness influencers or health-focused content.
        Light-hearted, social, entertaining content.""",
        expectations=TestBriefExpectations(
            expected_brand="Mahou",
            expected_niche="lifestyle",
            expected_tones=["humorous", "casual", "fun", "relatable"],
            excluded_niches=["fitness", "wellness"],
            must_not_have_niches=["fitness"],  # Should not return gym bros for beer
            min_creative_fit=0.5,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="tutorial_tech_content",
        category="creative_fit",
        description="Tutorial/educational tech content",
        query="""Samsung Spain tech campaign. Need 5 tech reviewers who create
        tutorial and educational content about smartphones and gadgets.
        Clear explanations, detailed reviews, unboxing content.
        NOT lifestyle/fashion influencers who just show products.
        Real tech expertise, comparison videos, how-to guides.""",
        expectations=TestBriefExpectations(
            expected_brand="Samsung",
            expected_niche="tech",
            expected_format="tutorial",
            expected_topics=["tech review", "smartphones", "gadgets"],
            min_creative_fit=0.5,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="storytelling_family_brand",
        category="creative_fit",
        description="Emotional storytelling for family brand",
        query="""Nestlé baby food campaign. Looking for parenting influencers
        who create heartfelt, emotional content about family life.
        Storytelling format - real parenting moments, milestones.
        Authentic, warm tone. NOT clinical or product-focused.
        Genuine family content, not staged perfection.""",
        expectations=TestBriefExpectations(
            expected_brand="Nestlé",
            expected_niche="parenting",
            expected_format="storytelling",
            expected_tones=["authentic", "warm", "heartfelt"],
            expected_themes=["family", "parenting", "milestones"],
            min_creative_fit=0.5,
            target_count=5,
        )
    ),
]

# ============================================================
# EDGE CASE TESTS
# These test specific edge cases and complex requirements
# ============================================================

EDGE_CASE_BRIEFS = [
    TestBrief(
        name="gender_split_3_3",
        category="edge_case",
        description="Explicit gender split requirement",
        query="""Fashion campaign needs 3 male and 3 female influencers.
        Mix of street style and casual fashion content.
        Followers between 50K-300K, high engagement required.
        Both genders should have similar aesthetic - urban, modern.""",
        expectations=TestBriefExpectations(
            expected_niche="fashion",
            target_count=6,
            target_male_count=3,
            target_female_count=3,
            preferred_follower_min=50000,
            preferred_follower_max=300000,
            min_niche_alignment=0.5,
        )
    ),
    
    TestBrief(
        name="micro_influencer_focus",
        category="edge_case",
        description="Micro-influencer specific requirement",
        query="""Looking for micro-influencers (10K-100K followers) for local
        restaurant promotion in Madrid. Food and lifestyle content creators.
        Prefer high engagement over follower count. Authentic food lovers.
        Local Madrid creators who know the food scene.""",
        expectations=TestBriefExpectations(
            expected_niche="food",
            preferred_follower_min=10000,
            preferred_follower_max=100000,
            expected_topics=["food", "restaurant", "Madrid"],
            min_niche_alignment=0.5,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="multi_niche_fitness_nutrition",
        category="edge_case",
        description="Multi-niche requirement (fitness + nutrition)",
        query="""Sports nutrition brand campaign - need influencers who combine
        fitness AND nutrition content. Workout routines plus healthy eating.
        Athletes who care about what they eat. Gym and kitchen content.
        Not just gym bros flexing, need actual nutrition knowledge.""",
        expectations=TestBriefExpectations(
            expected_niche="fitness",
            expected_topics=["fitness", "nutrition", "workout", "healthy eating"],
            min_niche_alignment=0.5,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="very_specific_niche_yoga",
        category="edge_case",
        description="Very specific niche (yoga)",
        query="""Yoga mat brand looking for 5 yoga instructors and practitioners.
        Morning routine content, meditation, mindfulness. 
        Calm, peaceful aesthetic. Wellness focused.
        No high-intensity fitness content - strictly yoga/meditation.""",
        expectations=TestBriefExpectations(
            expected_niche="yoga",
            expected_topics=["yoga", "meditation", "mindfulness", "wellness"],
            expected_tones=["calm", "peaceful"],
            excluded_niches=["crossfit", "fitness"],
            min_niche_alignment=0.6,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="exclude_multiple_niches",
        category="edge_case",
        description="Multiple niche exclusions",
        query="""Luxury watch brand campaign. Need 5 lifestyle influencers
        who appreciate fine craftsmanship and luxury goods.
        NO fitness influencers, NO gaming content, NO comedy accounts.
        Sophisticated, elegant content style. Travel, fashion, lifestyle.""",
        expectations=TestBriefExpectations(
            expected_niche="luxury",
            expected_topics=["luxury", "lifestyle", "fashion", "travel"],
            expected_tones=["sophisticated", "elegant"],
            excluded_niches=["fitness", "gaming", "comedy"],
            must_not_have_niches=["fitness", "gaming", "comedy"],
            min_niche_alignment=0.5,
            target_count=5,
        )
    ),
    
    TestBrief(
        name="high_engagement_priority",
        category="edge_case",
        description="High engagement explicitly prioritized",
        query="""Beauty brand campaign prioritizing engagement over follower count.
        Need 5 beauty influencers with MINIMUM 5% engagement rate.
        Makeup tutorials, skincare routines, product reviews.
        Smaller accounts with loyal audiences preferred over big accounts with low engagement.""",
        expectations=TestBriefExpectations(
            expected_niche="beauty",
            expected_topics=["makeup", "skincare", "beauty"],
            min_niche_alignment=0.6,
            target_count=5,
        )
    ),
]


# ============================================================
# ALL BRIEFS COMBINED
# ============================================================

ALL_TEST_BRIEFS: List[TestBrief] = (
    NICHE_PRECISION_BRIEFS +
    BRAND_MATCHING_BRIEFS +
    CREATIVE_FIT_BRIEFS +
    EDGE_CASE_BRIEFS
)


def get_briefs_by_category(category: str) -> List[TestBrief]:
    """Get all briefs in a specific category."""
    return [b for b in ALL_TEST_BRIEFS if b.category == category]


def get_brief_by_name(name: str) -> Optional[TestBrief]:
    """Get a specific brief by name."""
    for brief in ALL_TEST_BRIEFS:
        if brief.name == name:
            return brief
    return None


# Quick reference dict
BRIEFS_BY_NAME: Dict[str, TestBrief] = {b.name: b for b in ALL_TEST_BRIEFS}
