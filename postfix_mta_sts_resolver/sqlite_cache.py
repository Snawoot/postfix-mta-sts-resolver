# pylint: disable=invalid-name,protected-access

import asyncio
import sqlite3
import json
import logging

import aiosqlite

from .defaults import SQLITE_THREADS, SQLITE_TIMEOUT
from .base_cache import BaseCache, CacheEntry


class SqliteConnPool:
    def __init__(self, threads, conn_args=(), conn_kwargs=None, init_queries=()):
        self._threads = threads
        self._conn_args = conn_args
        self._conn_kwargs = conn_kwargs if conn_kwargs is not None else {}
        self._init_queries = init_queries
        self._free_conns = asyncio.Queue()
        self._ready = False
        self._stopped = False

    async def _new_conn(self):
        db = await aiosqlite.connect(*self._conn_args, **self._conn_kwargs)
        try:
            async with db.cursor() as cur:
                for q in self._init_queries:
                    await cur.execute(q)
        except:
            await db.close()
            raise
        return db

    async def prepare(self):
        for _ in range(self._threads):
            self._free_conns.put_nowait(await self._new_conn())
        self._ready = True

    async def stop(self):
        self._ready = False
        self._stopped = True
        try:
            while True:
                db = self._free_conns.get_nowait()
                await db.close()
        except asyncio.QueueEmpty:
            pass

    def borrow(self, timeout=None):
        if not self._ready:
            raise RuntimeError("Pool not prepared!")
        class PoolBorrow:
            # pylint: disable=no-self-argument
            def __init__(s):
                s._conn = None

            # pylint: disable=no-self-argument
            async def __aenter__(s):
                s._conn = await asyncio.wait_for(self._free_conns.get(),
                                                 timeout)
                return s._conn

            # pylint: disable=no-self-argument
            async def __aexit__(s, exc_type, exc, tb):
                if self._stopped:
                    await s._conn.close()
                    return
                if exc_type is not None:
                    await s._conn.close()
                    s._conn = await self._new_conn()
                self._free_conns.put_nowait(s._conn)
        return PoolBorrow()


class SqliteCache(BaseCache):
    def __init__(self, filename, *,
                 threads=SQLITE_THREADS, timeout=SQLITE_TIMEOUT):
        self._filename = filename
        self._threads = threads
        self._timeout = timeout
        self._last_proactive_fetch_ts_id = 1
        sqlitelogger = logging.getLogger("aiosqlite")
        if not sqlitelogger.hasHandlers():  # pragma: no cover
            sqlitelogger.addHandler(logging.NullHandler())
        self._pool = None

    async def setup(self):
        conn_init = [
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
        ]
        self._pool = SqliteConnPool(self._threads,
                                    conn_args=(self._filename,),
                                    conn_kwargs={
                                        "timeout": self._timeout,
                                    },
                                    init_queries=conn_init)
        await self._pool.prepare()
        queries = [
            "create table if not exists proactive_fetch_ts "
            "(id integer primary key, last_fetch_ts integer)",
            "create table if not exists sts_policy_cache "
            "(domain text, ts integer, pol_id text, pol_body text)",
            "create unique index if not exists sts_policy_domain on sts_policy_cache (domain)",
            "create index if not exists sts_policy_domain_ts on sts_policy_cache (domain, ts)",
        ]
        async with self._pool.borrow(self._timeout) as conn:
            async with conn.cursor() as cur:
                for q in queries:
                    await cur.execute(q)
            await conn.commit()

    async def get_proactive_fetch_ts(self):
        async with self._pool.borrow(self._timeout) as conn:
            async with conn.execute('select last_fetch_ts from '
                                    'proactive_fetch_ts where id = ?',
                                    (self._last_proactive_fetch_ts_id,)) as cur:
                res = await cur.fetchone()
        return int(res[0]) if res is not None else 0

    async def set_proactive_fetch_ts(self, timestamp):
        async with self._pool.borrow(self._timeout) as conn:
            try:
                await conn.execute('insert into proactive_fetch_ts (last_fetch_ts, id) '
                                   'values (?, ?)',
                                   (int(timestamp), self._last_proactive_fetch_ts_id))
                await conn.commit()
            except sqlite3.IntegrityError:
                await conn.execute('update proactive_fetch_ts '
                                   'set last_fetch_ts = ? where id = ?',
                                   (int(timestamp), self._last_proactive_fetch_ts_id))
                await conn.commit()


    async def get(self, key):
        async with self._pool.borrow(self._timeout) as conn:
            async with conn.execute('select ts, pol_id, pol_body from '
                                    'sts_policy_cache where domain=?',
                                    (key,)) as cur:
                res = await cur.fetchone()
        if res is not None:
            ts, pol_id, pol_body = res
            ts = int(ts)
            pol_body = json.loads(pol_body)
            return CacheEntry(ts, pol_id, pol_body)
        else:
            return None

    async def set(self, key, value):
        ts, pol_id, pol_body = value
        pol_body = json.dumps(pol_body)
        async with self._pool.borrow(self._timeout) as conn:
            try:
                await conn.execute('insert into sts_policy_cache (domain, ts, '
                                   'pol_id, pol_body) values (?, ?, ?, ?)',
                                   (key, int(ts), pol_id, pol_body))
                await conn.commit()
            except sqlite3.IntegrityError:
                await conn.execute('update sts_policy_cache set ts = ?, '
                                   'pol_id = ?, pol_body = ? where domain = ? '
                                   'and ts < ?',
                                   (int(ts), pol_id, pol_body, key, int(ts)))
                await conn.commit()

    async def scan(self, token, amount_hint):
        if token is None:
            token = 1

        async with self._pool.borrow(self._timeout) as conn:
            async with conn.execute('select rowid, ts, pol_id, pol_body, domain from '
                                    'sts_policy_cache where rowid between ? and ?',
                                    (token, token + amount_hint - 1)) as cur:
                res = await cur.fetchall()
        if res:
            result = []
            new_token = token
            for row in res:
                rowid, ts, pol_id, pol_body, domain = row
                ts = int(ts)
                rowid = int(rowid)
                new_token = max(new_token, rowid)
                pol_body = json.loads(pol_body)
                result.append((domain, CacheEntry(ts, pol_id, pol_body)))
            new_token += 1
            return new_token, result
        else:
            return None, []

    async def teardown(self):
        await self._pool.stop()
