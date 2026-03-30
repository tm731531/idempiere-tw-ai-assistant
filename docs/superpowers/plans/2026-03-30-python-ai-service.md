# Python AI Service — Implementation Plan (Rev 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI service that receives natural language questions, queries iDempiere's PostgreSQL with pre-defined SQL, masks PII, calls external LLMs, and returns answers with PII restored.

**Architecture:** FastAPI receives HMAC-authenticated requests from iDempiere plugin via HTTP POST. Sonnet classifies questions and selects pre-defined SQL in a single call. Queries run against a read-only PostgreSQL account with org-level filtering. PII is masked before LLM calls and restored after. All LLM calls are async via `asyncio.to_thread()`. Security-sensitive params (`ad_client_id`, `org_ids`) are always injected from the request context, never from LLM output.

**Tech Stack:** Python 3.11+, FastAPI, langchain-anthropic, langchain-groq, psycopg2 + ThreadedConnectionPool, pydantic, pytest

**Design Spec:** `docs/superpowers/specs/2026-03-30-idempiere-tw-ai-assistant-design.md` (Rev 4)

---

## Project Structure

```
idempiere-tw-ai-assistant/            # Monorepo
├── plugin/                        # Java iDempiere Plugin (Plan B — later)
├── service/                       # Python AI Service (this plan)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI + HMAC auth + rate limit + /ask + /health
│   │   ├── config.py              # Settings from env vars
│   │   ├── router.py              # Classify → tool select → query → mask → LLM → unmask
│   │   ├── queries/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py        # QUERY_REGISTRY dict + lookup
│   │   │   ├── executor.py        # PostgreSQL read-only + connection pool
│   │   │   └── definitions/
│   │   │       ├── __init__.py
│   │   │       └── sales.py       # Sales queries (all with org_ids filter)
│   │   ├── masking/
│   │   │   ├── __init__.py
│   │   │   ├── masker.py          # PIIMasker with [PII_*] tokens
│   │   │   └── rules.py           # PII column rules
│   │   └── llm/
│   │       ├── __init__.py
│   │       ├── caller.py          # LLM call + fallback + token usage extraction
│   │       └── prompts.py         # System prompts (with [PII_*] format)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py            # Shared fixtures
│   │   ├── test_masking.py
│   │   ├── test_registry.py
│   │   ├── test_executor.py
│   │   ├── test_caller.py
│   │   ├── test_router.py
│   │   └── test_integration.py
│   ├── .env.example
│   ├── requirements.txt
│   └── CLAUDE.md
├── scripts/
│   └── create_readonly_user.sql
├── .gitignore
├── CLAUDE.md
└── AGENTS.md
```

---

### Task 1: Project Scaffold + Config

**Files:**
- Create: `service/requirements.txt`
- Create: `service/.env.example`
- Create: `service/app/__init__.py`
- Create: `service/app/config.py`
- Create: `service/tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create directories and requirements.txt**

```bash
mkdir -p /home/tom/idempiere-tw-ai-assistant/service/{app/{queries/definitions,masking,llm,models},tests}
```

```
# service/requirements.txt
fastapi>=0.115
uvicorn>=0.34
langchain-anthropic>=0.3
langchain-groq>=0.2
psycopg2-binary>=2.9
python-dotenv>=1.0
pydantic>=2.0
pytest>=8.0
httpx>=0.27
```

- [ ] **Step 2: Create .env.example**

```
# service/.env.example
ANTHROPIC_API_KEY=sk-ant-xxxx
GROQ_API_KEY=gsk_xxxx
DB_HOST=localhost
DB_PORT=5432
DB_NAME=idempiere
DB_USER=ai_readonly
DB_PASSWORD=xxxx
HMAC_SECRET=change-me-to-a-random-string
SERVICE_PORT=8900
```

- [ ] **Step 3: Create .gitignore (project root)**

```
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 4: Create app/config.py**

```python
# service/app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
HMAC_SECRET = os.environ["HMAC_SECRET"]

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "idempiere")
DB_USER = os.getenv("DB_USER", "ai_readonly")
DB_PASSWORD = os.environ["DB_PASSWORD"]

SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8900"))
```

- [ ] **Step 5: Create empty __init__.py files and conftest.py**

```bash
touch /home/tom/idempiere-tw-ai-assistant/service/app/__init__.py
touch /home/tom/idempiere-tw-ai-assistant/service/tests/__init__.py
```

Create conftest.py NOW (not in Task 6) — Tasks 4+ will crash without it because
`config.py` reads `os.environ["ANTHROPIC_API_KEY"]` at import time.

```python
# service/tests/conftest.py
import os

# Set test env vars BEFORE any app module is imported.
# config.py uses os.environ[] (hard crash), so these must exist.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("HMAC_SECRET", "test-secret")
os.environ.setdefault("DB_PASSWORD", "test-pass")
```

- [ ] **Step 6: Install dependencies and verify**

```bash
cd /home/tom/idempiere-tw-ai-assistant/service
pip install -r requirements.txt
python -c "import fastapi, psycopg2; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
cd /home/tom/idempiere-tw-ai-assistant
git add -A
git commit -m "feat: project scaffold with config, HMAC secret, and dependencies"
```

---

### Task 2: PII Masking Layer

**Files:**
- Create: `service/app/masking/__init__.py`
- Create: `service/app/masking/rules.py`
- Create: `service/app/masking/masker.py`
- Create: `service/tests/test_masking.py`

- [ ] **Step 1: Write masking tests**

