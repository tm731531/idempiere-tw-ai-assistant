# Code Review Fixes — 2026-04-01

Reviewed by: Claude Opus (with Domain Brain + Domain Skill)
Code author: Qwen
Status: **✅ ALL 5 FIXES COMPLETED**

---

## ✅ COMPLETED FIXES

### Fix 1: router.py — Remove `asyncio.run(asyncio.to_thread(...))` ✅

**Files:** `service/app/router.py`

**Applied to:** `classify_node`, `database_query_node` (2 calls), `general_knowledge_node`, `clarification_node`

**Fix:** Replaced all `asyncio.run(asyncio.to_thread(caller.call, ...))` with direct `caller.call(...)` calls.

**Additional fix:** Added try/except in `classify_node` for graceful degradation (Fix 3).

---

### Fix 2: executor.py — Add `statement_timeout=10s` ✅

**File:** `service/app/queries/executor.py` line 26

**Fix:**
```python
options="-c search_path=adempiere -c statement_timeout=10000",  # 10s timeout
```

---

### Fix 3: router.py classify_node — Add try/except ✅

**File:** `service/app/router.py` function `classify_node`

**Fix:** Wrapped LLM call in try/except, defaults to `"clarification"` on failure.

---

### Fix 4: router.py database_query_node — Catch more JSON errors ✅

**File:** `service/app/router.py` line ~196

**Fix:** Changed exception handling from `json.JSONDecodeError` to `(json.JSONDecodeError, AttributeError, TypeError)`.

---

### Fix 5: caller.py — Add max_tokens to Groq models ✅

**File:** `service/app/llm/caller.py`

**Fix:**
```python
"llama_70b": {
    "class": ChatGroq,
    "model": "llama-3.1-70b-versatile",
    "max_tokens": 4096,
    "timeout": 25.0,
},
"llama_8b": {
    "class": ChatGroq,
    "model": "llama-3.1-8b-instant",
    "max_tokens": 2048,
    "timeout": 25.0,
},
```

Updated `_get_model()` to pass `max_tokens` to Groq models.

---

## ✅ Verification

All 39 tests pass:
```
============================== 39 passed in 1.34s ==============================
```

Git commit: `440db33`

---

## 📝 Notes

- All fixes applied per Claude Opus code review
- No breaking changes to API or behavior
- Improved error handling and robustness
- Added database query timeout protection
- Optimized thread usage (removed unnecessary nested threading)
