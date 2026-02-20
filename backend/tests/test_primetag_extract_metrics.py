"""
Unit tests for PrimeTagClient.extract_metrics() covering all 5 business requirements:

  BR1 — % audience in Spain (>= 60 threshold)
  BR2 — % women / % men  (genders extracted, sum ≈ 100)
  BR3 — % ages by bands   (female + male per label, null-safe)
  BR4 — Credibility        (Instagram only; null for other platforms)
  BR5 — Engagement rate    (present, decimal units, consistently mapped)

Also covers:
  - extract_encrypted_username() parsing
  - Spain name variants: "Spain", "España", "Espana"
  - Edge cases: missing data, empty lists, None values
"""
import pytest

from app.schemas.primetag import AudienceData, AudienceDataSection, MediaKit
from app.services.primetag_client import PrimeTagClient

from tests.fixtures.primetag_fixtures import (
    make_media_kit,
    make_audience_section,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def client() -> PrimeTagClient:
    """Instantiate PrimeTagClient without loading settings (pure extraction)."""
    obj = object.__new__(PrimeTagClient)
    return obj


# ---------------------------------------------------------------------------
# BR1 — Spain % Extraction
# ---------------------------------------------------------------------------

class TestSpainExtraction:

    def test_spain_by_english_name(self):
        kit = make_media_kit(location_by_country=[
            {"name": "Spain", "percentage": 65.0},
            {"name": "Mexico", "percentage": 12.0},
        ])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_geography"]["ES"] == 65.0

    def test_espana_accent_variant_mapped_to_es(self):
        """PrimeTag sometimes returns the Spanish-language spelling."""
        kit = make_media_kit(location_by_country=[
            {"name": "España", "percentage": 72.0},
            {"name": "Mexico", "percentage": 10.0},
        ])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_geography"].get("ES") == 72.0, (
            "España must map to ISO 'ES' in COUNTRY_NAME_TO_ISO"
        )

    def test_espana_no_accent_variant_mapped_to_es(self):
        """Accent-stripped variant 'Espana'."""
        kit = make_media_kit(location_by_country=[
            {"name": "Espana", "percentage": 61.0},
        ])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_geography"].get("ES") == 61.0

    def test_spain_absent_returns_zero_in_geography(self):
        """If Spain is not in the list, ES key should not appear (or be 0)."""
        kit = make_media_kit(location_by_country=[
            {"name": "France", "percentage": 80.0},
            {"name": "Germany", "percentage": 15.0},
        ])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_geography"].get("ES", 0) == 0

    def test_spain_uses_value_key_when_percentage_absent(self):
        """Some PrimeTag responses use 'value' instead of 'percentage'."""
        kit = make_media_kit(location_by_country=[
            {"name": "Spain", "value": 63.5},
        ])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_geography"]["ES"] == 63.5

    def test_empty_location_list(self):
        kit = make_media_kit(location_by_country=[])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_geography"] == {}

    def test_none_location(self):
        section = AudienceDataSection(location_by_country=None, genders=None, average_age=None)
        kit = make_media_kit(audience_data=AudienceData(followers=section))
        metrics = client().extract_metrics(kit)
        assert metrics["audience_geography"] == {}

    def test_percentage_zero_country_excluded(self):
        """Countries with 0% should not be stored (falsy check in code)."""
        kit = make_media_kit(location_by_country=[
            {"name": "Spain", "percentage": 0},
            {"name": "France", "percentage": 10.0},
        ])
        metrics = client().extract_metrics(kit)
        # Spain with 0% is excluded by the `if percentage` guard
        assert metrics["audience_geography"].get("ES", 0) == 0


# ---------------------------------------------------------------------------
# BR2 — Gender Extraction
# ---------------------------------------------------------------------------

class TestGenderExtraction:

    def test_genders_extracted(self):
        kit = make_media_kit(genders={"female": 55.2, "male": 44.8})
        metrics = client().extract_metrics(kit)
        assert metrics["audience_genders"] == {"female": 55.2, "male": 44.8}

    def test_genders_sum_approximately_100(self):
        kit = make_media_kit(genders={"female": 55.2, "male": 44.8})
        metrics = client().extract_metrics(kit)
        total = sum(metrics["audience_genders"].values())
        assert abs(total - 100.0) < 1.0, f"Gender sum {total} is not close to 100"

    def test_genders_none_returns_empty_dict(self):
        kit = make_media_kit(genders=None)
        # Explicitly set genders=None in the section
        section = AudienceDataSection(genders=None, average_age=[], location_by_country=[])
        kit2 = make_media_kit(audience_data=AudienceData(followers=section))
        metrics = client().extract_metrics(kit2)
        assert metrics["audience_genders"] == {}

    def test_genders_missing_audience_data(self):
        kit = MediaKit(username="nobody", platform_type=2, audience_data=None)
        metrics = client().extract_metrics(kit)
        assert metrics["audience_genders"] == {}


