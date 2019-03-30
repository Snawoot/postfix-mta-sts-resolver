import sqlite3
import json
import logging
import uuid

import aioredis
from . import defaults
from .base_cache import BaseCache, CacheEntry


def pack_entry(entry):
    ts, pol_id, pol_body = entry
    obj = (pol_id, pol_body)
    # add unique seed to entry in order to avoid set collisions
    # and use ZSET two-index table
    packed = uuid.uuid4().bytes + json.dumps(obj).encode('utf-8')
    return packed


def unpack_entry(packed):
    bin_obj = packed[16:]
    obj = json.loads(bin_obj.decode('utf-8'))
    pol_id, pol_body = obj
    return CacheEntry(ts=0, pol_id=pol_id, pol_body=pol_body)


class RedisCache(BaseCache):
    def __init__(self, **opts):
        self._opts = dict(opts)
        self._opts['timeout'] = self._opts.get('timeout',
                                               defaults.REDIS_TIMEOUT)
        self._opts['encoding'] = None

    async def setup(self):
        self._pool = await aioredis.create_redis_pool(**self._opts)

    async def get(self, key):
        key = key.encode('utf-8')
        res = await self._pool.zrevrange(key, 0, 0, "WITHSCORES")
        if not res:
            return None
        packed, ts = res[0]
        entry = unpack_entry(packed)
        return CacheEntry(ts=ts, pol_id=entry.pol_id, pol_body=entry.pol_body)

    async def set(self, key, value):
        packed = pack_entry(value)
        ts = value.ts
        key = key.encode('utf-8')

        # Write
        pipe = self._pool.pipeline()
        pipe.zadd(key, ts, packed)
        pipe.zremrangebyrank(key, 0, -2)
        results = await pipe.execute()

    async def teardown(self):
        self._pool.close()
        await self._pool.wait_closed()
