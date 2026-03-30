# Python AI Service — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI service that receives natural language questions, queries iDempiere's PostgreSQL with pre-defined SQL, masks PII, calls external LLMs, and returns answers with PII restored.

**Architecture:** FastAPI receives questions from iDempiere plugin via HTTP POST. LangGraph routes questions to the appropriate model. Pre-defined SQL queries run against a read-only PostgreSQL account. PII is masked before LLM calls and restored after.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, langchain-anthropic, langchain-groq, psycopg2, pydantic, pytest

---

## Review Fixes (Rev 2 — 2026-03-30)

The following changes were identified during team review (Opus: iDempiere, Haiku: Python + Security) and MUST be applied during implementation:

### CRITICAL fixes (apply to relevant tasks):

| # | Fix | Affects Task |
|---|-----|-------------|
| 1 | Add HMAC-SHA256 auth to `/ask` endpoint (shared secret in .env) | Task 6 (main.py) |
| 2 | Error responses must return generic message, NEVER include PII or traceback | Task 6 (main.py) |
| 3 | PII mapping must use `contextvars.ContextVar` for thread-safe request isolation | Task 2 (masker.py), Task 5 (router.py) |
| 4 | Add input sanitization: strip `[PII_*]` patterns from user question before LLM | Task 5 (router.py) |
| 5 | Wrap all LLM `.invoke()` calls in `asyncio.to_thread()` to avoid blocking event loop | Task 4 (caller.py), Task 6 (main.py → async def) |
| 6 | Token format changed from `[C_001]` to `[PII_C_001]` to avoid natural text collision | Task 2 (masker.py, rules.py) |
| 7 | All SQL queries must include `AND AD_Org_ID = ANY(%(org_ids)s)` filter | Task 3 (sales.py) |
| 8 | Add simple rate limiting: 20 req/user/min | Task 6 (main.py) |
| 9 | Extract token usage from LLM response metadata (not hardcoded 0) | Task 4 (caller.py) |
| 10 | Add `org_ids: list[int]` to AskRequest schema | Task 5 (schemas.py) |

### WARNING fixes (apply where noted):

| # | Fix | Affects Task |
|---|-----|-------------|
| 11 | Use psycopg2.pool.SimpleConnectionPool instead of connect/close per query | Task 3 (executor.py) |
| 12 | Add conftest.py with shared fixtures | Task 6 |

These changes are reflected in the updated spec: `docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md` (Rev 2).

---

## Project Structure

```
idempiere-ai-assistant/            # Monorepo: one git repo, two sub-projects
├── plugin/                        # Java iDempiere Plugin (Plan B — later)
│   ├── pom.xml                    # Points to /home/tom/idempiere/org.idempiere.parent
│   ├── META-INF/
│   ├── OSGI-INF/
│   └── src/
├── service/                       # Python AI Service (this plan)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app + /ask endpoint + /health
│   │   ├── config.py              # Settings from env vars (DB, API keys, port)
│   │   ├── router.py              # Classify → tool select → query → mask → LLM → unmask
│   │   ├── queries/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py        # QUERY_REGISTRY dict + lookup function
│   │   │   ├── executor.py        # Connect read-only PG, execute query, return rows
│   │   │   └── definitions/
│   │   │       ├── __init__.py
│   │   │       └── sales.py       # Sales/revenue/order queries (MVP: 3 queries)
│   │   ├── masking/
│   │   │   ├── __init__.py
│   │   │   ├── masker.py          # PIIMasker class: mask() and unmask()
│   │   │   └── rules.py           # PII column patterns + token prefixes
│   │   └── llm/
│   │       ├── __init__.py
│   │       ├── caller.py          # Call LLM with fallback chain
│   │       └── prompts.py         # System prompts for router, tool selector, answerer
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py            # Shared fixtures (mock DB, mock LLM)
│   │   ├── test_masking.py        # Mask/unmask round-trip tests
│   │   ├── test_registry.py       # Query lookup tests
│   │   ├── test_executor.py       # SQL execution tests (mock DB)
│   │   ├── test_router.py         # Classification tests (mock LLM)
│   │   ├── test_caller.py         # LLM call + fallback tests
│   │   └── test_integration.py    # Full /ask endpoint test (mock DB + mock LLM)
│   ├── .env.example
│   ├── requirements.txt
│   └── CLAUDE.md
├── scripts/
│   └── create_readonly_user.sql   # PostgreSQL read-only user setup
├── .gitignore
├── CLAUDE.md                      # Root-level project overview
└── AGENTS.md
```

