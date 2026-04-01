# service/app/config.py
"""Configuration settings from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# Mock mode: returns canned responses without calling LLM APIs
# Set MOCK_LLM=true in .env for development/testing (no token cost)
MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"

# Qwen API key (Alibaba DashScope) - PRIMARY MODEL
DASHSCOPE_API_KEY = (
    os.getenv("DASHSCOPE_API_KEY", "mock-key")
    if MOCK_LLM
    else os.environ["DASHSCOPE_API_KEY"]
)

# Groq API key (for Llama fallback)
GROQ_API_KEY = (
    os.getenv("GROQ_API_KEY", "mock-key")
    if MOCK_LLM
    else os.environ["GROQ_API_KEY"]
)

# Claude API key (kept for reference, not used)
# ANTHROPIC_API_KEY = (
#     os.getenv("ANTHROPIC_API_KEY", "mock-key")
#     if MOCK_LLM
#     else os.environ["ANTHROPIC_API_KEY"]
# )

# HMAC secret for authenticating requests from iDempiere plugin
# MUST match the AI_HMAC_SECRET system property in iDempiere
HMAC_SECRET = os.environ["HMAC_SECRET"]

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "idempiere")
DB_USER = os.getenv("DB_USER", "ai_readonly")
DB_PASSWORD = os.environ["DB_PASSWORD"]

# Service port
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8900"))
