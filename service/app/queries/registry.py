# service/app/queries/registry.py
"""Query registry for pre-defined SQL queries."""

from app.queries.definitions.sales import SALES_QUERIES

QUERY_REGISTRY: dict[str, dict] = {
    **SALES_QUERIES,
}


def get_query(name: str) -> dict | None:
    """Get a query definition by name."""
    return QUERY_REGISTRY.get(name)


def list_queries() -> dict[str, dict]:
    """List all registered queries."""
    return QUERY_REGISTRY


def get_query_descriptions() -> str:
    """Get formatted query descriptions for LLM prompt."""
    lines = []
    for name, q in QUERY_REGISTRY.items():
        params = ", ".join(q["params"])
        lines.append(f'- "{name}" (params: {params}): {q["description"]}')
    return "\n".join(lines)
