# service/tests/test_router.py
"""Tests for router pipeline."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import app.router as router_module
from app.router import AskRequest, AskResponse, process_question


@pytest.fixture
def mock_router_deps(monkeypatch):
    """Mock router dependencies (caller, executor)."""
    mock_caller = MagicMock()
    mock_executor = MagicMock()
    
    # Mock caller returns JSON classification + answer
    mock_caller.call.return_value = (
        '{"category": "database_query", "query_name": "top_customers_by_revenue", "params": {"limit": 5}}',
        100
    )
    
    # Mock executor returns sample data
    mock_executor.execute.return_value = [
        {"name": "王大明", "taxid": "A123456789", "revenue": 500000}
    ]
    
    # Inject mocks into router module
    router_module._caller = mock_caller
    router_module._executor = mock_executor
    
    yield mock_caller, mock_executor
    
    # Cleanup
    router_module._caller = None
    router_module._executor = None


def test_ask_request_creation():
    """Test AskRequest model."""
    req = AskRequest(
        question="上個月營收最高的客戶",
        user_id=100,
        role_id=200,
        client_id=11,
        org_ids=[1, 2],
        language="zh_TW",
    )
    assert req.question == "上個月營收最高的客戶"
    assert req.user_id == 100
    assert req.org_ids == [1, 2]


def test_ask_response_creation():
    """Test AskResponse model."""
    resp = AskResponse(
        answer="王大明營收最高",
        model_used="sonnet",
        tokens_used=150,
        query_used="top_customers_by_revenue",
        elapsed_ms=1000,
    )
    assert resp.answer == "王大明營收最高"
    assert resp.model_used == "sonnet"
    assert resp.query_used == "top_customers_by_revenue"


@pytest.mark.asyncio
async def test_process_question_database_query(mock_router_deps):
    """Test database_query category."""
    mock_caller, mock_executor = mock_router_deps
    
    # Make caller return different responses for different calls
    mock_caller.call.side_effect = [
        # First call: classification
        ('{"category": "database_query", "query_name": "top_customers_by_revenue", "params": {"limit": 5}}', 50),
        # Second call: answer generation
        ("[PII_C_001] 的營收最高，為 500000 元", 100),
    ]
    
    req = AskRequest(
        question="上個月營收最高的客戶",
        user_id=100,
        role_id=200,
        client_id=11,
        org_ids=[1, 2],
        language="zh_TW",
    )
    
    resp = await process_question(req)
    
    assert resp.model_used == "llama_70b"  # Groq Llama 70B is now the primary model
    assert resp.query_used == "top_customers_by_revenue"
    assert "王大明" in resp.answer  # PII should be unmasked
    assert resp.elapsed_ms >= 0


@pytest.mark.asyncio
async def test_process_question_general_knowledge(mock_router_deps):
    """Test general_knowledge category."""
    mock_caller, _ = mock_router_deps
    mock_caller.call.side_effect = [
        # Classification: general knowledge
        ('{"category": "general_knowledge"}', 50),
        # Answer
        ("iDempiere 是一個 ERP 系統...", 80),
    ]
    
    req = AskRequest(
        question="什麼是 iDempiere？",
        user_id=100,
        role_id=200,
        client_id=11,
        org_ids=[1],
        language="zh_TW",
    )
    
    resp = await process_question(req)
    
    assert resp.model_used == "llama_8b"
    assert resp.query_used is None


@pytest.mark.asyncio
async def test_process_question_clarification(mock_router_deps):
    """Test clarification category."""
    mock_caller, _ = mock_router_deps
    mock_caller.call.side_effect = [
        # Classification: clarification (invalid JSON)
        ("I don't understand", 30),
        # Clarification prompt
        ("請問您能提供更多細節嗎？", 50),
    ]
    
    req = AskRequest(
        question="訂單",  # Too vague
        user_id=100,
        role_id=200,
        client_id=11,
        org_ids=[1],
        language="zh_TW",
    )
    
    resp = await process_question(req)
    
    assert resp.model_used == "llama_8b"
    assert resp.query_used is None


@pytest.mark.asyncio
async def test_process_question_injects_security_params(mock_router_deps):
    """Verify ad_client_id and org_ids are injected from request, not LLM."""
    mock_caller, mock_executor = mock_router_deps
    mock_caller.call.side_effect = [
        ('{"category": "database_query", "query_name": "top_customers_by_revenue", "params": {}}', 50),
        ("Answer", 100),
    ]
    
    req = AskRequest(
        question="營收",
        user_id=100,
        role_id=200,
        client_id=11,
        org_ids=[1, 2],
        language="zh_TW",
    )
    
    await process_question(req)
    
    # Verify executor was called with security params from request
    call_args = mock_executor.execute.call_args
    params = call_args[0][1]  # Second positional arg is params dict
    assert params["ad_client_id"] == 11
    assert params["org_ids"] == [1, 2]


@pytest.mark.asyncio
async def test_process_question_sanitizes_input(mock_router_deps):
    """Verify PII tokens are stripped from question."""
    mock_caller, _ = mock_router_deps
    mock_caller.call.side_effect = [
        ('{"category": "general_knowledge"}', 50),
        ("Answer", 80),
    ]
    
    req = AskRequest(
        question="Tell me about [PII_C_001] and [PII_T_999]",
        user_id=100,
        role_id=200,
        client_id=11,
        org_ids=[1],
        language="en_US",
    )
    
    await process_question(req)
    
    # Verify caller received sanitized question (without PII tokens)
    call_args = mock_caller.call.call_args_list[0]
    user_content = call_args[0][2]  # Third arg is user_content
    assert "[PII_" not in user_content