```python
# service/tests/test_masking.py
from app.masking.masker import PIIMasker
from app.masking.rules import PII_COLUMN_RULES


def test_mask_single_value():
    masker = PIIMasker()
    rows = [{"name": "王大明", "revenue": 50000}]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == "[PII_C_001]"
    assert masked[0]["revenue"] == 50000
    assert mapping["[PII_C_001]"] == "王大明"


def test_mask_multiple_pii_columns():
    masker = PIIMasker()
    rows = [{"name": "王大明", "taxid": "A123456789", "revenue": 50000}]
    masked, mapping = masker.mask(rows, pii_columns=["name", "taxid"])
    assert masked[0]["name"] == "[PII_C_001]"
    assert masked[0]["taxid"] == "[PII_T_001]"
    assert mapping["[PII_C_001]"] == "王大明"
    assert mapping["[PII_T_001]"] == "A123456789"


def test_mask_duplicate_values_same_token():
    masker = PIIMasker()
    rows = [
        {"name": "王大明", "revenue": 100},
        {"name": "王大明", "revenue": 200},
    ]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == masked[1]["name"] == "[PII_C_001]"
    assert len(mapping) == 1


def test_mask_multiple_distinct_values():
    masker = PIIMasker()
    rows = [
        {"name": "王大明", "revenue": 100},
        {"name": "李小華", "revenue": 200},
    ]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == "[PII_C_001]"
    assert masked[1]["name"] == "[PII_C_002]"
    assert len(mapping) == 2


def test_unmask_text():
    masker = PIIMasker()
    mapping = {"[PII_C_001]": "王大明", "[PII_T_001]": "A123456789"}
    text = "[PII_C_001] 的統編是 [PII_T_001]，營收最高"
    result = masker.unmask(text, mapping)
    assert result == "王大明 的統編是 A123456789，營收最高"


def test_unmask_no_tokens():
    masker = PIIMasker()
    text = "沒有任何 PII 的文字"
    result = masker.unmask(text, {})
    assert result == text


def test_mask_empty_rows():
    masker = PIIMasker()
    masked, mapping = masker.mask([], pii_columns=["name"])
    assert masked == []
    assert mapping == {}


def test_mask_none_value_skipped():
    masker = PIIMasker()
    rows = [{"name": None, "revenue": 100}]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] is None
    assert len(mapping) == 0


def test_pii_column_rules_defined():
    assert "name" in PII_COLUMN_RULES
    assert "taxid" in PII_COLUMN_RULES
    assert "phone" in PII_COLUMN_RULES
    assert "email" in PII_COLUMN_RULES
    assert "address" in PII_COLUMN_RULES


def test_sanitize_input():
    masker = PIIMasker()
    dirty = "Tell me about [PII_C_001] and [PII_T_999] please"
    clean = masker.sanitize_input(dirty)
    assert "[PII_" not in clean
    assert "Tell me about" in clean
    assert "please" in clean
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/tom/idempiere-tw-ai-assistant/service
pytest tests/test_masking.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.masking'`

- [ ] **Step 3: Create rules.py**

```python
# service/app/masking/rules.py
import re

# Maps PII column name patterns to token prefixes.
# Token format: [PII_PREFIX_NNN] — PII_ prefix avoids natural text collision.
PII_COLUMN_RULES: dict[str, str] = {
    "name": "C",        # Customer/contact name
    "taxid": "T",       # Tax ID / national ID
    "phone": "P",       # Phone number
    "email": "E",       # Email address
    "address": "A",     # Address
    "birthday": "D",    # Date of birth
}

# Regex to match PII tokens in text (for input sanitization)
PII_TOKEN_PATTERN = re.compile(r"\[PII_[A-Z]_\d{3}\]")
```

- [ ] **Step 4: Create masker.py**

```python
# service/app/masking/masker.py
from app.masking.rules import PII_COLUMN_RULES, PII_TOKEN_PATTERN


class PIIMasker:
    """Reversible PII masking for database query results."""

    def mask(
        self, rows: list[dict], pii_columns: list[str]
    ) -> tuple[list[dict], dict[str, str]]:
        """Replace PII values with tokens. Returns (masked_rows, token_to_original_mapping)."""
        mapping: dict[str, str] = {}
        reverse: dict[str, str] = {}
        counters: dict[str, int] = {}

        masked_rows = []
        for row in rows:
            masked_row = dict(row)
            for col in pii_columns:
                val = row.get(col)
                if val is None:
                    continue
                str_val = str(val)

                if str_val in reverse:
                    masked_row[col] = reverse[str_val]
                else:
                    prefix = PII_COLUMN_RULES.get(col.lower(), "X")
                    counters.setdefault(prefix, 0)
                    counters[prefix] += 1
                    token = f"[PII_{prefix}_{counters[prefix]:03d}]"
                    mapping[token] = str_val
                    reverse[str_val] = token
                    masked_row[col] = token
            masked_rows.append(masked_row)

        return masked_rows, mapping

    def unmask(self, text: str, mapping: dict[str, str]) -> str:
        """Replace tokens in text back to original PII values."""
        result = text
        for token, original in mapping.items():
            result = result.replace(token, original)
        return result

    def sanitize_input(self, text: str) -> str:
        """Strip PII token patterns from user input to prevent prompt injection."""
        return PII_TOKEN_PATTERN.sub("", text).strip()
```

- [ ] **Step 5: Create __init__.py**

```bash
touch /home/tom/idempiere-tw-ai-assistant/service/app/masking/__init__.py
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_masking.py -v
```
Expected: 10 passed

- [ ] **Step 7: Commit**

```bash
cd /home/tom/idempiere-tw-ai-assistant
git add service/app/masking/ service/tests/test_masking.py
git commit -m "feat: PII masking layer with [PII_*] tokens and input sanitization"
```

---

### Task 3: Query Registry + Executor

