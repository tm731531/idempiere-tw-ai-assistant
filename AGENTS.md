# Agent Configuration

## Project: iDempiere AI Assistant

### Roles Table

| Role | Model | Responsibility | Files |
|------|-------|---------------|-------|
| Lead / Architect | opus | Design decisions, plan review, code review, spec updates | CLAUDE.md, docs/, all |
| Python Service Dev | sonnet | Implement service/ tasks per plan (Rev 4), TDD | service/**/*.py |
| Plugin Dev | sonnet | Implement plugin/ tasks per plan (Phase 2) | plugin/**/*.java |
| Explorer / Research | haiku | Search codebase, find patterns, check iDempiere APIs | read-only |

### Workflow Rules

1. **Always read the plans first:**
   - End-to-end: `docs/superpowers/plans/2026-03-30-end-to-end-overview.md`
   - Python (Tasks 1-7): `docs/superpowers/plans/2026-03-30-python-ai-service.md` (Rev 4)
   - Plugin (Tasks 8-14): `docs/superpowers/plans/2026-03-30-idempiere-plugin.md`
2. **TDD strictly** — Write failing test → verify fail → implement → verify pass → commit
3. **One task at a time** — Complete and commit before moving to next task
4. **Never generate dynamic SQL** — All SQL must be in `service/app/queries/definitions/`
5. **Reference tw-invoice for Java patterns** — `/home/tom/idempiere-tw-invoice-system/`
6. **Context params from request** — `ad_client_id`/`org_ids` always from HTTP request, never from LLM output
7. **No LangGraph** — Removed from dependencies. Plain Python functions for routing.

### Pre-Flight Checklist (before any agent starts work)

- [ ] Read CLAUDE.md (this project)
- [ ] Read the design spec in docs/superpowers/specs/ (Rev 4)
- [ ] Read the implementation plan in docs/superpowers/plans/ (Rev 4)
- [ ] Verify .env exists with API keys (service/)
- [ ] Verify directory structure matches plan
- [ ] Verify conftest.py exists in service/tests/ (Task 1 creates it)

### Critical Implementation Notes (from 4 rounds of review)

**Test mocking pattern:**
- router.py uses lazy-init singletons (`_caller`, `_executor`)
- Tests inject mocks via `router_module._caller = mock_caller` (NOT `@patch("app.router.LLMCaller")`)
- Integration tests must patch `init_pool`/`close_pool` to avoid real DB connections

**HMAC pattern:**
- Sign the raw JSON bytes you send, verify the raw bytes you receive
- Tests use `content=body_bytes` (NOT `json=body`) to control exact bytes
- No canonical form needed — Java and Python don't need identical serialization

**Security:**
- After LLM returns query params, force-override `ad_client_id` and `org_ids` from request context
- Never expose exception details to HTTP response — always generic "Request processing failed"

### Agent Team Resource Limits

- Max 3 agents concurrent (16GB machine)
- Opus agents: ~1GB each
- Sonnet agents: ~600MB each
- Haiku agents: ~400MB each
- Check `free -h` before spawning

### Review History

| Round | Reviewers | Findings | Result |
|-------|-----------|----------|--------|
| R1 | Opus + 2×Haiku | 8 CRITICAL (HMAC, PII, async, org_ids) | Spec+Plan Rev 2 |
| R2 | Opus | Code not updated in plan | Plan Rev 2 code rewrite |
| R3 | 2×Opus | 4 CRITICAL joints (ZK thread, HMAC bytes, PG schema, pool) | Spec+Plan Rev 3 |
| R4 | 3×Opus | 4 BLOCKED (conftest order, mock targets, lifespan, security) | Spec+Plan Rev 4 |
