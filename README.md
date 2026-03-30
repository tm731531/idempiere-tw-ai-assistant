# iDempiere TW AI Assistant

An AI-powered Q&A assistant for [iDempiere](https://www.idempiere.org/) ERP, designed for Taiwan's regulatory environment (Personal Data Protection Act compliance).

Users ask natural language questions about ERP data through a chat interface in iDempiere. The system queries the database using pre-approved SQL, masks personally identifiable information before sending to external LLMs, and returns answers with PII restored.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  iDempiere (Java/OSGi)                                   │
│                                                          │
│  ┌──────────────────────────────────────────────┐        │
│  │  AIChatForm (ZK Form via IFormFactory)       │        │
│  │  ┌────────────────────────────────────┐      │        │
│  │  │  Chat UI: input + bubbles + spinner│      │        │
│  │  └────────────────┬───────────────────┘      │        │
│  │                   │ onClick                   │        │
│  │                   ▼                           │        │
│  │  ┌────────────────────────────────────┐      │        │
│  │  │  AI_THREAD_POOL (isolated, max 4)  │      │        │
│  │  │  NOT shared getThreadPoolExecutor  │      │        │
│  │  └────────────────┬───────────────────┘      │        │
│  │                   │ ZkContextRunnable          │        │
│  │                   ▼                           │        │
│  │  ┌────────────────────────────────────┐      │        │
│  │  │  AIChatService                     │      │        │
│  │  │  ├─ Permission: MRole.getFormAccess│      │        │
│  │  │  ├─ Org IDs: AD_Role_OrgAccess    │      │        │
│  │  │  ├─ JSON: Gson                    │      │        │
│  │  │  ├─ HMAC-SHA256 on raw bytes      │      │        │
│  │  │  ├─ HTTP: java.net.http.HttpClient│      │        │
│  │  │  └─ Error: 401/429/500 → 中文訊息  │      │        │
│  │  └────────────────┬───────────────────┘      │        │
│  │                   │                           │        │
│  │                   │ ServerPushTemplate         │        │
│  │                   ▼ .executeAsync()           │        │
│  │  ┌────────────────────────────────────┐      │        │
│  │  │  MAIChatLog (audit trail)          │      │        │
│  │  │  best-effort save, trxName=null    │      │        │
│  │  └────────────────────────────────────┘      │        │
│  └──────────────────────────────────────────────┘        │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ POST /v1/ask + X-HMAC-Signature
                         │ {question, user_id, role_id,
                         │  client_id, org_ids, language}
                         ▼
┌──────────────────────────────────────────────────────────┐
│  Python AI Service (FastAPI @ localhost:8900)             │
│                                                          │
│  ┌─ HMAC verify (raw body bytes)                         │
│  ├─ Rate limit (20 req/user/min)                         │
│  ├─ Input sanitize (strip [PII_*] tokens)                │
│  ├─ Sonnet: classify + select query (1 combined call)    │
│  ├─ Force-inject ad_client_id/org_ids from request       │
│  ├─ Query Executor ──────────────────────────────┐       │
│  │   ThreadedConnectionPool                      │       │
│  │   search_path=adempiere                       ▼       │
│  │   statement_timeout=10s              ┌──────────────┐ │
│  │   fetchmany(200)                     │ PostgreSQL   │ │
│  │                                      │ ai_readonly  │ │
│  ├─ PII Masker                          │ SELECT only  │ │
│  │   name → [PII_C_001]                └──────────────┘ │
│  │   taxid → [PII_T_001]                                │
│  │   per-request mapping                                 │
│  │                                                       │
│  ├─ LLM Caller (timeout=25s) ────────────────────┐       │
│  │   Sonnet (primary)                            ▼       │
│  │   Llama 70B (fallback)              ┌──────────────┐  │
│  │   Llama 8B (clarification)          │ Anthropic /  │  │
│  │                                     │ Groq Cloud   │  │
│  ├─ PII Unmasker                       └──────────────┘  │
│  │   [PII_C_001] → 王大明                                 │
│  │   destroy mapping                                     │
│  │                                                       │
│  └─ Return {answer, model_used, tokens_used}             │
└──────────────────────────────────────────────────────────┘
```

## Project Structure

```
idempiere-tw-ai-assistant/
├── plugin/                # Java iDempiere Plugin
│   ├── pom.xml            # Maven, parent: iDempiere 12
│   ├── META-INF/
│   │   └── MANIFEST.MF    # OSGi bundle config
│   ├── OSGI-INF/          # DS component registrations
│   │   ├── AIAssistantModelFactory.xml
│   │   └── AIChatFormFactory.xml
│   ├── resources/
│   │   └── 2pack/         # AI_ChatLog table + Window + Form + Menu
│   └── src/idempiere/ai/assistant/
│       ├── AIAssistantActivator.java
│       ├── model/
│       │   ├── MAIChatLog.java           # PO model (@Model)
│       │   └── AIAssistantModelFactory.java
│       ├── service/
│       │   ├── AIChatService.java        # HTTP + HMAC + Gson + errors
│       │   └── HmacUtil.java
│       └── form/
│           ├── AIChatForm.java           # ZK chat UI
│           └── AIChatFormFactory.java    # IFormFactory
├── service/               # Python AI Service
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
├── scripts/
│   └── create_readonly_user.sql
└── docs/
    └── superpowers/
        ├── specs/         # Design specification (Rev 5)
        └── plans/         # 3 plans: overview + python + plugin
```

## Configuration

### API Keys & Secrets

```
Python 端 (service/.env)         Java 端 (iDempiere 啟動參數)
─────────────────────────        ──────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...     (not needed — Python handles LLM)
GROQ_API_KEY=gsk_...             (not needed — Python handles LLM)
HMAC_SECRET=random-string   ←→  -DAI_HMAC_SECRET=same-random-string
DB_HOST=localhost                (not needed — uses iDempiere's DB)
DB_PORT=5432
DB_NAME=idempiere
DB_USER=ai_readonly
DB_PASSWORD=xxx
SERVICE_PORT=8900                AI_SERVICE_URL in MSysConfig table
```

Key principle: **Java side never touches LLM API keys.** All AI calls go through Python. Java only needs the HMAC shared secret.

### Where to get API keys

| Key | Source | Cost |
|-----|--------|------|
| Anthropic (Claude) | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) | Pay per token |
| Groq (Llama) | [console.groq.com/keys](https://console.groq.com/keys) | Free tier available |

## Key Design Decisions

### Security

| Measure | Detail |
|---------|--------|
| **Pre-defined SQL only** | AI selects which query to run and fills parameters. It never generates dynamic SQL. |
| **PII masking** | All personal data (name, ID, tax ID, phone, email, address, DOB) is replaced with tokens like `[PII_C_001]` before reaching any external LLM. Tokens are restored in the response. Mapping is per-request and ephemeral. |
| **Read-only database** | Python connects via `ai_readonly` user (SELECT only, `statement_timeout=10s`, `REVOKE CREATE`). |
| **HMAC authentication** | Requests signed with HMAC-SHA256 on raw request body bytes. No canonical JSON needed. |
| **Org-level filtering** | All SQL queries filter by `AD_Org_ID`. Security params (`ad_client_id`, `org_ids`) always injected from request context, never from LLM output. |
| **Thread pool isolation** | Plugin uses its own `ExecutorService(4)`, never iDempiere's shared thread pool. |
| **Generic error responses** | Exception messages never include database data, stack traces, or PII. DB errors caught in executor, logged server-side only. |

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
| Classify + select query | Claude Sonnet | Every question (1 combined call) |
| Answer with data | Claude Sonnet | Database query results |
| Ask for clarification | Groq Llama 8B | Vague questions |
| Fallback | Sonnet ↔ Llama 70B | When primary model fails |

All LLM calls have a 25-second timeout (under the Java plugin's 30-second HTTP timeout to prevent orphaned requests).

## Getting Started

### Prerequisites

- iDempiere 12 (running)
- Python 3.11+
- PostgreSQL (iDempiere database)
- API keys: Anthropic + Groq

### 1. Set up the read-only database user

```bash
psql -U postgres -d idempiere -f scripts/create_readonly_user.sql
```

### 2. Configure and run the Python service

```bash
cd service/
cp .env.example .env
# Edit .env: fill in API keys, DB credentials, HMAC_SECRET

pip install -r requirements.txt
python -m app.main
# → http://localhost:8900
```

### 3. Verify Python service

```bash
curl http://localhost:8900/health
# → {"status": "ok", "service": "idempiere-ai-service", "db": "connected"}
```

### 4. Deploy iDempiere plugin

```bash
cd plugin/
mvn clean package -DskipTests
cp target/tw.idempiere.ai.assistant-*.jar /opt/idempiere-server/x86_64/plugins/
# Restart iDempiere or refresh OSGi bundles
```

### 5. Configure iDempiere

```bash
# Add to iDempiere startup parameters:
-DAI_HMAC_SECRET=same-secret-as-python-env
# Set AI_SERVICE_URL in MSysConfig table (default: http://localhost:8900)
```

### 6. Use it

1. Login to iDempiere Web UI
2. Menu → AI Assistant
3. Type a question → Send
4. AI answers with ERP data

## Testing

All Python tests use mocks — no real database or API keys needed.

```bash
cd service/
pytest tests/ -v
```

## Phased Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1** | Python Service (Tasks 1-7) + iDempiere Plugin (Tasks 8-14) | Ready to implement |
| **Phase 2** | More queries, conversation history, write ops (via iDempiere API, NOT direct SQL) | Planned |
| **Phase 3** | Prompt injection detection, cost monitoring, Docker | Planned |

## API Reference

### POST /v1/ask

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
  "org_ids": [1, 2],
  "language": "zh_TW"
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

| Code | Meaning | iDempiere UI Message |
|------|---------|---------------------|
| 401 | Invalid or missing HMAC | 系統設定錯誤，請聯繫管理員 |
| 429 | Rate limit exceeded (20/user/min) | 請求過於頻繁，請稍候再試 |
| 500 | Processing failed (generic, no PII) | AI 服務暫時無法使用 |

### GET /health

```json
{"status": "ok", "service": "idempiere-ai-service", "db": "connected"}
```

## Design Documents

- **Design Spec (Rev 5):** [`docs/superpowers/specs/`](docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md)
- **End-to-End Flow:** [`docs/superpowers/plans/2026-03-30-end-to-end-overview.md`](docs/superpowers/plans/2026-03-30-end-to-end-overview.md)
- **Python Plan (Tasks 1-7):** [`docs/superpowers/plans/2026-03-30-python-ai-service.md`](docs/superpowers/plans/2026-03-30-python-ai-service.md)
- **Plugin Plan (Tasks 8-14):** [`docs/superpowers/plans/2026-03-30-idempiere-plugin.md`](docs/superpowers/plans/2026-03-30-idempiere-plugin.md)

The design went through 6 rounds of review by 17 AI expert agents covering iDempiere/OSGi, Python/FastAPI, security/PII, database, architecture, developer implementability, and project management perspectives. Final score: 62/62 checks passed.

## License

MIT
