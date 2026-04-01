# service/tests/conftest.py
"""Shared pytest fixtures for all tests.

This file is automatically loaded by pytest before any tests run.
It sets up environment variables BEFORE any app module is imported,
because config.py uses os.environ[] which will crash if vars are missing.
"""

import os
import pytest

# Set test environment variables BEFORE any app module is imported.
# config.py uses os.environ["VAR"] (hard crash if missing), so these MUST exist.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("HMAC_SECRET", "test-secret")
os.environ.setdefault("DB_PASSWORD", "test-pass")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "idempiere")
os.environ.setdefault("DB_USER", "ai_readonly")
os.environ.setdefault("SERVICE_PORT", "8900")
os.environ.setdefault("MOCK_LLM", "true")


@pytest.fixture(scope="session")
def test_env():
    """Fixture that returns the test environment configuration."""
    return {
        "anthropic_api_key": "test-key",
        "groq_api_key": "test-key",
        "hmac_secret": "test-secret",
        "db_password": "test-pass",
        "db_host": "localhost",
        "db_port": "5432",
        "db_name": "idempiere",
        "db_user": "ai_readonly",
        "service_port": "8900",
        "mock_llm": True,
    }
