import collections

from .base_cache import BaseCache


class InternalLRUCache(BaseCache):
    def __init__(self, cache_size=10000):
        self._cache_size = cache_size
        self._cache = collections.OrderedDict()

    async def setup(self):
        pass

    async def teardown(self):
        pass

    async def get(self, key):
        try:
            value = self._cache.pop(key)
            self._cache[key] = value
            return value
        except KeyError:
            return None

    async def set(self, key, value):
        try:
            self._cache.pop(key)
        except KeyError:
            if len(self._cache) >= self._cache_size:
                self._cache.popitem(last=False)
        self._cache[key] = value
