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
    """Test database_query category - uses Claude Sonnet."""
    mock_caller, mock_executor = mock_router_deps
    
    # Mock responses:
    # 1. Router (Llama 8B) → "database_query"
    # 2. Selector (Sonnet) → JSON with query name
    # 3. Answer (Sonnet) → masked answer
    mock_caller.call.side_effect = [
        ("database_query", 10),  # Router classification
        ('{"query_name": "top_customers_by_revenue", "params": {"limit": 5}}', 50),  # Selector
        ("[PII_C_001] 的營收最高，為 500000 元", 100),  # Answer
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
    
    assert resp.model_used == "sonnet"  # Claude Sonnet for database queries
    assert resp.query_used == "top_customers_by_revenue"
    assert "王大明" in resp.answer  # PII should be unmasked
    assert resp.elapsed_ms >= 0


@pytest.mark.asyncio
async def test_process_question_general_knowledge(mock_router_deps):
    """Test general_knowledge category - uses Llama 70B."""
    mock_caller, _ = mock_router_deps
    
    # Mock responses:
    # 1. Router (Llama 8B) → "general_knowledge"
    # 2. Answer (Llama 70B) → answer text
    mock_caller.call.side_effect = [
        ("general_knowledge", 10),  # Router classification
        ("iDempiere 是一個 ERP 系統...", 80),  # Answer
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
    
    assert resp.model_used == "llama_70b"  # Llama 70B for general knowledge
    assert resp.query_used is None


@pytest.mark.asyncio
async def test_process_question_clarification(mock_router_deps):
    """Test clarification category - uses Llama 8B."""
    mock_caller, _ = mock_router_deps
    
    # Mock responses:
    # 1. Router (Llama 8B) → "clarification"
    # 2. Answer (Llama 8B) → clarification text
    mock_caller.call.side_effect = [
        ("clarification", 10),  # Router classification
        ("請問您能提供更多細節嗎？", 50),  # Clarification
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
    
    assert resp.model_used == "llama_8b"  # Llama 8B for clarification
    assert resp.query_used is None


@pytest.mark.asyncio
async def test_process_question_injects_security_params(mock_router_deps):
    """Verify ad_client_id and org_ids are injected from request, not LLM."""
    mock_caller, mock_executor = mock_router_deps
    
    # Mock responses:
    # 1. Router (Llama 8B) → "database_query"
    # 2. Selector (Sonnet) → JSON with empty params (security params should be injected)
    # 3. Answer (Sonnet) → answer text
    mock_caller.call.side_effect = [
        ("database_query", 10),  # Router classification
        ('{"query_name": "top_customers_by_revenue", "params": {}}', 50),  # Selector
        ("Answer", 100),  # Answer
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
