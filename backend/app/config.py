from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field
from functools import lru_cache
from typing import List
from pathlib import Path

# Get the path to the .env file (in project root, one level up from backend)
ENV_FILE_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def clean_database_url(url: str) -> str:
    """Clean database URL for asyncpg compatibility.
    
    Neon uses sslmode=require but asyncpg needs ssl=require.
    We remove unsupported params and add ssl=require for Neon connections.
    """
    # Remove sslmode and channel_binding params which asyncpg doesn't support
    needs_ssl = False
    if "?" in url:
        base_url, params = url.split("?", 1)
        param_pairs = params.split("&")
        # Check if SSL was requested
        needs_ssl = any(p.startswith("sslmode=require") for p in param_pairs)
        # Filter out unsupported params
        supported_params = [p for p in param_pairs if not p.startswith("sslmode=") and not p.startswith("channel_binding=")]
        # Add ssl=require for asyncpg if needed
        if needs_ssl:
            supported_params.append("ssl=require")
        if supported_params:
            return base_url + "?" + "&".join(supported_params)
        return base_url
    return url


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database - raw URL from environment
    database_url_raw: str = Field(..., validation_alias="DATABASE_URL")

    @computed_field
    @property
    def database_url(self) -> str:
        """Return cleaned database URL for asyncpg."""
        return clean_database_url(self.database_url_raw)

    # PrimeTag API
    primetag_api_base_url: str = Field(
        default="https://api.primetag.com",
        validation_alias="PRIMETAG_API_BASE_URL"
    )
    primetag_api_key: str = Field(..., validation_alias="PRIMETAG_API_KEY")

    # OpenAI
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-2024-08-06")

    # Apify API (Instagram content scraping)
    apify_api_token: str = Field(default="", validation_alias="APIFY_API_TOKEN")
    apify_posts_per_influencer: int = Field(default=6)  # ~$55 for 4000 influencers
    apify_batch_size: int = Field(default=50)

    # Cache settings
    cache_ttl_seconds: int = Field(default=900)  # 15 minutes
    influencer_cache_hours: int = Field(default=24)

    # Search defaults
    default_min_credibility: float = Field(
        default=70.0,
        validation_alias="DEFAULT_MIN_CREDIBILITY"
    )
    default_min_spain_audience: float = Field(
        default=60.0,
        validation_alias="DEFAULT_MIN_SPAIN_AUDIENCE"
    )
    default_result_limit: int = Field(default=10)

    # App settings
    debug: bool = Field(default=False, validation_alias="DEBUG")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001",
        validation_alias="CORS_ORIGINS"
    )
    # Vercel URL (auto-set by Vercel)
    vercel_url: str = Field(default="", validation_alias="VERCEL_URL")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string, plus Vercel URLs."""
        origins = [origin.strip() for origin in self.cors_origins.split(",")]
        # Add Vercel URL if present
        if self.vercel_url:
            origins.append(f"https://{self.vercel_url}")
        # Allow all Vercel preview deployments
        origins.append("https://*.vercel.app")
        return origins

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
