"""
Brand Intelligence Service

Provides brand competitor detection, ambassador tracking, and niche relevance scoring.
Used by the ranking service to:
1. Detect competitor conflicts (Nike campaign shouldn't show Adidas ambassadors)
2. Track brand saturation (flag existing ambassadors as "too obvious")
3. Calculate niche relevance (padel campaign should show padel players, not football stars)
"""

import yaml
from pathlib import Path
from typing import Optional, List, Set, Dict, Any, Tuple
from dataclasses import dataclass, field
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


@dataclass
class BrandInfo:
    """Structured brand information."""
    key: str
    name: str
    category: str
    instagram_handles: List[str]
    competitors: List[str]
    ambassadors: List[Dict[str, Any]]
    conflict_severity: str  # high/medium/low


@dataclass
class NicheInfo:
    """Structured niche information."""
    key: str
    keywords: List[str]
    aliases: List[str]
    related_niches: List[str]
    conflicting_niches: List[str]
    parent_category: str


@dataclass
class BrandConflictResult:
    """Result of brand conflict check."""
    has_conflict: bool = False
    conflict_type: Optional[str] = None  # "competitor_ambassador", "competitor_mention", None
    conflict_brands: List[str] = field(default_factory=list)
    severity: Optional[str] = None  # "high", "medium", "low"
    penalty_score: float = 0.5  # Score to use (lower = worse)
    details: str = ""


@dataclass
class SaturationResult:
    """Result of brand saturation check."""
    is_saturated: bool = False
    relationship: Optional[str] = None  # "lifetime_deal", "ambassador", "sponsored"
    since: Optional[str] = None
    warning_message: Optional[str] = None
    penalty_score: float = 0.5


@dataclass
class NicheRelevanceResult:
    """Result of niche relevance check."""
    score: float = 0.5
    match_type: str = "neutral"  # "exact", "related", "conflicting", "neutral"
    matched_keywords: List[str] = field(default_factory=list)
    is_celebrity_mismatch: bool = False
    details: str = ""


