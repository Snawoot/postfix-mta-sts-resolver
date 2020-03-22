import asyncio
import os

import pytest

from postfix_mta_sts_resolver.utils import enable_uvloop, create_cache, populate_cfg_defaults
from async_generator import yield_, async_generator

@pytest.fixture(scope="session")
def event_loop():
    uvloop_test = os.environ['TOXENV'].endswith('-uvloop')
    uvloop_enabled = enable_uvloop()
    assert uvloop_test == uvloop_enabled
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
@async_generator
async def function_cache_fixture():
    cfg = populate_cfg_defaults(None)
    cache = create_cache(cfg['cache']['type'],
                         cfg['cache']['options'])
    await cache.setup()
    await yield_(cache)
    await cache.teardown()


@pytest.fixture(scope="module")
@async_generator
async def module_cache_fixture():
    cfg = populate_cfg_defaults(None)
    cache = create_cache(cfg['cache']['type'],
                         cfg['cache']['options'])
    await cache.setup()
    await yield_(cache)
    await cache.teardown()