# service/app/router.py
"""Intelligent router pipeline with model selection based on question type.

Routing Strategy:
1. Llama 8B (cheap, fast) → Classify question type
2. Based on classification:
   - database_query → Claude Sonnet (understand data context)
   - general_knowledge → Llama 70B (good balance)
   - clarification → Llama 8B (just asking)
"""

import asyncio
import json
import logging
import time
from app.llm.caller import LLMCaller
from app.llm.prompts import (
    ROUTER_PROMPT,
    QUERY_SELECTOR_PROMPT,
    DATABASE_ANSWER_PROMPT,
    GENERAL_KNOWLEDGE_PROMPT,
    CLARIFICATION_PROMPT,
)
from app.masking.masker import PIIMasker
from app.queries.executor import QueryExecutor
from app.queries.registry import get_query, get_query_descriptions

logger = logging.getLogger(__name__)

# Lazy-init singletons (for test mocking)
_caller: LLMCaller | None = None
_executor: QueryExecutor | None = None


def _get_caller() -> LLMCaller:
    global _caller
    if _caller is None:
        _caller = LLMCaller()
    return _caller


def _get_executor() -> QueryExecutor:
    global _executor
    if _executor is None:
        _executor = QueryExecutor()
    return _executor


class AskRequest:
    """Request model for /v1/ask endpoint."""
    def __init__(
        self,
        question: str,
        user_id: int,
        role_id: int,
        client_id: int,
        org_ids: list[int],
        language: str = "zh_TW",
    ):
        self.question = question
        self.user_id = user_id
        self.role_id = role_id
        self.client_id = client_id
        self.org_ids = org_ids
        self.language = language


class AskResponse:
    """Response model for /v1/ask endpoint."""
    def __init__(
        self,
        answer: str,
        model_used: str,
        tokens_used: int,
        query_used: str | None,
        elapsed_ms: int,
    ):
        self.answer = answer
        self.model_used = model_used
        self.tokens_used = tokens_used
        self.query_used = query_used
        self.elapsed_ms = elapsed_ms


async def process_question(req: AskRequest) -> AskResponse:
    """
    Intelligent router pipeline:
    1. Classify question (Llama 8B - cheap)
    2. Route to appropriate model based on type
    3. Execute query if needed (Claude Sonnet for DB, Llama 70B for general)
    4. Mask/unmask PII
    
    Model Selection Strategy:
    - Llama 8B: Classification, clarification questions
    - Claude Sonnet: Database queries (needs to understand data context)
    - Llama 70B: General knowledge (good balance of speed/cost/quality)
    """
    start_time = time.time()
    masker = PIIMasker()
    executor = _get_executor()
    caller = _get_caller()
    
    # Step 1: Sanitize input (strip PII tokens from question)
    sanitized_question = masker.sanitize_input(req.question)
    logger.info("Sanitized question: %s", sanitized_question[:50])
    
    # Step 2: Classify question using Llama 8B (cheap, fast)
    router_input = ROUTER_PROMPT.format(question=sanitized_question)
    category, _ = await asyncio.to_thread(
        caller.call, "llama_8b", "You are a classifier. Respond with only one word.", router_input
    )
    category = category.strip().lower()
    
    # Validate category
    if category not in ["database_query", "general_knowledge", "clarification"]:
        logger.warning("Invalid category '%s', defaulting to clarification", category)
        category = "clarification"
    
    logger.info("Classified as: %s", category)
    
    # Step 3: Route based on category
    if category == "database_query":
        # Use Claude Sonnet for database queries (best at understanding data context)
        answer, tokens, query_name = await _handle_database_query(
            caller, executor, masker, req, sanitized_question
        )
        model_used = "sonnet"
        
    elif category == "general_knowledge":
        # Use Llama 70B for general knowledge (good balance)
        answer, tokens = await _handle_general_knowledge(
            caller, masker, req, sanitized_question
        )
        model_used = "llama_70b"
        query_name = None
        
    else:  # clarification
        # Use Llama 8B for clarification (cheap, sufficient)
        answer, tokens = await _handle_clarification(
            caller, masker, req, sanitized_question
        )
        model_used = "llama_8b"
        query_name = None
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    return AskResponse(
        answer=answer,
        model_used=model_used,
        tokens_used=tokens,
        query_used=query_name,
        elapsed_ms=elapsed_ms,
    )


async def _handle_database_query(
    caller: LLMCaller,
    executor: QueryExecutor,
    masker: PIIMasker,
    req: AskRequest,
    sanitized_question: str
) -> tuple[str, int, str]:
    """Handle database query using Claude Sonnet."""
    
    # Select query and extract parameters (Claude Sonnet)
    query_descriptions = get_query_descriptions()
    selector_prompt = QUERY_SELECTOR_PROMPT.format(
        query_descriptions=query_descriptions,
        question=sanitized_question
    )
    
    selection_result, _ = await asyncio.to_thread(
        caller.call, "sonnet", "You are a query selector. Respond in JSON.", selector_prompt
    )
    
    try:
        selection = json.loads(selection_result)
    except json.JSONDecodeError:
        logger.error("Failed to parse selection JSON")
        return "抱歉，無法理解您的問題", 0, None
    
    query_name = selection.get("query_name")
    if not query_name:
        return "抱歉，找不到合適的查詢", 0, None
    
    params = selection.get("params", {})
    
    # Force-inject security params from request context (NEVER from LLM)
    params["ad_client_id"] = req.client_id
    params["org_ids"] = req.org_ids
    
    # Execute query
    rows = executor.execute(query_name, params)
    
    # Get PII columns from query definition
    query_def = get_query(query_name)
    pii_columns = query_def.get("pii_columns", []) if query_def else []
    
    # Mask PII
    masked_rows, mapping = masker.mask(rows, pii_columns) if pii_columns else (rows, {})
    
    # Build answer prompt (Claude Sonnet)
    answer_prompt = DATABASE_ANSWER_PROMPT.format(
        language=req.language,
        query_name=query_name,
        results=masked_rows,
        question=sanitized_question
    )
    
    # Generate answer (Claude Sonnet)
    answer_text, tokens = await asyncio.to_thread(
        caller.call, "sonnet", answer_prompt, sanitized_question
    )
    
    # Unmask PII
    final_answer = masker.unmask(answer_text, mapping)
    
    return final_answer, tokens, query_name


async def _handle_general_knowledge(
    caller: LLMCaller,
    masker: PIIMasker,
    req: AskRequest,
    sanitized_question: str
) -> tuple[str, int]:
    """Handle general knowledge question using Llama 70B."""
    
    answer_prompt = GENERAL_KNOWLEDGE_PROMPT.format(
        language=req.language,
        question=sanitized_question
    )
    
    answer_text, tokens = await asyncio.to_thread(
        caller.call, "llama_70b", answer_prompt, sanitized_question
    )
    
    return answer_text, tokens


async def _handle_clarification(
    caller: LLMCaller,
    masker: PIIMasker,
    req: AskRequest,
    sanitized_question: str
) -> tuple[str, int]:
    """Handle clarification request using Llama 8B."""
    
    clarify_prompt = CLARIFICATION_PROMPT.format(
        language=req.language,
        question=sanitized_question
    )
    
    answer_text, tokens = await asyncio.to_thread(
        caller.call, "llama_8b", clarify_prompt, sanitized_question
    )
    
    return answer_text, tokens