**Files:**
- Create: `service/app/queries/__init__.py`
- Create: `service/app/queries/registry.py`
- Create: `service/app/queries/definitions/__init__.py`
- Create: `service/app/queries/definitions/sales.py`
- Create: `service/app/queries/executor.py`
- Create: `service/tests/test_registry.py`
- Create: `service/tests/test_executor.py`

- [ ] **Step 1: Write registry tests**

```python
# service/tests/test_registry.py
from app.queries.registry import get_query, list_queries


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
    queries = list_queries()
    for name, q in queries.items():
        assert len(q["description"]) >= 10, f"{name} description too short"


def test_all_queries_have_org_ids():
    """All queries must filter by AD_Org_ID for security."""
    queries = list_queries()
    for name, q in queries.items():
        assert "org_ids" in q["params"], f"{name} missing org_ids param"
        assert "AD_Org_ID" in q["sql"], f"{name} missing AD_Org_ID filter in SQL"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_registry.py -v
```
Expected: FAIL

- [ ] **Step 3: Create sales.py query definitions (all with org_ids filter)**

```python
# service/app/queries/definitions/sales.py

SALES_QUERIES = {
    "top_customers_by_revenue": {
        "description": "Find the top N customers ranked by total revenue within a date range. Use when user asks about best customers, highest revenue, or top buyers.",
        "sql": """
            SELECT bp.Name, bp.TaxID, SUM(ol.LineNetAmt) as Revenue,
                   COUNT(DISTINCT o.C_Order_ID) as OrderCount
            FROM C_OrderLine ol
            JOIN C_Order o ON o.C_Order_ID = ol.C_Order_ID
            JOIN C_BPartner bp ON bp.C_BPartner_ID = o.C_BPartner_ID
            WHERE o.DateOrdered BETWEEN %(date_from)s AND %(date_to)s
              AND o.DocStatus IN ('CO','CL')
              AND o.AD_Client_ID = %(ad_client_id)s
              AND o.AD_Org_ID = ANY(%(org_ids)s)
            GROUP BY bp.Name, bp.TaxID
            ORDER BY Revenue DESC
            LIMIT %(limit)s
        """,
        "params": ["date_from", "date_to", "ad_client_id", "org_ids", "limit"],
        "pii_columns": ["name", "taxid"],
    },
    "order_status_by_documentno": {
        "description": "Look up a specific order by its document number. Use when user asks about order status, order details, or references a document number.",
        "sql": """
            SELECT o.DocumentNo, o.DateOrdered, o.DocStatus,
                   o.GrandTotal, bp.Name, o.Description
            FROM C_Order o
            JOIN C_BPartner bp ON bp.C_BPartner_ID = o.C_BPartner_ID
            WHERE o.DocumentNo = %(document_no)s
              AND o.AD_Client_ID = %(ad_client_id)s
              AND o.AD_Org_ID = ANY(%(org_ids)s)
        """,
        "params": ["document_no", "ad_client_id", "org_ids"],
        "pii_columns": ["name"],
    },
    "monthly_revenue_summary": {
        "description": "Get monthly revenue summary for a given year. Use when user asks about monthly trends, revenue over time, or yearly performance.",
        "sql": """
            SELECT TO_CHAR(o.DateOrdered, 'YYYY-MM') as Month,
                   SUM(o.GrandTotal) as Revenue,
                   COUNT(*) as OrderCount
            FROM C_Order o
            WHERE EXTRACT(YEAR FROM o.DateOrdered) = %(year)s
              AND o.DocStatus IN ('CO','CL')
              AND o.AD_Client_ID = %(ad_client_id)s
              AND o.AD_Org_ID = ANY(%(org_ids)s)
            GROUP BY TO_CHAR(o.DateOrdered, 'YYYY-MM')
            ORDER BY Month
        """,
        "params": ["year", "ad_client_id", "org_ids"],
        "pii_columns": [],
    },
}
```

- [ ] **Step 4: Create registry.py**

```python
# service/app/queries/registry.py
from app.queries.definitions.sales import SALES_QUERIES

QUERY_REGISTRY: dict[str, dict] = {
    **SALES_QUERIES,
}


def get_query(name: str) -> dict | None:
    return QUERY_REGISTRY.get(name)


def list_queries() -> dict[str, dict]:
    return QUERY_REGISTRY


def get_query_descriptions() -> str:
    lines = []
    for name, q in QUERY_REGISTRY.items():
        params = ", ".join(q["params"])
        lines.append(f'- "{name}" (params: {params}): {q["description"]}')
    return "\n".join(lines)
```

- [ ] **Step 5: Create __init__.py files**

```bash
touch /home/tom/idempiere-tw-ai-assistant/service/app/queries/__init__.py
touch /home/tom/idempiere-tw-ai-assistant/service/app/queries/definitions/__init__.py
```

- [ ] **Step 6: Run registry tests**

```bash
pytest tests/test_registry.py -v
```
Expected: 6 passed

- [ ] **Step 7: Write executor tests**

```python
# service/tests/test_executor.py
import pytest
from unittest.mock import patch, MagicMock
import app.queries.executor as executor_module
from app.queries.executor import QueryExecutor


@pytest.fixture
def executor():
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
```

- [ ] **Step 8: Create executor.py (with connection pool)**

