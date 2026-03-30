# iDempiere AI Assistant — Design Spec

**Date:** 2026-03-30
**Status:** Approved (Rev 2 — post-review fixes)
**Author:** Tom + Claude
**Reviewed by:** Opus (iDempiere), Haiku (Python), Haiku (Security)

## Overview

An AI assistant integrated into iDempiere's Web UI as a Form-based chat window (via IFormFactory). Users ask natural language questions about ERP data, the system queries the database using pre-approved SQL, masks PII before sending to external LLMs, and returns the answer with PII restored.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  iDempiere (Java/OSGi)                              │
│  ┌───────────────────────┐  ┌──────────────────┐   │
│  │ AIChatForm (ZK Form)  │  │ AI_ChatLog       │   │
│  │ via IFormFactory       │  │ (audit trail)    │   │
│  └──────────┬────────────┘  └───────▲──────────┘   │
│             │                        │ save log     │
│             ▼                        │              │
│  ┌──────────────────────┐            │              │
│  │ AIChatService.java   │────────────┘              │
│  │ (plain class, NOT     │                           │
│  │  SvrProcess)          │                           │
│  │ Uses java.net.http    │                           │
│  └──────────┬────────────┘                           │
└─────────────┼────────────────────────────────────────┘
              │ POST + HMAC-SHA256 header
              │ {question, user_id, role_id, client_id, org_ids}
              ▼
┌─────────────────────────────────────────────────────┐
│  Python AI Service (FastAPI @ localhost:8900)        │
│                                                      │
│  0. HMAC Auth   — verify request from iDempiere      │
│  1. Router      — Llama 8B classifies question       │
│  2. Tool Select — pick pre-defined SQL or reply      │
│  3. Query Exec  — PostgreSQL read-only, +org filter  │
│  4. Mask PII    — replace PII with tokens (contextvars)│
│  5. LLM Call    — Sonnet or Llama (async via to_thread)│
│  6. Unmask      — restore tokens to real values       │
│  7. Return      — {answer, model, tokens_used}       │
└─────────────────────────────────────────────────────┘
```

## Data Flow (Detailed)

```
User types: "上個月營收最高的前5個客戶是誰？"
    ↓
iDempiere Plugin:
    1. Check AD_Role → MRole.getFormAccess(AD_Form_ID)
    2. Build request + HMAC-SHA256 signature
    3. POST to Python: {question, ad_user_id, ad_role_id, ad_client_id, org_ids: [1,2]}
    ↓
Python AI Service:
    4. Verify HMAC signature (reject if invalid)
    5. Sanitize input (strip [X_NNN] patterns from question)
    6. Router (Llama 8B): classify → "database_query"
    7. Tool selection (Sonnet): match to "top_customers_by_revenue"
    8. Execute pre-defined SQL with params + org_ids filter (read-only PG account)
       → [{name: "王大明", tax_id: "A123456789", revenue: 500000}, ...]
    9. Mask PII (via contextvars, request-scoped):
       → [{name: "[PII_C_001]", tax_id: "[PII_T_001]", revenue: 500000}, ...]
       → mapping stored in contextvars (thread-safe)
   10. Build prompt with masked data, send to Sonnet (via asyncio.to_thread)
   11. LLM responds: "[PII_C_001] has the highest revenue..."
   12. Unmask: "王大明 has the highest revenue..."
   13. Destroy mapping (contextvars auto-cleanup)
   14. Return {answer, model: "sonnet", tokens: 1234}
       (error responses: generic message only, no PII in errors)
    ↓
iDempiere Plugin:
   15. Display answer in chat panel
   16. Save to AI_ChatLog: user, question, answer, model, tokens, timestamp
