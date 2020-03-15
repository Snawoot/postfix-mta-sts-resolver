import json
import uuid

import aioredis
from . import defaults
from .base_cache import BaseCache, CacheEntry


def pack_entry(entry):
    ts, pol_id, pol_body = entry  # pylint: disable=invalid-name,unused-variable
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
        self._pool = None

    async def setup(self):
        self._pool = await aioredis.create_redis_pool(**self._opts)

    async def get(self, key):
        assert self._pool is not None
        key = key.encode('utf-8')
        res = await self._pool.zrevrange(key, 0, 0, "WITHSCORES")
        if not res:
            return None
        packed, ts = res[0]  # pylint: disable=invalid-name
        entry = unpack_entry(packed)
        return CacheEntry(ts=ts, pol_id=entry.pol_id, pol_body=entry.pol_body)

    async def set(self, key, value):
        assert self._pool is not None
        packed = pack_entry(value)
        ts = value.ts  # pylint: disable=invalid-name
        key = key.encode('utf-8')

        # Write
        pipe = self._pool.pipeline()
        pipe.zadd(key, ts, packed)
        pipe.zremrangebyrank(key, 0, -2)
        await pipe.execute()

    async def scan(self, token, amount_hint):
        assert self._pool is not None
        if token is None:
            token = b'0'

        new_token, keys = await self._pool.scan(cursor=token, count=amount_hint)
        if not new_token:
            new_token = None

        result = []
        for key in keys:
            key = key.decode('utf-8')
            if key != '_metadata':
                result.append((key, await self.get(key)))
        return new_token, result

    async def get_proactive_fetch_ts(self):
        assert self._pool is not None
        val = await self._pool.hget('_metadata', 'proactive_fetch_ts')
        return 0 if not val else float(val.decode('utf-8'))

    async def set_proactive_fetch_ts(self, timestamp):
        assert self._pool is not None
        val = str(timestamp).encode('utf-8')
        await self._pool.hset('_metadata', 'proactive_fetch_ts', val)

    async def teardown(self):
        assert self._pool is not None
        self._pool.close()
        await self._pool.wait_closed()
