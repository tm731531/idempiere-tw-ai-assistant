# service/app/router.py
"""Router pipeline: classify → select query → execute → mask → LLM → unmask."""

import asyncio
import logging
import time
from typing import Any
from app.llm.caller import LLMCaller
from app.llm.prompts import (
    CLASSIFY_AND_SELECT_PROMPT,
    ANSWER_WITH_DATA_PROMPT,
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
    Main pipeline: classify → select query → execute → mask → LLM → unmask.
    
    Args:
        req: AskRequest with user question and context
        
    Returns:
        AskResponse with answer and metadata
    """
    start_time = time.time()
    masker = PIIMasker()
    executor = _get_executor()
    caller = _get_caller()
    
    # Step 1: Sanitize input (strip PII tokens from question)
    sanitized_question = masker.sanitize_input(req.question)
    logger.info("Sanitized question: %s", sanitized_question[:50])
    
    # Step 2: Classify + select query (single Groq Llama 70B call)
    # Primary model: Groq Llama 70B (Qwen temporarily disabled)
    # Fallback: Groq Llama 8B for clarification
    query_descriptions = get_query_descriptions()
    classify_prompt = CLASSIFY_AND_SELECT_PROMPT.format(
        query_descriptions=query_descriptions
    )
    
    classify_input = f"User question: {sanitized_question}"
    classification_result = await asyncio.to_thread(
        caller.call, "sonnet", classify_prompt, classify_input
    )
    classification_text, _ = classification_result
    
    # Parse classification result (expecting JSON)
    import json
    try:
        classification = json.loads(classification_text)
    except json.JSONDecodeError:
        # Fallback: treat as clarification
        classification = {
            "category": "clarification",
            "query_name": None,
            "params": None,
        }
    
    category = classification.get("category", "clarification")
    query_name = classification.get("query_name")
    params = classification.get("params", {})
    
    # Step 3: Route based on category
    if category == "database_query" and query_name:
        # Force-inject security params from request context (NEVER from LLM)
        params["ad_client_id"] = req.client_id
        params["org_ids"] = req.org_ids
        
        # Get query definition for pii_columns
        query_def = get_query(query_name)
        pii_columns = query_def.get("pii_columns", []) if query_def else []
        
        # Execute query
        rows = executor.execute(query_name, params)
        
        # Mask PII
        masked_rows, mapping = masker.mask(rows, pii_columns) if pii_columns else (rows, {})
        
        # Build prompt with masked data
        answer_prompt = ANSWER_WITH_DATA_PROMPT.format(
            language=req.language,
            query_name=query_name,
            results=masked_rows,
            question=sanitized_question,
        )
        
        # Call LLM for answer (Groq Llama 70B)
        answer_text, tokens = await asyncio.to_thread(
            caller.call, "llama_70b", answer_prompt, sanitized_question
        )
        final_answer = masker.unmask(answer_text, mapping)
        model_used = "llama_70b"
        
    elif category == "general_knowledge":
        # No DB query needed
        answer_prompt = GENERAL_KNOWLEDGE_PROMPT.format(
            language=req.language,
            question=sanitized_question,
        )
        answer_text, tokens = await asyncio.to_thread(
            caller.call, "llama_8b", answer_prompt, sanitized_question
        )
        final_answer = answer_text
        model_used = "llama_8b"
        
    else:  # clarification
        clarify_prompt = CLARIFICATION_PROMPT.format(
            language=req.language,
            question=sanitized_question,
        )
        answer_text, tokens = await asyncio.to_thread(
            caller.call, "llama_8b", clarify_prompt, sanitized_question
        )
        final_answer = answer_text
        model_used = "llama_8b"
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    return AskResponse(
        answer=final_answer,
        model_used=model_used,
        tokens_used=tokens,
        query_used=query_name if category == "database_query" else None,
        elapsed_ms=elapsed_ms,
    )
