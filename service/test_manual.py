#!/usr/bin/env python3
"""
Manual test script for Python AI Service.

Usage:
    # Start the service first:
    cd service/
    ./venv/bin/python -m app.main
    
    # Then run this test:
    python test_manual.py
"""

import hashlib
import hmac
import json
import httpx

# Configuration
SERVICE_URL = "http://localhost:8900"
HMAC_SECRET = "test-secret"  # Must match service/.env HMAC_SECRET


def compute_hmac(body_bytes: bytes) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        HMAC_SECRET.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()


def test_health():
    """Test /health endpoint."""
    print("Testing /health...")
    response = httpx.get(f"{SERVICE_URL}/health")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("  ✓ PASSED\n")


def test_ask_question():
    """Test /v1/ask endpoint."""
    print("Testing /v1/ask...")
    
    # Build request
    body = {
        "question": "上個月營收最高的客戶是誰？",
        "user_id": 100,
        "role_id": 200,
        "client_id": 11,
        "org_ids": [1, 2],
        "language": "zh_TW",
    }
    body_json = json.dumps(body)
    body_bytes = body_json.encode("utf-8")
    
    # Compute HMAC
    signature = compute_hmac(body_bytes)
    
    # Send request
    response = httpx.post(
        f"{SERVICE_URL}/v1/ask",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-HMAC-Signature": signature,
        },
    )
    
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  Answer: {data['answer'][:100]}...")
        print(f"  Model: {data['model_used']}")
        print(f"  Tokens: {data['tokens_used']}")
        print(f"  Elapsed: {data['elapsed_ms']}ms")
        print("  ✓ PASSED\n")
    else:
        print(f"  Error: {response.json()}")
        print("  ✗ FAILED\n")


def test_invalid_hmac():
    """Test /v1/ask with invalid HMAC."""
    print("Testing /v1/ask with invalid HMAC...")
    
    body = {"question": "test", "user_id": 1, "role_id": 1, "client_id": 1, "org_ids": [1]}
    body_bytes = json.dumps(body).encode("utf-8")
    
    response = httpx.post(
        f"{SERVICE_URL}/v1/ask",
        content=body_bytes,
        headers={"X-HMAC-Signature": "invalid-signature"},
    )
    
    print(f"  Status: {response.status_code}")
    assert response.status_code == 401
    print("  ✓ PASSED (correctly rejected invalid HMAC)\n")


def test_missing_hmac():
    """Test /v1/ask without HMAC."""
    print("Testing /v1/ask without HMAC...")
    
    body = {"question": "test", "user_id": 1, "role_id": 1, "client_id": 1, "org_ids": [1]}
    
    response = httpx.post(
        f"{SERVICE_URL}/v1/ask",
        json=body,
    )
    
    print(f"  Status: {response.status_code}")
    assert response.status_code == 401
    print("  ✓ PASSED (correctly rejected missing HMAC)\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Manual Test Suite for Python AI Service")
    print("=" * 60 + "\n")
    
    try:
        test_health()
        test_missing_hmac()
        test_invalid_hmac()
        test_ask_question()
        
        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)
    except httpx.ConnectError as e:
        print(f"\n✗ Connection error: Could not connect to {SERVICE_URL}")
        print("Make sure the service is running:")
        print(f"  cd service/ && ./venv/bin/python -m app.main")
