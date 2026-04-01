# LangGraph Agent Architecture

## Overview

The Python AI Service now uses **LangGraph** for intelligent orchestration with **Tools** for SQL query execution.

## Architecture

```
User Question
    ↓
LangGraph Agent (StateGraph)
    ↓
Classify Node (Llama 8B)
    ↓
┌──────────────────────────────────────┐
│  Conditional Routing                 │
├──────────────────────────────────────┤
│  database_query    → Query Tool      │
│  general_knowledge → Llama 70B       │
│  clarification     → Llama 8B        │
└──────────────────────────────────────┘
    ↓
Answer with PII masking
```

## Tools

### 1. QueryTool (SQL Execution)

**Purpose:** Execute pre-defined SQL queries with automatic security parameter injection.

**How it works:**
1. LLM (Claude Sonnet) selects the best query from registry
2. LLM extracts parameters from user question
3. Tool injects `ad_client_id` and `org_ids` from request context (SECURITY!)
4. QueryExecutor runs the SQL with read-only connection
5. Results are masked for PII before LLM sees them

**Example:**
```python
query_tool = QueryTool(executor, client_id=11, org_ids=[1, 2])
rows = query_tool.execute("top_customers_by_revenue", {
    "date_from": "2026-01-01",
    "date_to": "2026-03-31",
    "limit": 5
})
# ad_client_id=11 and org_ids=[1,2] are automatically injected
```

### 2. GeneralKnowledgeTool

**Purpose:** Answer general questions without database access.

**Model:** Llama 70B (good balance of cost/quality)

### 3. ClarificationTool

**Purpose:** Ask for more details when question is too vague.

**Model:** Llama 8B (cheap, sufficient for simple questions)

## State Graph

### AgentState Fields

| Field | Type | Description |
|-------|------|-------------|
| `question` | str | Original user question |
| `sanitized_question` | str | Question with PII tokens stripped |
| `user_id` | int | User ID from request |
| `role_id` | int | Role ID from request |
| `client_id` | int | Client ID from request (SECURITY) |
| `org_ids` | List[int] | Org IDs from request (SECURITY) |
| `language` | str | User's language (e.g., "zh_TW") |
| `category` | str | Classification result |
| `query_name` | str | Selected query name |
| `query_params` | dict | Extracted parameters |
| `query_results` | list | Raw query results |
| `pii_mapping` | dict | PII token → original value |
| `answer` | str | Final answer |
| `model_used` | str | Which model was used |
| `tokens_used` | int | Total tokens consumed |
| `elapsed_ms` | int | Total processing time |

### Graph Flow

```
Entry Point → classify_node
                ↓
        route_node (conditional)
                ↓
    ┌───────────┼───────────┐
    ↓           ↓           ↓
database   general    clarification
_query   _knowledge
    ↓           ↓           ↓
    └───────────┼───────────┘
                ↓
              END
```

## Model Selection Strategy

| Node | Model | Reason |
|------|-------|--------|
| classify | Llama 8B | Cheap, fast, sufficient for classification |
| database_query | Claude Sonnet | Best at understanding data context |
| general_knowledge | Llama 70B | Good balance of cost/quality |
| clarification | Llama 8B | Simple questions, cheap is fine |

## Security Features

### 1. Security Parameter Injection

**CRITICAL:** `ad_client_id` and `org_ids` are ALWAYS injected from the HTTP request context, NEVER from LLM output.

```python
# In QueryTool.execute()
params["ad_client_id"] = self.client_id  # From request, not LLM!
params["org_ids"] = self.org_ids  # From request, not LLM!
```

This prevents prompt injection attacks where the LLM might try to access data from other clients or organizations.

### 2. PII Masking

Before query results reach the LLM:
1. Scan for PII columns (name, taxid, phone, email, etc.)
2. Replace values with tokens: `[PII_C_001]`, `[PII_T_001]`, etc.
3. Store mapping in state
4. After LLM generates answer, restore original values

### 3. Pre-defined SQL Only

The LLM can only select from pre-defined queries in `service/app/queries/definitions/`. It cannot generate dynamic SQL.

## Example Execution

**User Question:** "上個月營收最高的前 5 個客戶是誰？"

**Graph Execution:**

1. **classify_node** (Llama 8B):
   - Input: "上個月營收最高的前 5 個客戶是誰？"
   - Output: `category = "database_query"`

2. **database_query_node** (Claude Sonnet):
   - Select query: `top_customers_by_revenue`
   - Extract params: `{"date_from": "2026-02-01", "date_to": "2026-02-28", "limit": 5}`
   - Inject security: `ad_client_id=11, org_ids=[1,2]`
   - Execute SQL → `[{name: "[PII_C_001]", revenue: 500000}, ...]`
   - Mask PII → `[{name: "[PII_C_001]", revenue: 500000}]`
   - Generate answer → `"[PII_C_001] 的營收最高..."`
   - Unmask → `"王大明的營收最高..."`

3. **Return Response:**
   ```json
   {
     "answer": "王大明的營收最高，為 500,000 元",
     "model_used": "sonnet",
     "tokens_used": 234,
     "query_used": "top_customers_by_revenue",
     "elapsed_ms": 1234
   }
   ```

## Testing

Run tests with:
```bash
cd service/
pytest tests/test_router.py -v
```

## Mock Mode

For development without API costs:
```bash
MOCK_LLM=true  # In .env
```

Mock mode:
- ✅ Classification works
- ✅ Query execution works (real DB)
- ✅ PII masking works
- ❌ LLM returns canned response: "Mock response - LLM call skipped in mock mode"

## Dependencies

```txt
langgraph>=0.2       # Agent orchestration
langchain>=0.3       # LLM abstractions
langchain-anthropic  # Claude
langchain-groq      # Groq Llama
```

## Migration Notes

**From:** Plain Python functions (Rev 5)  
**To:** LangGraph StateGraph (current)

**Benefits:**
- Better separation of concerns (Tools)
- Easier to add new tools in Phase 2
- Clear state management
- Visual graph representation possible

**Breaking Changes:**
- Router now uses LangGraph StateGraph
- Tools pattern for SQL execution
- State passed between nodes

---

**Last Updated:** 2026-04-01  
**Version:** LangGraph Edition (Rev 6)
