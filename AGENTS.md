# Agent Configuration

## Project: iDempiere AI Assistant

### Roles Table

| Role | Model | Responsibility | Files |
|------|-------|---------------|-------|
| Lead / Architect | opus | Design decisions, plan review, code review, spec updates | CLAUDE.md, docs/, all |
| Python Service Dev | sonnet | Implement service/ tasks per plan, TDD | service/**/*.py |
| Plugin Dev | sonnet | Implement plugin/ tasks per plan (Phase 2) | plugin/**/*.java |
| Explorer / Research | haiku | Search codebase, find patterns, check iDempiere APIs | read-only |

### Workflow Rules

1. **Always read the plan first** — `docs/superpowers/plans/2026-03-30-python-ai-service.md`
2. **TDD strictly** — Write failing test → verify fail → implement → verify pass → commit
3. **One task at a time** — Complete and commit before moving to next task
4. **Never generate dynamic SQL** — All SQL must be in `service/app/queries/definitions/`
5. **Reference tw-invoice for Java patterns** — `/home/tom/idempiere-tw-invoice-system/`

### Pre-Flight Checklist (before any agent starts work)

- [ ] Read CLAUDE.md (this project)
- [ ] Read the design spec in docs/superpowers/specs/
- [ ] Read the implementation plan in docs/superpowers/plans/
- [ ] Verify .env exists with API keys (service/)
- [ ] Verify directory structure matches plan

### Agent Team Resource Limits

- Max 3 agents concurrent (16GB machine)
- Sonnet agents: ~600MB each
- Haiku agents: ~400MB each
- Check `free -h` before spawning
