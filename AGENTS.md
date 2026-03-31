# Agent Configuration

## Project: iDempiere TW AI Assistant

### Roles Table

| Role | Model | Responsibility | Files |
|------|-------|---------------|-------|
| Lead / Architect | **opus** | Design decisions, plan review, code review, spec updates | CLAUDE.md, docs/, all |
| Python Service Dev | **haiku** | Implement service/ tasks per plan, TDD, copy-paste from plan | service/**/*.py |
| Plugin Dev | **haiku** | Implement plugin/ tasks per plan | plugin/**/*.java |
| Code Review | **opus** | Review completed tasks before merge | all |
| Explorer / Research | **haiku** | Search codebase, find patterns, check iDempiere APIs | read-only |

> **Note:** Sonnet is currently unavailable (resets Apr 3). Use Opus for thinking/review, Haiku for implementation. Haiku follows plan code blocks closely (copy-paste level); Opus reviews the output.

### Workflow Rules

1. **Always read the plans first:**
   - End-to-end: `docs/superpowers/plans/2026-03-30-end-to-end-overview.md`
   - Python (Tasks 1-7): `docs/superpowers/plans/2026-03-30-python-ai-service.md`
   - Plugin (Tasks 8-14): `docs/superpowers/plans/2026-03-30-idempiere-plugin.md`
2. **TDD strictly** — Write failing test → verify fail → implement → verify pass → commit
3. **One task at a time** — Complete and commit before moving to next task
4. **Never generate dynamic SQL** — All SQL must be in `service/app/queries/definitions/`
5. **Reference tw-invoice for Java patterns** — `/home/tom/idempiere-tw-invoice-system/`
6. **Context params from request** — `ad_client_id`/`org_ids` always from HTTP request, never from LLM output
7. **No LangGraph** — Removed from dependencies. Plain Python functions for routing.
8. **Thread pool isolation** — Plugin uses `AI_THREAD_POOL`, NOT `Adempiere.getThreadPoolExecutor()`
9. **API versioning** — All endpoints use `/v1/` prefix

### Pre-Flight Checklist (before any agent starts work)

- [ ] Read CLAUDE.md → get Domain Brain + Domain Skill declarations
- [ ] Read Domain Brains: `brain/idempiere-osgi-bundle.md`, `brain/idempiere-2pack.md`, `brain/idempiere-po-model.md`, `brain/python-llm-integration.md`
- [ ] Read Domain Skills (invoke via Skill tool): `idempiere-zul-form`, `idempiere-mapped-model-factory-service`, `idempiere-osgi-event-handler`
- [ ] Read the design spec in docs/superpowers/specs/ (Rev 5)
- [ ] Read the relevant implementation plan (Python or Plugin)
- [ ] Verify .env exists with API keys (service/)
- [ ] Verify directory structure matches plan
- [ ] Verify conftest.py exists in service/tests/ (Task 1 creates it)

### Critical Implementation Notes (from 6 rounds of review)

**Test mocking pattern (Python):**
- router.py uses lazy-init singletons (`_caller`, `_executor`)
- Tests inject mocks via `router_module._caller = mock_caller` (NOT `@patch("app.router.LLMCaller")`)
- Integration tests must patch `init_pool`/`close_pool` to avoid real DB connections

**HMAC pattern (both sides):**
- Sign the raw JSON bytes you send, verify the raw bytes you receive
- Tests use `content=body_bytes` (NOT `json=body`) to control exact bytes
- No canonical form needed — Java and Python don't need identical serialization

**Security:**
- After LLM returns query params, force-override `ad_client_id` and `org_ids` from request context
- Never expose exception details to HTTP response — always generic "Request processing failed"
- DB errors caught in executor, logged server-side, generic message to client

**Java plugin:**
- Use isolated `Executors.newFixedThreadPool(4)` for AI requests
- org_ids from `AD_Role_OrgAccess` table (NOT `MRole.getOrgAccess()` which is private)
- `AI_SERVICE_URL` and `AI_HMAC_SECRET` both from `System.getProperty` (Phase 1; Phase 2 may move URL to MSysConfig)
- Error mapping: 401→系統設定錯誤, 429→請求過於頻繁, 500→暫時無法使用

### Agent Team Resource Limits

- Max 3 agents concurrent (16GB machine)
- Opus agents: ~1GB each
- Haiku agents: ~400MB each
- Check `free -h` before spawning
- **Current constraint:** Sonnet unavailable, use Opus + Haiku only

### Review History

| Round | Reviewers | Findings | Result |
|-------|-----------|----------|--------|
| R1 | Opus + 2×Haiku | 8 CRITICAL (HMAC, PII, async, org_ids) | Rev 2 |
| R2 | Opus | Code not updated → full rewrite | Rev 2 code |
| R3 | 2×Opus | 4 CRITICAL joints (ZK thread, HMAC bytes, PG schema, pool) | Rev 3 |
| R4 | 3×Opus | 4 BLOCKED (conftest, mock targets, lifespan, security) | Rev 4 |
| R5 | 2×Opus | Old×New system dialog: thread pool, statement_timeout, /v1, language | Rev 5 |
| R6 | 2×Opus + Haiku | Final: 62/62 checks PASS | ✅ READY |