```python
# service/app/queries/executor.py
import psycopg2
import psycopg2.pool
from app.queries.registry import get_query

MAX_ROWS = 200

# Pool is initialized by FastAPI lifespan, NOT at import time.
# This avoids crash if DB is not reachable when service starts.
pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool(host, port, dbname, user, password):
    """Called by FastAPI lifespan on startup."""
    global pool
    pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1, maxconn=5,
        host=host, port=port, dbname=dbname,
        user=user, password=password,
        options="-c search_path=adempiere",  # iDempiere tables are in adempiere schema
    )


def close_pool():
    """Called by FastAPI lifespan on shutdown."""
    global pool
    if pool:
        pool.closeall()
        pool = None


class QueryExecutor:
    """Execute pre-defined SQL queries against read-only PostgreSQL."""

    def execute(self, query_name: str, params: dict) -> list[dict]:
        query_def = get_query(query_name)
        if query_def is None:
            raise ValueError(f"Unknown query: {query_name}")

        for p in query_def["params"]:
            if p not in params:
                raise ValueError(f"Missing parameter: {p}")

        # Ensure org_ids is list (not tuple) for psycopg2 ARRAY adaptation
        if "org_ids" in params and isinstance(params["org_ids"], tuple):
            params = {**params, "org_ids": list(params["org_ids"])}

        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query_def["sql"], params)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchmany(MAX_ROWS)  # Safety net: never return unbounded results
                return [dict(zip(columns, row)) for row in rows]
        finally:
            pool.putconn(conn)
```

- [ ] **Step 9: Run executor tests**

```bash
pytest tests/test_executor.py -v
```
Expected: 5 passed

- [ ] **Step 10: Commit**

```bash
cd /home/tom/idempiere-tw-ai-assistant
git add service/app/queries/ service/tests/test_registry.py service/tests/test_executor.py
git commit -m "feat: query registry with org_ids filter and connection-pooled executor"
```

---

### Task 4: LLM Caller with Fallback + Token Usage

**Files:**
- Create: `service/app/llm/__init__.py`
- Create: `service/app/llm/prompts.py`
- Create: `service/app/llm/caller.py`
- Create: `service/tests/test_caller.py`

- [ ] **Step 1: Write caller tests**

```python
# service/tests/test_caller.py
import pytest
from unittest.mock import patch, MagicMock
from app.llm.caller import LLMCaller


@pytest.fixture
def mock_models():
    with patch("app.llm.caller.ChatAnthropic") as mock_anth, \
         patch("app.llm.caller.ChatGroq") as mock_groq:
        mock_sonnet = MagicMock()
        mock_llama70b = MagicMock()
        mock_llama8b = MagicMock()
        mock_anth.return_value = mock_sonnet
        mock_groq.side_effect = [mock_llama70b, mock_llama8b]
        caller = LLMCaller()
        yield caller, mock_sonnet, mock_llama70b, mock_llama8b


def _make_response(content, input_tokens=100, output_tokens=50):
    resp = MagicMock()
    resp.content = content
    resp.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return resp


def test_call_returns_content_and_tokens(mock_models):
    caller, mock_sonnet, _, _ = mock_models
    mock_sonnet.invoke.return_value = _make_response("Sonnet answer", 100, 50)
    content, tokens = caller.call("sonnet", "system", "question")
    assert content == "Sonnet answer"
    assert tokens == 150


def test_call_llama_70b(mock_models):
    caller, _, mock_llama70b, _ = mock_models
    mock_llama70b.invoke.return_value = _make_response("Llama answer", 80, 40)
    content, tokens = caller.call("llama_70b", "system", "question")
    assert content == "Llama answer"
    assert tokens == 120


def test_fallback_sonnet_to_llama(mock_models):
    caller, mock_sonnet, mock_llama70b, _ = mock_models
    mock_sonnet.invoke.side_effect = Exception("API down")
    mock_llama70b.invoke.return_value = _make_response("Fallback answer")
    content, tokens = caller.call("sonnet", "system", "question")
    assert content == "Fallback answer"


def test_both_fail_raises(mock_models):
    caller, mock_sonnet, mock_llama70b, _ = mock_models
    mock_sonnet.invoke.side_effect = Exception("API down")
    mock_llama70b.invoke.side_effect = Exception("Also down")
    with pytest.raises(RuntimeError, match="All models failed"):
        caller.call("sonnet", "system", "question")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_caller.py -v
```
Expected: FAIL

- [ ] **Step 3: Create prompts.py (with [PII_*] format)**

```python
# service/app/llm/prompts.py

CLASSIFY_AND_SELECT_PROMPT = """You are an ERP data assistant. Given a user question and available queries, classify the question AND select the best query in ONE step.

Available pre-defined queries:
{query_descriptions}

Step 1 — Classify the question:
- "database_query": needs data from database (revenue, orders, customers, inventory)
- "general_knowledge": conceptual question, no database needed
- "clarification": question too vague, need more details

Step 2 — If database_query, select the best matching query and extract parameters:
- For date_from/date_to: infer from "上個月", "今年", etc. Use ISO format YYYY-MM-DD
- For limit: default to 10 if not specified
- Do NOT include ad_client_id or org_ids in params (they are injected by the system)
- If no query matches, set query_name to "none"

Respond with ONLY valid JSON:
{{"category": "database_query|general_knowledge|clarification", "query_name": "exact_name_or_none", "params": {{}}, "reason": "brief"}}"""


ANSWERER_PROMPT = """You are a helpful ERP data analyst. Answer the user's question based on the query results provided.

Rules:
- Be concise and direct
- If the user asks in Chinese, reply in Chinese
- Format numbers with commas for readability
- If the data is empty, say so clearly
- Do not make up data that isn't in the results
- Reference entities by their identifiers as shown in the data (these may be masked tokens like [PII_C_001])"""


CLARIFICATION_PROMPT = """The user's question is too vague to answer. Ask them to be more specific.
Reply in the same language as the user's question. Be brief and friendly."""
```

- [ ] **Step 4: Create caller.py (with token usage extraction)**

