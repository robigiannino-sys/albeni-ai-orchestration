"""
AI Orchestration Layer - Configuration
Albeni 1905 - Invisible Luxury Ecosystem
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Albeni 1905 AI Orchestration Layer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database — Railway provides DATABASE_URL directly
    DATABASE_URL: str = "postgresql://albeni_admin:password@db:5432/albeni_ai_db"
    # Legacy fields (used if DATABASE_URL not set via env)
    DB_USER: str = "albeni_admin"
    DB_PASSWORD: str = "password"
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "albeni_ai_db"

    @property
    def effective_database_url(self) -> str:
        """Use DATABASE_URL from env (Railway) or build from components."""
        env_url = os.getenv("DATABASE_URL")
        if env_url:
            return env_url
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis — Railway provides REDIS_URL directly
    REDIS_URL: str = "redis://redis:6379"

    # AI Provider: "gemini" or "openai"
    AI_PROVIDER: str = "gemini"

    # Google Gemini (DEFAULT)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # OpenAI (alternative)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Klaviyo
    KLAVIYO_API_KEY: str = ""
    KLAVIYO_PUBLIC_KEY: str = ""
    KLAVIYO_REVISION: str = "2024-02-15"

    # GA4
    GA4_MEASUREMENT_ID: str = ""
    GA4_API_SECRET: str = ""

    # Shopify
    SHOPIFY_STORE_URL: str = ""
    SHOPIFY_ACCESS_TOKEN: str = ""

    # Domains
    DOMAIN_TOFU: str = "https://worldofmerino.com"
    DOMAIN_MOFU: str = "https://merinouniversity.com"
    DOMAIN_BOFU_TECH: str = "https://perfectmerinoshirt.com"
    DOMAIN_BOFU_HERITAGE: str = "https://albeni1905.com"

    # IDS Thresholds
    IDS_TOFU_MAX: int = 30
    IDS_MOFU_MAX: int = 65
    IDS_BOFU_MIN: int = 65

    # IDS Weights (must sum to 1.0)
    IDS_WEIGHT_DWELL_TIME: float = 0.20
    IDS_WEIGHT_SCROLL_DEPTH: float = 0.20
    IDS_WEIGHT_INTERACTIONS: float = 0.40
    IDS_WEIGHT_FREQUENCY: float = 0.20

    # CPA Thresholds
    CPA_GREEN_MAX: float = 9.0
    CPA_YELLOW_MAX: float = 15.0

    # SEO
    CANNIBALIZATION_WARNING: float = 6.0
    CANNIBALIZATION_CRITICAL: float = 12.0

    # Content Quality
    CONTENT_QUALITY_MIN: float = 76.0

    # Cluster Prediction
    CLUSTER_CONFIDENCE_TARGET: float = 0.85

    # Semrush
    SEMRUSH_API_KEY: str = ""

    # Notion
    NOTION_API_TOKEN: str = ""
    NOTION_TOKEN: str = ""  # alias for NOTION_API_TOKEN
    NOTION_CONTENT_PIPELINE_DB: str = ""
    NOTION_CALENDARIO_DB: str = ""
    NOTION_KEYWORD_MATRIX_DB: str = ""
    NOTION_GLOSSARIO_DB: str = ""

    # Google Ads (Offline Conversions API)
    GOOGLE_ADS_CUSTOMER_ID: str = ""
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    GOOGLE_ADS_CLIENT_ID: str = ""
    GOOGLE_ADS_CLIENT_SECRET: str = ""
    GOOGLE_ADS_REFRESH_TOKEN: str = ""
    GOOGLE_ADS_CONVERSION_ACTION_ID: str = ""

    # Meta Conversions API (CAPI)
    META_PIXEL_ID: str = ""
    META_ACCESS_TOKEN: str = ""
    META_TEST_EVENT_CODE: str = ""  # per testing, rimuovere in produzione

    # ADV Intelligence
    ADV_IDS_HIGH_QUALITY_THRESHOLD: int = 70   # IDS > 70 = High Quality Lead
    ADV_IDS_LOW_QUALITY_THRESHOLD: int = 10    # IDS < 10 dopo 3 pagine = Low Quality
    ADV_BOT_DWELL_TIME_MIN_MS: int = 2000      # < 2s = sospetto bot
    ADV_BOT_MIN_MOUSE_EVENTS: int = 3          # < 3 mouse events = sospetto bot
    ADV_BOT_MAX_PAGES_PER_MIN: int = 10        # > 10 pagine/min = bot
    ADV_BUDGET_MONTHLY_EUR: float = 250.0      # Budget mensile ADV

    # Security
    JWT_SECRET: str = "change-this-secret"
    API_KEY: str = "change-this-api-key"

    # Supported Languages
    SUPPORTED_LANGUAGES: list = ["it", "en", "fr", "de", "es"]

    # Cluster Definitions
    CLUSTERS: list = [
        "business_professional",
        "heritage_mature",
        "conscious_premium",
        "modern_minimalist",
        "italian_authentic"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
