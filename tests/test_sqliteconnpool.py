import asyncio
import tempfile

import pytest

from postfix_mta_sts_resolver.sqlite_cache import SqliteConnPool

CONN_INIT = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
]

@pytest.fixture
def dbfile():
    with tempfile.NamedTemporaryFile() as f:
        yield f.name

@pytest.mark.asyncio
async def test_raises_re(dbfile):
    pool = SqliteConnPool(1, (dbfile,), init_queries=CONN_INIT)
    with pytest.raises(RuntimeError):
        async with pool.borrow() as conn:
            pass

@pytest.mark.asyncio
@pytest.mark.timeout(2)
async def test_basic(dbfile):
    pool = SqliteConnPool(1, (dbfile,), init_queries=CONN_INIT)
    await pool.prepare()
    try:
        async with pool.borrow() as conn:
            await conn.execute("create table if not exists t (id int)")
        async with pool.borrow() as conn:
            for i in range(10):
                await conn.execute("insert into t (id) values (?)", (i,))
            await conn.commit()
        async with pool.borrow() as conn:
            async with conn.execute('select sum(id) from t') as cur:
                res = await cur.fetchone()
        assert res[0] == sum(range(10))
    finally:
        await pool.stop()

@pytest.mark.asyncio
@pytest.mark.timeout(2)
async def test_early_stop(dbfile):
    pool = SqliteConnPool(5, (dbfile,), init_queries=CONN_INIT)
    await pool.prepare()
    async with pool.borrow() as conn:
        await pool.stop()
        await conn.execute("create table if not exists t (id int)")
        for i in range(10):
            await conn.execute("insert into t (id) values (?)", (i,))
        await conn.commit()
        async with conn.execute('select sum(id) from t') as cur:
            res = await cur.fetchone()
    assert res[0] == sum(range(10))

@pytest.mark.asyncio
@pytest.mark.timeout(2)
async def test_borrow_timeout(dbfile):
    pool = SqliteConnPool(1, (dbfile,), init_queries=CONN_INIT)
    await pool.prepare()
    try:
        async with pool.borrow(1) as conn1:
            with pytest.raises(asyncio.TimeoutError):
                async with pool.borrow(1) as conn2:
                    pass
    finally:
        await pool.stop()
