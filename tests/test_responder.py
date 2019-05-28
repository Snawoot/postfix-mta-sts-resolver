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
    cfg = utils.populate_cfg_defaults(None)
    resp = STSSocketmapResponder(cfg, event_loop)
    await resp.start()
    result = resp, cfg['host'], cfg['port']
    await yield_(result)
    await resp.stop()

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

buf_sizes = [4096, 128, 16, 1]
reqresps = [
    (b'test vm-0.com', b'OK secure match=mx.vm-0.com'),
    (b'test vm-0.com.', b'OK secure match=mx.vm-0.com'),
    (b'test .vm-0.com', b'NOTFOUND '),
    (b'test mta-sts.vm-0.com', b'NOTFOUND '),
    (b'test .mta-sts.vm-0.com', b'NOTFOUND '),
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
        while True:
            writer.write(pynetstring.encode(request))
            data = await reader.read(bufsize)
            assert data
            res = decoder.feed(data)
            if res:
                assert res[0] == response
                break
    finally:
        writer.close()

@pytest.mark.parametrize("params", itertools.product(reqresps, buf_sizes))
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_responder_with_custom_socket(responder, params):
    (request, response), bufsize = params
    resp, host, port = responder
    decoder = pynetstring.Decoder()
    sock = await utils.create_custom_socket(host, 0, flags=0,
                                            options=[(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)])
    sock.connect((host, port))
    reader, writer = await asyncio.open_connection(sock=sock)
    try:
        while True:
            writer.write(pynetstring.encode(request))
            data = await reader.read(bufsize)
            assert data
            res = decoder.feed(data)
            if res:
                assert res[0] == response
                break
    finally:
        writer.close()
