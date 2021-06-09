import sys
import asyncio
import itertools
import socket

import pytest

from postfix_mta_sts_resolver import netstring
from postfix_mta_sts_resolver.responder import STSSocketmapResponder
import postfix_mta_sts_resolver.utils as utils

from testdata import load_testdata

@pytest.fixture(scope="module")
async def responder(event_loop):
    import postfix_mta_sts_resolver.utils as utils
    cfg = utils.populate_cfg_defaults({"default_zone": {"require_sni": False}})
    cfg["zones"]["test2"] = cfg["default_zone"]
    cfg["port"] = 28461
    cache = utils.create_cache(cfg['cache']['type'],
                               cfg['cache']['options'])
    await cache.setup()
    resp = STSSocketmapResponder(cfg, event_loop, cache)
    await resp.start()
    result = resp, cfg['host'], cfg['port']
    yield result
    await resp.stop()
    await cache.teardown()

buf_sizes = [4096, 128, 16, 1]
reqresps = list(load_testdata('refdata_nosni'))
@pytest.mark.parametrize("params", tuple(itertools.product(reqresps, buf_sizes)))
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_responder(responder, params):
    (request, response), bufsize = params
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    stream_reader = netstring.StreamReader()
    string_reader = stream_reader.next_string()
    try:
        writer.write(netstring.encode(request))
        res = b''
        while True:
            try:
                part = string_reader.read()
            except netstring.WantRead:
                data = await reader.read(bufsize)
                assert data
                stream_reader.feed(data)
            else:
                if not part:
                    break
                res += part
        assert res == response
    finally:
        writer.close()
