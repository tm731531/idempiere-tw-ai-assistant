# service/tests/test_caller.py
"""Tests for LLM caller.

Note: These tests run in MOCK_LLM=true mode (set by conftest.py).
They verify the mock mode behavior. For non-mock tests, we'd need
API keys which aren't available in CI.
"""

import pytest
from app.llm.caller import LLMCaller


def test_mock_mode_returns_canned_response():
    """Test that MOCK_LLM=true returns mock response."""
    caller = LLMCaller()
    content, tokens = caller.call("sonnet", "system prompt", "question")
    assert "Mock response" in content
    assert tokens == 0


def test_mock_mode_all_model_types():
    """Test mock mode works for all model types."""
    caller = LLMCaller()
    
    # Test sonnet
    content, tokens = caller.call("sonnet", "system", "question")
    assert "Mock response" in content
    assert tokens == 0
    
    # Test llama_70b
    content, tokens = caller.call("llama_70b", "system", "question")
    assert "Mock response" in content
    
    # Test llama_8b
    content, tokens = caller.call("llama_8b", "system", "question")
    assert "Mock response" in content


def test_mock_mode_ignores_prompt_content():
    """Test that mock mode returns same response regardless of prompt."""
    caller = LLMCaller()
    
    content1, _ = caller.call("sonnet", "system A", "question A")
    content2, _ = caller.call("sonnet", "system B", "question B")
    
    # Both should return the same mock response
    assert content1 == content2
