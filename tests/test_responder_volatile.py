import sys
import asyncio
import itertools
import socket

import pytest

from postfix_mta_sts_resolver import netstring
from postfix_mta_sts_resolver.responder import STSSocketmapResponder
import postfix_mta_sts_resolver.utils as utils
from async_generator import yield_, async_generator

@pytest.fixture
@async_generator
async def responder(event_loop):
    import postfix_mta_sts_resolver.utils as utils
    cfg = utils.populate_cfg_defaults(None)
    cfg["port"] = 38461
    cfg["shutdown_timeout"] = 1
    cfg["cache_grace"] = 0
    cfg["zones"]["test2"] = cfg["default_zone"]
    cache = utils.create_cache(cfg['cache']['type'],
                               cfg['cache']['options'])
    await cache.setup()
    resp = STSSocketmapResponder(cfg, event_loop, cache)
    await resp.start()
    result = resp, cfg['host'], cfg['port']
    await yield_(result)
    await resp.stop()
    await cache.teardown()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_hanging_stop(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    await resp.stop()
    assert await reader.read() == b''
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_inprogress_stop(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(netstring.encode(b'test blackhole.loc'))
    await writer.drain()
    await asyncio.sleep(0.2)
    await resp.stop()
    assert await reader.read() == b''
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_extended_stop(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(netstring.encode(b'test blackhole.loc'))
    writer.write(netstring.encode(b'test blackhole.loc'))
    writer.write(netstring.encode(b'test blackhole.loc'))
    await writer.drain()
    await asyncio.sleep(0.2)
    await resp.stop()
    assert await reader.read() == b''
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(7)
async def test_grace_expired(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    stream_reader = netstring.StreamReader()
    async def answer():
        string_reader = stream_reader.next_string()
        res = b''
        while True:
            try:
                part = string_reader.read()
            except netstring.WantRead:
                data = await reader.read(4096)
                assert data
                stream_reader.feed(data)
            else:
                if not part:
                    break
                res += part
        return res
    try:
        writer.write(netstring.encode(b'test good.loc'))
        answer_a = await answer()
        await asyncio.sleep(2)
        writer.write(netstring.encode(b'test good.loc'))
        answer_b = await answer()
        assert answer_a == answer_b
    finally:
        writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(7)
async def test_fast_expire(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    stream_reader = netstring.StreamReader()
    async def answer():
        string_reader = stream_reader.next_string()
        res = b''
        while True:
            try:
                part = string_reader.read()
            except netstring.WantRead:
                data = await reader.read(4096)
                assert data
                stream_reader.feed(data)
            else:
                if not part:
                    break
                res += part
        return res
    try:
        writer.write(netstring.encode(b'test fast-expire.loc'))
        answer_a = await answer()
        await asyncio.sleep(2)
        writer.write(netstring.encode(b'test fast-expire.loc'))
        answer_b = await answer()
        assert answer_a == answer_b == b'OK secure match=mail.loc servername=hostname'
    finally:
        writer.close()
