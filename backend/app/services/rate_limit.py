"""A bounded, process-local limiter for the single-worker pilot."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from fastapi import HTTPException

_attempts = defaultdict(deque)
_lock = Lock()


def rate_limit(key):
    now = monotonic()
    with _lock:
        for old_key in list(_attempts):
            if not _attempts[old_key] or now - _attempts[old_key][-1] > 60:
                del _attempts[old_key]
        attempts = _attempts[key]
        while attempts and now - attempts[0] > 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(
                429,
                "Too many requests. Try again in a minute.",
                headers={"Retry-After": "60"},
            )
        attempts.append(now)
