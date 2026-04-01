# service/tests/test_integration.py
"""Integration tests for FastAPI endpoints."""

import hashlib
import hmac
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app, verify_hmac, check_rate_limit, RATE_LIMIT_MAX


@pytest.fixture
def client():
    """Test client with mocked dependencies."""
    # Mock database pool
    with patch("app.queries.executor.pool", MagicMock()):
        # Mock router dependencies
        mock_caller = MagicMock()
        mock_executor = MagicMock()
        mock_caller.call.return_value = (
            '{"category": "general_knowledge"}',
            50
        )
        
        with patch("app.router._caller", mock_caller), \
             patch("app.router._executor", mock_executor):
            
            yield TestClient(app)


def test_health_endpoint(client):
    """Test /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "idempiere-ai-service"


def test_ask_missing_hmac(client):
    """Test /v1/ask without HMAC signature."""
    response = client.post(
        "/v1/ask",
        json={"question": "test", "user_id": 1, "role_id": 1, "client_id": 1, "org_ids": [1]},
    )
    assert response.status_code == 401
    assert "HMAC" in response.json()["detail"]


def test_ask_invalid_hmac(client):
    """Test /v1/ask with invalid HMAC signature."""
    body = {"question": "test", "user_id": 1, "role_id": 1, "client_id": 1, "org_ids": [1]}
    body_json = json.dumps(body)
    
    response = client.post(
        "/v1/ask",
        content=body_json.encode("utf-8"),
        headers={"X-HMAC-Signature": "invalid-signature"},
    )
    assert response.status_code == 401
    assert "HMAC" in response.json()["detail"]


def test_ask_valid_hmac(client):
    """Test /v1/ask with valid HMAC signature."""
    body = {"question": "test", "user_id": 1, "role_id": 1, "client_id": 1, "org_ids": [1]}
    body_json = json.dumps(body)
    
    # Compute valid HMAC
    from app import config
    signature = hmac.new(
        config.HMAC_SECRET.encode("utf-8"),
        body_json.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    response = client.post(
        "/v1/ask",
        content=body_json.encode("utf-8"),
        headers={"X-HMAC-Signature": signature},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "model_used" in data


def test_verify_hmac_function():
    """Test HMAC verification function."""
    from app import config
    
    body = b"test body"
    signature = hmac.new(
        config.HMAC_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    
    assert verify_hmac(body, signature) is True
    assert verify_hmac(body, "wrong-signature") is False


def test_rate_limit():
    """Test rate limiting logic."""
    # Clear any existing timestamps
    from app.main import user_request_timestamps
    user_request_timestamps.clear()
    
    user_id = 999
    
    # First 20 requests should succeed
    for i in range(RATE_LIMIT_MAX):
        assert check_rate_limit(user_id) is True
    
    # 21st request should fail
    assert check_rate_limit(user_id) is False


def test_rate_limit_window():
    """Test rate limit window resets."""
    from app.main import user_request_timestamps
    from datetime import datetime, timedelta
    
    user_id = 888
    user_request_timestamps.clear()
    
    # Add a timestamp from 2 minutes ago
    old_time = datetime.now() - timedelta(minutes=2)
    user_request_timestamps[user_id].append(old_time)
    
    # Should be allowed (old timestamp is outside window)
    assert check_rate_limit(user_id) is True