# ---------------------------------------------------------------------------
# BR3 — Age Band Totals (female + male per label)
# ---------------------------------------------------------------------------

class TestAgeBandExtraction:

    def test_age_bands_computed_as_female_plus_male(self):
        kit = make_media_kit(average_age=[
            {"label": "18-24", "female": 18.5, "male": 16.3},
            {"label": "25-34", "female": 22.0, "male": 20.1},
        ])
        metrics = client().extract_metrics(kit)
        dist = metrics["audience_age_distribution"]
        assert abs(dist["18-24"] - (18.5 + 16.3)) < 0.001
        assert abs(dist["25-34"] - (22.0 + 20.1)) < 0.001

    def test_age_null_female_handled(self):
        """None female value should be treated as 0, not raise TypeError."""
        kit = make_media_kit(average_age=[
            {"label": "55+", "female": None, "male": 1.2},
        ])
        metrics = client().extract_metrics(kit)
        assert abs(metrics["audience_age_distribution"]["55+"] - 1.2) < 0.001

    def test_age_null_male_handled(self):
        kit = make_media_kit(average_age=[
            {"label": "35-44", "female": 8.5, "male": None},
        ])
        metrics = client().extract_metrics(kit)
        assert abs(metrics["audience_age_distribution"]["35-44"] - 8.5) < 0.001

    def test_age_both_null_gives_zero(self):
        kit = make_media_kit(average_age=[
            {"label": "45-54", "female": None, "male": None},
        ])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_age_distribution"]["45-54"] == 0.0

    def test_age_missing_label_skipped(self):
        """Items without a 'label' key should be silently skipped."""
        kit = make_media_kit(average_age=[
            {"female": 10.0, "male": 8.0},          # no label
            {"label": "18-24", "female": 18.5, "male": 16.3},
        ])
        metrics = client().extract_metrics(kit)
        assert list(metrics["audience_age_distribution"].keys()) == ["18-24"]

    def test_age_empty_list(self):
        kit = make_media_kit(average_age=[])
        metrics = client().extract_metrics(kit)
        assert metrics["audience_age_distribution"] == {}

    def test_age_none_list(self):
        section = AudienceDataSection(average_age=None, genders=None, location_by_country=[])
        kit = make_media_kit(audience_data=AudienceData(followers=section))
        metrics = client().extract_metrics(kit)
        assert metrics["audience_age_distribution"] == {}

    def test_age_band_totals_sum_roughly_100(self):
        """Full default fixture: all bands should sum close to 100."""
        kit = make_media_kit()
        metrics = client().extract_metrics(kit)
        total = sum(metrics["audience_age_distribution"].values())
        assert 95.0 <= total <= 105.0, f"Age band total {total} too far from 100"


# ---------------------------------------------------------------------------
# BR4 — Credibility (Instagram only)
# ---------------------------------------------------------------------------

class TestCredibilityExtraction:

    def test_credibility_present_for_instagram(self):
        kit = make_media_kit(platform_type=2, credibility=82.0)
        metrics = client().extract_metrics(kit)
        assert metrics["credibility_score"] == 82.0

    def test_credibility_null_for_tiktok(self):
        """platform_type=6 (TikTok) must return credibility_score=None."""
        kit = make_media_kit(platform_type=6, credibility=75.0)
        metrics = client().extract_metrics(kit)
        assert metrics["credibility_score"] is None, (
            "Credibility is only meaningful for Instagram (platform_type=2)"
        )

    def test_credibility_null_when_field_missing(self):
        """audience_credibility_percentage absent → credibility_score=None."""
        section = AudienceDataSection(
            audience_credibility_percentage=None,
            genders=None, average_age=[], location_by_country=[]
        )
        kit = make_media_kit(platform_type=2, audience_data=AudienceData(followers=section))
        metrics = client().extract_metrics(kit)
        assert metrics["credibility_score"] is None

    def test_credibility_null_when_no_audience_data(self):
        kit = MediaKit(username="nobody", platform_type=2, audience_data=None)
        metrics = client().extract_metrics(kit)
        assert metrics["credibility_score"] is None


