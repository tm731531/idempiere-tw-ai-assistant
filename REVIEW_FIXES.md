# Code Review Fixes — 2026-04-01

Reviewed by: Claude Opus (with Domain Brain + Domain Skill)
Code author: Qwen
Status: **5 issues to fix**

---

## 🔴 CRITICAL (must fix)

### Fix 1: router.py — Remove `asyncio.run(asyncio.to_thread(...))` inside graph nodes

**Files:** `service/app/router.py` lines 134, 186, 231, 259, 280

**Problem:** `process_question()` in `main.py` already calls `await asyncio.to_thread(graph.invoke, ...)`, so all graph nodes run in a worker thread. Inside those nodes, `asyncio.run(asyncio.to_thread(...))` creates a NEW event loop inside a thread, then spawns ANOTHER thread. This is unnecessary, fragile, and can cause `RuntimeError: This event loop is already running` in some environments.

**Fix:** Replace all `asyncio.run(asyncio.to_thread(caller.call, ...))` with direct `caller.call(...)` calls:

```python
# BEFORE (wrong — double-threaded):
category, tokens = asyncio.run(asyncio.to_thread(
    caller.call, "llama_8b", "You are a classifier.", classification_prompt
))

# AFTER (correct — already in worker thread):
category, tokens = caller.call("llama_8b", "You are a classifier.", classification_prompt)
```

**Apply to ALL nodes:** `classify_node`, `database_query_node` (2 calls), `general_knowledge_node`, `clarification_node`

After fix, `import asyncio` at the top of router.py can be removed (only needed in `process_question` which uses it via main.py).

---

### Fix 2: executor.py — Add `statement_timeout=10s`

**File:** `service/app/queries/executor.py` line 26

**Problem:** Only `search_path=adempiere` is set. A runaway SQL query can hang indefinitely, blocking the connection pool.

**Fix:**
```python
# BEFORE:
options="-c search_path=adempiere",

# AFTER:
options="-c search_path=adempiere -c statement_timeout=10000",
```

Note: `statement_timeout` value is in milliseconds. 10000 = 10 seconds.

---

## 🟡 IMPORTANT (should fix)

### Fix 3: router.py classify_node — Add try/except for graceful degradation

**File:** `service/app/router.py` function `classify_node` (line ~119)

**Problem:** If the LLM call fails (timeout, API down, rate limit), the entire graph crashes with an unhandled exception. User sees a 500 error.

**Fix:** Wrap the LLM call in try/except, default to `"clarification"` on failure:

```python
def classify_node(state: AgentState) -> AgentState:
    """Classify the question using LLM (Llama 8B for cost efficiency)."""
    caller = _get_caller()

    classification_prompt = f"""..."""

    try:
        category, tokens = caller.call(
            "llama_8b", "You are a classifier.", classification_prompt
        )
        category = category.strip().lower()
        if category not in ["database_query", "general_knowledge", "clarification"]:
            logger.warning("Invalid category '%s', defaulting to clarification", category)
            category = "clarification"
    except Exception as e:
        logger.error("Classification failed: %s", e)
        category = "clarification"
        tokens = 0

    logger.info("Classified as: %s", category)

    return {
        **state,
        "category": category,
        "tokens_used": tokens,
    }
```

---

## ⚠️ MODERATE (nice to fix)

### Fix 4: router.py database_query_node — Catch more JSON parse errors

**File:** `service/app/router.py` line ~191

**Problem:** Only catches `json.JSONDecodeError`. If LLM returns `None` or non-string, `.strip()` or `json.loads()` can raise `AttributeError` or `TypeError`.

**Fix:**
```python
# BEFORE:
except json.JSONDecodeError:

# AFTER:
except (json.JSONDecodeError, AttributeError, TypeError):
```

---

### Fix 5: caller.py — Add max_tokens to Groq models

**File:** `service/app/llm/caller.py` Groq model initialization

**Problem:** Groq models have specific max_tokens limits. Without explicit setting, LangChain may use a default that exceeds the model's capability.

**Fix:**
```python
# llama_70b — add max_tokens=4096:
ChatGroq(model="llama-3.3-70b-versatile", max_tokens=4096, timeout=25.0, ...)

# llama_8b — add max_tokens=2048:
ChatGroq(model="llama-3.1-8b-instant", max_tokens=2048, timeout=25.0, ...)
```

---

## 💡 SUGGESTION (optional optimization)

### Suggestion 6: router.py — Cache the compiled graph

**File:** `service/app/router.py` line ~385

**Problem:** `build_graph()` is called on every request. The graph structure never changes at runtime.

**Suggestion:** Cache as lazy-init singleton:
```python
_graph = None

def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

# In process_question():
graph = _get_graph()  # instead of build_graph()
```

---

## Verification after fixes

Run tests:
```bash
cd service/
pytest tests/ -v
```

Quick manual test:
```bash
# Start with MOCK_LLM=true (no API cost)
MOCK_LLM=true python -m app.main

# Health check
curl http://localhost:8900/health

# Test ask (need HMAC — use test_manual.py)
python test_manual.py
```