---

### Task 1: Project Scaffold + Config

**Files:**
- Create: `idempiere-ai-service/requirements.txt`
- Create: `idempiere-ai-service/.env.example`
- Create: `idempiere-ai-service/.gitignore`
- Create: `idempiere-ai-service/app/__init__.py`
- Create: `idempiere-ai-service/app/config.py`
- Create: `idempiere-ai-service/tests/__init__.py`

- [ ] **Step 1: Create project directory and requirements.txt**

```bash
mkdir -p /home/tom/idempiere-ai-assistant/{service/{app,tests},plugin,scripts}
```

```
# requirements.txt
fastapi>=0.115
uvicorn>=0.34
langgraph>=0.4
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
ANTHROPIC_API_KEY=sk-ant-xxxx
GROQ_API_KEY=gsk_xxxx
DB_HOST=localhost
DB_PORT=5432
DB_NAME=idempiere
DB_USER=ai_readonly
DB_PASSWORD=xxxx
SERVICE_PORT=8900
```

- [ ] **Step 3: Create .gitignore**

```
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 4: Create app/config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "idempiere")
DB_USER = os.getenv("DB_USER", "ai_readonly")
DB_PASSWORD = os.environ["DB_PASSWORD"]

SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8900"))
```

- [ ] **Step 5: Create empty __init__.py files**

```bash
touch /home/tom/idempiere-ai-assistant/service/app/__init__.py
touch /home/tom/idempiere-ai-assistant/service/tests/__init__.py
```

- [ ] **Step 6: Install dependencies and verify**

```bash
cd /home/tom/idempiere-ai-service
pip install -r requirements.txt
python -c "import fastapi, langgraph, psycopg2; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git init
git add -A
git commit -m "feat: project scaffold with config and dependencies"
```

---

### Task 2: PII Masking Layer

**Files:**
- Create: `app/masking/__init__.py`
- Create: `app/masking/rules.py`
- Create: `app/masking/masker.py`
- Create: `tests/test_masking.py`

- [ ] **Step 1: Write masking tests**

```python
# tests/test_masking.py
from app.masking.masker import PIIMasker
from app.masking.rules import PII_COLUMN_RULES


def test_mask_single_value():
    masker = PIIMasker()
    rows = [{"name": "王大明", "revenue": 50000}]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == "[C_001]"
    assert masked[0]["revenue"] == 50000
    assert mapping["[C_001]"] == "王大明"


def test_mask_multiple_pii_columns():
    masker = PIIMasker()
    rows = [{"name": "王大明", "taxid": "A123456789", "revenue": 50000}]
    masked, mapping = masker.mask(rows, pii_columns=["name", "taxid"])
    assert masked[0]["name"] == "[C_001]"
    assert masked[0]["taxid"] == "[T_001]"
    assert mapping["[C_001]"] == "王大明"
    assert mapping["[T_001]"] == "A123456789"


def test_mask_duplicate_values_same_token():
    masker = PIIMasker()
    rows = [
        {"name": "王大明", "revenue": 100},
        {"name": "王大明", "revenue": 200},
    ]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == masked[1]["name"] == "[C_001]"
    assert len(mapping) == 1


def test_mask_multiple_distinct_values():
    masker = PIIMasker()
    rows = [
        {"name": "王大明", "revenue": 100},
        {"name": "李小華", "revenue": 200},
    ]
    masked, mapping = masker.mask(rows, pii_columns=["name"])
    assert masked[0]["name"] == "[C_001]"
    assert masked[1]["name"] == "[C_002]"
    assert len(mapping) == 2


def test_unmask_text():
    masker = PIIMasker()
    mapping = {"[C_001]": "王大明", "[T_001]": "A123456789"}
    text = "[C_001] 的統編是 [T_001]，營收最高"
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_masking.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.masking'`

