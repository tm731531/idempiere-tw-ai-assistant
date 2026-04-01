# service/tests/test_executor.py
"""Tests for query executor."""

import pytest
from unittest.mock import patch, MagicMock
import app.queries.executor as executor_module
from app.queries.executor import QueryExecutor


@pytest.fixture
def executor():
    """Fixture with mocked database pool."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_pool.getconn.return_value = mock_conn
    mock_cursor.description = [("name",), ("revenue",)]
    mock_cursor.fetchmany.return_value = [("王大明", 50000)]

    # Inject mock pool (replaces the module-level pool variable)
    executor_module.pool = mock_pool

    ex = QueryExecutor()
    yield ex, mock_cursor, mock_pool, mock_conn

    executor_module.pool = None


def test_execute_returns_dicts(executor):
    ex, mock_cursor, _, _ = executor
    rows = ex.execute(
        "top_customers_by_revenue",
        {"date_from": "2026-01-01", "date_to": "2026-03-31",
         "ad_client_id": 11, "org_ids": [1, 2], "limit": 5},
    )
    assert rows == [{"name": "王大明", "revenue": 50000}]


def test_execute_returns_conn_to_pool(executor):
    ex, _, mock_pool, mock_conn = executor
    ex.execute(
        "top_customers_by_revenue",
        {"date_from": "2026-01-01", "date_to": "2026-03-31",
         "ad_client_id": 11, "org_ids": [1], "limit": 5},
    )
    mock_pool.putconn.assert_called_once_with(mock_conn)


def test_execute_unknown_query(executor):
    ex, _, _, _ = executor
    with pytest.raises(ValueError, match="Unknown query"):
        ex.execute("nonexistent_query", {})


def test_execute_missing_param(executor):
    ex, _, _, _ = executor
    with pytest.raises(ValueError, match="Missing parameter"):
        ex.execute("top_customers_by_revenue", {"date_from": "2026-01-01"})


def test_execute_uses_fetchmany(executor):
    """Verify row limit safety net."""
    ex, mock_cursor, _, _ = executor
    ex.execute(
        "top_customers_by_revenue",
        {"date_from": "2026-01-01", "date_to": "2026-03-31",
         "ad_client_id": 11, "org_ids": [1], "limit": 5},
    )
    mock_cursor.fetchmany.assert_called_once_with(200)


def test_execute_converts_tuple_to_list(executor):
    """Verify org_ids tuple is converted to list for psycopg2."""
    ex, _, _, _ = executor
    # Should not raise even with tuple
    rows = ex.execute(
        "top_customers_by_revenue",
        {"date_from": "2026-01-01", "date_to": "2026-03-31",
         "ad_client_id": 11, "org_ids": (1, 2), "limit": 5},
    )
    assert len(rows) == 1
