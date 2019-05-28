import pytest
import postfix_mta_sts_resolver.utils as utils
import postfix_mta_sts_resolver.base_cache as base_cache

@pytest.mark.parametrize("cache_type,cache_opts", [
    ("internal", {}),
    ("sqlite", {"filename": "test.db"}),
    ("redis", {"address": "redis://127.0.0.1/0?timeout=5"}),
])
@pytest.mark.asyncio
async def test_cache_lifecycle(cache_type, cache_opts):
    cache = utils.create_cache(cache_type, cache_opts)
    await cache.setup()
    assert await cache.get("nonexistent") == None
    stored = base_cache.CacheEntry(0, "pol_id", "pol_body")
    await cache.set("test", stored)
    await cache.set("test", stored) # second time for testing conflicting insert
    assert await cache.get("test") == stored
    await cache.teardown()

@pytest.mark.asyncio
async def test_capped_cache():
    cache = utils.create_cache("internal", {"cache_size": 2})
    await cache.setup()
    stored = base_cache.CacheEntry(0, "pol_id", "pol_body")
    await cache.set("test1", stored)
    await cache.set("test2", stored)
    await cache.set("test3", stored)
    assert await cache.get("test2") == stored
    assert await cache.get("test3") == stored

def test_unknown_cache_lifecycle():
    with pytest.raises(NotImplementedError):
        cache = utils.create_cache("void", {})
