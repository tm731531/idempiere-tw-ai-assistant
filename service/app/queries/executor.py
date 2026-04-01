# service/app/queries/executor.py
"""Query executor with connection pooling for read-only PostgreSQL access."""

import logging
import psycopg2
import psycopg2.pool
from app.queries.registry import get_query

MAX_ROWS = 200

# Pool is initialized by FastAPI lifespan, NOT at import time.
# This avoids crash if DB is not reachable when service starts.
pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool(host, port, dbname, user, password):
    """
    Initialize the database connection pool.
    Called by FastAPI lifespan on startup.
    """
    global pool
    pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1, maxconn=5,
        host=host, port=port, dbname=dbname,
        user=user, password=password,
        options="-c search_path=adempiere -c statement_timeout=10000",  # 10s timeout prevents runaway queries
    )


def close_pool():
    """
    Close all database connections.
    Called by FastAPI lifespan on shutdown.
    """
    global pool
    if pool:
        pool.closeall()
        pool = None


class QueryExecutor:
    """Execute pre-defined SQL queries against read-only PostgreSQL."""

    def execute(self, query_name: str, params: dict) -> list[dict]:
        """
        Execute a pre-defined query with the given parameters.
        
        Args:
            query_name: Name of the query from the registry
            params: Query parameters (must include ad_client_id, org_ids)
            
        Returns:
            List of result rows as dicts
            
        Raises:
            ValueError: If query unknown, parameter missing, or DB error
            RuntimeError: If pool not initialized
        """
        query_def = get_query(query_name)
        if query_def is None:
            raise ValueError(f"Unknown query: {query_name}")

        for p in query_def["params"]:
            if p not in params:
                raise ValueError(f"Missing parameter: {p}")

        # Ensure org_ids is list (not tuple) for psycopg2 ARRAY adaptation
        if "org_ids" in params and isinstance(params["org_ids"], tuple):
            params = {**params, "org_ids": list(params["org_ids"])}

        if pool is None:
            raise RuntimeError("Database pool not initialized")

        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query_def["sql"], params)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchmany(MAX_ROWS)  # Safety net: never return unbounded results
                return [dict(zip(columns, row)) for row in rows]
        except Exception as db_error:
            logger = logging.getLogger(__name__)
            logger.error("Query %s failed: %s", query_name, db_error)
            raise ValueError("Database query failed") from None  # strip traceback, no PII
        finally:
            pool.putconn(conn)
