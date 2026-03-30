# End-to-End Data Flow — Complete System Overview

**Purpose:** This document maps the ENTIRE data flow from user keystroke to AI answer, across all system boundaries. Implementation plans for each layer reference this as the authoritative flow.

**Related Plans:**
- Python Service: `2026-03-30-python-ai-service.md` (Rev 4) — Tasks 1-7
- iDempiere Plugin: `2026-03-30-idempiere-plugin.md` — Tasks 8-14

**Implementation Order:** Bottom-up (Python first, Plugin second), but this overview covers top-down.

---

## Complete Data Flow

```
USER                    iDEMPIERE PLUGIN (Java/OSGi)              PYTHON SERVICE (FastAPI)              EXTERNAL
─────                   ────────────────────────────              ───────────────────────              ────────

1. User opens             2. AIChatForm loads
   "AI Assistant"            via IFormFactory
   from menu                 (AD_Form entry)
      │                          │
      │                    3. Check permission:
      │                       MRole.getFormAccess(formId)
      │                       → denied? show "no access"
      │                          │ allowed
      │                          ▼
      │                    4. Show chat UI:
      │                       Textbox + Send button
      │                       + chat panel (Div)
      │                          │
5. User types            ────────│
   question                      │
   + clicks Send                 │
      │                          ▼
      │                    6. ZK event handler:
      │                       a. Disable button + textbox
      │                       b. Show "AI 思考中..." bubble
      │                       c. desktop.enableServerPush(true)
      │                          │
      │                    7. Background thread:
      │                       Adempiere.getThreadPoolExecutor()
      │                       .submit(new ZkContextRunnable() {
      │                          │
      │                          ▼
      │                    8. AIChatService.ask():
      │                       a. Get org_ids from AD_Role_OrgAccess
      │                       b. Build JSON body (Gson):
      │                          {question, user_id, role_id,
      │                           client_id, org_ids}
      │                       c. Compute HMAC-SHA256 on raw bytes
      │                       d. HTTP POST localhost:8900/ask
      │                          + X-HMAC-Signature header
      │                          │
      │                          │ HTTP POST                        9. FastAPI /ask endpoint:
      │                          │─────────────────────────────────────▶ a. Read raw body bytes
      │                          │                                      b. Verify HMAC signature
      │                          │                                         → 401 if invalid
      │                          │                                      c. Parse AskRequest (Pydantic)
      │                          │                                      d. Check rate limit (20/user/min)
      │                          │                                         → 429 if exceeded
      │                          │                                      e. asyncio.to_thread(process_question)
      │                          │                                         │
      │                          │                                   10. process_question():
      │                          │                                       a. Sanitize input
      │                          │                                          (strip [PII_*] tokens)
      │                          │                                       b. Call Sonnet: classify
      │                          │                                          + select query ──────────────▶ Anthropic API
      │                          │                                          (1 combined call)  ◀──────── {category, query_name, params}
      │                          │                                         │
      │                          │                                       ┌─┴────────────────────────┐
      │                          │                                       │                          │
      │                          │                                  [database_query]          [general / clarification]
      │                          │                                       │                          │
      │                          │                                  11. Force-inject               12. Call LLM directly
      │                          │                                      ad_client_id +                 (Sonnet or Llama 8B)
      │                          │                                      org_ids from request            ──────▶ LLM API
      │                          │                                       │                               ◀──── answer
      │                          │                                  12. executor.execute()                │
      │                          │                                      (ThreadedConnectionPool)          │
      │                          │                                      search_path=adempiere             │
      │                          │                                      fetchmany(200)                    │
      │                          │                                       │                                │
      │                          │                                       ▼                                │
      │                          │                                  PostgreSQL                            │
      │                          │                                  (ai_readonly user)                    │
      │                          │                                  SELECT only                           │
      │                          │                                  AD_Org_ID = ANY(org_ids)              │
      │                          │                                       │                                │
      │                          │                                       ▼                                │
      │                          │                                  13. PIIMasker.mask()                  │
      │                          │                                      name → [PII_C_001]                │
      │                          │                                      taxid → [PII_T_001]               │
      │                          │                                      mapping: {token→original}         │
      │                          │                                       │                                │
      │                          │                                  14. Call Sonnet with                  │
      │                          │                                      masked data ──────────────▶ Anthropic API
      │                          │                                      (timeout=25s)  ◀──────── masked answer
      │                          │                                       │                                │
      │                          │                                  15. PIIMasker.unmask()                │
      │                          │                                      [PII_C_001] → 王大明               │
      │                          │                                      destroy mapping                   │
      │                          │                                       │                                │
      │                          │                                       ├────────────────────────────────┘
      │                          │                                       ▼
      │                          │                                  16. Return AskResponse:
      │                          │   HTTP 200 JSON                      {answer, model_used,
      │                          │◀─────────────────────────────────────  tokens_used, query_used,
      │                          │                                       elapsed_ms}
      │                          ▼
      │                    17. AIChatService receives response:
      │                       a. Parse JSON (Gson)
      │                       b. Save MAIChatLog (best-effort):
      │                          - trxName=null (auto-commit)
      │                          - try-catch: if save fails,
      │                            still return answer
      │                       c. Return answer string
      │                          │
      │                    18. On error (401/429/500/timeout/refused):
      │                       Map to user-friendly message:
      │                       - 401 → "系統設定錯誤，請聯繫管理員"
      │                       - 429 → "請求過於頻繁，請稍候再試"
      │                       - 500 → "AI 服務暫時無法使用"
      │                       - timeout → "請求逾時，請縮短問題"
      │                       - refused → "AI 服務未啟動"
      │                          │
      │                          ▼
      │                    19. ServerPushTemplate.executeAsync():
      │                       Push back to ZK event thread:
      │                       a. Replace "AI 思考中..." with answer
      │                       b. Re-enable button + textbox
      │                       c. Focus textbox
      │                          │
      │                          ▼
20. User sees          ◀──── Answer displayed in chat bubble
    answer                   (PII restored, original names shown)
```