class BrandIntelligenceService:
    """
    Service for brand competitor detection, ambassador tracking, and niche relevance scoring.

    Usage:
        service = BrandIntelligenceService()

        # Check for competitor conflicts
        conflict = service.check_brand_conflict("leomessi", ["adidas"], "nike")

        # Check if influencer is already this brand's ambassador
        saturation = service.check_brand_saturation("leomessi", "adidas")

        # Check niche relevance
        relevance = service.check_niche_relevance(
            influencer_interests=["football", "sports"],
            campaign_niche="padel",
            follower_count=500_000_000
        )
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize service and load data files."""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"

        self.data_dir = data_dir
        self._brand_data: Dict[str, Any] = {}
        self._niche_data: Dict[str, Any] = {}

        # Indexes for fast lookups
        self._handle_to_brand: Dict[str, str] = {}
        self._username_to_brands: Dict[str, List[Dict[str, Any]]] = {}
        self._niche_keywords: Dict[str, str] = {}  # keyword -> niche_key

        # Load data
        self._load_brand_data()
        self._load_niche_data()
        self._build_indexes()

    def _load_brand_data(self) -> None:
        """Load brand intelligence YAML file."""
        brand_file = self.data_dir / "brand_intelligence.yaml"
        if brand_file.exists():
            with open(brand_file, 'r', encoding='utf-8') as f:
                self._brand_data = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(self._brand_data.get('brands', {}))} brands")
        else:
            logger.warning(f"Brand intelligence file not found: {brand_file}")

    def _load_niche_data(self) -> None:
        """Load niche taxonomy YAML file."""
        niche_file = self.data_dir / "niche_taxonomy.yaml"
        if niche_file.exists():
            with open(niche_file, 'r', encoding='utf-8') as f:
                self._niche_data = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(self._niche_data.get('niches', {}))} niches")
        else:
            logger.warning(f"Niche taxonomy file not found: {niche_file}")

    def _build_indexes(self) -> None:
        """Build lookup indexes for fast access."""
        # Index: Instagram handle -> brand key
        for brand_key, brand_data in self._brand_data.get('brands', {}).items():
            for handle in brand_data.get('instagram_handles', []):
                self._handle_to_brand[handle.lower()] = brand_key

        # Index: Ambassador username -> list of brand relationships
        for brand_key, brand_data in self._brand_data.get('brands', {}).items():
            for ambassador in brand_data.get('ambassadors', []):
                username = ambassador.get('username', '').lower()
                if username:
                    if username not in self._username_to_brands:
                        self._username_to_brands[username] = []
                    self._username_to_brands[username].append({
                        'brand_key': brand_key,
                        'brand_name': brand_data.get('name', brand_key),
                        **ambassador
                    })

        # Index: Niche keyword -> niche key
        for niche_key, niche_data in self._niche_data.get('niches', {}).items():
            for keyword in niche_data.get('keywords', []):
                self._niche_keywords[keyword.lower()] = niche_key

    # ==================== BRAND METHODS ====================

    def get_brand(self, brand_key_or_handle: str) -> Optional[BrandInfo]:
        """
        Get brand info by key or Instagram handle.

        Args:
            brand_key_or_handle: Brand key (e.g., "adidas") or handle (e.g., "@nike")

        Returns:
            BrandInfo or None if not found
        """
        key = brand_key_or_handle.lower().lstrip('@')

        # Try direct key lookup
        brands = self._brand_data.get('brands', {})
        if key in brands:
            return self._to_brand_info(key, brands[key])

        # Try handle lookup
        brand_key = self._handle_to_brand.get(key)
        if brand_key and brand_key in brands:
            return self._to_brand_info(brand_key, brands[brand_key])

        return None

    def get_competitors(self, brand_key_or_handle: str) -> Set[str]:
        """Get all competitor brand keys for a brand."""
        brand = self.get_brand(brand_key_or_handle)
        if brand:
            return set(brand.competitors)
        return set()

    def get_competitor_handles(self, brand_key_or_handle: str) -> Set[str]:
        """Get all Instagram handles of competitor brands."""
        competitors = self.get_competitors(brand_key_or_handle)
        handles = set()

        for comp_key in competitors:
            brand_data = self._brand_data.get('brands', {}).get(comp_key, {})
            handles.update(h.lower() for h in brand_data.get('instagram_handles', []))

        return handles

    def get_ambassador_brands(self, username: str) -> List[Dict[str, Any]]:
        """
        Get all brands that have this user as a known ambassador.

        Returns list of dicts with brand info and relationship details.
        """
        return self._username_to_brands.get(username.lower(), [])

    def check_brand_conflict(
        self,
        influencer_username: str,
        influencer_brand_mentions: List[str],
        target_brand: str
    ) -> BrandConflictResult:
        """
        Check for brand conflicts between influencer and target brand.

        This detects:
        1. Competitor ambassador conflicts (Messi is Adidas ambassador, bad for Nike)
        2. Competitor brand mentions (has mentioned Nike, bad for Adidas)

        Args:
            influencer_username: Influencer's Instagram username
            influencer_brand_mentions: List of brands the influencer has mentioned
            target_brand: Target brand key or handle for the campaign

        Returns:
            BrandConflictResult with conflict details and penalty score
        """
        result = BrandConflictResult()

        # Get target brand info
        target_info = self.get_brand(target_brand)
        if not target_info:
            # Unknown brand - no penalty
            return result

        competitor_keys = set(target_info.competitors)
        competitor_handles = self.get_competitor_handles(target_brand)

        # Check 1: Is influencer a known ambassador for a competitor?
        ambassador_brands = self.get_ambassador_brands(influencer_username)
        ambassador_brand_keys = {b['brand_key'] for b in ambassador_brands}
        ambassador_conflicts = ambassador_brand_keys & competitor_keys

        if ambassador_conflicts:
            conflict_names = [
                self._brand_data.get('brands', {}).get(k, {}).get('name', k)
                for k in ambassador_conflicts
            ]
            result.has_conflict = True
            result.conflict_type = "competitor_ambassador"
            result.conflict_brands = list(ambassador_conflicts)
            result.severity = "high"
            result.penalty_score = 0.05  # Heavy penalty - nearly excluded
            result.details = f"Known ambassador for competitor(s): {', '.join(conflict_names)}"
            return result

        # Check 2: Has influencer mentioned competitor brands?
        mentions_normalized = [m.lower().lstrip('@') for m in influencer_brand_mentions]

        # Check against competitor handles
        mention_conflicts = set(mentions_normalized) & competitor_handles

        # Also check against competitor brand keys
        mention_conflicts.update(set(mentions_normalized) & competitor_keys)

        if mention_conflicts:
            result.has_conflict = True
            result.conflict_type = "competitor_mention"
            result.conflict_brands = list(mention_conflicts)
            result.severity = target_info.conflict_severity

            # Penalty based on severity
            if target_info.conflict_severity == "high":
                result.penalty_score = 0.25  # 75% penalty
            elif target_info.conflict_severity == "medium":
                result.penalty_score = 0.35  # 65% penalty
            else:
                result.penalty_score = 0.45  # 55% penalty

            result.details = f"Has mentioned competitor brand(s): {', '.join(mention_conflicts)}"

        return result

    def check_brand_saturation(
        self,
        influencer_username: str,
        target_brand: str
    ) -> SaturationResult:
        """
        Check if influencer is already an ambassador for the target brand.

        This is for saturation warnings - when the client might want fresh faces
        instead of their existing, obvious ambassadors.

        Args:
            influencer_username: Influencer's Instagram username
            target_brand: Target brand key or handle

        Returns:
            SaturationResult with saturation details
        """
        result = SaturationResult()

        # Normalize target brand to key
        target_info = self.get_brand(target_brand)
        if not target_info:
            return result

        # Check if influencer is this brand's ambassador
        ambassador_brands = self.get_ambassador_brands(influencer_username)

        for brand_rel in ambassador_brands:
            if brand_rel['brand_key'] == target_info.key:
                result.is_saturated = True
                result.relationship = brand_rel.get('relationship', 'ambassador')
                result.since = brand_rel.get('since')

                # Build warning message
                since_str = f" since {result.since}" if result.since else ""
                result.warning_message = (
                    f"Already {target_info.name} {result.relationship}{since_str}"
                )

                # Saturation penalty (less severe than competitor conflict)
                if result.relationship == "lifetime_deal":
                    result.penalty_score = 0.35  # Too obvious
                elif result.relationship == "ambassador":
                    result.penalty_score = 0.40
                else:
                    result.penalty_score = 0.45  # Sponsored is less "saturated"

                break

        return result

    # ==================== NICHE METHODS ====================

    def get_niche(self, niche_key: str) -> Optional[NicheInfo]:
        """Get niche info by key."""
        niches = self._niche_data.get('niches', {})
        if niche_key.lower() in niches:
            niche_data = niches[niche_key.lower()]
            return NicheInfo(
                key=niche_key.lower(),
                keywords=niche_data.get('keywords', []),
                aliases=niche_data.get('aliases', []),
                related_niches=niche_data.get('related_niches', []),
                conflicting_niches=niche_data.get('conflicting_niches', []),
                parent_category=niche_data.get('parent_category', '')
            )
        return None

    def get_niche_relationships(self, niche_key: str) -> Dict[str, List[str]]:
        """
        Get related and conflicting niches for a given niche.

        Args:
            niche_key: The niche to look up (e.g., "padel")

        Returns:
            Dict with "related" and "conflicting" lists, or empty lists if niche not found
        """
        niche = self.get_niche(niche_key)
        if niche:
            return {
                "related": niche.related_niches,
                "conflicting": niche.conflicting_niches
            }
        return {"related": [], "conflicting": []}

    def get_all_allowed_niches(self, campaign_niche: str) -> Set[str]:
        """
        Get all niches that are allowed for a campaign (exact + related).

        Args:
            campaign_niche: The primary niche for the campaign (e.g., "padel")

        Returns:
            Set of allowed niche keys including the campaign niche and related niches
        """
        allowed = {campaign_niche.lower()}
        relationships = self.get_niche_relationships(campaign_niche)
        allowed.update(r.lower() for r in relationships["related"])
        return allowed

    def get_all_excluded_niches(
        self,
        campaign_niche: str,
        explicit_excludes: Optional[List[str]] = None
    ) -> Set[str]:
        """
        Get all niches that should be excluded for a campaign.

        Combines:
        1. Taxonomy-defined conflicting niches for the campaign niche
        2. User-specified explicit exclusions from the search query

        Args:
            campaign_niche: The primary niche for the campaign (e.g., "padel")
            explicit_excludes: Additional niches to exclude (from user query)

        Returns:
            Set of excluded niche keys
        """
        excluded = set()

        # Add taxonomy-defined conflicts
        relationships = self.get_niche_relationships(campaign_niche)
        excluded.update(c.lower() for c in relationships["conflicting"])

        # Add user-specified excludes
        if explicit_excludes:
            excluded.update(e.lower() for e in explicit_excludes)

        return excluded

    def get_all_niche_keys(self) -> List[str]:
        """Get all available niche keys from the taxonomy."""
        return list(self._niche_data.get('niches', {}).keys())

    def detect_influencer_niche(
        self,
        interests: List[str],
        bio: str = ""
    ) -> Tuple[Optional[str], List[str]]:
        """
        Detect an influencer's primary niche from their interests and bio.

        Returns:
            Tuple of (primary_niche_key, list of matched keywords)
        """
        searchable = bio.lower() + " " + " ".join(str(i).lower() for i in interests)

        niche_matches: Dict[str, List[str]] = {}

        for keyword, niche_key in self._niche_keywords.items():
            if keyword in searchable:
                if niche_key not in niche_matches:
                    niche_matches[niche_key] = []
                niche_matches[niche_key].append(keyword)

        if not niche_matches:
            return None, []

        # Return niche with most keyword matches
        primary_niche = max(niche_matches.keys(), key=lambda k: len(niche_matches[k]))
        return primary_niche, niche_matches[primary_niche]

    def detect_influencer_niche_enhanced(
        self,
        interests: List[str],
        bio: str = "",
        post_content: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], List[str], float]:
        """
        Enhanced niche detection using post content from Apify scraping.

        Uses hashtags and caption keywords from actual posts for more accurate
        niche detection compared to just bio/interests.

        Args:
            interests: Coarse interest categories from PrimeTag
            bio: Profile bio text
            post_content: Aggregated post content from Apify scraping
                {
                    "top_hashtags": {"padel": 45, "fitness": 23},
                    "caption_keywords": {"tournament": 12, "training": 5},
                    "scrape_status": "complete"
                }

        Returns:
            Tuple of (primary_niche_key, matched_keywords, confidence_score)
        """
        # Build searchable text from base data
        searchable = bio.lower() + " " + " ".join(str(i).lower() for i in interests)

        # Weight post content heavily if available and complete
        has_post_data = (
            post_content
            and post_content.get("scrape_status") == "complete"
            and post_content.get("top_hashtags")
        )

        if has_post_data:
            hashtags = post_content.get("top_hashtags", {})
            keywords = post_content.get("caption_keywords", {})

            # Add hashtags to searchable text (weighted by frequency)
            for tag, count in hashtags.items():
                # Repeat high-frequency hashtags for weight
                repeats = min(count // 3, 15)  # Max 15 repeats
                searchable += f" {tag}" * repeats

            # Add caption keywords (weighted)
            for word, count in keywords.items():
                repeats = min(count // 2, 10)  # Max 10 repeats
                searchable += f" {word}" * repeats

        # Match against niche taxonomy
        niche_scores: Dict[str, Tuple[float, List[str]]] = {}

        for niche_key, niche_data in self._niche_data.get('niches', {}).items():
            niche_keywords = niche_data.get('keywords', [])
            matched = [kw for kw in niche_keywords if kw.lower() in searchable]

            if matched:
                # Score based on number of matches relative to total keywords
                base_score = len(matched) / max(len(niche_keywords), 1)

                # Boost score if we have post data (more reliable signal)
                if has_post_data:
                    # Check how many hashtags match this niche's keywords
                    hashtag_matches = sum(
                        1 for tag in post_content.get("top_hashtags", {}).keys()
                        if any(kw.lower() in tag.lower() for kw in niche_keywords)
                    )
                    hashtag_boost = min(hashtag_matches * 0.05, 0.2)
                    base_score = min(base_score + hashtag_boost, 1.0)

                niche_scores[niche_key] = (base_score, matched)

        if not niche_scores:
            return None, [], 0.0

        # Return highest scoring niche
        best_niche = max(niche_scores.keys(), key=lambda k: niche_scores[k][0])
        score, matched = niche_scores[best_niche]

        # Confidence is higher if we have post data
        confidence = score * (1.3 if has_post_data else 1.0)
        confidence = min(confidence, 1.0)

        return best_niche, matched, confidence

    def check_niche_relevance(
        self,
        influencer_interests: List[str],
        influencer_bio: str,
        campaign_niche: str,
        follower_count: int = 0,
        post_content: Optional[Dict[str, Any]] = None
    ) -> NicheRelevanceResult:
        """
        Check how relevant an influencer's niche is to the campaign niche.

        This solves the Messi/Padel problem: Messi (football) should score low
        for a padel campaign, even if he's famous.

        When post_content is available (from Apify scraping), uses enhanced
        detection based on actual post hashtags and captions for more accuracy.

        Args:
            influencer_interests: List of influencer's interests/categories
            influencer_bio: Influencer's bio text
            campaign_niche: Target niche for the campaign (e.g., "padel")
            follower_count: Influencer's follower count (for celebrity penalty)
            post_content: Optional aggregated post content from Apify scraping

        Returns:
            NicheRelevanceResult with score and match details
        """
        result = NicheRelevanceResult()
        rules = self._niche_data.get('rules', {})

        # Get campaign niche info
        campaign_niche_info = self.get_niche(campaign_niche)
        if not campaign_niche_info:
            # Unknown campaign niche - return neutral
            result.score = rules.get('neutral_score', 0.5)
            result.match_type = "neutral"
            result.details = f"Unknown campaign niche: {campaign_niche}"
            return result

        # Use enhanced detection if post content is available
        has_post_data = (
            post_content
            and post_content.get("scrape_status") == "complete"
            and post_content.get("top_hashtags")
        )

        if has_post_data:
            influencer_niche, matched_keywords, confidence = self.detect_influencer_niche_enhanced(
                influencer_interests, influencer_bio, post_content
            )
        else:
            influencer_niche, matched_keywords = self.detect_influencer_niche(
                influencer_interests, influencer_bio
            )
            confidence = 0.5 if influencer_niche else 0.0

        result.matched_keywords = matched_keywords

        # Check for exact match or alias (aliases scored identically to exact)
        is_alias = influencer_niche and influencer_niche in campaign_niche_info.aliases
        if influencer_niche == campaign_niche_info.key or is_alias:
            # Higher score with post data (more confident)
            base_score = rules.get('exact_match_score', 0.95)
            if has_post_data and confidence > 0.5:
                result.score = min(base_score + 0.03, 1.0)  # Slight boost for post-backed match
            else:
                result.score = base_score
            result.match_type = "exact"
            result.details = f"{'Alias' if is_alias else 'Exact'} niche match: {influencer_niche}"
            if has_post_data:
                result.details += " (confirmed by post content)"
            return result

        # Check for related niche
        if influencer_niche and influencer_niche in campaign_niche_info.related_niches:
            result.score = rules.get('related_niche_score', 0.70)
            result.match_type = "related"
            result.details = f"Related niche: {influencer_niche} is related to {campaign_niche}"
            return result

        # Check for conflicting niche
        if influencer_niche and influencer_niche in campaign_niche_info.conflicting_niches:
            result.score = rules.get('conflicting_niche_penalty', 0.20)
            result.match_type = "conflicting"
            result.details = f"Conflicting niche: {influencer_niche} conflicts with {campaign_niche}"

            # Extra penalty for large celebrities in wrong niche
            celebrity_threshold = rules.get('celebrity_threshold', 5_000_000)
            if follower_count > celebrity_threshold:
                result.is_celebrity_mismatch = True
                result.score = rules.get('celebrity_mismatch_penalty', 0.15)
                result.details += f" (celebrity with {follower_count:,} followers)"

            # Additional confidence in conflict if we have post data
            if has_post_data:
                result.details += " - conflict confirmed by post analysis"

            return result

        # Check if influencer has ANY matching keywords for campaign niche
        # Include post content in searchable text if available
        campaign_keywords = campaign_niche_info.keywords
        searchable = influencer_bio.lower() + " " + " ".join(
            str(i).lower() for i in influencer_interests
        )

        # Add post hashtags to searchable if available
        if has_post_data:
            hashtags = post_content.get("top_hashtags", {})
            searchable += " " + " ".join(hashtags.keys())

        direct_matches = [kw for kw in campaign_keywords if kw.lower() in searchable]
        if direct_matches:
            # Some keyword overlap - partial match
            match_ratio = len(direct_matches) / len(campaign_keywords)
            result.score = 0.5 + (match_ratio * 0.3)  # 0.5 - 0.8
            result.match_type = "partial"
            result.matched_keywords = direct_matches
            result.details = f"Partial match with {len(direct_matches)} campaign keywords"
            return result

        # No clear niche connection
        result.score = rules.get('neutral_score', 0.5)
        result.match_type = "neutral"
        result.details = "No clear niche connection"

        # Penalty for large celebrities with no niche match
        celebrity_threshold = rules.get('celebrity_threshold', 5_000_000)
        if follower_count > celebrity_threshold:
            result.is_celebrity_mismatch = True
            result.score = 0.30  # Generic celebrity penalty
            result.details = f"Generic celebrity ({follower_count:,} followers) with no niche match"

        return result

    # ==================== COMBINED SCORING ====================

    def calculate_brand_affinity_score(
        self,
        influencer_username: str,
        influencer_brand_mentions: List[str],
        target_brand: Optional[str],
        overlap_data: Optional[Dict[str, float]] = None
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """
        Calculate comprehensive brand affinity score.

        Combines:
        - Competitor conflict detection
        - Brand saturation checking
        - Audience overlap data (if available)
        - Prior brand mention boost

        Args:
            influencer_username: Influencer's username
            influencer_brand_mentions: Brands the influencer has mentioned
            target_brand: Target brand for campaign
            overlap_data: Optional audience overlap data {brand: overlap_pct}

        Returns:
            Tuple of (score, warning_type, warning_message)
            - score: 0.0-1.0 (lower = worse fit)
            - warning_type: "competitor_conflict", "saturation", or None
            - warning_message: Human-readable warning or None
        """
        if not target_brand:
            return 0.5, None, None

        target_brand = target_brand.lower().lstrip('@')

        # Check for competitor conflicts (most severe)
        conflict = self.check_brand_conflict(
            influencer_username,
            influencer_brand_mentions,
            target_brand
        )

        if conflict.has_conflict:
            return (
                conflict.penalty_score,
                "competitor_conflict",
                conflict.details
            )

        # Check for saturation (less severe)
        saturation = self.check_brand_saturation(influencer_username, target_brand)

        if saturation.is_saturated:
            return (
                saturation.penalty_score,
                "saturation",
                saturation.warning_message
            )

        # No conflicts - check for positive signals

        # If we have overlap data, use it
        if overlap_data:
            overlap_pct = overlap_data.get(target_brand, 0)
            # Normalize: 0-50% overlap maps to 0.5-1.0 score
            return 0.5 + min(overlap_pct / 0.50, 0.5), None, None

        # Check if influencer has mentioned THIS brand before (positive signal)
        mentions_normalized = [m.lower().lstrip('@') for m in influencer_brand_mentions]
        target_info = self.get_brand(target_brand)

        if target_info:
            target_handles = set(h.lower() for h in target_info.instagram_handles)
            target_handles.add(target_info.key)

            if set(mentions_normalized) & target_handles:
                return 0.75, None, None  # Boost for prior brand relationship

        # Neutral - no conflicts, no positive signals
        return 0.5, None, None

    # ==================== HELPERS ====================

    def _to_brand_info(self, key: str, data: Dict) -> BrandInfo:
        """Convert dict to BrandInfo dataclass."""
        return BrandInfo(
            key=key,
            name=data.get('name', key),
            category=data.get('category', 'unknown'),
            instagram_handles=data.get('instagram_handles', []),
            competitors=data.get('competitors', []),
            ambassadors=data.get('ambassadors', []),
            conflict_severity=data.get('conflict_severity', 'medium')
        )


# Singleton instance
_service_instance: Optional[BrandIntelligenceService] = None


def get_brand_intelligence_service() -> BrandIntelligenceService:
    """Get or create the brand intelligence service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = BrandIntelligenceService()
    return _service_instance


def reload_brand_intelligence_service() -> BrandIntelligenceService:
    """Force reload the brand intelligence service (useful after data updates)."""
    global _service_instance
    _service_instance = BrandIntelligenceService()
    return _service_instance