```python
# service/app/llm/caller.py
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import ANTHROPIC_API_KEY, GROQ_API_KEY

FALLBACK_CHAIN = {
    "sonnet": "llama_70b",
    "llama_70b": "sonnet",
    "llama_8b": "llama_70b",
}


class LLMCaller:
    """Call LLMs with automatic fallback. Returns (content, total_tokens)."""

    def __init__(self):
        self.models = {
            "sonnet": ChatAnthropic(
                model="claude-sonnet-4-6", max_tokens=4096,
                api_key=ANTHROPIC_API_KEY, timeout=25.0,
            ),
            "llama_70b": ChatGroq(
                model="llama-3.3-70b-versatile", max_tokens=4096,
                api_key=GROQ_API_KEY, timeout=25.0,
            ),
            "llama_8b": ChatGroq(
                model="llama-3.1-8b-instant", max_tokens=2048,
                api_key=GROQ_API_KEY, timeout=25.0,
            ),
        }

    def call(self, model_name: str, system_prompt: str, user_message: str) -> tuple[str, int]:
        """Call a model with fallback. Returns (content, total_tokens)."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        try:
            response = self.models[model_name].invoke(messages)
            return response.content, self._extract_tokens(response)
        except Exception as primary_err:
            fallback = FALLBACK_CHAIN.get(model_name)
            if fallback is None:
                raise RuntimeError(f"All models failed: {primary_err}")
            try:
                response = self.models[fallback].invoke(messages)
                return response.content, self._extract_tokens(response)
            except Exception as fallback_err:
                raise RuntimeError(
                    f"All models failed: primary({model_name})={primary_err}, "
                    f"fallback({fallback})={fallback_err}"
                )

    def _extract_tokens(self, response) -> int:
        """Extract total token usage from LLM response metadata."""
        meta = getattr(response, "usage_metadata", None)
        if meta and isinstance(meta, dict):
            return meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
        return 0
```

- [ ] **Step 5: Create __init__.py**

```bash
touch /home/tom/idempiere-tw-ai-assistant/service/app/llm/__init__.py
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_caller.py -v
```
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
cd /home/tom/idempiere-tw-ai-assistant
git add service/app/llm/ service/tests/test_caller.py
git commit -m "feat: LLM caller with fallback and token usage extraction"
```

---

### Task 5: Router Pipeline

**Files:**
- Create: `service/app/router.py`
- Create: `service/app/models/__init__.py`
- Create: `service/app/models/schemas.py`
- Create: `service/tests/test_router.py`

- [ ] **Step 1: Create pydantic schemas (with org_ids)**

```python
# service/app/models/schemas.py
from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    user_id: int
    role_id: int
    client_id: int
    org_ids: list[int]
    # session_id and history removed in Phase 1 — each question is independent.
    # Will be added in Phase 2 when conversation continuity is implemented.


class AskResponse(BaseModel):
    answer: str
    model_used: str
    tokens_used: int
    query_used: str | None
    elapsed_ms: int
```

```bash
touch /home/tom/idempiere-tw-ai-assistant/service/app/models/__init__.py
```

- [ ] **Step 2: Write router tests (with sanitization and [PII_*] tokens)**

```python
# service/tests/test_router.py
import pytest
from unittest.mock import patch, MagicMock
import app.router as router_module


@pytest.fixture
def mock_deps():
    """Mock the lazy-init singletons by injecting mocks directly."""
    mock_caller = MagicMock()
    mock_caller.call.return_value = ("", 0)
    mock_executor = MagicMock()

    # Inject mocks into module-level lazy-init vars
    router_module._caller = mock_caller
    router_module._executor = mock_executor
    yield mock_caller, mock_executor

    # Cleanup
    router_module._caller = None
    router_module._executor = None


def test_general_knowledge_no_db(mock_deps):
    caller, executor = mock_deps
    # ONE call: classify+select returns general_knowledge
    # TWO call: Sonnet answers the question
    caller.call.side_effect = [
        ('{"category": "general_knowledge", "query_name": "none", "params": {}, "reason": "concept"}', 10),
        ("Docker is a containerization platform.", 50),
    ]

    result = router_module.process_question("What is Docker?", client_id=11, org_ids=[1])
    assert result["answer"] == "Docker is a containerization platform."
    assert result["query_used"] is None
    assert result["tokens_used"] == 60
    executor.execute.assert_not_called()


def test_database_query_with_masking(mock_deps):
    caller, executor = mock_deps
    # ONE call: classify+select returns database_query with query
    # TWO call: Sonnet answers with masked data
    caller.call.side_effect = [
        ('{"category": "database_query", "query_name": "top_customers_by_revenue", "params": {"date_from": "2026-02-01", "date_to": "2026-02-28", "limit": 5}, "reason": "matches"}', 20),
        ("[PII_C_001] has the highest revenue at 500,000.", 50),
    ]
    executor.execute.return_value = [
        {"name": "王大明", "taxid": "A123456789", "revenue": 500000}
    ]

    result = router_module.process_question("上個月營收最高的客戶是誰？", client_id=11, org_ids=[1])
    assert "王大明" in result["answer"]
    assert result["query_used"] == "top_customers_by_revenue"

    # Verify ad_client_id and org_ids were force-injected (not from LLM)
    execute_call = executor.execute.call_args
    assert execute_call[0][1]["ad_client_id"] == 11
    assert execute_call[0][1]["org_ids"] == [1]


