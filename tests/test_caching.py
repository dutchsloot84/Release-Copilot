import os
import time
from src.kit.caching import cache_json


def test_cache_ttl(monkeypatch):
    calls = {'count': 0}

    @cache_json('test', ttl_hours=1)
    def func(x):
        calls['count'] += 1
        return x

    # First call computes
    assert func(1) == 1
    assert calls['count'] == 1

    # Second call uses cache
    assert func(1) == 1
    assert calls['count'] == 1

    # Expire cache by advancing time
    orig_time = time.time()
    monkeypatch.setattr(time, 'time', lambda: orig_time + 7200)
    assert func(1) == 1
    assert calls['count'] == 2