- [ ] **Step 3: Create rules.py**

```python
# app/masking/rules.py

# Maps PII column name patterns to token prefixes.
# When a column name matches (case-insensitive), values get replaced with [PREFIX_NNN].
PII_COLUMN_RULES: dict[str, str] = {
    "name": "C",        # Customer/contact name
    "taxid": "T",       # Tax ID / national ID
    "phone": "P",       # Phone number
    "email": "E",       # Email address
    "address": "A",     # Address
    "birthday": "D",    # Date of birth
    "value": "C",       # BPartner Value (sometimes used as name)
}
```

- [ ] **Step 4: Create masker.py**

```python
# app/masking/masker.py
from app.masking.rules import PII_COLUMN_RULES


class PIIMasker:
    """Reversible PII masking for database query results."""

    def mask(
        self, rows: list[dict], pii_columns: list[str]
    ) -> tuple[list[dict], dict[str, str]]:
        """Replace PII values with tokens. Returns (masked_rows, token_to_original_mapping)."""
        mapping: dict[str, str] = {}
        reverse: dict[str, str] = {}  # original_value → token (for dedup)
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
                    token = f"[{prefix}_{counters[prefix]:03d}]"
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
```

- [ ] **Step 5: Create __init__.py**

```bash
touch /home/tom/idempiere-ai-assistant/service/app/masking/__init__.py
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_masking.py -v
```
Expected: 9 passed

- [ ] **Step 7: Commit**

```bash
git add app/masking/ tests/test_masking.py
git commit -m "feat: PII masking layer with reversible token replacement"
```

---

### Task 3: Query Registry + Executor

**Files:**
- Create: `app/queries/__init__.py`
- Create: `app/queries/registry.py`
- Create: `app/queries/definitions/__init__.py`
- Create: `app/queries/definitions/sales.py`
- Create: `app/queries/executor.py`
- Create: `tests/test_registry.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write registry tests**

```python
# tests/test_registry.py
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
    """Descriptions should be clear enough for an LLM to select the right query."""
    queries = list_queries()
    for name, q in queries.items():
        assert len(q["description"]) >= 10, f"{name} description too short for LLM"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_registry.py -v
