import sys
import asyncio
import itertools
import socket

import pynetstring
import pytest

from postfix_mta_sts_resolver.responder import STSSocketmapResponder
import postfix_mta_sts_resolver.utils as utils
from async_generator import yield_, async_generator

@pytest.fixture(scope="module")
@async_generator
async def responder(event_loop):
    import postfix_mta_sts_resolver.utils as utils
    cfg = utils.populate_cfg_defaults({"default_zone": {"strict_testing": True}})
    cfg["zones"]["test2"] = cfg["default_zone"]
    resp = STSSocketmapResponder(cfg, event_loop)
    await resp.start()
    result = resp, cfg['host'], cfg['port']
    await yield_(result)
    await resp.stop()

#@pytest.fixture(scope="module")
#def event_loop():
#    loop = asyncio.get_event_loop()
#    yield loop
#    loop.close()
#
buf_sizes = [4096, 128, 16, 1]
reqresps = [
    (b'test good.loc', b'OK secure match=mail.loc'),
    (b'test2 good.loc', b'OK secure match=mail.loc'),
    (b'test good.loc.', b'OK secure match=mail.loc'),
    (b'test .good.loc', b'NOTFOUND '),
    (b'test valid-none.loc', b'NOTFOUND '),
    (b'test testing.loc', b'OK secure match=mail.loc'),
    (b'test no-record.loc', b'NOTFOUND '),
    (b'test .no-record.loc', b'NOTFOUND '),
    (b'test bad-record1.loc', b'NOTFOUND '),
    (b'test bad-record2.loc', b'NOTFOUND '),
    (b'test bad-policy1.loc', b'NOTFOUND '),
    (b'test bad-policy2.loc', b'NOTFOUND '),
    (b'test bad-policy3.loc', b'NOTFOUND '),
    (b'test bad-cert1.loc', b'NOTFOUND '),
    (b'test bad-cert2.loc', b'NOTFOUND '),
]
@pytest.mark.parametrize("params", itertools.product(reqresps, buf_sizes))
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_responder(responder, params):
    (request, response), bufsize = params
    resp, host, port = responder
    decoder = pynetstring.Decoder()
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(pynetstring.encode(request))
        while True:
            data = await reader.read(bufsize)
            assert data
            res = decoder.feed(data)
            if res:
                assert res[0] == response
                break
    finally:
        writer.close()
