"""
Tests for core configuration.

These tests verify that:
1. Settings load correctly from environment variables
2. Default values work when env vars are missing
3. Validation catches invalid values
4. The settings singleton (lru_cache) works correctly
"""

import pytest
from app.core.config import get_settings, Settings


class TestSettings:
    """Test suite for application settings."""

    def test_settings_load_from_env(self):
        """Settings should read from environment variables set in conftest."""
        settings = get_settings()
        assert settings.env == "development"
        assert settings.log_level == "DEBUG"
        assert settings.openai_model == "gpt-4o"

    def test_settings_app_defaults(self):
        """Default values should be sensible."""
        settings = get_settings()
        assert settings.app_name == "ARIES"
        assert settings.app_version == "0.1.0"

    def test_settings_cors_parsing(self):
        """CORS origins string should be parsed into a list."""
        settings = get_settings()
        origins = settings.cors_origins_list
        assert isinstance(origins, list)
        assert "http://localhost:5173" in origins

    def test_settings_environment_flags(self):
        """is_development and is_production should reflect the env setting."""
        settings = get_settings()
        assert settings.is_development is True
        assert settings.is_production is False

    def test_settings_openai_key_loaded(self):
        """The OpenAI API key should be loaded from OPENAI_API_KEY."""
        settings = get_settings()
        assert settings.openai_api_key is not None

    def test_settings_singleton_behavior(self):
        """get_settings() should return the same object (cached)."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_interview_defaults(self):
        """Interview defaults should have reasonable values."""
        settings = get_settings()
        assert 3 <= settings.default_max_questions <= 50
        assert 5 <= settings.default_timeout_minutes <= 180

    def test_log_level_normalization(self):
        """Log level should accept lowercase and normalize to uppercase."""
        # This tests the field_validator
        settings = Settings(
            log_level="debug",
            database_url="sqlite+aiosqlite:///./test.db",
        )
        assert settings.log_level == "DEBUG"

    def test_openai_temperature_validation(self):
        """Temperature must be between 0.0 and 2.0."""
        with pytest.raises(Exception):  # ValidationError
            Settings(
                openai_temperature=3.0,
                database_url="sqlite+aiosqlite:///./test.db",
            )

    def test_openai_max_tokens_validation(self):
        """Max tokens must be between 100 and 16384."""
        with pytest.raises(Exception):
            Settings(
                openai_max_tokens=50,
                database_url="sqlite+aiosqlite:///./test.db",
            )

    def test_database_url_normalization(self):
        """Standard postgres URLs should be converted to postgresql+asyncpg."""
        s1 = Settings(database_url="postgres://user:pass@host:5432/db")
        assert s1.database_url == "postgresql+asyncpg://user:pass@host:5432/db"

        s2 = Settings(database_url="postgresql://user:pass@host:5432/db")
        assert s2.database_url == "postgresql+asyncpg://user:pass@host:5432/db"

        s3 = Settings(database_url="sqlite+aiosqlite:///./test.db")
        assert s3.database_url == "sqlite+aiosqlite:///./test.db"
