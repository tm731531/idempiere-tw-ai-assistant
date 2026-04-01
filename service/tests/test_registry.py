# service/tests/test_registry.py
"""Tests for query registry."""

from app.queries.registry import get_query, list_queries, get_query_descriptions


def test_list_queries_not_empty():
    queries = list_queries()
    assert len(queries) >= 3


def test_list_queries_has_required_fields():
    queries = list_queries()
    for name, q in queries.items():
        assert "description" in q, f"{name} missing description"
        assert "sql" in q, f"{name} missing sql"
        assert "params" in q, f"{name} missing params"
        assert "pii_columns" in q, f"{name} missing pii_columns"


def test_get_query_existing():
    q = get_query("top_customers_by_revenue")
    assert q is not None
    assert "SELECT" in q["sql"]


def test_get_query_nonexistent():
    q = get_query("does_not_exist")
    assert q is None


def test_query_descriptions_for_llm():
    descriptions = get_query_descriptions()
    assert len(descriptions) >= 3
    assert "top_customers_by_revenue" in descriptions
    assert "params:" in descriptions


def test_all_queries_have_org_ids():
    """All queries must filter by AD_Org_ID for security."""
    queries = list_queries()
    for name, q in queries.items():
        assert "org_ids" in q["params"], f"{name} missing org_ids param"
        assert "AD_Org_ID" in q["sql"], f"{name} missing AD_Org_ID filter in SQL"
