import json
import uuid

from redis import asyncio as aioredis
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
        self._opts['socket_timeout'] = self._opts.get('socket_timeout',
            defaults.REDIS_TIMEOUT)
        self._opts['socket_connect_timeout'] = self._opts.get(
            'socket_connect_timeout', defaults.REDIS_CONNECT_TIMEOUT)
        self._opts['encoding'] = 'utf-8'
        self._pool = None

    async def setup(self):
        url = self._opts['url']
        opts = dict((k,v) for k, v in self._opts.items() if k != 'url')
        self._pool = aioredis.from_url(url, **opts)

    async def get(self, key):
        assert self._pool is not None
        key = key.encode('utf-8')
        res = await self._pool.zrevrange(key, 0, 0, withscores=True)
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
        async with self._pool.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {packed: ts})
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
        await self._pool.close()

class RedisSentinelCache(BaseCache):
    def __init__(self, **opts):
        self._opts = dict(opts)
        self._opts['socket_timeout'] = self._opts.get(
            'socket_timeout',defaults.REDIS_TIMEOUT
        )
        self._opts['socket_connect_timeout'] = self._opts.get(
            'socket_connect_timeout', defaults.REDIS_CONNECT_TIMEOUT
        )
        self._opts['encoding'] = 'utf-8'
        self._pool = None

    async def setup(self):
        sentinel = aioredis.sentinel.Sentinel(self._opts['sentinels'])
        sentinel_master_name = self._opts['sentinel_master_name']
        for key in ['sentinels', 'sentinel_master_name']:
          self._opts.pop(key)
        opts = dict((k,v) for k, v in self._opts.items())
        self._pool = sentinel.master_for(sentinel_master_name, **opts)

    async def get(self, key):
        assert self._pool is not None
        key = key.encode('utf-8')
        res = await self._pool.zrevrange(key, 0, 0, withscores=True)
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
        async with self._pool.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {packed: ts})
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
        await self._pool.close()
