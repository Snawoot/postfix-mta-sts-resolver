import tempfile
import pytest
import postfix_mta_sts_resolver.utils as utils
import postfix_mta_sts_resolver.base_cache as base_cache
from postfix_mta_sts_resolver import constants


async def setup_cache(cache_type, cache_opts):
    tmpfile = None
    if cache_type == 'sqlite':
        tmpfile = tempfile.NamedTemporaryFile()
        cache_opts["filename"] = tmpfile.name
    cache = utils.create_cache(cache_type, cache_opts)
    await cache.setup()
    if cache_type == 'redis':
        await cache._pool.flushdb()
    if cache_type == 'postgres':
        async with cache._pool.acquire() as conn:
            await conn.execute('TRUNCATE sts_policy_cache')
            await conn.execute('TRUNCATE proactive_fetch_ts')
    return cache, tmpfile

@pytest.mark.parametrize("cache_type,cache_opts,safe_set", [
    ("internal", {}, True),
    ("internal", {}, False),
    ("sqlite", {}, True),
    ("sqlite", {}, False),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, True),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, False),
    ("postgres", {"dsn": "postgres://postgres@localhost:5432"}, True),
    ("postgres", {"dsn": "postgres://postgres@localhost:5432"}, False),
])
@pytest.mark.asyncio
async def test_cache_lifecycle(cache_type, cache_opts, safe_set):
    cache, tmpfile = await setup_cache(cache_type, cache_opts)

    try:
        assert await cache.get("nonexistent") == None
        stored = base_cache.CacheEntry(0, "pol_id", "pol_body")
        if safe_set:
            await cache.safe_set("test", stored, None)
            await cache.safe_set("test", stored, None)  # second time for testing conflicting insert
        else:
            await cache.set("test", stored)
            await cache.set("test", stored)  # second time for testing conflicting insert
        assert await cache.get("test") == stored
    finally:
        await cache.teardown()
        if cache_type == 'sqlite':
            tmpfile.close()

@pytest.mark.parametrize("cache_type,cache_opts", [
    ("internal", {}),
    ("sqlite", {}),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}),
])
@pytest.mark.asyncio
async def test_proactive_fetch_ts_lifecycle(cache_type, cache_opts):
    cache, tmpfile = await setup_cache(cache_type, cache_opts)

    try:
        assert await cache.get_proactive_fetch_ts() >= 0  # works with empty db
        await cache.set_proactive_fetch_ts(123)
        await cache.set_proactive_fetch_ts(123)  # second time for testing conflicting insert
        assert await cache.get_proactive_fetch_ts() == 123

        await cache.set_proactive_fetch_ts(321)  # updating the db works
        assert await cache.get_proactive_fetch_ts() == 321
    finally:
        await cache.teardown()
        if cache_type == 'sqlite':
            tmpfile.close()

@pytest.mark.parametrize("cache_type,cache_opts,n_items,batch_size_limit", [
    ("internal", {}, 3, 1),
    ("internal", {}, 3, 2),
    ("internal", {}, 3, 3),
    ("internal", {}, 3, 4),
    ("internal", {}, 0, 4),
    ("internal", {}, constants.DOMAIN_QUEUE_LIMIT*2, constants.DOMAIN_QUEUE_LIMIT),
    ("sqlite", {}, 3, 1),
    ("sqlite", {}, 3, 2),
    ("sqlite", {}, 3, 3),
    ("sqlite", {}, 3, 4),
    ("sqlite", {}, 0, 4),
    ("sqlite", {}, constants.DOMAIN_QUEUE_LIMIT*2, constants.DOMAIN_QUEUE_LIMIT),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, 3, 1),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, 3, 2),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, 3, 3),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, 3, 4),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, 0, 4),
    ("redis", {"url": "redis://127.0.0.1/0?socket_timeout=5&socket_connect_timeout=5"}, constants.DOMAIN_QUEUE_LIMIT*2, constants.DOMAIN_QUEUE_LIMIT),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}, 3, 1),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}, 3, 2),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}, 3, 3),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}, 3, 4),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}, 0, 4),
    ("postgres", {"dsn": "postgres://postgres@%2Frun%2Fpostgresql/postgres"}, constants.DOMAIN_QUEUE_LIMIT*2, constants.DOMAIN_QUEUE_LIMIT),
])
@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_scanning_in_batches(cache_type, cache_opts, n_items, batch_size_limit):
    # Prepare
    cache, tmpfile = await setup_cache(cache_type, cache_opts)
    data = []
    for n in range(n_items):
        item = ("test{:04d}".format(n+1), base_cache.CacheEntry(n+1, "pol_id", "pol_body"))
        data.append(item)
        await cache.set(*item)

    # Test (scan)
    token = None
    scanned = []
    while True:
        token, cache_items = await cache.scan(token, batch_size_limit)
        for cache_item in cache_items:
            scanned.append(cache_item)
        if token is None:
            break

    try:
        # Verify scanned data is same as inserted (order agnostic)
        assert len(scanned) == len(data)
        assert sorted(scanned) == sorted(data)
        # For internal LRU, verify it's scanned from LRU to MRU record
        if cache_type == "internal":
            assert scanned == data
    finally:
        await cache.teardown()
        if cache_type == 'sqlite':
            tmpfile.close()

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
