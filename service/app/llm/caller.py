# service/app/llm/caller.py
"""LLM caller with fallback and token usage extraction.

Primary model: Qwen (Alibaba DashScope)
Fallback model: Groq Llama
"""

import logging
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

# DashScope (Qwen) - uses dashscope library directly
import dashscope
from dashscope import Generation

from app.config import DASHSCOPE_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)

# Check MOCK_LLM dynamically at call time (not import time)
def _is_mock_mode():
    return os.getenv("MOCK_LLM", "false").lower() == "true"


# Model configurations with timeouts (25s < Java's 30s timeout)
# Qwen Max: Alibaba's most powerful model
# Groq Llama 70B: Fast fallback
MODEL_CONFIG = {
    "qwen_max": {
        "model": dashscope.Generation.Models.qwen_max,
        "timeout": 25.0,
    },
    "llama_70b": {
        "class": ChatGroq,
        "model": "llama-3.1-70b-versatile",
        "timeout": 25.0,
    },
    "llama_8b": {
        "class": ChatGroq,
        "model": "llama-3.1-8b-instant",
        "timeout": 25.0,
    },
}


class LLMCaller:
    """Call LLM models with fallback chain and token usage extraction.
    
    Primary: Qwen Max (Alibaba DashScope)
    Fallback: Groq Llama 70B
    Clarification: Groq Llama 8B
    """

    def __init__(self):
        self._groq_models: dict[str, object] = {}
        
        # Initialize Qwen API key
        if not _is_mock_mode():
            dashscope.api_key = DASHSCOPE_API_KEY

    def _get_groq_model(self, model_key: str):
        """Lazy-load Groq model instances."""
        if model_key not in self._groq_models:
            config = MODEL_CONFIG[model_key]
            self._groq_models[model_key] = config["class"](
                model=config["model"],
                timeout=config["timeout"],
                api_key=GROQ_API_KEY,
            )
        return self._groq_models[model_key]

    def call(self, model_key: str, system_prompt: str, user_content: str) -> tuple[str, int]:
        """
        Call an LLM model with fallback.
        
        Args:
            model_key: Model to use ("qwen_max", "llama_70b", "llama_8b")
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
        if model_key == "qwen_max":
            chain = ["qwen_max", "llama_70b"]
        elif model_key == "llama_8b":
            chain = ["llama_8b", "llama_70b"]
        else:
            chain = [model_key]

        last_error = None
        for key in chain:
            try:
                if key == "qwen_max":
                    content, tokens = self._call_qwen(system_prompt, user_content)
                else:
                    content, tokens = self._call_groq(key, system_prompt, user_content)
                
                logger.info(f"Model {key} returned {tokens} tokens")
                return content, tokens
                
            except Exception as e:
                logger.warning(f"Model {key} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(f"All models failed. Last error: {last_error}")

    def _call_qwen(self, system_prompt: str, user_content: str) -> tuple[str, int]:
        """Call Qwen Max via DashScope API."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        response = Generation.call(
            model=MODEL_CONFIG["qwen_max"]["model"],
            messages=messages,
            result_format='message',  # Return in message format
            timeout=MODEL_CONFIG["qwen_max"]["timeout"],
        )
        
        if response.status_code == 200:
            content = response.output.choices[0].message.content
            # Extract token usage
            usage = response.usage
            total_tokens = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            return content, total_tokens
        else:
            raise RuntimeError(f"Qwen API error: {response.code} - {response.message}")

    def _call_groq(self, model_key: str, system_prompt: str, user_content: str) -> tuple[str, int]:
        """Call Groq Llama model."""
        model = self._get_groq_model(model_key)
        response = model.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ])
        
        content = response.content
        tokens = self._extract_tokens(response)
        return content, tokens

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
