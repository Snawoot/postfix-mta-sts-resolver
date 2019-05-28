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

    @abstractmethod
    async def teardown(self):
        """ Abstract method """
