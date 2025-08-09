import json
import hashlib
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

CACHE_DIR = Path('data/.cache')


def _make_key(func: Callable, args: tuple[Any], kwargs: dict[str, Any]) -> str:
    raw = json.dumps([func.__name__, args, sorted(kwargs.items())], sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def cache_json(namespace: str, ttl_hours: int = 12):
    """Cache decorator storing JSON responses under data/.cache."""

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
                if time.time() - payload['ts'] < ttl_hours * 3600:
                    return payload['data']
            data = func(*args, **kwargs)
            with open(file_path, 'w') as f:
                json.dump({'ts': time.time(), 'data': data}, f)
            return data

        return wrapper

    return decorator
