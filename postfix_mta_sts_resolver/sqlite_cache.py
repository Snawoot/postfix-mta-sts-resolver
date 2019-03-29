import aiosqlite
import sqlite3
import json
import logging

from .base_cache import BaseCache, CacheEntry


class SqliteCache(BaseCache):
    def __init__(self, filename):
        self._filename = filename
        sqlitelogger = logging.getLogger("aiosqlite")
        if not sqlitelogger.hasHandlers():
            sqlitelogger.addHandler(logging.NullHandler())

    async def setup(self):
        queries = [
        "create table if not exists sts_policy_cache (domain text, ts integer, pol_id text, pol_body text)",
        "create unique index if not exists sts_policy_domain on sts_policy_cache (domain)",
        ]
        async with aiosqlite.connect(self._filename) as db:
            for q in queries:
                await db.execute(q)
            await db.commit()

    async def get(self, key):
        async with aiosqlite.connect(self._filename) as db:
            async with db.execute('select ts, pol_id, pol_body from '
                                  'sts_policy_cache where domain=?',
                                  (key,)) as cur:
                res = await cur.fetchone()
        if res is not None:
            ts, pol_id, pol_body = res
            pol_id = int(pol_id)
            pol_body = json.loads(pol_body)
            return CacheEntry(ts, pol_id, pol_body)
        else:
            return None

    async def set(self, key, value):
        ts, pol_id, pol_body = value
        pol_body = json.dumps(pol_body)
        async with aiosqlite.connect(self._filename) as db:
            try:
                await db.execute('insert into sts_policy_cache (domain, ts, '
                                 'pol_id, pol_body) values (?, ?, ?, ?)',
                                 (key, int(ts), pol_id, pol_body))
                await db.commit()
            except sqlite3.IntegrityError:
                await db.execute('update sts_policy_cache set ts = ?, '
                                 'pol_id = ?, pol_body = ? where domain = ?',
                                 (int(ts), pol_id, pol_body, key))
                await db.commit()
