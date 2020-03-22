import asyncio
import time

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
    cfg['proactive_policy_fetching']['enabled'] = True
    cfg['proactive_policy_fetching']['interval'] = 1
    cfg['proactive_policy_fetching']['grace_ratio'] = 1000
    cfg["default_zone"]["timeout"] = 1
    cfg['shutdown_timeout'] = 1

    await cache.set(domain, base_cache.CacheEntry(0, init_policy_id, {}))

    pf = STSProactiveFetcher(cfg, event_loop, cache)
    await pf.start()

    # Wait for policy fetcher to do its rounds
    await asyncio.sleep(3)

    # Verify
    assert time.time() - await cache.get_proactive_fetch_ts() < 10

    result = await cache.get(domain)
    assert result
    assert result.pol_id == expected_policy_id
    if expected_update:
        assert time.time() - result.ts < 10  # update
        # Due to an id change, a new body must be fetched
        if init_policy_id != expected_policy_id:
            assert result.pol_body
        # Otherwise we don't fetch a new policy body
        else:
            assert not result.pol_body
    else:
        assert result.ts == 0
        assert not result.pol_body

    await pf.stop()

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_no_cache_update_during_grace_period(event_loop, cache):
    cfg = utils.populate_cfg_defaults(None)
    cfg['proactive_policy_fetching']['enabled'] = True
    cfg['proactive_policy_fetching']['interval'] = 86400
    cfg['proactive_policy_fetching']['grace_ratio'] = 2.0
    cfg['shutdown_timeout'] = 1

    init_record = base_cache.CacheEntry(time.time() - 1, "19990907T090909", {})
    await cache.set("good.loc", init_record)

    pf = STSProactiveFetcher(cfg, event_loop, cache)
    await pf.start()

    # Wait for policy fetcher to do its round
    await asyncio.sleep(3)

    # Verify
    assert time.time() - await cache.get_proactive_fetch_ts() < 10

    result = await cache.get("good.loc")
    assert result == init_record  # no update (cached being fresh enough)

    await pf.stop()

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_respect_previous_proactive_fetch_ts(event_loop, cache):
    cfg = utils.populate_cfg_defaults(None)
    cfg['proactive_policy_fetching']['enabled'] = True
    cfg['proactive_policy_fetching']['interval'] = 86400
    cfg['proactive_policy_fetching']['grace_ratio'] = 2.0
    cfg['shutdown_timeout'] = 1

    previous_proactive_fetch_ts = time.time() - 1
    init_record = base_cache.CacheEntry(0, "19990907T090909", {})
    await cache.set("good.loc", init_record)
    await cache.set_proactive_fetch_ts(previous_proactive_fetch_ts)

    pf = STSProactiveFetcher(cfg, event_loop, cache)
    await pf.start()

    # Wait for policy fetcher to do its potential work
    await asyncio.sleep(3)

    # Verify
    assert previous_proactive_fetch_ts == await cache.get_proactive_fetch_ts()

    result = await cache.get("good.loc")
    assert result == init_record  # no update

    await pf.stop()
