# service/app/router.py
"""LangGraph-based router with Tools for intelligent query execution.

Architecture:
1. Agent receives user question
2. Agent decides which Tool to use (SQL query or general response)
3. Tool executes with parameters extracted by LLM
4. Results masked for PII, sent to LLM for answer generation
5. PII restored, answer returned

Tools:
- query_executor: Execute pre-defined SQL queries
- general_knowledge: Answer general questions (no DB)
- clarification: Ask for more details when question is vague
"""

import asyncio
import json
import logging
import time
from typing import Annotated, List, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.llm.caller import LLMCaller
from app.llm.prompts import (
    AGENT_SYSTEM_PROMPT,
    DATABASE_ANSWER_PROMPT,
    GENERAL_KNOWLEDGE_PROMPT,
    CLARIFICATION_PROMPT,
)
from app.masking.masker import PIIMasker
from app.queries.executor import QueryExecutor
from app.queries.registry import get_query, get_query_descriptions, list_queries

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


# ============== State Definition ==============

class AgentState(TypedDict):
    """State for LangGraph agent."""
    question: str
    sanitized_question: str
    user_id: int
    role_id: int
    client_id: int
    org_ids: List[int]
    language: str
    category: str  # database_query, general_knowledge, clarification
    query_name: str | None
    query_params: dict | None
    query_results: list | None
    pii_mapping: dict | None
    answer: str
    model_used: str
    tokens_used: int
    elapsed_ms: int


# ============== Tools ==============

class QueryTool:
    """Tool for executing pre-defined SQL queries."""
    
    name = "query_executor"
    description = """Execute a pre-defined SQL query to retrieve ERP data.
    Use when the user asks about specific data like orders, customers, revenue, etc.
    Available queries: {query_descriptions}
    """
    
    def __init__(self, executor: QueryExecutor, client_id: int, org_ids: List[int]):
        self.executor = executor
        self.client_id = client_id
        self.org_ids = org_ids
    
    def execute(self, query_name: str, params: dict) -> list:
        """Execute query with security params injected."""
        # Force-inject security params (NEVER from LLM)
        params["ad_client_id"] = self.client_id
        params["org_ids"] = self.org_ids
        
        return self.executor.execute(query_name, params)


class GeneralKnowledgeTool:
    """Tool for answering general knowledge questions."""
    
    name = "general_knowledge"
    description = "Answer general knowledge questions about ERP, iDempiere, or other topics. Use when no database query is needed."


class ClarificationTool:
    """Tool for asking clarifying questions."""
    
    name = "clarification"
    description = "Ask the user for more details when their question is too vague or ambiguous."


# ============== LangGraph Nodes ==============

def classify_node(state: AgentState) -> AgentState:
    """Classify the question using LLM (Llama 8B for cost efficiency)."""
    caller = _get_caller()
    
    classification_prompt = f"""Classify this question into ONE category:

Categories:
- database_query: Asks about specific ERP data (orders, customers, revenue, products, etc.)
- general_knowledge: General questions about ERP, iDempiere, or non-data topics
- clarification: Too vague or needs more context

Question: {state['sanitized_question']}

Respond with ONLY the category name (database_query, general_knowledge, or clarification)."""

    category, tokens = asyncio.run(asyncio.to_thread(
        caller.call, "llama_8b", "You are a classifier.", classification_prompt
    ))
    
    category = category.strip().lower()
    if category not in ["database_query", "general_knowledge", "clarification"]:
        logger.warning("Invalid category '%s', defaulting to clarification", category)
        category = "clarification"
    
    logger.info("Classified as: %s", category)
    
    return {
        **state,
        "category": category,
        "tokens_used": tokens,
    }


def route_node(state: AgentState) -> Literal["database_query", "general_knowledge", "clarification"]:
    """Route based on classification."""
    return state["category"]


