import logging
import os
from functools import lru_cache
from typing import Any, List, Optional

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, EmailStr, Field, model_validator, validator
try:
    from pydantic_settings import BaseSettings
    from pydantic import ConfigDict
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, ConfigDict

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables.

    Uses Pydantic BaseSettings to support environment-based configuration with
    sensible development defaults. This includes security, database, storage,
    integrations, and feature flags.
    """

    # -------------------------------------------------------------------------
    # Core App
    # -------------------------------------------------------------------------
    APP_NAME: str = Field("DocFoundry.app", description="Human-friendly product name.")
    APP_DESCRIPTION: str = Field(
        "Forge any document into clean, usable data.",
        description="Short marketing tagline for metadata and docs.",
    )
    ENVIRONMENT: str = Field(
        "development",
        description="Runtime environment: development | staging | production",
    )
    DEBUG: bool = Field(True, description="Enable debug/verbose logging.")

    BACKEND_HOST: str = Field(
        "0.0.0.0",
        description="Host interface for FastAPI to bind.",
    )
    BACKEND_PORT: int = Field(
        8000,
        description="Port for FastAPI to listen on.",
    )

    API_PREFIX: str = Field("/api", description="Base prefix for all API routes.")
    PUBLIC_API_PREFIX: str = Field(
        "/api/v1",
        description="Base prefix for public programmatic API routes.",
    )

    # -------------------------------------------------------------------------
    # Security / Auth
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        "dev-secret-key-change-me",
        description="Global secret key used for signing JWTs and tokens.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        60 * 24,
        description="JWT access token expiry in minutes for session cookies.",
    )
    JWT_ALGORITHM: str = Field("HS256", description="Algorithm for JWT signing.")

    SESSION_COOKIE_NAME: str = Field(
        "docfoundry_session",
        description="Name of HTTPOnly cookie for user sessions.",
    )
    SESSION_COOKIE_SECURE: bool = Field(
        False,
        description="Set secure flag on session cookie (HTTPS only).",
    )
    SESSION_COOKIE_SAMESITE: str = Field(
        "lax",
        description="SameSite attribute for session cookie: lax | strict | none.",
    )
    CSRF_COOKIE_NAME: str = Field(
        "docfoundry_csrf",
        description="Cookie name for CSRF token when using JWT cookies.",
    )

    PASSWORD_MIN_LENGTH: int = Field(
        8,
        description="Minimum password length for local auth.",
    )

    ALLOW_GOOGLE_OAUTH: bool = Field(
        True,
        description="Whether Google OAuth login is enabled.",
    )

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    CORS_ALLOW_ORIGINS: List[AnyHttpUrl] = Field(
        default_factory=list,
        description="List of allowed CORS origins.",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        True,
        description="Whether to allow credentials with CORS.",
    )
    CORS_ALLOW_METHODS: List[str] = Field(
        default=["*"],
        description="List of allowed CORS HTTP methods.",
    )
    CORS_ALLOW_HEADERS: List[str] = Field(
        default=["*"],
        description="List of allowed CORS HTTP headers.",
    )

    @model_validator(mode="before")
    @classmethod
    def merge_legacy_cors_origins(cls, data: Any) -> Any:
        """Map comma-separated CORS_ORIGINS env (legacy) into CORS_ALLOW_ORIGINS."""
        if not isinstance(data, dict):
            data = {}
        if "CORS_ALLOW_ORIGINS" in data and data["CORS_ALLOW_ORIGINS"] is not None:
            return data
        legacy = os.environ.get("CORS_ORIGINS")
        if not legacy or not str(legacy).strip():
            return data
        parts = [p.strip().rstrip("/") for p in str(legacy).split(",") if p.strip()]
        if not parts:
            return data
        return {**data, "CORS_ALLOW_ORIGINS": parts}

    # -------------------------------------------------------------------------
    # Database (Postgres)
    # -------------------------------------------------------------------------
    DB_HOST: str = Field("localhost", env="DB_HOST")
    DB_PORT: int = Field(5432, env="DB_PORT")
    DB_NAME: str = Field(..., env="DB_NAME")
    DB_USER: str = Field(..., env="DB_USER")
    DB_PASSWORD: str = Field(..., env="DB_PASSWORD")

    DB_POOL_SIZE: int = Field(
        10,
        description="SQLAlchemy connection pool size.",
    )
    DB_MAX_OVERFLOW: int = Field(
        20,
        description="Maximum overflow connections beyond pool size.",
    )
    DB_POOL_TIMEOUT: int = Field(
        30,
        description="Seconds to wait for a database connection from the pool.",
    )

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Construct the SQLAlchemy/Postgres connection URI.

        Returns:
            str: Database connection URI.
        """
        user = self.DB_USER
        password = self.DB_PASSWORD
        host = self.DB_HOST
        port = self.DB_PORT
        name = self.DB_NAME

        # Basic escaping for special characters in user/password if needed
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    # -------------------------------------------------------------------------
    # Storage
    # -------------------------------------------------------------------------
    STORAGE_PROVIDER: str = Field(
        "local",
        description="Storage provider identifier, e.g. local | s3 (future).",
    )
    STORAGE_ROOT: str = Field(
        "/data/storage",
        description=(
            "Root directory for file storage when using local provider. "
            "Should be mapped to a persistent Docker volume in production."
        ),
    )
    MAX_FILE_SIZE_MB: int = Field(
        25,
        description="Maximum upload file size in megabytes.",
    )

    # -------------------------------------------------------------------------
    # OCR / Document Processing - Google Cloud Vision
    # -------------------------------------------------------------------------
    GOOGLE_CLOUD_PROJECT_ID: str = Field(
        ...,
        description="Google Cloud project ID (required for Vision API).",
    )
    GOOGLE_CLOUD_VISION_CREDENTIALS_PATH: Optional[str] = Field(
        None,
        description=(
            "Path to Google Cloud service account JSON file. "
            "If None, uses Application Default Credentials (ADC). "
            "Example: /path/to/service-account-key.json"
        ),
    )
    GOOGLE_CLOUD_VISION_TIMEOUT_SECONDS: int = Field(
        60,
        description="Timeout in seconds for Google Vision API requests.",
    )
    GOOGLE_CLOUD_VISION_MAX_PAGES_PER_REQUEST: int = Field(
        5,
        description="Maximum number of pages to process per batch request for PDFs.",
    )
    GOOGLE_CLOUD_VISION_ENABLE_ASYNC: bool = Field(
        True,
        description="Use async batch API for PDF processing (recommended for large PDFs).",
    )

    # -------------------------------------------------------------------------
    # Email (Resend)
    # -------------------------------------------------------------------------
    RESEND_API_KEY: Optional[str] = Field(
        None,
        description="API key for Resend transactional email service.",
    )
    EMAIL_FROM: EmailStr = Field(
        "no-reply@localhost.local",
        description="Default 'from' address for outgoing emails.",
    )

    # -------------------------------------------------------------------------
    # AI / LLM (OpenAI)
    # -------------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = Field(
        None,
        description="API key for OpenAI service (used for AI template generation).",
    )
    OPENAI_MODEL: str = Field(
        "gpt-4.1",
        description="OpenAI model to use for template generation (e.g., gpt-4.1, gpt-4, gpt-4-turbo, gpt-3.5-turbo).",
    )
    ENABLE_AI_TEMPLATE_GENERATION: bool = Field(
        True,
        description="Enable AI-powered template generation feature.",
    )

    # -------------------------------------------------------------------------
    # Stripe / Billing
    # -------------------------------------------------------------------------
    STRIPE_API_KEY: Optional[str] = Field(
        None,
        description="Secret key for Stripe API.",
    )
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(
        None,
        description="Stripe webhook signing secret.",
    )
    STRIPE_PRICE_BASIC: Optional[str] = Field(
        None,
        description="Stripe price ID for Basic plan.",
    )
    STRIPE_PRICE_PRO: Optional[str] = Field(
        None,
        description="Stripe price ID for Pro plan.",
    )
    STRIPE_BILLING_PORTAL_RETURN_URL: Optional[AnyHttpUrl] = Field(
        None,
        description="Default return URL for Stripe billing portal sessions.",
    )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = Field(
        "INFO",
        description="Root log level: DEBUG | INFO | WARNING | ERROR | CRITICAL.",
    )
    LOG_SQL_QUERIES: bool = Field(
        False,
        description="Enable SQLAlchemy engine echo for debugging.",
    )

    # -------------------------------------------------------------------------
    # Job / Worker config
    # -------------------------------------------------------------------------
    JOB_POLL_INTERVAL_SECONDS: int = Field(
        5,
        description="Polling interval in seconds for worker job loop.",
    )
    JOB_MAX_ATTEMPTS_DEFAULT: int = Field(
        5,
        description="Default maximum attempts for jobs when not specified.",
    )
    worker_poll_interval_seconds: float = Field(
        2.0,
        description="Polling interval in seconds for job processor worker.",
    )
    worker_batch_size: int = Field(
        10,
        description="Number of jobs to process in each batch.",
    )
    worker_stuck_job_timeout_minutes: int = Field(
        5,
        description="Minutes before a PROCESSING job is considered stuck and recovered.",
    )

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------
    WEBHOOK_MAX_RETRIES: int = Field(
        5,
        description="Default maximum attempts for webhook deliveries.",
    )
    WEBHOOK_BACKOFF_BASE_SECONDS: int = Field(
        5,
        description="Base backoff interval for webhook retries.",
    )

    # -------------------------------------------------------------------------
    # Multi-tenancy / Workspace
    # -------------------------------------------------------------------------
    DEFAULT_WORKSPACE_TRIAL_DAYS: int = Field(
        14,
        description="Default trial period in days for new workspaces.",
    )

    # -------------------------------------------------------------------------
    # Feature Flags
    # -------------------------------------------------------------------------
    ENABLE_AUDIT_LOGGING: bool = Field(
        True,
        description="Enable audit logging system-wide.",
    )
    ENABLE_NOTIFICATIONS: bool = Field(
        True,
        description="Enable notifications (email + in-app).",
    )

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = Field(
        True,
        description="Enable rate limiting globally.",
    )
    RATE_LIMIT_STORAGE_URL: Optional[str] = Field(
        None,
        description="Redis URL for rate limit storage (e.g., redis://localhost:6379/0). If None, uses in-memory storage.",
    )
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = Field(
        60,
        description="Default rate limit per minute for authenticated users.",
    )
    RATE_LIMIT_AUTH_PER_MINUTE: int = Field(
        5,
        description="Rate limit per minute for authentication endpoints (login, register).",
    )
    RATE_LIMIT_API_KEY_PER_MINUTE: int = Field(
        100,
        description="Rate limit per minute for API key authenticated requests.",
    )
    RATE_LIMIT_FILE_UPLOAD_PER_MINUTE: int = Field(
        10,
        description="Rate limit per minute for file upload endpoints.",
    )

    # -------------------------------------------------------------------------
    # Brute Force Protection
    # -------------------------------------------------------------------------
    BRUTE_FORCE_MAX_ATTEMPTS: int = Field(
        5,
        description="Maximum failed login attempts before lockout.",
    )
    BRUTE_FORCE_LOCKOUT_MINUTES: int = Field(
        15,
        description="Lockout duration in minutes after max attempts exceeded.",
    )
    BRUTE_FORCE_WINDOW_MINUTES: int = Field(
        15,
        description="Time window in minutes for counting failed attempts.",
    )

    # -------------------------------------------------------------------------
    # Security Headers
    # -------------------------------------------------------------------------
    SECURITY_HEADERS_ENABLED: bool = Field(
        True,
        description="Enable security headers middleware.",
    )
    CSP_POLICY: str = Field(
        "default-src 'self'",
        description="Content Security Policy header value.",
    )
    HSTS_MAX_AGE: int = Field(
        31536000,
        description="HSTS max-age in seconds (1 year default).",
    )
    HSTS_INCLUDE_SUBDOMAINS: bool = Field(
        True,
        description="Include subdomains in HSTS header.",
    )

    # -------------------------------------------------------------------------
    # Request Size Limits
    # -------------------------------------------------------------------------
    MAX_REQUEST_BODY_SIZE_MB: int = Field(
        100,
        description="Maximum request body size in megabytes.",
    )
    MAX_HEADERS_SIZE_KB: int = Field(
        16,
        description="Maximum headers size in kilobytes.",
    )

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @validator("SESSION_COOKIE_SECURE", pre=True, always=True)
    def enforce_secure_cookies_in_production(
        cls,
        v: Optional[bool],
        values: dict,
    ) -> bool:
        """Ensure secure cookies are used in production environments."""
        env = values.get("ENVIRONMENT", "development")
        if env == "production":
            return True
        return bool(v)

    @validator("DEBUG", pre=True, always=True)
    def disable_debug_in_production(cls, v: Optional[bool], values: dict) -> bool:
        """Disable debug mode automatically in production."""
        env = values.get("ENVIRONMENT", "development")
        if env == "production":
            return False
        return bool(v)

    # -------------------------------------------------------------------------
    # Compatibility properties for auth module
    # -------------------------------------------------------------------------
    @property
    def auth_access_token_expire_seconds(self) -> int:
        """Access token expiry in seconds (compatibility property)."""
        return self.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    def auth_access_token_timedelta(self, seconds: int):
        """Create timedelta for token expiry (compatibility method)."""
        from datetime import timedelta
        return timedelta(seconds=seconds)

    @property
    def auth_jwt_secret_key(self) -> str:
        """JWT secret key (compatibility property)."""
        return self.SECRET_KEY

    @property
    def auth_jwt_algorithm(self) -> str:
        """JWT algorithm (compatibility property)."""
        return self.JWT_ALGORITHM

    @property
    def auth_cookie_name(self) -> str:
        """Auth cookie name (compatibility property)."""
        return self.SESSION_COOKIE_NAME

    @property
    def cookies_secure(self) -> bool:
        """Cookie secure flag (compatibility property)."""
        return self.SESSION_COOKIE_SECURE

    @property
    def cookies_samesite(self) -> str:
        """Cookie SameSite attribute (compatibility property)."""
        return self.SESSION_COOKIE_SAMESITE

    @property
    def access_token_expire_minutes(self) -> int:
        """Access token expiry in minutes (compatibility property)."""
        return self.ACCESS_TOKEN_EXPIRE_MINUTES

    model_config = ConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables not defined in the model
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings.

    Using LRU cache ensures that settings are only loaded and validated once
    during the application lifecycle, which is efficient and thread-safe.
    """
    try:
        settings = Settings()
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        )
        logger.debug("Settings loaded successfully.")
        return settings
    except Exception as exc:
        # Fail fast with clear logging if configuration is invalid
        logging.basicConfig(level=logging.ERROR)
        logger.exception("Failed to load application settings: %s", exc)
        raise


# Eagerly initialize settings at import time for early validation in most flows.
settings = get_settings()