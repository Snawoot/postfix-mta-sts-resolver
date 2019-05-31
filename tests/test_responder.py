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
    cfg["zones"]["test2"] = cfg["default_zone"]
    resp = STSSocketmapResponder(cfg, event_loop)
    await resp.start()
    result = resp, cfg['host'], cfg['port']
    await yield_(result)
    await resp.stop()

buf_sizes = [4096, 128, 16, 1]
reqresps = [
    (b'test good.loc', b'OK secure match=mail.loc'),
    (b'test2 good.loc', b'OK secure match=mail.loc'),
    (b'test good.loc.', b'OK secure match=mail.loc'),
    (b'test .good.loc', b'NOTFOUND '),
    (b'test valid-none.loc', b'NOTFOUND '),
    (b'test testing.loc', b'NOTFOUND '),
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

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_empty_dialog(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_corrupt_dialog(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    msg = pynetstring.encode(b'test good.loc')[:-1] + b'!'
    writer.write(msg)
    assert await reader.read() == b''
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_early_disconnect(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(pynetstring.encode(b'test good.loc'))
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_cached(responder):
    resp, host, port = responder
    decoder = pynetstring.Decoder()
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(pynetstring.encode(b'test good.loc'))
    writer.write(pynetstring.encode(b'test good.loc'))
    answers = []
    try:
        while True:
            data = await reader.read(4096)
            assert data
            res = decoder.feed(data)
            if res:
                answers += res
                if len(answers) == 2:
                    break
        assert answers[0] == answers[1]
    finally:
        writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(7)
async def test_fast_expire(responder):
    resp, host, port = responder
    decoder = pynetstring.Decoder()
    reader, writer = await asyncio.open_connection(host, port)
    async def answer():
        while True:
            data = await reader.read(4096)
            assert data
            res = decoder.feed(data)
            if res:
                return res[0]
    try:
        writer.write(pynetstring.encode(b'test fast-expire.loc'))
        answer_a = await answer()
        await asyncio.sleep(2)
        writer.write(pynetstring.encode(b'test fast-expire.loc'))
        answer_b = await answer()
        assert answer_a == answer_b == b'OK secure match=mail.loc'
    finally:
        writer.close()

@pytest.mark.parametrize("params", itertools.product(reqresps, buf_sizes))
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_responder_with_custom_socket(event_loop, responder, params):
    (request, response), bufsize = params
    resp, host, port = responder
    decoder = pynetstring.Decoder()
    sock = await utils.create_custom_socket(host, 0, flags=0,
                                            options=[(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)])
    await event_loop.run_in_executor(None, sock.connect, (host, port))
    reader, writer = await asyncio.open_connection(sock=sock)
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
