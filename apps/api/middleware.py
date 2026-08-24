"""Production middleware for Local Market Lab API.

Provides rate limiting, request ID tracing, and catch-all exception handling.
All middleware is self-contained (no extra dependencies beyond FastAPI/Starlette).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Structured logger (JSON lines to stderr)
# ---------------------------------------------------------------------------
logger = logging.getLogger("lml.api")
if not logger.handlers:
    _handler = logging.StreamHandler()  # stderr by default
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def log_json(level: str, **fields) -> None:
    """Emit a single JSON-line log entry to stderr."""
    entry = {"level": level, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    logger.log(getattr(logging, level.upper(), 20), json.dumps(entry, default=str))


# ---------------------------------------------------------------------------
# Rate limiter  (sliding window, 100 req/min per IP)
# ---------------------------------------------------------------------------
class _RateLimiter:
    """Thread-safe (async-safe) sliding-window rate limiter keyed by IP."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, client_ip: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            ts = self._hits[client_ip]
            # purge old entries
            cutoff = now - self.window
            ts[:] = [t for t in ts if t > cutoff]
            if len(ts) >= self.max_requests:
                return True
            ts.append(now)
            return False


_rate_limiter = _RateLimiter(max_requests=100, window_seconds=60)


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID; honour X-Request-ID if the client sent one."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        start = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        log_json(
            "info",
            request_id=rid,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


# ---------------------------------------------------------------------------
# Rate-limit middleware
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject with 429 when an IP exceeds 100 req/min."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if await _rate_limiter.is_rate_limited(client_ip):
            log_json("warning", request_id=getattr(request.state, "request_id", None),
                     client_ip=client_ip, event="rate_limited")
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limit_exceeded", "retry_after_seconds": 60},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Catch-all exception middleware
# ---------------------------------------------------------------------------
class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """Return JSON (not HTML) for any unhandled exception."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001
            rid = getattr(request.state, "request_id", None)
            log_json(
                "error",
                request_id=rid,
                method=request.method,
                path=request.url.path,
                exc_type=type(exc).__name__,
                exc_msg=str(exc),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "request_id": rid,
                    "detail": str(exc),
                },
            )
