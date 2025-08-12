import hashlib
import json
import time
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Tuple

CACHE_DIR = Path("data/.cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _make_key(func: Callable, args: tuple[Any], kwargs: dict[str, Any]) -> str:
    raw = json.dumps([func.__name__, args, sorted(kwargs.items())], sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def cache_json(namespace: str, ttl_hours: int = 12):
    """Cache decorator storing JSON responses under ``data/.cache``.

    This existing decorator is left for backwards compatibility. New code
    should prefer :func:`load_cache_or_call` for explicit cache handling.
    """

    def decorator(func: Callable):
        ns_dir = CACHE_DIR / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = _make_key(func, args, kwargs)
            file_path = ns_dir / f"{key}.json"
            if file_path.exists():
                with open(file_path) as f:
                    payload = json.load(f)
                if time.time() - payload["ts"] < ttl_hours * 3600:
                    return payload["data"]
            data = func(*args, **kwargs)
            with open(file_path, "w") as f:
                json.dump({"ts": time.time(), "data": data}, f)
            return data

        return wrapper

    return decorator


@dataclass
class CacheKey:
    """Helper to build stable cache keys.

    Parameters
    ----------
    namespace:
        Prefix that identifies the type of data, e.g. ``"bb:commits"``.
    parts:
        Key/value pairs that further identify the cache entry.
    """

    namespace: str
    parts: dict[str, Any]

    def __str__(self) -> str:  # pragma: no cover - trivial
        items = [f"{k}={v}" for k, v in sorted(self.parts.items())]
        return f"{self.namespace}|" + "|".join(items)


def _cache_path(key: str) -> Path:
    h = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def load_cache_or_call(
    key: str,
    ttl_hours: int,
    fetch_fn: Callable[[], Any],
    force_refresh: bool = False,
) -> Tuple[Any, str]:
    """Load cached JSON if fresh, otherwise call ``fetch_fn``.

    Returns a tuple of ``(data, source)`` where ``source`` is ``"cache"``
    or ``"api"`` to aid logging.
    """

    path = _cache_path(key)
    if not force_refresh and path.exists():
        with path.open() as f:
            payload = json.load(f)
        if time.time() - payload.get("ts", 0) < ttl_hours * 3600:
            return payload.get("data"), "cache"

    data = fetch_fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump({"ts": time.time(), "data": data}, f)
    return data, "api"
