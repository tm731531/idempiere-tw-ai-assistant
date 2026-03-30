# iDempiere AI Assistant

## What This Is
A monorepo containing two sub-projects that together provide an AI-powered Q&A assistant for iDempiere ERP:
- `service/` — Python FastAPI backend (LangGraph multi-model routing, PII masking, pre-defined SQL queries)
- `plugin/` — Java iDempiere OSGi plugin (ZK chat window UI, audit logging, permission control)

## Architecture
```
iDempiere Plugin (Java) → HTTP POST → Python AI Service (FastAPI)
                                        ├─ Router (Llama 8B classifies)
                                        ├─ Query Executor (read-only PostgreSQL)
                                        ├─ PII Masker (reversible tokenization)
                                        ├─ LLM Caller (Sonnet/Llama + fallback)
                                        └─ PII Unmasker (restore tokens)
```

## Iron Rules
1. **SQL is pre-defined** — AI selects which query + fills params, NEVER generates dynamic SQL
2. **Reversible PII masking** — PII → tokens before LLM, tokens → PII after LLM. Mapping is ephemeral
3. **Read-only DB** — Python connects with `ai_readonly` PostgreSQL user (SELECT only)
4. **localhost only** — Python service not exposed to network
5. **Audit trail in iDempiere** — Every Q&A logged in AI_ChatLog table
6. **PII scope** — Taiwan 個資法: name, national ID, tax ID, phone, email, address, DOB
7. **All code in English** — Comments, variables, output messages, docs

## Design Spec
`docs/superpowers/specs/2026-03-30-idempiere-ai-assistant-design.md`

## Implementation Plans
- Python Service: `docs/superpowers/plans/2026-03-30-python-ai-service.md`
- iDempiere Plugin: (to be written after service is complete)

## Implementation Order
1. **Phase 1 (current):** Python AI Service — 7 tasks, TDD
2. **Phase 2:** iDempiere Plugin — ZK chat window + AIChatProcess + MAIChatLog
3. **Phase 3:** Harden — rate limiting, prompt injection detection, Docker

## Key Paths
- iDempiere source: `/home/tom/idempiere/` (release-12)
- iDempiere server: `/opt/idempiere-server/x86_64/`
- iDempiere DB: PostgreSQL on localhost:5432, database `idempiere`
- tw-invoice plugin (reference): `/home/tom/idempiere-tw-invoice-system/`

## Running (Python Service)
```bash
cd service/
cp .env.example .env  # fill in API keys + DB credentials
pip install -r requirements.txt
python -m app.main    # starts on localhost:8900
```

## Testing
```bash
cd service/
pytest tests/ -v
```
