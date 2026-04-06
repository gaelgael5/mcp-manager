"""Rate limiting middleware — in-memory token bucket per IP/user."""
import time
import logging
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from mcp_manager.api.routers.auth import _get_user_from_request

logger = logging.getLogger(__name__)

# Config: (max_requests, window_seconds)
LIMITS = {
    "search": (30, 60),       # 30 req/min for /search
    "get": (60, 60),          # 60 req/min for GET
    "post": (10, 60),         # 10 req/min for POST
    "authenticated": (120, 60),  # 120 req/min for authenticated users
}


class RateBucket:
    __slots__ = ("tokens", "last_refill", "max_tokens", "refill_rate")

    def __init__(self, max_tokens: int, window_seconds: int):
        self.tokens = max_tokens
        self.max_tokens = max_tokens
        self.refill_rate = max_tokens / window_seconds
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

    @property
    def remaining(self) -> int:
        return max(0, int(self.tokens))

    @property
    def retry_after(self) -> int:
        if self.tokens >= 1:
            return 0
        return max(1, int((1 - self.tokens) / self.refill_rate))


# Store: key -> RateBucket
_buckets: dict[str, RateBucket] = defaultdict(lambda: None)
_last_cleanup = time.monotonic()


def _get_bucket(key: str, max_tokens: int, window: int) -> RateBucket:
    if key not in _buckets or _buckets[key] is None:
        _buckets[key] = RateBucket(max_tokens, window)
    return _buckets[key]


def _cleanup():
    """Remove stale buckets every 5 minutes."""
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < 300:
        return
    _last_cleanup = now
    stale = [k for k, b in _buckets.items() if b and b.tokens >= b.max_tokens]
    for k in stale:
        del _buckets[k]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        _cleanup()

        path = request.url.path
        method = request.method

        # Skip health checks
        if "/health" in path:
            return await call_next(request)

        # Check if authenticated (JWT or API key)
        user = _get_user_from_request(request)

        # Validate API key if present
        api_key_header = request.headers.get("X-API-Key", "")
        auth_header = request.headers.get("Authorization", "")
        if not api_key_header and auth_header.startswith("Bearer mcp_"):
            api_key_header = auth_header[7:]

        if api_key_header:
            from mcp_manager.db.session import SessionLocal
            from mcp_manager.api.routers.api_keys import validate_api_key
            async with SessionLocal() as db:
                api_user = await validate_api_key(api_key_header, db)
            if api_user:
                user = api_user
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired API key"},
                )

        # Admin: no limits
        if user and user.get("is_admin"):
            return await call_next(request)

        # Determine client key and limits
        client_ip = request.headers.get("x-real-ip") or request.client.host if request.client else "unknown"

        if user:
            key = f"user:{user.get('email', client_ip)}"
            max_tokens, window = LIMITS["authenticated"]
        elif "/search" in path:
            key = f"ip:{client_ip}:search"
            max_tokens, window = LIMITS["search"]
        elif method == "POST":
            key = f"ip:{client_ip}:post"
            max_tokens, window = LIMITS["post"]
        else:
            key = f"ip:{client_ip}:get"
            max_tokens, window = LIMITS["get"]

        bucket = _get_bucket(key, max_tokens, window)

        if not bucket.consume():
            logger.warning("Rate limited: %s (%s %s)", key, method, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={
                    "Retry-After": str(bucket.retry_after),
                    "X-RateLimit-Limit": str(max_tokens),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(bucket.retry_after),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_tokens)
        response.headers["X-RateLimit-Remaining"] = str(bucket.remaining)
        return response