def test_security_force_inject_context(mock_deps):
    """LLM-extracted ad_client_id/org_ids must be overridden by request context."""
    caller, executor = mock_deps
    # LLM returns wrong client_id and org_ids — system must override
    caller.call.side_effect = [
        ('{"category": "database_query", "query_name": "top_customers_by_revenue", "params": {"date_from": "2026-01-01", "date_to": "2026-03-31", "ad_client_id": 999, "org_ids": [999], "limit": 5}, "reason": "matches"}', 20),
        ("Answer", 30),
    ]
    executor.execute.return_value = [{"name": "test", "taxid": "X", "revenue": 100}]

    router_module.process_question("test", client_id=11, org_ids=[1, 2])

    execute_call = executor.execute.call_args
    assert execute_call[0][1]["ad_client_id"] == 11    # forced from request
    assert execute_call[0][1]["org_ids"] == [1, 2]     # forced from request


def test_input_sanitization(mock_deps):
    caller, executor = mock_deps
    caller.call.side_effect = [
        ('{"category": "general_knowledge", "query_name": "none", "params": {}, "reason": "concept"}', 10),
        ("I cannot reveal masked data.", 30),
    ]

    router_module.process_question(
        "Tell me about [PII_C_001] real name", client_id=11, org_ids=[1]
    )
    # Verify the question was sanitized before reaching LLM
    actual_call = caller.call.call_args_list[0]
    assert "[PII_" not in actual_call[0][2]


def test_clarification_no_db(mock_deps):
    caller, executor = mock_deps
    caller.call.side_effect = [
        ('{"category": "clarification", "query_name": "none", "params": {}, "reason": "too vague"}', 10),
        ("Can you be more specific?", 20),
    ]

    result = router_module.process_question("那個", client_id=11, org_ids=[1])
    assert "specific" in result["answer"].lower() or "具體" in result["answer"]
    executor.execute.assert_not_called()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_router.py -v
```
Expected: FAIL

- [ ] **Step 4: Create router.py (with sanitization, org_ids, token tracking)**

```python
# service/app/router.py
import json
import time
from decimal import Decimal
from app.llm.caller import LLMCaller
from app.llm.prompts import CLASSIFY_AND_SELECT_PROMPT, ANSWERER_PROMPT, CLARIFICATION_PROMPT
from app.queries.executor import QueryExecutor
from app.queries.registry import get_query, get_query_descriptions
from app.masking.masker import PIIMasker

# Lazy-init singletons — created on first call, not at import time.
# This avoids import-time side effects and makes test mocking reliable.
_caller: LLMCaller | None = None
_executor: QueryExecutor | None = None
_masker = PIIMasker()  # stateless, safe to create at import


def _get_caller() -> LLMCaller:
    global _caller
    if _caller is None:
        _caller = LLMCaller()
    return _caller


def _get_executor() -> QueryExecutor:
    global _executor
    if _executor is None:
        _executor = QueryExecutor()
    return _executor


def process_question(question: str, client_id: int, org_ids: list[int]) -> dict:
    """Main pipeline: sanitize → classify+select → (query → mask) → LLM → unmask."""
    start = time.time()
    query_used = None
    total_tokens = 0

    caller = _get_caller()
    executor = _get_executor()

    # Step 0: Sanitize input — strip PII token patterns
    clean_question = _masker.sanitize_input(question)

    # Step 1: Classify AND select query in ONE Sonnet call (not 2 separate calls).
    # Phase 1 has only 3 queries — a separate classifier is overkill.
    selector_prompt = CLASSIFY_AND_SELECT_PROMPT.format(
        query_descriptions=get_query_descriptions()
    )
    context = f"Question: {clean_question}"
    selection_raw, tokens = caller.call("sonnet", selector_prompt, context)
    total_tokens += tokens

    try:
        selection = json.loads(selection_raw.strip())
        category = selection.get("category", "general_knowledge")
        query_name = selection.get("query_name", "none")
        params = selection.get("params", {})
    except json.JSONDecodeError:
        category = "general_knowledge"
        query_name = "none"
        params = {}

    # Step 2: Handle by category
    if category == "clarification":
        answer, tokens = caller.call("llama_8b", CLARIFICATION_PROMPT, clean_question)
        total_tokens += tokens
        model_used = "llama_8b"

    elif category == "database_query" and query_name != "none" and get_query(query_name) is not None:
        # SECURITY: Force-inject ad_client_id and org_ids from request context.
        # NEVER trust LLM-extracted values for these — they could be hallucinated or injected.
        params["ad_client_id"] = client_id
        params["org_ids"] = org_ids

        query_def = get_query(query_name)
        rows = executor.execute(query_name, params)
        query_used = query_name

        # Mask PII
        masked_rows, mapping = _masker.mask(rows, query_def["pii_columns"])

        # Call LLM with masked data (Decimal→float for proper JSON numbers)
        def _json_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            return str(obj)

        data_text = json.dumps(masked_rows, ensure_ascii=False, default=_json_default)
        prompt = f"Question: {clean_question}\n\nQuery results:\n{data_text}"
        masked_answer, tokens = caller.call("sonnet", ANSWERER_PROMPT, prompt)
        total_tokens += tokens
        model_used = "sonnet"

        # Unmask PII in answer
        answer = _masker.unmask(masked_answer, mapping)
    else:
        # general_knowledge or no matching query
        answer, tokens = caller.call("sonnet", ANSWERER_PROMPT, clean_question)
        total_tokens += tokens
        model_used = "sonnet"

    elapsed_ms = int((time.time() - start) * 1000)

    return {
        "answer": answer,
        "model_used": model_used,
        "tokens_used": total_tokens,
        "query_used": query_used,
        "elapsed_ms": elapsed_ms,
    }
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_router.py -v
```
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
cd /home/tom/idempiere-tw-ai-assistant
git add service/app/router.py service/app/models/ service/tests/test_router.py
git commit -m "feat: router pipeline with input sanitization, org_ids, and token tracking"
```

---

