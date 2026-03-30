# iDempiere AI Assistant

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
3. **Read-only DB** — Python connects with `ai_readonly` PostgreSQL user (SELECT only, search_path=adempiere)
4. **localhost + HMAC** — Python service on localhost, requests authenticated via HMAC-SHA256 on raw body bytes
5. **Audit trail in iDempiere** — Every Q&A logged in AI_ChatLog table (best-effort, never blocks answer)
6. **PII scope** — Taiwan 個資法: name, national ID, tax ID, phone, email, address, DOB
7. **All code in English** — Comments, variables, output messages, docs
8. **No PII in errors** — Exception messages return generic text, never include DB data or stack traces
9. **Context params from request** — ad_client_id and org_ids ALWAYS injected from request, NEVER from LLM output
10. **Org-level filtering** — All SQL queries include AD_Org_ID = ANY(org_ids) filter

## Design Spec
`docs/superpowers/specs/2026-03-30-idempiere-tw-ai-assistant-design.md` (Rev 4)

## Implementation Plans
- **End-to-End Overview:** `docs/superpowers/plans/2026-03-30-end-to-end-overview.md` — complete data flow from UI to LLM
- **Python Service (Tasks 1-7):** `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Rev 4)
- **iDempiere Plugin (Tasks 8-14):** `docs/superpowers/plans/2026-03-30-idempiere-plugin.md`

## Implementation Order
1. **Phase 1 (current):** Python AI Service — 7 tasks, TDD
2. **Phase 2:** iDempiere Plugin — ZK Form + AIChatService + MAIChatLog
3. **Phase 3:** Harden — prompt injection detection, cost monitoring, Docker

## Key Paths
- iDempiere source: `/home/tom/idempiere/` (release-12)
- iDempiere server: `/opt/idempiere-server/x86_64/`
- iDempiere DB: PostgreSQL on localhost:5432, database `idempiere`, schema `adempiere`
- tw-invoice plugin (reference): `/home/tom/idempiere-tw-invoice-system/`

## Running (Python Service)
```bash
cd service/
cp .env.example .env  # fill in API keys + DB credentials + HMAC_SECRET
pip install -r requirements.txt
python -m app.main    # starts on localhost:8900
```

## Testing
```bash
cd service/
pytest tests/ -v
# All tests use mocks — no real DB or API keys needed
```

## Phase 1 Done Criteria
- All pytest pass (~30 tests)
- `/health` returns `{"status": "ok", "db": "connected"}`
- One successful `/ask` round-trip with real LLM + real DB via manual test script

## Integration Joints (critical connection points)
| Joint | Key Constraint |
|-------|----------------|
| ZK → Thread | `getThreadPoolExecutor()` + `ServerPushTemplate`, NOT `Executions.schedule()` |
| Java → Python HTTP | HMAC on raw body bytes; `java.net.http.HttpClient` singleton; Gson for JSON |
| Python → PostgreSQL | `ThreadedConnectionPool`; `search_path=adempiere`; `fetchmany(200)` row limit |
| Security params | `ad_client_id`/`org_ids` force-injected from request, override LLM output |
| LLM timeouts | Python 25s < Java 30s (prevents orphaned requests) |
| Error boundary | Generic messages only; 401/429/500/timeout → specific user-facing text |
| Audit log | Best-effort `trxName=null`; never blocks answer display |
