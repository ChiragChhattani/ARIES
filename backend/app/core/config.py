"""
Application configuration loaded from environment variables.

Uses Pydantic Settings to provide validated, typed configuration.
All secrets come from the environment — never hardcoded.

Usage:
    from app.core.config import get_settings
    settings = get_settings()
    print(settings.openai_api_key)  # Read from OPENAI_API_KEY env var
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings.

    Pydantic Settings reads values from environment variables automatically.
    Variable names are mapped by converting field names to uppercase and
    prepending the env_prefix where configured.

    Example:
        Field `log_level` with prefix `ARIES_` → reads from `ARIES_LOG_LEVEL`
    """

    model_config = SettingsConfigDict(
        # Look for a .env file in the backend/ directory
        env_file=".env",
        env_file_encoding="utf-8",
        # All ARIES-specific vars start with ARIES_
        env_prefix="ARIES_",
        # Don't fail on extra env vars we don't know about
        extra="ignore",
        # Strip whitespace from values
        str_strip_whitespace=True,
    )

    # --- Application ---
    app_name: str = "ARIES"
    app_version: str = "0.1.0"
    env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./aries.db"

    # --- CORS ---
    # Stored as comma-separated string, parsed into list
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- LLM Provider Configuration ---
    llm_provider: Literal["openai", "groq"] = "groq"
    
    # --- OpenAI ---
    # Note: OPENAI_API_KEY does NOT use the ARIES_ prefix (industry standard)
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key. Read from OPENAI_API_KEY env var.",
    )
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = Field(default=4096, ge=100, le=16384)
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    
    # --- Groq ---
    # Note: GROQ_API_KEY does NOT use the ARIES_ prefix (industry standard)
    groq_api_key: str = Field(
        default="",
        description="Groq API key. Read from GROQ_API_KEY env var.",
    )
    groq_model: str = "llama-3.3-70b-versatile"

    # --- Interview Defaults ---
    default_max_questions: int = Field(default=10, ge=3, le=50)
    default_timeout_minutes: int = Field(default=45, ge=5, le=180)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Accept lowercase log levels from env vars."""
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Ensure postgresql URLs use asyncpg driver."""
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.env == "development"

    @property
    def is_production(self) -> bool:
        return self.env == "production"


# Override the env_prefix for OPENAI_API_KEY, GROQ_API_KEY, and standard DATABASE_URL
# since they are industry standards that don't always use our ARIES_ prefix.
class _StandardEnvSettings(BaseSettings):
    """Reads standard API keys and database URL without the ARIES_ prefix."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    openai_api_key: str = ""
    groq_api_key: str = ""
    database_url: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings singleton.

    Uses lru_cache so the settings are loaded once and reused.
    This avoids re-reading env vars and .env files on every call.

    Returns:
        Settings: Validated application settings.
    """
    # Read the ARIES_-prefixed settings
    settings = Settings()

    # Load standard environment variables if not populated via ARIES_ prefix
    std_settings = _StandardEnvSettings()
    if not settings.openai_api_key and std_settings.openai_api_key:
        object.__setattr__(settings, "openai_api_key", std_settings.openai_api_key)
    if not settings.groq_api_key and std_settings.groq_api_key:
        object.__setattr__(settings, "groq_api_key", std_settings.groq_api_key)
    if (
        settings.database_url == "sqlite+aiosqlite:///./aries.db"
        and std_settings.database_url
    ):
        normalized = Settings.normalize_database_url(std_settings.database_url)
        object.__setattr__(settings, "database_url", normalized)

    return settings