### Task 6: FastAPI Endpoint + HMAC Auth + Rate Limit

**Files:**
- Create: `service/app/main.py`
- Create: `service/tests/conftest.py`
- Create: `service/tests/test_integration.py`

- [ ] **Step 1: conftest.py already created in Task 1. No action needed.**

- [ ] **Step 2: Write integration tests (with HMAC)**

```python
# service/tests/test_integration.py
import hmac
import hashlib
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import app.router as router_module


def _make_signed_request(body: dict, secret: str = "test-secret") -> tuple[bytes, str]:
    """Serialize body and compute HMAC on the exact bytes that will be sent."""
    body_bytes = json.dumps(body).encode()
    sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return body_bytes, sig


@pytest.fixture
def client():
    """Create test client with lifespan patched to skip real DB connection."""
    with patch("app.main.init_pool"), patch("app.main.close_pool"):
        from app.main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture
def mock_router():
    """Inject mock caller/executor into router module."""
    mock_caller = MagicMock()
    mock_executor = MagicMock()
    router_module._caller = mock_caller
    router_module._executor = mock_executor
    yield mock_caller, mock_executor
    router_module._caller = None
    router_module._executor = None


def test_ask_with_valid_hmac(client, mock_router):
    caller, executor = mock_router
    caller.call.side_effect = [
        ('{"category": "general_knowledge", "query_name": "none", "params": {}, "reason": "concept"}', 10),
        ("Docker is a container platform.", 50),
    ]

    body = {"question": "What is Docker?", "user_id": 100, "role_id": 200,
            "client_id": 11, "org_ids": [1]}
    body_bytes, sig = _make_signed_request(body)
    response = client.post("/ask", content=body_bytes,
                           headers={"X-HMAC-Signature": sig, "Content-Type": "application/json"})
    assert response.status_code == 200
    assert "Docker" in response.json()["answer"]


def test_ask_without_hmac_rejected(client):
    body_bytes = json.dumps({"question": "Hello", "user_id": 100, "role_id": 200,
                             "client_id": 11, "org_ids": [1]}).encode()
    response = client.post("/ask", content=body_bytes,
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 401


def test_ask_with_wrong_hmac_rejected(client):
    body_bytes = json.dumps({"question": "Hello", "user_id": 100, "role_id": 200,
                             "client_id": 11, "org_ids": [1]}).encode()
    response = client.post("/ask", content=body_bytes,
                           headers={"X-HMAC-Signature": "wrong", "Content-Type": "application/json"})
    assert response.status_code == 401


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_error_returns_generic_message(client, mock_router):
    caller, _ = mock_router
    caller.call.side_effect = Exception("Secret PII data: 王大明")

    body = {"question": "test", "user_id": 100, "role_id": 200,
            "client_id": 11, "org_ids": [1]}
    body_bytes, sig = _make_signed_request(body)
    response = client.post("/ask", content=body_bytes,
                           headers={"X-HMAC-Signature": sig, "Content-Type": "application/json"})
    assert response.status_code == 500
    assert "王大明" not in response.json()["detail"]
    assert "Request processing failed" in response.json()["detail"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_integration.py -v
```
Expected: FAIL

- [ ] **Step 4: Create main.py (with HMAC auth, rate limit, generic errors, async)**

```python
# service/app/main.py
import hmac
import hashlib
import json
import time
import asyncio
import logging
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from app.models.schemas import AskRequest, AskResponse
from app.router import process_question
from app.config import HMAC_SECRET, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB pool on startup, close on shutdown."""
    from app.queries.executor import init_pool, close_pool
    init_pool(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
    logger.info("DB connection pool initialized (search_path=adempiere)")
    yield
    close_pool()
    logger.info("DB connection pool closed")


app = FastAPI(
    title="iDempiere AI Service",
    description="AI assistant backend for iDempiere ERP",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter: max 20 requests per user per minute
RATE_LIMIT = 20
RATE_WINDOW = 60  # seconds
_request_log: dict[int, deque] = defaultdict(deque)


def _verify_hmac(body_bytes: bytes, signature: str) -> bool:
    expected = hmac.new(HMAC_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _check_rate_limit(user_id: int) -> bool:
    now = time.time()
    log = _request_log[user_id]
    while log and log[0] < now - RATE_WINDOW:
        log.popleft()
    if len(log) >= RATE_LIMIT:
        return False
    log.append(now)
    return True


@app.post("/ask", response_model=AskResponse)
async def ask(request: Request):
    """Process a natural language question about ERP data."""
    # Read raw body for HMAC verification
    body_bytes = await request.body()

    # Verify HMAC signature
    signature = request.headers.get("X-HMAC-Signature", "")
    if not signature or not _verify_hmac(body_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid or missing HMAC signature")

    # Parse request
    req = AskRequest.model_validate_json(body_bytes)

    # Rate limit
    if not _check_rate_limit(req.user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 20 requests per minute.")

    # Process question in thread to avoid blocking event loop
    try:
        result = await asyncio.to_thread(
            process_question,
            question=req.question,
            client_id=req.client_id,
            org_ids=req.org_ids,
        )
        return AskResponse(**result)
    except Exception as e:
        logger.error("Request processing failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Request processing failed")


@app.get("/health")
def health():
    """Health check with DB connectivity status."""
    from app.queries.executor import pool
    db_status = "disconnected"
    if pool:
        try:
            conn = pool.getconn()
            pool.putconn(conn)
            db_status = "connected"
        except Exception:
            db_status = "error"
    return {"status": "ok", "service": "idempiere-ai-service", "db": db_status}


if __name__ == "__main__":
    import uvicorn
    from app.config import SERVICE_PORT
    uvicorn.run(app, host="127.0.0.1", port=SERVICE_PORT)
```