def database_query_node(state: AgentState) -> AgentState:
    """Handle database queries using Claude Sonnet."""
    caller = _get_caller()
    executor = _get_executor()
    masker = PIIMasker()
    
    # Select query and extract parameters (Claude Sonnet)
    query_descriptions = get_query_descriptions()
    selector_prompt = f"""You are an ERP query selector. Given available queries and a user question, select the best match and extract parameters.

Available queries:
{query_descriptions}

User question: {state['sanitized_question']}

Respond in JSON format:
{{
  "query_name": "<best matching query name>",
  "params": {{
    "date_from": "YYYY-MM-DD or null",
    "date_to": "YYYY-MM-DD or null",
    "document_no": "string or null",
    "year": "YYYY or null",
    "limit": "number (default 5)"
  }}
}}

If no query matches well, set query_name to null."""

    selection_result, tokens = asyncio.run(asyncio.to_thread(
        caller.call, "sonnet", "You are a query selector. Respond in JSON.", selector_prompt
    ))
    
    try:
        selection = json.loads(selection_result)
    except json.JSONDecodeError:
        logger.error("Failed to parse selection JSON")
        return {
            **state,
            "answer": "抱歉，無法理解您的問題",
            "model_used": "sonnet",
            "tokens_used": tokens,
        }
    
    query_name = selection.get("query_name")
    if not query_name:
        return {
            **state,
            "answer": "抱歉，找不到合適的查詢",
            "model_used": "sonnet",
            "tokens_used": tokens,
        }
    
    params = selection.get("params", {})
    
    # Execute query (security params injected by tool)
    query_tool = QueryTool(executor, state["client_id"], state["org_ids"])
    rows = query_tool.execute(query_name, params)
    
    # Get PII columns
    query_def = get_query(query_name)
    pii_columns = query_def.get("pii_columns", []) if query_def else []
    
    # Mask PII
    masked_rows, pii_mapping = masker.mask(rows, pii_columns) if pii_columns else (rows, {})
    
    # Generate answer (Claude Sonnet)
    answer_prompt = DATABASE_ANSWER_PROMPT.format(
        language=state["language"],
        query_name=query_name,
        results=masked_rows,
        question=state["sanitized_question"]
    )
    
    answer_text, answer_tokens = asyncio.run(asyncio.to_thread(
        caller.call, "sonnet", answer_prompt, state["sanitized_question"]
    ))
    
    # Unmask PII
    final_answer = masker.unmask(answer_text, pii_mapping)
    
    return {
        **state,
        "query_name": query_name,
        "query_params": params,
        "query_results": rows,
        "pii_mapping": pii_mapping,
        "answer": final_answer,
        "model_used": "sonnet",
        "tokens_used": tokens + answer_tokens,
    }


def general_knowledge_node(state: AgentState) -> AgentState:
    """Handle general knowledge questions using Llama 70B."""
    caller = _get_caller()
    
    answer_prompt = GENERAL_KNOWLEDGE_PROMPT.format(
        language=state["language"],
        question=state["sanitized_question"]
    )
    
    answer_text, tokens = asyncio.run(asyncio.to_thread(
        caller.call, "llama_70b", answer_prompt, state["sanitized_question"]
    ))
    
    return {
        **state,
        "answer": answer_text,
        "model_used": "llama_70b",
        "tokens_used": tokens,
    }


def clarification_node(state: AgentState) -> AgentState:
    """Handle clarification requests using Llama 8B."""
    caller = _get_caller()
    
    clarify_prompt = CLARIFICATION_PROMPT.format(
        language=state["language"],
        question=state["sanitized_question"]
    )
    
    answer_text, tokens = asyncio.run(asyncio.to_thread(
        caller.call, "llama_8b", clarify_prompt, state["sanitized_question"]
    ))
    
    return {
        **state,
        "answer": answer_text,
        "model_used": "llama_8b",
        "tokens_used": tokens,
    }


# ============== Graph Builder ==============

def build_graph() -> StateGraph:
    """Build the LangGraph workflow."""
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify", classify_node)
    workflow.add_node("database_query", database_query_node)
    workflow.add_node("general_knowledge", general_knowledge_node)
    workflow.add_node("clarification", clarification_node)
    
    # Set entry point
    workflow.set_entry_point("classify")
    
    # Add conditional edges based on classification
    workflow.add_conditional_edges(
        "classify",
        route_node,
        {
            "database_query": "database_query",
            "general_knowledge": "general_knowledge",
            "clarification": "clarification",
        }
    )
    
    # Add terminal edges
    workflow.add_edge("database_query", END)
    workflow.add_edge("general_knowledge", END)
    workflow.add_edge("clarification", END)
    
    return workflow.compile()


# ============== Main Entry Point ==============

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
    Process question using LangGraph agent.
    
    Flow:
    1. Sanitize input
    2. Classify question (Llama 8B)
    3. Route to appropriate handler
    4. Execute query or generate answer
    5. Return response
    """
    start_time = time.time()
    masker = PIIMasker()
    
    # Sanitize input
    sanitized_question = masker.sanitize_input(req.question)
    logger.info("Sanitized question: %s", sanitized_question[:50])
    
    # Build and run graph
    graph = build_graph()
    
    # Initial state
    initial_state = {
        "question": req.question,
        "sanitized_question": sanitized_question,
        "user_id": req.user_id,
        "role_id": req.role_id,
        "client_id": req.client_id,
        "org_ids": req.org_ids,
        "language": req.language,
        "category": None,
        "query_name": None,
        "query_params": None,
        "query_results": None,
        "pii_mapping": None,
        "answer": None,
        "model_used": None,
        "tokens_used": 0,
        "elapsed_ms": 0,
    }
    
    # Run graph
    final_state = await asyncio.to_thread(graph.invoke, initial_state)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    return AskResponse(
        answer=final_state["answer"],
        model_used=final_state["model_used"],
        tokens_used=final_state["tokens_used"],
        query_used=final_state["query_name"],
        elapsed_ms=elapsed_ms,
    )
