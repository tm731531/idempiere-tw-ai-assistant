# service/app/llm/caller.py
"""LLM caller with fallback and token usage extraction.

Primary model: Claude Sonnet (Anthropic)
Fallback model: Groq Llama
"""

import logging
import os
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import ANTHROPIC_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)

# Check MOCK_LLM dynamically at call time (not import time)
def _is_mock_mode():
    return os.getenv("MOCK_LLM", "false").lower() == "true"


# Model configurations with timeouts (25s < Java's 30s timeout)
# Claude Sonnet: Primary model for classification and answering
# Groq Llama 70B: Fallback when Claude fails
# Groq Llama 8B: Fast model for clarification questions
MODEL_CONFIG = {
    "sonnet": {
        "class": ChatAnthropic,
        "model": "claude-sonnet-4-20250514",
        "timeout": 25.0,
    },
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
    # Qwen Max (Alibaba DashScope) - temporarily disabled
    # "qwen_max": {
    #     "model": dashscope.Generation.Models.qwen_max,
    #     "timeout": 25.0,
    # },
}


class LLMCaller:
    """Call LLM models with fallback chain and token usage extraction.
    
    Primary: Claude Sonnet (Anthropic)
    Fallback: Groq Llama 70B
    Clarification: Groq Llama 8B
    """

    def __init__(self):
        self._models: dict[str, object] = {}

    def _get_model(self, model_key: str):
        """Lazy-load model instances."""
        if model_key not in self._models:
            config = MODEL_CONFIG[model_key]
            # Build model kwargs
            kwargs = {
                "model": config["model"],
                "timeout": config["timeout"],
                "api_key": (
                    ANTHROPIC_API_KEY if config["class"] == ChatAnthropic
                    else GROQ_API_KEY
                ),
            }
            # Add max_tokens for Groq models
            if "max_tokens" in config:
                kwargs["max_tokens"] = config["max_tokens"]
            
            self._models[model_key] = config["class"](**kwargs)
        return self._models[model_key]

    def call(self, model_key: str, system_prompt: str, user_content: str) -> tuple[str, int]:
        """
        Call an LLM model with fallback.
        
        Args:
            model_key: Model to use ("sonnet", "llama_70b", "llama_8b")
            system_prompt: System message
            user_content: User's question/content
            
        Returns:
            Tuple of (response_content, total_tokens_used)
            
        Raises:
            RuntimeError: If all models in fallback chain fail
        """
        if _is_mock_mode():
            # Mock mode: return canned response (no API cost)
            logger.info("MOCK_LLM=true, returning mock response")
            return "Mock response - LLM call skipped in mock mode", 0

        # Determine fallback chain
        if model_key == "sonnet":
            chain = ["sonnet", "llama_70b"]
        elif model_key == "llama_8b":
            chain = ["llama_8b", "llama_70b"]
        else:
            chain = [model_key]

        last_error = None
        for key in chain:
            try:
                model = self._get_model(key)
                response = model.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_content),
                ])
                
                content = response.content
                tokens = self._extract_tokens(response)
                logger.info(f"Model {key} returned {tokens} tokens")
                return content, tokens
                
            except Exception as e:
                logger.warning(f"Model {key} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(f"All models failed. Last error: {last_error}")

    def _extract_tokens(self, response) -> int:
        """Extract token usage from response metadata."""
        try:
            metadata = getattr(response, "response_metadata", {})
            usage = metadata.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            return input_tokens + output_tokens
        except Exception:
            # If metadata not available, estimate
            return 0
