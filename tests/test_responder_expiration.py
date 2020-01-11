import asyncio
import tempfile
import os
import contextlib

import pytest

from postfix_mta_sts_resolver import netstring
from postfix_mta_sts_resolver.responder import STSSocketmapResponder
import postfix_mta_sts_resolver.utils as utils
import postfix_mta_sts_resolver.base_cache as base_cache

@contextlib.contextmanager
def set_env(**environ):
    old_environ = dict(os.environ)
    os.environ.update(environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_responder_expiration(event_loop):
    async def query(host, port, domain):
        reader, writer = await asyncio.open_connection(host, port)
        stream_reader = netstring.StreamReader()
        string_reader = stream_reader.next_string()
        writer.write(netstring.encode(b'test ' + domain.encode('ascii')))
        try:
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
        finally:
            writer.close()
    with tempfile.NamedTemporaryFile() as cachedb:
        cfg = {}
        cfg["port"] = 18461
        cfg["cache_grace"] = 0
        cfg["shutdown_timeout"] = 1
        cfg["cache"] = {
            "type": "sqlite",
            "options": {
                "filename": cachedb.name,
            },
        }
        cfg = utils.populate_cfg_defaults(cfg)
        cache = utils.create_cache(cfg['cache']['type'],
                                   cfg['cache']['options'])
        await cache.setup()
        pol_body = {
            "version": "STSv1",
            "mode": "enforce",
            "mx": [ "mail.loc" ],
            "max_age": 1,
        }
        await cache.set("no-record.loc", base_cache.CacheEntry(0, "0", pol_body))
        await cache.teardown()

        resp = STSSocketmapResponder(cfg, event_loop)
        await resp.start()
        try:
            result = await query(cfg['host'], cfg['port'], 'no-record.loc')
            assert result == b'NOTFOUND '
        finally:
            await resp.stop()