```

## Iron Rules

1. **SQL is pre-defined** — AI selects which query to use and fills parameters, never generates SQL dynamically
2. **Reversible PII masking** — PII fields are replaced with tokens before LLM, restored after. Mapping is request-scoped via contextvars (thread-safe), destroyed after response
3. **Audit trail in iDempiere** — Every Q&A is logged in AI_ChatLog table with user, role, model used, token count, timestamp
4. **Read-only DB access** — Python connects with a PostgreSQL user that only has SELECT privileges
5. **localhost + HMAC** — Python service on localhost, requests authenticated via HMAC-SHA256 shared secret
6. **PII scope** — Taiwan Personal Data Protection Act (個資法): name, national ID, tax ID, phone, email, address, date of birth
7. **No PII in errors** — Exception messages return generic text, never include data from DB or LLM
8. **Input sanitization** — User questions are stripped of `[PII_*]` patterns before any LLM call to prevent prompt injection
9. **Org-level filtering** — All SQL queries include AD_Org_ID filter based on user's role access

## iDempiere Plugin Components

### 1. AIChatForm (ZK Form via IFormFactory)

A dedicated Form window registered via `IFormFactory` as an OSGi DS component. Users open it from the menu. Phase 2 may add a toolbar icon for quick access.

**UI elements:**
- Chat panel: message bubbles (user = right, AI = left)
- Input textbox + send button
- Loading state: button disabled + "AI 思考中..." spinner
- Clear conversation button

**Behavior:**
- Send button → disable input → show spinner → call AIChatService in background (ZK `Executions.schedule()`, NOT raw Thread) → display response → re-enable input
- Chat history maintained in ZK session (client-side, lost on page refresh)
- Persistent history available via AI_ChatLog table

### 2. AIChatService (Plain Java Class — NOT SvrProcess)

Bridge between ZK Form and Python service. This is a plain service class, not `SvrProcess`, because interactive chat needs sub-second feedback without the AD_PInstance lifecycle overhead.

**Responsibilities:**
- Validate user has AI permission (MRole.getFormAccess)
- Get user's accessible org IDs (MRole.getOrgAccess)
- Build HTTP request with user context + HMAC signature
- Call Python service (`java.net.http.HttpClient`, timeout 30s)
- Parse JSON response
- Save to AI_ChatLog via MAIChatLog PO
- Return answer to UI

### 3. MAIChatLog (PO Model)

Database table for audit trail. Registered via `@Model` annotation + `AnnotationBasedModelFactory` as OSGi DS component.

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| AI_ChatLog_ID | int (PK) | Auto-increment |
| AI_ChatLog_UU | varchar(36) | UUID (required by iDempiere 12) |
| AD_Client_ID | int (FK) | Tenant |
| AD_Org_ID | int (FK) | Organization |
| AD_User_ID | int (FK) | Who asked |
| AD_Role_ID | int (FK) | Which role |
| SessionID | varchar(36) | Conversation session UUID |
| Question | text | User's question |
| Answer | text | AI's response (with PII restored) |
| ModelUsed | varchar(40) | sonnet / llama_70b / llama_8b |
| TokensUsed | int | Total tokens consumed |
| QueryUsed | varchar(100) | Which pre-defined SQL was used (null if none) |
| ResponseTimeMS | int | Round-trip time in milliseconds |
| Created | timestamp | When |
| CreatedBy | int | Who |
| Updated | timestamp | Last update |
| UpdatedBy | int | Updated by |
| IsActive | char(1) | Y/N |

### 4. AIChatActivator (Activator)

OSGi bundle activator using Incremental2PackActivator.

**2Pack installs:**
- AI_ChatLog table + columns (including _UU, Updated, UpdatedBy)
- Window + Tab for viewing chat logs (admin)
- Form entry for AI Chat (AD_Form)
- Menu entry
- Role permission defaults

### 5. OSGi Service Components

| Component | Type | Registration |
|-----------|------|-------------|
| AIAssistantModelFactory | IModelFactory (AnnotationBasedModelFactory) | OSGI-INF/AIAssistantModelFactory.xml |
| AIChatFormFactory | IFormFactory | OSGI-INF/AIChatFormFactory.xml |

Note: No IProcessFactory needed — AIChatService is a plain class, not SvrProcess.

## Python AI Service Components

### 1. FastAPI Endpoint

```
POST /ask
Headers:  X-HMAC-Signature: <hmac-sha256 of request body with shared secret>
Request:  {question: str, user_id: int, role_id: int, client_id: int, org_ids: list[int], session_id: str, history: list}
Response: {answer: str, model_used: str, tokens_used: int, query_used: str|null, elapsed_ms: int}

