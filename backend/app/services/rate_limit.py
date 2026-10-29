"""A bounded, process-local limiter for the single-worker pilot."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException

_attempts = defaultdict(deque)
_lock = Lock()


def client_ip(request) -> str:
    """Safely extract client IP, trusting forwarded headers only from loopback/proxies."""
    if not request or not getattr(request, "client", None):
        return "unknown"
    host = request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return forwarded.split(",")[0].strip()
    return host


def rate_limit(key: str, limit: int = 10, window: int = 60):
    now = monotonic()
    with _lock:
        for old_key in list(_attempts):
            if not _attempts[old_key] or now - _attempts[old_key][-1] > window:
                del _attempts[old_key]
        attempts = _attempts[key]
        while attempts and now - attempts[0] > window:
            attempts.popleft()
        if len(attempts) >= limit:
            raise HTTPException(
                429,
                "Too many requests. Try again in a minute.",
                headers={"Retry-After": str(window)},
            )
        attempts.append(now)
