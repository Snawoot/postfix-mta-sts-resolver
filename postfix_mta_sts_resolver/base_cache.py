from abc import ABC, abstractmethod

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
