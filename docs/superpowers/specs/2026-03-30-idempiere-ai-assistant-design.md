# iDempiere AI Assistant — Design Spec

**Date:** 2026-03-30
**Status:** Approved
**Author:** Tom + Claude

## Overview

An AI assistant embedded in iDempiere's Web UI as a floating chat window. Users ask natural language questions about ERP data, the system queries the database using pre-approved SQL, masks PII before sending to external LLMs, and returns the answer with PII restored.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  iDempiere (Java/OSGi)                          │
│  ┌───────────────────────┐  ┌────────────────┐  │
│  │ Chat Window (ZK)      │  │ AI_ChatLog     │  │
│  │ (UI + loading anim)   │  │ (audit trail)  │  │
│  └──────────┬────────────┘  └───────▲────────┘  │
│             │ HTTP POST              │ save log  │
│             ▼                        │           │
│  ┌──────────────────────┐            │           │
│  │ AIChatProcess.java   │────────────┘           │
│  │ (auth + call Python) │                        │
│  └──────────┬────────────┘                        │
└─────────────┼────────────────────────────────────┘
              │ POST {question, user_id, role, ad_client_id}
              ▼
┌─────────────────────────────────────────────────┐
│  Python AI Service (FastAPI @ localhost:8900)    │
│                                                  │
│  1. Router       — Llama 8B classifies question  │
│  2. Tool Select  — pick pre-defined SQL or reply │
│  3. Query Exec   — PostgreSQL read-only account  │
│  4. Mask PII     — replace PII with tokens       │
│  5. LLM Call     — Sonnet or Llama with masked   │
│  6. Unmask       — restore tokens to real values  │
│  7. Return       — {answer, model, tokens_used}  │
└─────────────────────────────────────────────────┘
```

## Data Flow (Detailed)

```
User types: "上個月營收最高的前5個客戶是誰？"
    ↓
iDempiere Plugin:
    1. Check AD_Role permission (can this user use AI?)
    2. POST to Python: {question, ad_user_id, ad_role_id, ad_client_id}
    ↓
Python AI Service:
    3. Router (Llama 8B): classify → "database_query"
    4. Tool selection (Sonnet): match to "top_customers_by_revenue"
    5. Execute pre-defined SQL with params (read-only PG account)
       → [{name: "王大明", tax_id: "A123456789", revenue: 500000}, ...]
    6. Mask PII:
       → [{name: "[C_001]", tax_id: "[T_001]", revenue: 500000}, ...]
       → mapping: {"[C_001]": "王大明", "[T_001]": "A123456789"}
    7. Build prompt with masked data, send to Sonnet
       → "Based on this data: [C_001] revenue 500,000 ..."
    8. LLM responds: "[C_001] has the highest revenue at 500,000..."
    9. Unmask: "王大明 has the highest revenue at 500,000..."
   10. Destroy mapping table
   11. Return {answer, model: "sonnet", tokens: 1234}
    ↓
iDempiere Plugin:
   12. Display answer in chat bubble
   13. Save to AI_ChatLog: user, question, answer, model, tokens, timestamp