Error Response: {detail: "Request processing failed"} — NEVER includes PII or stack trace
```

### 2. HMAC Authentication

- Shared secret stored in `.env` on both sides (iDempiere + Python)
- Plugin computes `HMAC-SHA256(request_body, secret)` and sends in header
- Python verifies before processing
- Rejects requests with invalid/missing signature

### 3. Input Sanitization

Before any LLM call, strip potential injection patterns from user question:
- Remove `[PII_*]` token patterns
- Remove `[C_*]`, `[T_*]`, `[P_*]`, `[E_*]`, `[A_*]`, `[D_*]` patterns
- This prevents users from referencing masking tokens in their questions

### 4. LangGraph Router

Uses Llama 8B to classify question into categories:
- `database_query` → needs to query DB, select a pre-defined SQL
- `general_knowledge` → answer from LLM directly (no DB needed)
- `clarification` → question too vague, ask user to be more specific

### 5. Query Executor

- Connects to PostgreSQL with read-only account (connection pooling via psycopg2.pool)
- Only executes queries from the pre-defined query registry
- All queries include `AND AD_Org_ID IN (%(org_ids)s)` filter
- Sonnet selects which query matches the user's question and extracts parameters
- Returns raw result rows

**Pre-defined query example:**

```python
QUERY_REGISTRY = {
    "top_customers_by_revenue": {
        "description": "Top N customers by revenue in a date range",
        "sql": """SELECT bp.Name, bp.TaxID, SUM(ol.LineNetAmt) as Revenue
                  FROM C_OrderLine ol
                  JOIN C_Order o ON ...
                  WHERE o.DateOrdered BETWEEN %(date_from)s AND %(date_to)s
                    AND o.DocStatus IN ('CO','CL')
                    AND o.AD_Client_ID = %(ad_client_id)s
                    AND o.AD_Org_ID = ANY(%(org_ids)s)
                  GROUP BY bp.Name, bp.TaxID
                  ORDER BY Revenue DESC
                  LIMIT %(limit)s""",
        "params": ["date_from", "date_to", "ad_client_id", "org_ids", "limit"],
        "pii_columns": ["name", "taxid"],
    },
}
```

### 6. Masking Layer

**Token format:** `[PII_PREFIX_NNN]` — uses `PII_` prefix to avoid natural text collision.

**PII fields (Taiwan 個資法):**
- Name → `[PII_C_001]`, `[PII_C_002]`, ...
- National ID / Tax ID → `[PII_T_001]`, ...
- Phone → `[PII_P_001]`, ...
- Email → `[PII_E_001]`, ...
- Address → `[PII_A_001]`, ...
- Date of birth → `[PII_D_001]`, ...

**Implementation:**
- Mapping stored in `contextvars.ContextVar` (thread-safe, request-scoped)
- Scan query results for columns marked as PII in query definition
- Replace each unique value with a sequential token
- After LLM response, string-replace tokens back to original values
- ContextVar auto-cleans up when request context ends

### 7. LLM Caller

All LLM calls wrapped in `asyncio.to_thread()` to avoid blocking FastAPI's event loop.

Model selection by router:
- `database_query` → Sonnet (needs to understand data context)
- `general_knowledge` → per router classification (Sonnet/Llama70B/Llama8B)
- `clarification` → Llama 8B (just asking for more info)

Fallback chain:
- Sonnet fails → Llama 70B
- Llama 70B fails → Sonnet
- Llama 8B fails → Llama 70B

Token usage extracted from `response.response_metadata["usage"]`.

### 8. Rate Limiting

Simple per-user rate limit in Phase 1:
- Max 20 requests per user per minute
- In-memory counter (dict[user_id] → deque of timestamps)
- Returns 429 if exceeded

## Security Boundaries

| Layer | Protection |
|-------|-----------|
| iDempiere | AD_Role + MRole.getFormAccess controls who can use AI |
| HTTP Auth | HMAC-SHA256 shared secret validates requests from iDempiere |
| Rate Limit | 20 req/user/min prevents abuse and cost overrun |
| Input | User questions sanitized (strip PII token patterns) |
| PostgreSQL | Read-only account, SELECT only |
| SQL | Pre-defined queries only, no dynamic SQL |
| Org Filter | All queries filter by user's AD_Org_ID access list |
| PII | Masked before LLM, mapping in contextvars (request-scoped) |
| Errors | Generic error messages, no PII in exceptions |
| Audit | Full Q&A logged in iDempiere DB (AI_ChatLog) |
| LLM calls | Async via to_thread, non-blocking |

## Tech Stack

**iDempiere Plugin:**
- Java 17 + OSGi
- ZK 9.x (Form-based chat UI via IFormFactory)
- `java.net.http.HttpClient` (built-in, no OSGi import issues)
- 2Pack (install DB schema)

**Python AI Service:**
- FastAPI + uvicorn
- LangGraph (routing)
- langchain-anthropic + langchain-groq (models)
- psycopg2 + psycopg2.pool (PostgreSQL read-only, connection pooling)
- pydantic (data validation)
- contextvars (request-scoped PII mapping)

## Phased Implementation

### Phase 1: Core (MVP)
- Python service with router + 3-5 pre-defined queries + masking + HMAC auth + rate limiting
- iDempiere plugin with Form-based chat + logging
- Read-only, no streaming, async LLM calls

### Phase 2: Expand
- More pre-defined queries (20+)
- Limited write operations (create draft, update notes)
- Conversation history across sessions
- Toolbar icon for quick access to chat form
- PII access audit log (who viewed which customer data)

### Phase 3: Harden
- Prompt injection detection (beyond basic sanitization)
- Cost monitoring dashboard
- Docker containerization
- Connection pooling tuning
- Log redaction filters

## Not In Scope
- Streaming/SSE (future consideration)
- External-facing chatbot
- Dynamic SQL generation
- File upload/attachment
- Voice input
