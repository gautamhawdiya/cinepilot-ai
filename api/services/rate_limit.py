import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request


def _limit_from_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


# A pipeline run costs six Gemini calls, a live Parallel search, and an image
# for every shot in the storyboard -- tens of image generations, most of them
# generated in the background after the run reports complete. An open URL is
# therefore a standing invitation to burn the project's Vertex image quota,
# which empirically 429s well before a determined caller would. Runs take
# minutes each, so these ceilings sit far above genuine use. Set either to 0
# to disable that check.
_RUNS_PER_IP_PER_HOUR = _limit_from_env("RATE_LIMIT_RUNS_PER_IP_PER_HOUR", 10)
_RUNS_GLOBAL_PER_HOUR = _limit_from_env("RATE_LIMIT_RUNS_GLOBAL_PER_HOUR", 12)
_UPLOADS_PER_IP_PER_HOUR = _limit_from_env("RATE_LIMIT_UPLOADS_PER_IP_PER_HOUR", 30)

_WINDOW_SECONDS = 3600


class SlidingWindowLimiter:
    """Per-key sliding window counter.

    In-process state is correct only because the service runs with
    --max-instances=1; more instances would each keep their own counts and
    multiply the effective limit.
    """

    def __init__(self, limit: int, window_seconds: int = _WINDOW_SECONDS):
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def try_acquire(self, key: str) -> int | None:
        """Record a hit and return None, or return seconds to wait if over."""
        if self._limit == 0:
            return None

        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= self._limit:
                return max(1, int(self._window - (now - hits[0])))

            hits.append(now)
            return None


_run_limiter_per_ip = SlidingWindowLimiter(_RUNS_PER_IP_PER_HOUR)
_run_limiter_global = SlidingWindowLimiter(_RUNS_GLOBAL_PER_HOUR)
_upload_limiter_per_ip = SlidingWindowLimiter(_UPLOADS_PER_IP_PER_HOUR)


def client_key(request: Request) -> str:
    # Cloud Run terminates TLS at its front end, so the caller's address only
    # survives in X-Forwarded-For; request.client is the proxy.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _reject(retry_after: int, message: str) -> None:
    raise HTTPException(
        status_code=429,
        detail=message,
        headers={"Retry-After": str(retry_after)},
    )


def enforce_run_limit(request: Request) -> None:
    key = client_key(request)

    retry_after = _run_limiter_per_ip.try_acquire(key)
    if retry_after is not None:
        _reject(
            retry_after,
            "Too many pipeline runs from this address. Try again later.",
        )

    retry_after = _run_limiter_global.try_acquire("global")
    if retry_after is not None:
        _reject(
            retry_after,
            "CinePilot is at capacity right now. Try again shortly.",
        )


def enforce_upload_limit(request: Request) -> None:
    retry_after = _upload_limiter_per_ip.try_acquire(client_key(request))
    if retry_after is not None:
        _reject(
            retry_after,
            "Too many screenplay uploads from this address. Try again later.",
        )
