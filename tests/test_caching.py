import time

from release_copilot.kit.caching import cache_json, load_cache_or_call


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


def test_load_cache_or_call_ttl(monkeypatch):
    calls = {"count": 0}

    def fetch():
        calls["count"] += 1
        return calls["count"]

    key = "test:key"

    orig_time = time.time()
    monkeypatch.setattr(time, "time", lambda: orig_time)
    data, source = load_cache_or_call(key, 1, fetch)
    assert source == "api" and data == 1

    # Within TTL -> cache hit
    data2, source2 = load_cache_or_call(key, 1, fetch)
    assert source2 == "cache" and data2 == 1

    # Advance time beyond TTL -> API again
    monkeypatch.setattr(time, "time", lambda: orig_time + 7200)
    data3, source3 = load_cache_or_call(key, 1, fetch)
    assert source3 == "api" and data3 == 2
