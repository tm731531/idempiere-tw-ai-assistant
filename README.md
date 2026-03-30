# iDempiere TW AI Assistant

An AI-powered Q&A assistant for [iDempiere](https://www.idempiere.org/) ERP, designed for Taiwan's regulatory environment (Personal Data Protection Act compliance).

Users ask natural language questions about ERP data through a chat interface. The system queries the database using pre-approved SQL, masks personally identifiable information before sending to external LLMs, and returns answers with PII restored.

## Architecture

```
┌────────────────────────────┐         ┌──────────────────────────────────┐
│  iDempiere Plugin (Java)   │  HTTP   │  Python AI Service (FastAPI)     │
│                            │  POST   │                                  │
│  ZK Form chat UI           │────────>│  HMAC verify                     │
│  Permission check (Role)   │  HMAC   │  Classify + select query (1 call)│
│  Audit log (AI_ChatLog)    │<────────│  Execute pre-defined SQL         │
│                            │  JSON   │  Mask PII → LLM → Unmask PII    │
└────────────────────────────┘         └──────────┬───────────────────────┘
                                                  │ read-only
                                                  ▼
                                       ┌──────────────────────┐
                                       │  PostgreSQL           │
                                       │  (iDempiere DB)       │
                                       │  schema: adempiere    │
                                       └──────────────────────┘
```

## Project Structure

```
idempiere-tw-ai-assistant/
├── service/               # Python AI Service (Phase 1)
│   ├── app/
│   │   ├── main.py        # FastAPI + HMAC auth + rate limit
│   │   ├── config.py      # Environment configuration
│   │   ├── router.py      # Classify → query → mask → LLM → unmask
│   │   ├── queries/       # Pre-defined SQL registry
│   │   ├── masking/       # Reversible PII tokenization
│   │   └── llm/           # LLM caller with fallback
│   ├── tests/             # ~34 tests, all mocked
│   ├── requirements.txt
│   └── .env.example
├── plugin/                # Java iDempiere Plugin (Phase 2)
├── scripts/
│   └── create_readonly_user.sql
└── docs/
    └── superpowers/
        ├── specs/         # Design specification (Rev 4)
        └── plans/         # Implementation plan (Rev 4)
```

## Key Design Decisions

### Security

| Measure | Detail |
|---------|--------|
| **Pre-defined SQL only** | AI selects which query to run and fills parameters. It never generates dynamic SQL. |
| **PII masking** | All personal data (name, ID, tax ID, phone, email, address, DOB) is replaced with tokens like `[PII_C_001]` before reaching any external LLM. Tokens are restored in the response. Mapping is per-request and ephemeral. |
| **Read-only database** | Python service connects with a PostgreSQL user that only has SELECT privileges. |
| **HMAC authentication** | Requests from the iDempiere plugin are signed with HMAC-SHA256. The Python service verifies the signature on the raw request body bytes. |
| **Org-level filtering** | All SQL queries filter by the user's accessible organizations (`AD_Org_ID`). Security-sensitive parameters (`ad_client_id`, `org_ids`) are always injected from the HTTP request context, never from LLM output. |
| **Generic error responses** | Exception messages never include database data, stack traces, or PII. |

### Taiwan Personal Data Protection Act (個資法) Compliance

PII fields masked before external LLM calls:
- Name (姓名)
- National ID (身分證號)
- Tax ID (統一編號)
- Phone (電話)
- Email (電子信箱)
- Address (地址)
- Date of birth (生日)

### Multi-Model Routing

| Role | Model | When |
|------|-------|------|
| Classify + select query | Claude Sonnet | Every question (1 call) |
| Answer with data | Claude Sonnet | Database query results |
| Ask for clarification | Groq Llama 8B | Vague questions |
| Fallback | Sonnet ↔ Llama 70B | When primary model fails |

All LLM calls have a 25-second timeout (under the Java plugin's 30-second HTTP timeout to prevent orphaned requests).

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL (iDempiere database)
- API keys: [Anthropic](https://console.anthropic.com/settings/keys) + [Groq](https://console.groq.com/keys)

### 1. Set up the read-only database user

```sql
-- Run as PostgreSQL superuser
psql -U postgres -d idempiere -f scripts/create_readonly_user.sql
```

### 2. Configure and run the Python service

```bash
cd service/
cp .env.example .env
# Edit .env: fill in API keys, DB credentials, HMAC_SECRET

pip install -r requirements.txt
python -m app.main
# Service starts on http://localhost:8900
```

### 3. Verify

```bash
# Health check (includes DB connectivity)
curl http://localhost:8900/health
# → {"status": "ok", "service": "idempiere-ai-service", "db": "connected"}
```

## Testing

All tests use mocks — no real database or API keys needed.

```bash
cd service/
pytest tests/ -v
```

## Phased Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1** | Python AI Service: router, 3 pre-defined queries, PII masking, HMAC auth, rate limiting | In progress |
| **Phase 2** | iDempiere Plugin: ZK Form chat UI, AIChatService, MAIChatLog audit table, role permissions | Planned |
| **Phase 3** | Hardening: prompt injection detection, cost monitoring, Docker containerization | Planned |

## API Reference

### POST /ask

Processes a natural language question about ERP data.

**Headers:**
- `Content-Type: application/json`
- `X-HMAC-Signature: <hmac-sha256 hex digest of raw request body>`

**Request:**
```json
{
  "question": "上個月營收最高的前5個客戶是誰？",
  "user_id": 100,
  "role_id": 200,
  "client_id": 11,
  "org_ids": [1, 2]
}
```

**Response:**
```json
{
  "answer": "營收最高的客戶是王大明，金額為 500,000 元...",
  "model_used": "sonnet",
  "tokens_used": 1234,
  "query_used": "top_customers_by_revenue",
  "elapsed_ms": 3200
}
```

**Error codes:**
| Code | Meaning |
|------|---------|
| 401 | Invalid or missing HMAC signature |
| 429 | Rate limit exceeded (20 requests/user/minute) |
| 500 | Processing failed (generic message, no PII) |

### GET /health

Returns service status and database connectivity.

```json
{"status": "ok", "service": "idempiere-ai-service", "db": "connected"}
```

## Design Documents

- **Design Spec (Rev 4):** [`docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md`](docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md)
- **Implementation Plan (Rev 4):** [`docs/superpowers/plans/2026-03-30-python-ai-service.md`](docs/superpowers/plans/2026-03-30-python-ai-service.md)

The design went through 5 rounds of review by 13 AI expert agents covering iDempiere/OSGi, Python/FastAPI, security/PII, architecture, developer implementability, and project management perspectives.

## License

MIT
