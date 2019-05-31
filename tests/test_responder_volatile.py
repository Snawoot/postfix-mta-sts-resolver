import sys
import asyncio
import itertools
import socket

import pynetstring
import pytest

from postfix_mta_sts_resolver.responder import STSSocketmapResponder
import postfix_mta_sts_resolver.utils as utils
from async_generator import yield_, async_generator

@pytest.fixture
@async_generator
async def responder(event_loop):
    import postfix_mta_sts_resolver.utils as utils
    cfg = utils.populate_cfg_defaults(None)
    cfg["zones"]["test2"] = cfg["default_zone"]
    resp = STSSocketmapResponder(cfg, event_loop)
    await resp.start()
    result = resp, cfg['host'], cfg['port']
    await yield_(result)
    await resp.stop()

@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_hanging_stop(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    await resp.stop()
    assert await reader.read() == b''
    writer.close()