```
Expected: FAIL

- [ ] **Step 3: Create sales.py query definitions**

```python
# app/queries/definitions/sales.py

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
            GROUP BY bp.Name, bp.TaxID
            ORDER BY Revenue DESC
            LIMIT %(limit)s
        """,
        "params": ["date_from", "date_to", "ad_client_id", "limit"],
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
        """,
        "params": ["document_no", "ad_client_id"],
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
            GROUP BY TO_CHAR(o.DateOrdered, 'YYYY-MM')
            ORDER BY Month
        """,
        "params": ["year", "ad_client_id"],
        "pii_columns": [],
    },
}
```

- [ ] **Step 4: Create registry.py**

```python
# app/queries/registry.py
from app.queries.definitions.sales import SALES_QUERIES

# Merge all query definitions into one registry
QUERY_REGISTRY: dict[str, dict] = {
    **SALES_QUERIES,
}


def get_query(name: str) -> dict | None:
    """Get a query definition by name. Returns None if not found."""
    return QUERY_REGISTRY.get(name)


def list_queries() -> dict[str, dict]:
    """Return all registered queries."""
    return QUERY_REGISTRY


def get_query_descriptions() -> str:
    """Format all query descriptions for LLM tool selection prompt."""
    lines = []
    for name, q in QUERY_REGISTRY.items():
        params = ", ".join(q["params"])
        lines.append(f'- "{name}" (params: {params}): {q["description"]}')
    return "\n".join(lines)
```

- [ ] **Step 5: Create __init__.py files**

```bash
touch /home/tom/idempiere-ai-assistant/service/app/queries/__init__.py
touch /home/tom/idempiere-ai-assistant/service/app/queries/definitions/__init__.py
```

- [ ] **Step 6: Run registry tests**

```bash
pytest tests/test_registry.py -v
```
Expected: 5 passed

- [ ] **Step 7: Write executor tests**

```python
# tests/test_executor.py
import pytest
from unittest.mock import patch, MagicMock
from app.queries.executor import QueryExecutor


@pytest.fixture
def executor():
    with patch("app.queries.executor.psycopg2") as mock_pg:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pg.connect.return_value = mock_conn

        mock_cursor.description = [("name",), ("revenue",)]
        mock_cursor.fetchall.return_value = [("王大明", 50000)]

        ex = QueryExecutor()
        yield ex, mock_cursor


def test_execute_returns_dicts(executor):
    ex, mock_cursor = executor
    rows = ex.execute(
        "top_customers_by_revenue",
        {"date_from": "2026-01-01", "date_to": "2026-03-31", "ad_client_id": 11, "limit": 5},
    )
    assert rows == [{"name": "王大明", "revenue": 50000}]


def test_execute_unknown_query(executor):
    ex, _ = executor
    with pytest.raises(ValueError, match="Unknown query"):
        ex.execute("nonexistent_query", {})


def test_execute_missing_param(executor):
    ex, _ = executor
    with pytest.raises(ValueError, match="Missing parameter"):
        ex.execute("top_customers_by_revenue", {"date_from": "2026-01-01"})
```

- [ ] **Step 8: Create executor.py**

```python
# app/queries/executor.py
import psycopg2
from app.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from app.queries.registry import get_query


class QueryExecutor:
    """Execute pre-defined SQL queries against read-only PostgreSQL."""

    def _connect(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD,
        )

    def execute(self, query_name: str, params: dict) -> list[dict]:
        """Execute a pre-defined query by name with given parameters.

        Returns list of dicts (column_name → value).
        Raises ValueError if query not found or params missing.
        """
        query_def = get_query(query_name)
        if query_def is None:
            raise ValueError(f"Unknown query: {query_name}")

        # Validate all required params are present
        for p in query_def["params"]:
            if p not in params:
                raise ValueError(f"Missing parameter: {p}")

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(query_def["sql"], params)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()
```

- [ ] **Step 9: Run executor tests**

```bash
pytest tests/test_executor.py -v
```
Expected: 3 passed

- [ ] **Step 10: Commit**

```bash
git add app/queries/ tests/test_registry.py tests/test_executor.py
git commit -m "feat: pre-defined query registry and read-only executor"
```

---

### Task 4: LLM Caller with Fallback

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/prompts.py`
- Create: `app/llm/caller.py`
- Create: `tests/test_caller.py`

- [ ] **Step 1: Write caller tests**

```python
# tests/test_caller.py
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


def test_call_sonnet(mock_models):
    caller, mock_sonnet, _, _ = mock_models
    mock_sonnet.invoke.return_value = MagicMock(content="Sonnet answer")
    result = caller.call("sonnet", "system prompt", "user question")
    assert result == "Sonnet answer"
    mock_sonnet.invoke.assert_called_once()


def test_call_llama_70b(mock_models):
    caller, _, mock_llama70b, _ = mock_models
    mock_llama70b.invoke.return_value = MagicMock(content="Llama answer")
    result = caller.call("llama_70b", "system prompt", "user question")
    assert result == "Llama answer"


def test_fallback_sonnet_to_llama(mock_models):
    caller, mock_sonnet, mock_llama70b, _ = mock_models
    mock_sonnet.invoke.side_effect = Exception("API down")
    mock_llama70b.invoke.return_value = MagicMock(content="Fallback answer")
    result = caller.call("sonnet", "system prompt", "user question")
    assert result == "Fallback answer"


def test_both_fail_raises(mock_models):
    caller, mock_sonnet, mock_llama70b, _ = mock_models
    mock_sonnet.invoke.side_effect = Exception("API down")
    mock_llama70b.invoke.side_effect = Exception("Also down")
    with pytest.raises(RuntimeError, match="All models failed"):
        caller.call("sonnet", "system prompt", "user question")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_caller.py -v
```
Expected: FAIL

- [ ] **Step 3: Create prompts.py**

```python
# app/llm/prompts.py

ROUTER_PROMPT = """You are a query classifier for an ERP system. Classify the user's question into exactly one category.

