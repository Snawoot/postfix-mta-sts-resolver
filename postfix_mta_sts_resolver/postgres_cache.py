# pylint: disable=invalid-name,protected-access

import json
import logging

import asyncpg

from .defaults import POSTGRES_TIMEOUT
from .base_cache import BaseCache, CacheEntry


class PostgresCache(BaseCache):
    def __init__(self, *, timeout=POSTGRES_TIMEOUT, **kwargs):
        self._last_proactive_fetch_ts_id = 1
        asyncpglogger = logging.getLogger("asyncpg")
        if not asyncpglogger.hasHandlers():  # pragma: no cover
            asyncpglogger.addHandler(logging.NullHandler())
        self._timeout = timeout
        self._pool = None
        self.kwargs = kwargs

    async def setup(self):
        queries = [
            "CREATE TABLE IF NOT EXISTS proactive_fetch_ts "
            "(id serial primary key, last_fetch_ts integer)",
            "CREATE TABLE IF NOT EXISTS sts_policy_cache "
            "(id serial primary key, domain text, ts integer, pol_id text, pol_body jsonb)",
            "CREATE UNIQUE INDEX IF NOT EXISTS sts_policy_domain ON sts_policy_cache (domain)",
            "CREATE INDEX IF NOT EXISTS sts_policy_domain_ts ON sts_policy_cache (domain, ts)",
        ]

        async def set_type_codec(conn):
            await conn.set_type_codec(
                'jsonb',
                encoder=json.dumps,
                decoder=json.loads,
                schema='pg_catalog',
            )

        self._pool = await asyncpg.create_pool(init=set_type_codec, **self.kwargs)
        async with self._pool.acquire(timeout=self._timeout) as conn:
            async with conn.transaction():
                for q in queries:
                    await conn.execute(q)

    async def get_proactive_fetch_ts(self):
        async with self._pool.acquire(timeout=self._timeout) as conn, conn.transaction():
            cur = await conn.cursor('SELECT last_fetch_ts FROM '
                                    'proactive_fetch_ts where id = $1',
                                    self._last_proactive_fetch_ts_id)
            res = await cur.fetchrow()
        return int(res[0]) if res is not None else 0

    async def set_proactive_fetch_ts(self, timestamp):
        async with self._pool.acquire(timeout=self._timeout) as conn, conn.transaction():
            await conn.execute("""
                INSERT INTO proactive_fetch_ts (last_fetch_ts, id)
                VALUES ($1, $2)
                ON CONFLICT (id) DO UPDATE SET last_fetch_ts = EXCLUDED.last_fetch_ts
                """,
                int(timestamp), self._last_proactive_fetch_ts_id,
            )

    async def get(self, key):
        async with self._pool.acquire(timeout=self._timeout) as conn, conn.transaction():
            cur = await conn.cursor('SELECT ts, pol_id, pol_body FROM '
                                    'sts_policy_cache WHERE domain=$1',
                                    key)
            res = await cur.fetchrow()
        if res is not None:
            ts, pol_id, pol_body = res
            ts = int(ts)
            return CacheEntry(ts, pol_id, pol_body)
        else:
            return None

    async def set(self, key, value):
        ts, pol_id, pol_body = value
        async with self._pool.acquire(timeout=self._timeout) as conn, conn.transaction():
            await conn.execute("""
                INSERT INTO sts_policy_cache (domain, ts, pol_id, pol_body) VALUES ($1, $2, $3, $4)
                ON CONFLICT (domain) DO UPDATE
                SET ts = EXCLUDED.ts, pol_id = EXCLUDED.pol_id, pol_body = EXCLUDED.pol_body
                WHERE sts_policy_cache.ts < EXCLUDED.ts
            """, key, int(ts), pol_id, pol_body)

    async def scan(self, token, amount_hint):
        if token is None:
            token = 1

        async with self._pool.acquire(timeout=self._timeout) as conn, conn.transaction():
            res = await conn.fetch('SELECT id, ts, pol_id, pol_body, domain FROM '
                                    'sts_policy_cache WHERE id >= $1 LIMIT $2',
                                    token, amount_hint)
        if res:
            result = []
            new_token = token
            for row in res:
                rowid, ts, pol_id, pol_body, domain = row
                ts = int(ts)
                rowid = int(rowid)
                new_token = max(new_token, rowid)
                result.append((domain, CacheEntry(ts, pol_id, pol_body)))
            new_token += 1
            return new_token, result
        else:
            return None, []

    async def teardown(self):
        await self._pool.close()
