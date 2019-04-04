import asyncio
import aiosqlite
import sqlite3
import json
import logging

from .utils import _anext
from .defaults import SQLITE_THREADS, SQLITE_TIMEOUT
from .base_cache import BaseCache, CacheEntry


class SqliteConnPool:
    def __init__(self, threads, conn_args=(), conn_kwargs={}, init_queries=()):
        self._threads = threads
        self._conn_args = conn_args
        self._conn_kwargs = conn_kwargs
        self._init_queries = init_queries
        self._free_conns = asyncio.Queue()
        self._ready = False
        self._stopped = False

    async def _new_conn(self):
        async def gen():
            async with aiosqlite.connect(*self._conn_args, **self._conn_kwargs) as c:
                for q in self._init_queries:
                    await c.execute(q)
                yield c
        it = gen()
        return it, await _anext(it)

    async def prepare(self):
        for _ in range(self._threads):
            self._free_conns.put_nowait(await self._new_conn())
        self._ready = True

    async def stop(self):
        self._ready = False
        self._stopped = True
        try:
            while True:
                g, db = self._free_conns.get_nowait()
                await _anext(g, None)
        except asyncio.QueueEmpty:
            pass

    def borrow(self, timeout=None):
        #assert self._ready
        class PoolBorrow:
            async def __aenter__(s):
                s._conn = await asyncio.wait_for(self._free_conns.get(),
                                                 timeout)
                return s._conn[1]

            async def __aexit__(s, exc_type, exc, tb):
                if self._stopped:
                    await _anext(s._conn[0], None)
                    return
                if exc_type is not None:
                    await _anext(s._conn[0], None)
                    s._conn = self._new_conn()
                self._free_conns.put_nowait(s._conn)
        return PoolBorrow()


class SqliteCache(BaseCache):
    def __init__(self, filename, *,
                 threads=SQLITE_THREADS, timeout=SQLITE_TIMEOUT):
        self._filename = filename
        self._threads = threads
        self._timeout = timeout
        sqlitelogger = logging.getLogger("aiosqlite")
        if not sqlitelogger.hasHandlers():
            sqlitelogger.addHandler(logging.NullHandler())

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
            "create table if not exists sts_policy_cache (domain text, ts integer, pol_id text, pol_body text)",
            "create unique index if not exists sts_policy_domain on sts_policy_cache (domain)",
            "create index if not exists sts_policy_domain_ts on sts_policy_cache (domain, ts)",
        ]
        async with self._pool.borrow(self._timeout) as db:
            for q in queries:
                await db.execute(q)
            await db.commit()

    async def get(self, key):
        async with self._pool.borrow(self._timeout) as db:
            async with db.execute('select ts, pol_id, pol_body from '
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
        async with self._pool.borrow(self._timeout) as db:
            try:
                await db.execute('insert into sts_policy_cache (domain, ts, '
                                 'pol_id, pol_body) values (?, ?, ?, ?)',
                                 (key, int(ts), pol_id, pol_body))
                await db.commit()
            except sqlite3.IntegrityError:
                await db.execute('update sts_policy_cache set ts = ?, '
                                 'pol_id = ?, pol_body = ? where domain = ? '
                                 'and ts < ?',
                                 (int(ts), pol_id, pol_body, key, int(ts)))
                await db.commit()

    async def teardown(self):
        await self._pool.stop()
