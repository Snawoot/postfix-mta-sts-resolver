import asyncio

import pytest

from postfix_mta_sts_resolver import base_cache
from postfix_mta_sts_resolver.proactive_fetcher import STSProactiveFetcher
from async_generator import yield_, async_generator

from postfix_mta_sts_resolver.utils import populate_cfg_defaults, create_cache


@pytest.fixture
@async_generator
async def cache():
    cfg = populate_cfg_defaults(None)
    cache = create_cache(cfg['cache']['type'],
                         cfg['cache']['options'])
    await cache.setup()
    await yield_(cache)
    await cache.teardown()

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_cache_update(event_loop, cache):
    import postfix_mta_sts_resolver.utils as utils
    cfg = utils.populate_cfg_defaults(None)
    cfg['shutdown_timeout'] = 1
    cfg['cache']['proactive_fetch_enabled'] = True
    cfg['cache']['proactive_fetch_interval'] = 1

    # This should be updated by the proactive fetcher
    await cache.set("good.loc", base_cache.CacheEntry(0, "0", {}))

    pf = STSProactiveFetcher(cfg, event_loop, cache)
    await pf.start()

    # Wait for policy fetcher to do its rounds
    await asyncio.sleep(3)

    # Verify
    result = await cache.get("good.loc")
    assert result

    await pf.stop()