---

## Layer Boundaries

| Layer | Technology | Runs In | Communicates Via |
|-------|-----------|---------|-----------------|
| UI | ZK 9.x Components | iDempiere JVM, ZK event thread | ZK event model |
| Background Thread | Java 17 thread pool | iDempiere JVM, background thread | Method calls |
| HTTP Client | java.net.http.HttpClient | iDempiere JVM, background thread | HTTP + HMAC |
| API Gateway | FastAPI + uvicorn | Python process | HTTP JSON |
| Router | Plain Python functions | Python process (via to_thread) | Method calls |
| Query Executor | psycopg2 + ThreadedConnectionPool | Python process | PostgreSQL wire protocol |
| PII Masker | Pure Python (PIIMasker class) | Python process | Method calls |
| LLM Caller | langchain-anthropic / langchain-groq | Python process | HTTPS to Anthropic/Groq |
| Database | PostgreSQL | Separate process | TCP 5432 |
| External LLM | Claude Sonnet / Groq Llama | Cloud API | HTTPS |

---

## Security Checkpoints (in order of data flow)

| Step | Check | What Happens If Fails |
|------|-------|----------------------|
| 3 | AD_Role permission | User sees "no access", cannot open form |
| 9b | HMAC signature | HTTP 401, request rejected |
| 9d | Rate limit | HTTP 429, request rejected |
| 10a | Input sanitization | PII tokens stripped silently |
| 11 | Force-inject context params | LLM-supplied client_id/org_ids overridden |
| 12 | Read-only DB user | INSERT/UPDATE/DELETE impossible |
| 12 | AD_Org_ID filter | User cannot see other orgs' data |
| 12 | Pre-defined SQL only | No dynamic SQL injection possible |
| 12 | fetchmany(200) | Unbounded result sets capped |
| 13 | PII masking | Real names/IDs never reach external LLM |
| 14 | LLM timeout 25s | Orphaned requests prevented |
| 16 | Generic error response | No PII in error messages |
| 17b | Best-effort audit log | Answer shown even if log write fails |

---

## Implementation Order (bottom-up)

```
IMPLEMENT FIRST (no dependencies):
  Task 1-7: Python Service
    1. Scaffold + config + conftest
    2. PII Masking layer
    3. Query Registry + Executor
    4. LLM Caller + fallback
    5. Router pipeline
    6. FastAPI endpoint + HMAC + rate limit
    7. DB setup + manual test

IMPLEMENT SECOND (depends on Python service running):
  Task 8-14: iDempiere Plugin
    8.  Plugin scaffold (pom.xml, MANIFEST.MF, Activator)
    9.  2Pack: AI_ChatLog table + Window + Form + Menu
    10. MAIChatLog PO model + ModelFactory
    11. AIChatService (HTTP client + HMAC + Gson + error mapping)
    12. AIChatForm (ZK UI + background thread + ServerPush)
    13. AIChatFormFactory (OSGi DS registration)
    14. Build JAR + deploy + end-to-end test
```

---

## Configuration Touchpoints

| Config Item | Where (Python) | Where (Java) |
|-------------|---------------|-------------|
| HMAC shared secret | `.env` → `HMAC_SECRET` | `idempiere.properties` → `AI_HMAC_SECRET` or system property |
| Python service URL | N/A (it IS the service) | `idempiere.properties` → `AI_SERVICE_URL=http://localhost:8900` |
| Anthropic API key | `.env` → `ANTHROPIC_API_KEY` | N/A (Python handles LLM) |
| Groq API key | `.env` → `GROQ_API_KEY` | N/A (Python handles LLM) |
| DB read-only user | `.env` → `DB_USER`, `DB_PASSWORD` | N/A (Python connects directly) |
| DB host/port/name | `.env` → `DB_HOST`, `DB_PORT`, `DB_NAME` | Already configured in iDempiere |
