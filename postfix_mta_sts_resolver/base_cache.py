import collections

from abc import ABC, abstractmethod


CacheEntry = collections.namedtuple('CacheEntry', ('ts', 'pol_id', 'pol_body'))


class BaseCache(ABC):
    @abstractmethod
    async def setup(self):
        pass

    @abstractmethod
    async def get(self, key):
        pass

    @abstractmethod
    async def set(self, key, value):
        pass

    @abstractmethod
    async def teardown(self):
        pass
