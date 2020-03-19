import asyncio

import pytest

from postfix_mta_sts_resolver import base_cache, utils
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


@pytest.mark.parametrize("domain, init_policy_id, expected_policy_id, expected_update",
                         [("good.loc", "19990907T090909", "20180907T090909", True),
                          ("good.loc", "20180907T090909", "20180907T090909", True),
                          ("valid-none.loc", "19990907T090909", "20180907T090909", True),
                          ("blackhole.loc", "19990907T090909", "19990907T090909", False),
                          ("bad-record1.loc", "19990907T090909", "19990907T090909", False),
                          ("bad-policy1.loc", "19990907T090909", "19990907T090909", False)
                          ])
@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_cache_update(event_loop, cache,
                            domain, init_policy_id, expected_policy_id, expected_update):
    cfg = utils.populate_cfg_defaults(None)
    cfg['shutdown_timeout'] = 1
    cfg['cache']['proactive_fetch_enabled'] = True
    cfg['cache']['proactive_fetch_interval'] = 1

    await cache.set(domain, base_cache.CacheEntry(0, init_policy_id, {}))

    pf = STSProactiveFetcher(cfg, event_loop, cache)
    await pf.start()

    # Wait for policy fetcher to do its rounds
    await asyncio.sleep(3)

    # Verify
    result = await cache.get(domain)
    assert result
    assert result.pol_id == expected_policy_id
    if expected_update:
        assert result.ts > 0
        assert result.pol_body
    else:
        assert result.ts == 0

    await pf.stop()