```

## Iron Rules

1. **SQL is pre-defined** — AI selects which query to use and fills parameters, never generates SQL dynamically
2. **Reversible PII masking** — PII fields are replaced with tokens before LLM, restored after. Mapping table is ephemeral (destroyed after each conversation)
3. **Audit trail in iDempiere** — Every Q&A is logged in AI_ChatLog table with user, role, model used, token count, timestamp
4. **Read-only DB access** — Python connects with a PostgreSQL user that only has SELECT privileges
5. **localhost only** — Python service not exposed to network, only iDempiere can call it
6. **PII scope** — Taiwan Personal Data Protection Act (個資法): name, national ID, tax ID, phone, email, address, date of birth

## iDempiere Plugin Components

### 1. AIChatWindow (ZK Component)

Floating chat window anchored to bottom-right of iDempiere Web UI.

**UI elements:**
- Floating button (AI icon) → click to expand
- Chat panel: message bubbles (user = right, AI = left)
- Input textbox + send button
- Loading state: button disabled + "AI 思考中..." animation
- Close/minimize button

**Behavior:**
- Send button → disable input → show loading → call AIChatProcess in background thread → display response → re-enable input
- Chat history maintained in ZK session (client-side, lost on page refresh)
- Persistent history available via AI_ChatLog table

### 2. AIChatProcess (SvrProcess)

Bridge between ZK UI and Python service.

**Responsibilities:**
- Validate user has AI permission (check AD_Role)
- Build HTTP request with user context (AD_User_ID, AD_Role_ID, AD_Client_ID)
- Call Python service (Apache HttpClient, timeout 30s)
- Parse response
- Save to AI_ChatLog
- Return answer to UI

### 3. MAIChatLog (PO Model)

Database table for audit trail.

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| AI_ChatLog_ID | int (PK) | Auto-increment |
| AD_Client_ID | int (FK) | Tenant |
| AD_Org_ID | int (FK) | Organization |
| AD_User_ID | int (FK) | Who asked |
| AD_Role_ID | int (FK) | Which role |
| SessionID | varchar(40) | Conversation session ID |
| Question | text | User's question |
| Answer | text | AI's response (with PII restored) |
| ModelUsed | varchar(40) | sonnet / llama_70b / llama_8b |
| TokensUsed | int | Total tokens consumed |
| QueryUsed | varchar(100) | Which pre-defined SQL was used (null if none) |
| ResponseTimeMS | int | Round-trip time in milliseconds |
| Created | timestamp | When |
| CreatedBy | int | Who |
| IsActive | char(1) | Y/N |

### 4. AIChatActivator (Activator)

OSGi bundle activator using Incremental2PackActivator.

**2Pack installs:**
- AI_ChatLog table + columns
- Window + Tab for viewing chat logs (admin)
- Menu entry for chat log viewer
- Role permission defaults

## Python AI Service Components

### 1. FastAPI Endpoint

```
POST /ask
Request:  {question: str, user_id: int, role_id: int, client_id: int, session_id: str, history: list}
Response: {answer: str, model_used: str, tokens_used: int, query_used: str|null, elapsed_ms: int}
```

### 2. LangGraph Router

Uses Llama 8B to classify question into categories:
- `database_query` → needs to query DB, select a pre-defined SQL
- `general_knowledge` → answer from LLM directly (no DB needed)
- `clarification` → question too vague, ask user to be more specific

### 3. Query Executor

- Connects to PostgreSQL with read-only account
- Only executes queries from the pre-defined query registry
- Sonnet selects which query matches the user's question and extracts parameters
- Returns raw result rows

**Pre-defined query example:**

```python
QUERY_REGISTRY = {
    "top_customers_by_revenue": {
        "description": "Top N customers by revenue in a date range",
        "sql": "SELECT bp.Name, bp.TaxID, SUM(ol.LineNetAmt) as Revenue FROM ...",
        "params": ["date_from", "date_to", "ad_client_id", "limit"],
        "pii_columns": ["name", "taxid"],
    },
    # ... more pre-defined queries
}
```

### 4. Masking Layer

**PII fields (Taiwan 個資法):**
- Name → `[C_001]`, `[C_002]`, ...
- National ID / Tax ID → `[T_001]`, `[T_002]`, ...
- Phone → `[P_001]`, ...
- Email → `[E_001]`, ...
- Address → `[A_001]`, ...
- Date of birth → `[D_001]`, ...

**Implementation:**
- Scan query results for columns marked as PII in query definition
- Replace each unique value with a sequential token
- Store mapping in memory (dict)
- After LLM response, string-replace tokens back to original values
- Destroy mapping dict after response is sent

### 5. LLM Caller

Model selection by router:
- `database_query` → Sonnet (needs to understand data context)
- `general_knowledge` → per router classification (Sonnet/Llama70B/Llama8B)
- `clarification` → Llama 8B (just asking for more info)

Fallback chain:
- Sonnet fails → Llama 70B
- Llama 70B fails → Sonnet
- Llama 8B fails → Llama 70B

## Security Boundaries

| Layer | Protection |
|-------|-----------|
| iDempiere | AD_Role controls who can access AI assistant |
| HTTP | Plugin ↔ Python on localhost only, not exposed |
| PostgreSQL | Python uses read-only account, SELECT only |
| SQL | Pre-defined queries only, no dynamic SQL |
| PII | Masked before LLM, mapping not persisted |
| Audit | Full Q&A logged in iDempiere DB |
| Mapping | Ephemeral, destroyed after each response |

## Tech Stack

**iDempiere Plugin:**
- Java 17 + OSGi
- ZK 9.x (chat window UI)
- Apache HttpClient 5.x (call Python)
- 2Pack (install DB schema)

**Python AI Service:**
- FastAPI + uvicorn
- LangGraph (routing)
- langchain-anthropic + langchain-groq (models)
- psycopg2 (PostgreSQL read-only)
- pydantic (data validation)

## Phased Implementation

### Phase 1: Core (MVP)
- Python service with router + 3-5 pre-defined queries + masking
- iDempiere plugin with chat window + logging
- Read-only, no streaming

### Phase 2: Expand
- More pre-defined queries (20+)
- Limited write operations (create draft, update notes)
- Conversation history across sessions

### Phase 3: Harden
- Rate limiting
- Prompt injection detection
- Cost monitoring dashboard
- Docker containerization

## Not In Scope
- Streaming/SSE (future consideration)
- External-facing chatbot
- Dynamic SQL generation
- File upload/attachment
- Voice input
