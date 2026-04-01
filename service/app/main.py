# service/app/main.py
"""FastAPI application with HMAC authentication and rate limiting."""

import hashlib
import hmac
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import app.config as config
from app.queries.executor import init_pool, close_pool
from app.router import AskRequest, AskResponse, process_question

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Rate limiting: max 20 requests per user per minute
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = timedelta(minutes=1)
user_request_timestamps: dict[int, list[datetime]] = defaultdict(list)


def check_rate_limit(user_id: int) -> bool:
    """
    Check if user has exceeded rate limit.
    Returns True if request is allowed, False if exceeded.
    """
    now = datetime.now()
    cutoff = now - RATE_LIMIT_WINDOW
    
    # Remove old timestamps
    user_request_timestamps[user_id] = [
        ts for ts in user_request_timestamps[user_id]
        if ts > cutoff
    ]
    
    # Check limit
    if len(user_request_timestamps[user_id]) >= RATE_LIMIT_MAX:
        return False
    
    # Add current timestamp
    user_request_timestamps[user_id].append(now)
    return True


def verify_hmac(request_body: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature on request body.
    """
    expected = hmac.new(
        config.HMAC_SECRET.encode("utf-8"),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


class AskRequestPayload(BaseModel):
    """Pydantic model for /v1/ask request."""
    question: str
    user_id: int
    role_id: int
    client_id: int
    org_ids: list[int]
    language: str = "zh_TW"


class HealthResponse(BaseModel):
    """Pydantic model for /health response."""
    status: str
    service: str = "idempiere-ai-service"
    db: str = "disconnected"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting up...")
    try:
        init_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
        )
        logger.info("Database pool initialized")
    except Exception as e:
        logger.error("Failed to initialize database pool: %s", e)
        # Don't crash - allow health checks to report disconnected
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    close_pool()


app = FastAPI(
    title="iDempiere TW AI Assistant",
    description="AI-powered Q&A assistant for iDempiere ERP",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    # Check if pool is initialized
    from app.queries.executor import pool
    db_status = "connected" if pool else "disconnected"
    
    return HealthResponse(
        status="ok",
        db=db_status,
    )


@app.post("/v1/ask")
async def ask(request: Request) -> dict:
    """
    Process a natural language question about ERP data.
    
    Requires HMAC-SHA256 signature in X-HMAC-Signature header.
    """
    # Read raw body bytes for HMAC verification
    body_bytes = await request.body()
    
    # Verify HMAC signature
    signature = request.headers.get("X-HMAC-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing HMAC signature"
        )
    
    if not verify_hmac(body_bytes, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature"
        )
    
    # Parse request
    try:
        import json
        payload = AskRequestPayload(**json.loads(body_bytes.decode("utf-8")))
    except Exception as e:
        logger.error("Failed to parse request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request format"
        )
    
    # Check rate limit
    if not check_rate_limit(payload.user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    # Build AskRequest
    ask_req = AskRequest(
        question=payload.question,
        user_id=payload.user_id,
        role_id=payload.role_id,
        client_id=payload.client_id,
        org_ids=payload.org_ids,
        language=payload.language,
    )
    
    # Process question
    try:
        response = await process_question(ask_req)
        return {
            "answer": response.answer,
            "model_used": response.model_used,
            "tokens_used": response.tokens_used,
            "query_used": response.query_used,
            "elapsed_ms": response.elapsed_ms,
        }
    except ValueError as e:
        # Database or query errors (generic message, no PII)
        logger.error("Query error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Request processing failed"
        )
    except Exception as e:
        # Unexpected errors (generic message, no stack trace)
        logger.error("Unexpected error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Request processing failed"
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler to ensure consistent error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=config.SERVICE_PORT,
        reload=False,
    )