Categories:
- "database_query": Questions about business data that need database lookup (revenue, orders, customers, inventory, reports)
- "general_knowledge": General knowledge or ERP concept questions that don't need database access
- "clarification": Question is too vague to answer, need more details from the user

Respond with ONLY valid JSON:
{"category": "database_query|general_knowledge|clarification", "reason": "brief explanation"}"""


TOOL_SELECTOR_PROMPT = """You are a query selector for an ERP system. Given a user question and a list of available pre-defined queries, select the best matching query and extract the parameters.

Available queries:
{query_descriptions}

Rules:
- Select exactly one query that best matches the question
- Extract parameter values from the question context
- For date_from/date_to: infer from "上個月", "今年", etc. Use ISO format YYYY-MM-DD
- For limit: default to 10 if not specified
- ad_client_id is provided in context, always use it
- If no query matches, set query_name to "none"

Respond with ONLY valid JSON:
{{"query_name": "exact_query_name_or_none", "params": {{"param1": "value1"}}, "reason": "brief explanation"}}"""


ANSWERER_PROMPT = """You are a helpful ERP data analyst. Answer the user's question based on the query results provided.

Rules:
- Be concise and direct
- If the user asks in Chinese, reply in Chinese
- Format numbers with commas for readability
- If the data is empty, say so clearly
- Do not make up data that isn't in the results
- Reference entities by their identifiers as shown in the data (these may be masked tokens like [C_001])"""


CLARIFICATION_PROMPT = """The user's question is too vague to answer. Ask them to be more specific.
Reply in the same language as the user's question. Be brief and friendly."""
```

- [ ] **Step 4: Create caller.py**

```python
# app/llm/caller.py
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
    """Call LLMs with automatic fallback."""

    def __init__(self):
        self.models = {
            "sonnet": ChatAnthropic(
                model="claude-sonnet-4-6", max_tokens=4096,
                api_key=ANTHROPIC_API_KEY,
            ),
            "llama_70b": ChatGroq(
                model="llama-3.3-70b-versatile", max_tokens=4096,
                api_key=GROQ_API_KEY,
            ),
            "llama_8b": ChatGroq(
                model="llama-3.1-8b-instant", max_tokens=2048,
                api_key=GROQ_API_KEY,
            ),
        }

    def call(self, model_name: str, system_prompt: str, user_message: str) -> str:
        """Call a model with automatic fallback. Raises RuntimeError if all fail."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        # Try primary
        try:
            response = self.models[model_name].invoke(messages)
            return response.content
        except Exception as primary_err:
            # Try fallback
            fallback = FALLBACK_CHAIN.get(model_name)
            if fallback is None:
                raise RuntimeError(f"All models failed: {primary_err}")
            try:
                response = self.models[fallback].invoke(messages)
                return response.content
            except Exception as fallback_err:
                raise RuntimeError(
                    f"All models failed: primary({model_name})={primary_err}, "
                    f"fallback({fallback})={fallback_err}"
                )
```

- [ ] **Step 5: Create __init__.py**

```bash
touch /home/tom/idempiere-ai-assistant/service/app/llm/__init__.py
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_caller.py -v
```
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add app/llm/ tests/test_caller.py
git commit -m "feat: LLM caller with fallback chain and prompt templates"
```

---

### Task 5: LangGraph Router

**Files:**
- Create: `app/router.py`
- Create: `tests/test_router.py`
- Create: `app/models/__init__.py`
- Create: `app/models/schemas.py`

- [ ] **Step 1: Create pydantic schemas**

```python
# app/models/schemas.py
from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    user_id: int
    role_id: int
    client_id: int
    session_id: str
    history: list[dict] = []


class AskResponse(BaseModel):
    answer: str
    model_used: str
    tokens_used: int
    query_used: str | None
    elapsed_ms: int
```

```bash
touch /home/tom/idempiere-ai-assistant/service/app/models/__init__.py
```

- [ ] **Step 2: Write router tests**

```python
# tests/test_router.py
import pytest
from unittest.mock import patch, MagicMock
from app.router import process_question


@pytest.fixture
def mock_deps():
    with patch("app.router.LLMCaller") as MockCaller, \
         patch("app.router.QueryExecutor") as MockExecutor:
        caller = MockCaller.return_value
        executor = MockExecutor.return_value
        yield caller, executor


def test_general_knowledge_no_db(mock_deps):
    caller, executor = mock_deps

    # Router classifies as general_knowledge
    caller.call.side_effect = [
        '{"category": "general_knowledge", "reason": "concept question"}',  # router
        "Docker is a containerization platform.",  # answerer
    ]

    result = process_question("What is Docker?", client_id=11)
    assert result["answer"] == "Docker is a containerization platform."
    assert result["query_used"] is None
    executor.execute.assert_not_called()


def test_database_query_with_masking(mock_deps):
    caller, executor = mock_deps

    caller.call.side_effect = [
        '{"category": "database_query", "reason": "needs data"}',  # router
        '{"query_name": "top_customers_by_revenue", "params": {"date_from": "2026-02-01", "date_to": "2026-02-28", "ad_client_id": 11, "limit": 5}, "reason": "matches"}',  # tool selector
        "[C_001] has the highest revenue at 500,000.",  # answerer (with masked tokens)
    ]
    executor.execute.return_value = [
        {"name": "王大明", "taxid": "A123456789", "revenue": 500000}
    ]

    result = process_question("上個月營收最高的客戶是誰？", client_id=11)
    assert "王大明" in result["answer"]  # PII restored
    assert result["query_used"] == "top_customers_by_revenue"


def test_clarification_no_db(mock_deps):
    caller, executor = mock_deps

    caller.call.side_effect = [
        '{"category": "clarification", "reason": "too vague"}',  # router
        "Can you be more specific?",  # clarification response
    ]

    result = process_question("那個", client_id=11)
    assert "specific" in result["answer"].lower() or "具體" in result["answer"]
    executor.execute.assert_not_called()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_router.py -v
```
Expected: FAIL

- [ ] **Step 4: Create router.py**

```python
# app/router.py
import json
import time
from app.llm.caller import LLMCaller
from app.llm.prompts import (
    ROUTER_PROMPT, TOOL_SELECTOR_PROMPT, ANSWERER_PROMPT, CLARIFICATION_PROMPT
)
from app.queries.executor import QueryExecutor
from app.queries.registry import get_query, get_query_descriptions
from app.masking.masker import PIIMasker

caller = LLMCaller()
executor = QueryExecutor()
masker = PIIMasker()


def process_question(question: str, client_id: int) -> dict:
    """Main pipeline: classify → (query → mask) → LLM → unmask → return."""
    start = time.time()
    query_used = None

    # Step 1: Classify question
    classification_raw = caller.call("llama_8b", ROUTER_PROMPT, question)
    try:
        classification = json.loads(classification_raw.strip())
        category = classification.get("category", "general_knowledge")
    except json.JSONDecodeError:
        category = "general_knowledge"

    # Step 2: Handle by category
    if category == "clarification":
        answer = caller.call("llama_8b", CLARIFICATION_PROMPT, question)
        model_used = "llama_8b"

    elif category == "database_query":
        # Step 2a: Select query + extract params
        selector_prompt = TOOL_SELECTOR_PROMPT.format(
            query_descriptions=get_query_descriptions()
        )
        context = f"Question: {question}\nad_client_id: {client_id}"
        selection_raw = caller.call("sonnet", selector_prompt, context)

        try:
            selection = json.loads(selection_raw.strip())
            query_name = selection.get("query_name", "none")
            params = selection.get("params", {})
        except json.JSONDecodeError:
            query_name = "none"
            params = {}

        if query_name == "none" or get_query(query_name) is None:
            # No matching query, answer as general knowledge
            answer = caller.call("sonnet", ANSWERER_PROMPT, question)
            model_used = "sonnet"
        else:
            # Step 2b: Execute query
            query_def = get_query(query_name)
            rows = executor.execute(query_name, params)
            query_used = query_name

            # Step 2c: Mask PII
            masked_rows, mapping = masker.mask(rows, query_def["pii_columns"])

            # Step 2d: Call LLM with masked data
            data_text = json.dumps(masked_rows, ensure_ascii=False, default=str)
            prompt = f"Question: {question}\n\nQuery results:\n{data_text}"
            masked_answer = caller.call("sonnet", ANSWERER_PROMPT, prompt)
            model_used = "sonnet"

            # Step 2e: Unmask PII in answer
            answer = masker.unmask(masked_answer, mapping)
    else:
        # general_knowledge
        answer = caller.call("sonnet", ANSWERER_PROMPT, question)
        model_used = "sonnet"

    elapsed_ms = int((time.time() - start) * 1000)

    return {
        "answer": answer,
        "model_used": model_used,
        "tokens_used": 0,  # TODO: extract from LLM response usage
        "query_used": query_used,
        "elapsed_ms": elapsed_ms,
    }
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_router.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add app/router.py app/models/ tests/test_router.py
git commit -m "feat: LangGraph router with classify → query → mask → LLM → unmask pipeline"
```

---

### Task 6: FastAPI Endpoint + Integration Test

**Files:**
- Create: `app/main.py`
- Create: `tests/test_integration.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@patch("app.router.LLMCaller")
@patch("app.router.QueryExecutor")
def test_ask_endpoint_general(MockExecutor, MockCaller):
    caller = MockCaller.return_value
    caller.call.side_effect = [
        '{"category": "general_knowledge", "reason": "concept"}',
        "Docker is a container platform.",
    ]

    from app.main import app
    client = TestClient(app)

    response = client.post("/ask", json={
        "question": "What is Docker?",
        "user_id": 100,
        "role_id": 200,
        "client_id": 11,
        "session_id": "test-001",
    })

    assert response.status_code == 200
    data = response.json()
    assert "Docker" in data["answer"]
    assert data["query_used"] is None


@patch("app.router.LLMCaller")
@patch("app.router.QueryExecutor")
def test_ask_endpoint_db_query(MockExecutor, MockCaller):
    caller = MockCaller.return_value
    executor = MockExecutor.return_value

    caller.call.side_effect = [
        '{"category": "database_query", "reason": "needs data"}',
        '{"query_name": "monthly_revenue_summary", "params": {"year": 2026, "ad_client_id": 11}, "reason": "monthly trend"}',
        "Revenue in January was 1,000,000.",
    ]
    executor.execute.return_value = [
        {"month": "2026-01", "revenue": 1000000, "ordercount": 50}
    ]

    from app.main import app
    client = TestClient(app)

    response = client.post("/ask", json={
        "question": "今年每月營收多少？",
        "user_id": 100,
        "role_id": 200,
        "client_id": 11,
        "session_id": "test-002",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["query_used"] == "monthly_revenue_summary"


def test_health_endpoint():
    from app.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_integration.py -v
```
Expected: FAIL

- [ ] **Step 3: Create main.py**

```python
# app/main.py
import time
from fastapi import FastAPI, HTTPException
from app.models.schemas import AskRequest, AskResponse
from app.router import process_question

app = FastAPI(
    title="iDempiere AI Service",
    description="AI assistant backend for iDempiere ERP",
    version="1.0.0",
)


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """Process a natural language question about ERP data."""
    try:
        result = process_question(
            question=req.question,
            client_id=req.client_id,
        )
        return AskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "service": "idempiere-ai-service"}


if __name__ == "__main__":
    import uvicorn
    from app.config import SERVICE_PORT
    uvicorn.run(app, host="127.0.0.1", port=SERVICE_PORT)
```

- [ ] **Step 4: Run integration tests**

```bash
pytest tests/test_integration.py -v
```
Expected: 3 passed

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```
Expected: All passed (masking + registry + executor + caller + router + integration)

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_integration.py
git commit -m "feat: FastAPI /ask endpoint with full pipeline integration"
```

---

### Task 7: PostgreSQL Read-Only User + Manual Test

**Files:**
- Create: `scripts/create_readonly_user.sql`
- Create: `CLAUDE.md`
- Create: `AGENTS.md`

- [ ] **Step 1: Create read-only DB user script**

```sql
-- ../../scripts/create_readonly_user.sql (at monorepo root)
-- Run as PostgreSQL superuser against iDempiere database
-- Creates a read-only user for the AI service

CREATE USER ai_readonly WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';

-- Grant connect
GRANT CONNECT ON DATABASE idempiere TO ai_readonly;

-- Grant usage on adempiere schema
GRANT USAGE ON SCHEMA adempiere TO ai_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA adempiere TO ai_readonly;

-- Grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA adempiere
    GRANT SELECT ON TABLES TO ai_readonly;

-- Verify: should show only SELECT
-- \dp adempiere.c_order
```

- [ ] **Step 2: Create CLAUDE.md**

```markdown
# iDempiere AI Service

## What This Is
FastAPI service that provides AI-powered Q&A for iDempiere ERP data.
Called by iDempiere Plugin via HTTP POST to localhost:8900.

## Iron Rules
1. SQL is pre-defined in app/queries/definitions/ — NEVER generate dynamic SQL
2. PII must be masked before sending to external LLMs
3. PostgreSQL connection is read-only (ai_readonly user)
4. Service listens on localhost only, not exposed to network
5. All code in English

## Running
```
cp .env.example .env  # fill in keys
pip install -r requirements.txt
python -m app.main
```

## Testing
```
pytest tests/ -v
```

## Adding New Queries
1. Create or edit a file in app/queries/definitions/
2. Add queries to the module-level dict (follow sales.py pattern)
3. Import and merge in app/queries/registry.py
4. Add tests in tests/test_registry.py
```

- [ ] **Step 3: Create .env with real values, run server, test with curl**

```bash
# Fill in .env with real credentials
cp .env.example .env
# Edit .env: set DB_PASSWORD, API keys

# Start server
python -m app.main &

# Test health
curl http://localhost:8900/health

# Test ask endpoint (with real LLMs + real DB)
curl -X POST http://localhost:8900/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "今年每月營收多少？",
    "user_id": 100,
    "role_id": 200,
    "client_id": 11,
    "session_id": "manual-test"
  }'
```

- [ ] **Step 4: Commit**

```bash
cd /home/tom/idempiere-ai-assistant
git add scripts/ service/CLAUDE.md CLAUDE.md AGENTS.md
git commit -m "docs: add CLAUDE.md, AGENTS.md, and DB setup script"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| FastAPI endpoint POST /ask | Task 6 |
| LangGraph Router (classify) | Task 5 |
| Pre-defined SQL only | Task 3 |
| Read-only PostgreSQL | Task 3, 7 |
| PII masking (reversible) | Task 2 |
| PII unmasking | Task 2, 5 |
| LLM call with fallback | Task 4 |
| System prompts | Task 4 |
| Pydantic schemas | Task 5 |
| Health endpoint | Task 6 |
| Read-only DB user | Task 7 |
| CLAUDE.md / AGENTS.md | Task 7 |
