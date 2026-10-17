"""
Shared test fixtures and configuration.

WHY conftest.py?
----------------
pytest automatically discovers conftest.py and makes its fixtures
available to all test files in the same directory (and subdirectories).
This avoids duplicating setup code across test files.

KEY CONCEPT: FIXTURES
---------------------
A fixture is a function that provides test setup (and optional teardown).
Instead of each test creating its own database connection, they all
request the `test_client` fixture, which creates a properly configured
FastAPI TestClient once.
"""

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """
    Set environment variables for all tests automatically.

    autouse=True means this runs before EVERY test without needing
    to explicitly request it. This ensures tests never accidentally
    use production credentials.
    """
    monkeypatch.setenv("ARIES_ENV", "development")
    monkeypatch.setenv("ARIES_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ARIES_DATABASE_URL", "sqlite+aiosqlite:///./test_aries.db")
    monkeypatch.setenv("ARIES_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
    monkeypatch.setenv("ARIES_OPENAI_MODEL", "gpt-4o")

    # Clear the cached settings so each test gets fresh config
    from app.core.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def test_client():
    """
    Create a FastAPI TestClient for HTTP endpoint testing.

    TestClient wraps the ASGI app in a synchronous interface,
    so tests can call client.get("/health") without async/await.
    """
    from app.main import create_app

    # Clear cache to ensure fresh settings for each test
    from app.core.config import get_settings
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        yield client
