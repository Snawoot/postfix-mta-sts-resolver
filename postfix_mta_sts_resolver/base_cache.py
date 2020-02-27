import asyncio
import collections

from abc import ABC, abstractmethod


CacheEntry = collections.namedtuple('CacheEntry', ('ts', 'pol_id', 'pol_body'))


class BaseCache(ABC):
    @abstractmethod
    async def setup(self):
        """ Abstract method """

    @abstractmethod
    async def get(self, key):
        """ Abstract method """

    @abstractmethod
    async def set(self, key, value):
        """ Abstract method """

    async def safe_set(self, domain, entry, logger):
        try:
            await self.set(domain, entry)
        except asyncio.CancelledError:  # pragma: no cover pylint: disable=try-except-raise
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception("Cache set failed: %s", str(exc))

    @abstractmethod
    async def scan(self, token, amount_hint):
        """ Abstract method """

    @abstractmethod
    async def get_proactive_fetch_ts(self):
        """ Abstract method """

    @abstractmethod
    async def set_proactive_fetch_ts(self, timestamp):
        """ Abstract method """

    @abstractmethod
    async def teardown(self):
        """ Abstract method """
