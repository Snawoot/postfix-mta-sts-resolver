import sys
import asyncio
import itertools
import socket
import os

import pytest

from postfix_mta_sts_resolver import netstring
from postfix_mta_sts_resolver.responder import STSSocketmapResponder
import postfix_mta_sts_resolver.utils as utils

from testdata import load_testdata

@pytest.fixture(scope="module")
async def responder(event_loop):
    import postfix_mta_sts_resolver.utils as utils
    cfg = utils.populate_cfg_defaults(None)
    cfg["zones"]["test2"] = cfg["default_zone"]
    cache = utils.create_cache(cfg['cache']['type'],
                               cfg['cache']['options'])
    await cache.setup()
    resp = STSSocketmapResponder(cfg, event_loop, cache)
    await resp.start()
    result = resp, cfg['host'], cfg['port']
    yield result
    await resp.stop()
    await cache.teardown()

@pytest.fixture(scope="module")
async def unix_responder(event_loop):
    import postfix_mta_sts_resolver.utils as utils
    cfg = utils.populate_cfg_defaults({'path': '/tmp/mta-sts.sock', 'mode': 0o666})
    cfg["zones"]["test2"] = cfg["default_zone"]
    cache = utils.create_cache(cfg['cache']['type'],
                               cfg['cache']['options'])
    await cache.setup()
    resp = STSSocketmapResponder(cfg, event_loop, cache)
    await resp.start()
    result = resp, cfg['path']
    yield result
    await resp.stop()
    await cache.teardown()

buf_sizes = [4096, 128, 16, 1]
reqresps = list(load_testdata('refdata'))
bufreq_pairs = tuple(itertools.product(reqresps, buf_sizes))
@pytest.mark.parametrize("params", bufreq_pairs)
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_responder(responder, params):
    (request, response), bufsize = params
    resp, host, port = responder
    stream_reader = netstring.StreamReader()
    string_reader = stream_reader.next_string()
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(netstring.encode(request))
        res = b''
        while True:
            try:
                part = string_reader.read()
            except netstring.WantRead:
                buf = await reader.read(bufsize)
                assert buf
                stream_reader.feed(buf)
            else:
                if not part:
                    break
                res += part
        assert res == response
    finally:
        writer.close()

@pytest.mark.parametrize("params", tuple(itertools.product(reqresps, buf_sizes)))
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_unix_responder(unix_responder, params):
    (request, response), bufsize = params
    resp, path = unix_responder
    stream_reader = netstring.StreamReader()
    string_reader = stream_reader.next_string()
    assert os.stat(path).st_mode & 0o777 == 0o666
    reader, writer = await asyncio.open_unix_connection(path)
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
    msg = netstring.encode(b'test good.loc')[:-1] + b'!'
    writer.write(msg)
    assert await reader.read() == b''
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_early_disconnect(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(netstring.encode(b'test good.loc'))
    writer.close()

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_cached(responder):
    resp, host, port = responder
    reader, writer = await asyncio.open_connection(host, port)
    stream_reader = netstring.StreamReader()
    writer.write(netstring.encode(b'test good.loc'))
    writer.write(netstring.encode(b'test good.loc'))
    answers = []
    try:
        for _ in range(2):
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
            answers.append(res)
        assert answers[0] == answers[1]
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

@pytest.mark.parametrize("params", tuple(itertools.product(reqresps, buf_sizes)))
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_responder_with_custom_socket(event_loop, responder, params):
    (request, response), bufsize = params
    resp, host, port = responder
    sock = await utils.create_custom_socket(host, 0, flags=0,
                                            options=[(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)])
    stream_reader = netstring.StreamReader()
    string_reader = stream_reader.next_string()
    await event_loop.run_in_executor(None, sock.connect, (host, port))
    reader, writer = await asyncio.open_connection(sock=sock)
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
