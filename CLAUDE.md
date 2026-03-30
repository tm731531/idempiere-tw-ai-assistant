# iDempiere TW AI Assistant

## What This Is
A monorepo containing two sub-projects that together provide an AI-powered Q&A assistant for iDempiere ERP:
- `service/` — Python FastAPI backend (Sonnet classify+select, PII masking, pre-defined SQL queries)
- `plugin/` — Java iDempiere OSGi plugin (ZK Form chat UI, audit logging, permission control)

## Architecture
```
iDempiere Plugin (Java)
  → HTTP POST + HMAC-SHA256 (raw body bytes)
  → Python AI Service (FastAPI @ localhost:8900)
      ├─ HMAC verify
      ├─ Input sanitize (strip [PII_*] tokens)
      ├─ Sonnet: classify question + select query (1 call)
      ├─ Query Executor (read-only PostgreSQL, adempiere schema, ThreadedConnectionPool)
      ├─ PII Masker ([PII_C_001] format, per-request mapping)
      ├─ LLM Caller (Sonnet/Llama + fallback, timeout=25s)
      ├─ PII Unmasker (restore tokens → original values)
      └─ Return {answer, model_used, tokens_used}
```

## Iron Rules
1. **SQL is pre-defined** — AI selects which query + fills params, NEVER generates dynamic SQL
2. **Reversible PII masking** — PII → [PII_*] tokens before LLM, restore after. Mapping is per-request, ephemeral
3. **Read-only DB** — Python connects with `ai_readonly` PostgreSQL user (SELECT only, search_path=adempiere, statement_timeout=10s)
4. **localhost + HMAC** — Python service on localhost, requests authenticated via HMAC-SHA256 on raw body bytes
5. **Audit trail in iDempiere** — Every Q&A logged in AI_ChatLog table (best-effort, never blocks answer)
6. **PII scope** — Taiwan 個資法: name, national ID, tax ID, phone, email, address, DOB
7. **All code in English** — Comments, variables, output messages, docs
8. **No PII in errors** — Exception messages return generic text, never include DB data or stack traces
9. **Context params from request** — ad_client_id and org_ids ALWAYS injected from request, NEVER from LLM output
10. **Org-level filtering** — All SQL queries include AD_Org_ID = ANY(org_ids) filter
11. **Thread pool isolation** — Plugin uses its own ExecutorService(4), NOT iDempiere's shared getThreadPoolExecutor()

## Design Spec
`docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md` (Rev 5)

## Implementation Plans
- **End-to-End Overview:** `docs/superpowers/plans/2026-03-30-end-to-end-overview.md`
- **Python Service (Tasks 1-7):** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Rev 5)
- **iDempiere Plugin (Tasks 8-14):** `docs/superpowers/plans/2026-03-30-idempiere-plugin.md` (Rev 5)

## Implementation Order
1. **Phase 1 (current):** Python AI Service — 7 tasks, TDD → then iDempiere Plugin — 7 tasks
2. **Phase 2:** Expand queries, conversation history, write ops (via iDempiere API, NOT direct SQL)
3. **Phase 3:** Prompt injection detection, cost monitoring, Docker

## Key Paths
- iDempiere source: `/home/tom/idempiere/` (release-12)
- iDempiere server: `/opt/idempiere-server/x86_64/`
- iDempiere DB: PostgreSQL on localhost:5432, database `idempiere`, schema `adempiere`
- tw-invoice plugin (reference): `/home/tom/idempiere-tw-invoice-system/`

## Running (Python Service)
```bash
cd service/
cp .env.example .env  # fill in DB credentials + HMAC_SECRET
pip install -r requirements.txt

# Mock mode (plugin development, no token cost):
MOCK_LLM=true python -m app.main

# Real mode (requires API keys in .env):
MOCK_LLM=false python -m app.main
```

## Testing
```bash
# Unit tests (all mocked, no DB/API needed):
cd service/
pytest tests/ -v

# Integration test (mock mode, real DB, no LLM cost):
# 1. Set MOCK_LLM=true in .env
# 2. python -m app.main
# 3. Deploy plugin JAR → open AI Chat form → verify round-trip
```

## Mock Mode (MOCK_LLM=true)
- HMAC, rate limit, DB queries, PII masking all work normally
- LLM calls return canned responses (no API cost, no API keys needed)
- Use this for plugin development and end-to-end testing
- Switch to MOCK_LLM=false + real API keys for production

## Phase 1 Done Criteria
- All pytest pass (35 tests: 10+6+5+4+5+5)
- `/health` returns `{"status": "ok", "db": "connected"}`
- One successful `/v1/ask` round-trip with real LLM + real DB via manual test script
- Plugin deployed, AI Chat form opens, end-to-end Q&A works

## Integration Joints
| Joint | Key Constraint |
|-------|----------------|
| ZK → Thread | `AI_THREAD_POOL` (isolated, max 4), NOT shared `getThreadPoolExecutor()` |
| Java → Python HTTP | HMAC on raw body bytes; `java.net.http.HttpClient` singleton; Gson; `/v1/ask` |
| Python → PostgreSQL | `ThreadedConnectionPool`; `search_path=adempiere`; `statement_timeout=10s`; `fetchmany(200)` |
| Security params | `ad_client_id`/`org_ids` force-injected from request, override LLM output |
| LLM timeouts | Python 25s < Java 30s (prevents orphaned requests) |
| Error boundary | Generic messages only; 401/429/500/timeout → specific user-facing Chinese text |
| DB errors | executor catches exceptions, returns generic "Database query failed", logs detail server-side |
| Audit log | Best-effort `trxName=null`; never blocks answer display |

## Review History (6 rounds, 17 AI expert agents)
| Round | Experts | Result |
|-------|---------|--------|
| R1 | Opus + 2×Haiku | 12 fixes → Rev 2 |
| R2 | Opus | Code blocks rewritten |
| R3 | 2×Opus | 12 joint fixes → Rev 3 |
| R4 | 3×Opus | 10 fixes → Rev 4 |
| R5 | 2×Opus | 4 MUST + 6 SHOULD → Rev 5 |
| R6 | 2×Opus + Haiku | 62/62 checks ✅ READY |