- [ ] **Step 5: Run integration tests**

```bash
pytest tests/test_integration.py -v
```
Expected: 5 passed

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```
Expected: All passed (~28 tests)

- [ ] **Step 7: Commit**

```bash
cd /home/tom/idempiere-tw-ai-assistant
git add service/app/main.py service/tests/conftest.py service/tests/test_integration.py
git commit -m "feat: FastAPI endpoint with HMAC auth, rate limiting, and generic error responses"
```

---

### Task 7: PostgreSQL Read-Only User + Service CLAUDE.md + Manual Test

**Files:**
- Create: `scripts/create_readonly_user.sql`
- Create: `service/CLAUDE.md`

- [ ] **Step 1: Create read-only DB user script**

```sql
-- scripts/create_readonly_user.sql
-- Run as PostgreSQL superuser against iDempiere database

CREATE USER ai_readonly WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';

GRANT CONNECT ON DATABASE idempiere TO ai_readonly;
GRANT USAGE ON SCHEMA adempiere TO ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA adempiere TO ai_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA adempiere
    GRANT SELECT ON TABLES TO ai_readonly;

-- Set default search_path so queries can reference tables without schema prefix
ALTER USER ai_readonly SET search_path TO adempiere;
```

- [ ] **Step 2: Create service/CLAUDE.md**

```markdown
# iDempiere AI Service

## What This Is
FastAPI service providing AI-powered Q&A for iDempiere ERP data.
Called by iDempiere Plugin via authenticated HTTP POST to localhost:8900.

## Iron Rules
1. SQL is pre-defined in app/queries/definitions/ — NEVER generate dynamic SQL
2. PII must be masked ([PII_*] tokens) before sending to external LLMs
3. PostgreSQL connection is read-only (ai_readonly user, connection pool)
4. Service listens on localhost only, not exposed to network
5. All requests authenticated via HMAC-SHA256
6. Error responses NEVER include PII or stack traces
7. All code in English

## Running
```bash
cp .env.example .env  # fill in keys + HMAC_SECRET
pip install -r requirements.txt
python -m app.main
```

## Testing
```bash
pytest tests/ -v
```

## Adding New Queries
1. Create or edit a file in app/queries/definitions/
2. All queries MUST include `AND AD_Org_ID = ANY(%(org_ids)s)` filter
3. All queries MUST list PII columns in `pii_columns`
4. Import and merge in app/queries/registry.py
5. Add tests in tests/test_registry.py
```

- [ ] **Step 3: Create .env, start server, manual test**

```bash
cd /home/tom/idempiere-tw-ai-assistant/service
cp .env.example .env
# Edit .env with real credentials

python -m app.main &

# Test health
curl http://localhost:8900/health

# Test with HMAC — generate body + signature, then curl with exact same bytes
python3 << 'PYEOF'
import hmac, hashlib, json, os, subprocess
from dotenv import load_dotenv
load_dotenv()

body = {"question": "今年每月營收多少？", "user_id": 100, "role_id": 200,
        "client_id": 11, "org_ids": [1]}
body_bytes = json.dumps(body).encode()
sig = hmac.new(os.environ["HMAC_SECRET"].encode(), body_bytes, hashlib.sha256).hexdigest()

# Call with exact same bytes used for HMAC
result = subprocess.run([
    "curl", "-s", "-X", "POST", "http://localhost:8900/ask",
    "-H", "Content-Type: application/json",
    "-H", f"X-HMAC-Signature: {sig}",
    "-d", body_bytes.decode(),
], capture_output=True, text=True)
print(result.stdout)
PYEOF
```

- [ ] **Step 4: Commit**

```bash
cd /home/tom/idempiere-tw-ai-assistant
git add scripts/ service/CLAUDE.md
git commit -m "docs: service CLAUDE.md and DB setup script"
```

---

## Spec Coverage Check (Rev 3)

| Spec Requirement | Task | Fix # |
|-----------------|------|-------|
| HMAC-SHA256 auth | Task 6 | Fix #1 |
| Generic error messages (no PII) | Task 6 | Fix #2 |
| contextvars-style isolation (per-request masking) | Task 2, 5 | Fix #3 |
| Input sanitization ([PII_*] stripping) | Task 2, 5 | Fix #4 |
| asyncio.to_thread for LLM calls | Task 6 | Fix #5 |
| [PII_*] token format | Task 2 | Fix #6 |
| AD_Org_ID filter in all SQL | Task 3 | Fix #7 |
| Rate limiting (20 req/user/min) | Task 6 | Fix #8 |
| Token usage from metadata | Task 4 | Fix #9 |
| org_ids in AskRequest | Task 5 | Fix #10 |
| Connection pooling | Task 3 | Fix #11 |
| conftest.py shared fixtures | Task 6 | Fix #12 |
| Pre-defined SQL only | Task 3 | — |
| Read-only PostgreSQL | Task 3, 7 | — |
| PII masking (reversible) | Task 2, 5 | — |
| LLM call with fallback | Task 4 | — |
| System prompts | Task 4 | — |
| Health endpoint | Task 6 |
| ThreadedConnectionPool (not Simple) | Task 3 | Joint J4 |
| search_path=adempiere | Task 3, 7 | Joint J3 |
| HMAC on raw body bytes | Task 6 | Joint J2 |
| LLM timeout=25s | Task 4 | Joint J8 |
| Decimal→float serializer | Task 5 | Joint J9 |
| fetchmany(200) row limit | Task 3 | Joint J12 |
| Remove session_id/history (Phase 1) | Task 5 | Joint J10 |
| Pool lifespan init/close | Task 6 | Joint J4 | — |