# ---------------------------------------------------------------------------
# BR5 — Engagement Rate
# ---------------------------------------------------------------------------

class TestEngagementRate:

    def test_er_mapped_to_output_field(self):
        kit = make_media_kit(avg_engagement_rate=0.034)
        metrics = client().extract_metrics(kit)
        assert metrics["engagement_rate"] == 0.034

    def test_er_present_and_is_decimal(self):
        """ER must be < 1.0 (decimal, not percentage like 3.4)."""
        kit = make_media_kit(avg_engagement_rate=0.034)
        metrics = client().extract_metrics(kit)
        assert metrics["engagement_rate"] < 1.0, (
            "ER should be a decimal fraction (e.g. 0.034), not a percentage (3.4)"
        )

    def test_er_zero_is_present_not_none(self):
        kit = make_media_kit(avg_engagement_rate=0.0)
        metrics = client().extract_metrics(kit)
        assert "engagement_rate" in metrics
        assert metrics["engagement_rate"] == 0.0


# ---------------------------------------------------------------------------
# extract_encrypted_username
# ---------------------------------------------------------------------------

class TestExtractEncryptedUsername:

    def test_standard_url(self):
        url = "https://mediakit.primetag.com/instagram/Z0FBQUFBQm1PckVx"
        assert PrimeTagClient.extract_encrypted_username(url) == "Z0FBQUFBQm1PckVx"

    def test_url_with_trailing_slash(self):
        url = "https://mediakit.primetag.com/instagram/Z0FBQUFBQm1/"
        assert PrimeTagClient.extract_encrypted_username(url) == "Z0FBQUFBQm1"

    def test_none_url_returns_none(self):
        assert PrimeTagClient.extract_encrypted_username(None) is None

    def test_empty_string_returns_none(self):
        assert PrimeTagClient.extract_encrypted_username("") is None

    def test_url_single_segment_returns_none(self):
        # Only one path segment → can't extract platform + token
        assert PrimeTagClient.extract_encrypted_username("https://mediakit.primetag.com/Z0FB") is None


# ---------------------------------------------------------------------------
# Worked end-to-end example (Spain >= 60 pass / fail)
# ---------------------------------------------------------------------------

class TestWorkedExample:
    """
    Fully worked example per business requirements.
    Demonstrates that a 65%-Spain influencer passes and a 59%-Spain influencer fails.
    """

    def _build_metrics(self, spain_pct: float) -> dict:
        kit = make_media_kit(location_by_country=[
            {"name": "Spain",  "percentage": spain_pct},
            {"name": "Mexico", "percentage": 12.0},
        ])
        return client().extract_metrics(kit)

    def test_spain_65_all_brs_pass(self):
        metrics = self._build_metrics(65.0)

        # BR1
        assert metrics["audience_geography"]["ES"] == 65.0
        # BR2
        assert metrics["audience_genders"]["female"] == 55.0
        assert abs(sum(metrics["audience_genders"].values()) - 100.0) < 1.0
        # BR3 — total per band
        dist = metrics["audience_age_distribution"]
        assert "18-24" in dist
        assert dist["18-24"] == round(18.5 + 16.3, 4)
        # BR4
        assert metrics["credibility_score"] == 82.0   # Instagram default
        # BR5
        assert 0.0 < metrics["engagement_rate"] < 1.0

    def test_spain_65_passes_60_threshold(self):
        from app.services.filter_service import FilterService
        metrics = self._build_metrics(65.0)
        inf = {"audience_geography": metrics["audience_geography"]}
        fs = FilterService()
        assert fs._passes_spain_pct(inf, min_val=60.0, lenient=False) is True

    def test_spain_59_fails_60_threshold(self):
        from app.services.filter_service import FilterService
        metrics = self._build_metrics(59.0)
        inf = {"audience_geography": metrics["audience_geography"]}
        fs = FilterService()
        assert fs._passes_spain_pct(inf, min_val=60.0, lenient=False) is False

    def test_spain_exactly_60_passes(self):
        from app.services.filter_service import FilterService
        metrics = self._build_metrics(60.0)
        inf = {"audience_geography": metrics["audience_geography"]}
        fs = FilterService()
        assert fs._passes_spain_pct(inf, min_val=60.0, lenient=False) is True
