import collections
from itertools import islice

from .base_cache import BaseCache


class InternalLRUCache(BaseCache):
    def __init__(self, cache_size=10000):
        self._cache_size = cache_size
        self._cache = collections.OrderedDict()
        self._proactive_fetch_ts = 0

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

    async def scan(self, token, amount_hint):
        if token is None:
            token = 0

        total = len(self._cache)
        left = total - token
        if left > 0:
            amount = min(left, amount_hint)
            new_token = token + amount if token + amount < total else None
            # Take "amount" of oldest
            result = list(islice(self._cache.items(), amount))
            for key, _ in result:  # for LRU consistency
                await self.get(key)
            return new_token, result
        return None, []

    async def get_proactive_fetch_ts(self):
        return self._proactive_fetch_ts

    async def set_proactive_fetch_ts(self, timestamp):
        self._proactive_fetch_ts = timestamp
