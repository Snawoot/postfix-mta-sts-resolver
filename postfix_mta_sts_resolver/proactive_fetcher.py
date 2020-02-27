import asyncio
import logging
import time

from postfix_mta_sts_resolver import constants
from postfix_mta_sts_resolver.base_cache import CacheEntry
from postfix_mta_sts_resolver.resolver import STSResolver, STSFetchResult


class STSProactiveFetcher:
    def __init__(self, cfg, loop, cache):
        self._shutdown_timeout = cfg['shutdown_timeout']
        self._proactive_fetch_interval = cfg['cache']['proactive_fetch_interval']
        self._logger = logging.getLogger("PF")
        self._loop = loop
        self._cache = cache
        self._periodic_fetch_task = None
        self._resolver = STSResolver(loop=loop,
                                     timeout=cfg["default_zone"]["timeout"])

    async def process_domain(self, domain_queue):
        while True:  # Run until cancelled
            cache_item = await domain_queue.get()
            try:
                domain, cached = cache_item
                status, policy = await self._resolver.resolve(domain)
                if status is STSFetchResult.VALID:
                    pol_id, pol_body = policy
                    cached = CacheEntry(time.time(), pol_id, pol_body)
                    await self._cache.safe_set(domain, cached, self._logger)
                elif status is STSFetchResult.NOT_CHANGED:
                    pass
                else:
                    self._logger.warning("Domain %s has an invalid policy.", domain)
            except asyncio.CancelledError:  # pragma: no cover pylint: disable=try-except-raise
                raise
            except Exception as exc:  # pragma: no cover
                self._logger.exception("Unhandled exception: %s", exc)
            finally:
                domain_queue.task_done()

    async def iterate_domains(self):
        self._logger.info("Proactive policy fetching "
                          "for all domains in cache started...")

        # Create domain processor tasks
        domain_processors = []
        domain_queue = asyncio.Queue(maxsize=constants.DOMAIN_QUEUE_LIMIT)
        for _ in range(constants.DOMAIN_REQUEST_LIMIT):
            domain_processor = self._loop.create_task(self.process_domain(domain_queue))
            domain_processors.append(domain_processor)

        # Produce work for domain processors
        try:
            token = None
            while True:
                token, cache_items = await self._cache.scan(token, constants.DOMAIN_QUEUE_LIMIT)
                self._logger.debug("Enqueued %d domains for processing.", len(cache_items))
                for cache_item in cache_items:
                    await domain_queue.put(cache_item)
                if token is None:
                    break

            # Wait for queue to clear
            await domain_queue.join()
        # Clean up the domain processors
        finally:
            for domain_processor in domain_processors:
                domain_processor.cancel()
            await asyncio.gather(*domain_processors, return_exceptions=True)

        # Update the proactive fetch timestamp
        await self._cache.set_proactive_fetch_ts(time.time())

        self._logger.info("Proactive policy fetching "
                          "for all domains in cache finished.")

    async def fetch_periodically(self):
        async def fetch():
            domain_iteration_future = self._loop.create_task(self.iterate_domains())

            try:
                await asyncio.shield(domain_iteration_future)
            except asyncio.CancelledError:  # pragma: no cover
                try:
                    await asyncio.wait_for(domain_iteration_future, self._shutdown_timeout)
                except asyncio.TimeoutError:  # pragma: no cover
                    self._logger.warning("Shutdown timeout expired. "
                                         "Shutting down forcefully.")
                    await domain_iteration_future
                raise
            except Exception as exc:  # pragma: no cover
                self._logger.exception("Unhandled exception: %s", exc)

        while True:  # Run until cancelled
            next_fetch_ts = await self._cache.get_proactive_fetch_ts() + \
                            self._proactive_fetch_interval
            sleep_duration = max(constants.MIN_PROACTIVE_FETCH_INTERVAL,
                                 next_fetch_ts - time.time() + 1)

            self._logger.debug("Sleeping for %ds until next fetch.", sleep_duration)
            await asyncio.sleep(sleep_duration)
            await fetch()

    async def start(self):
        self._periodic_fetch_task = self._loop.create_task(self.fetch_periodically())

    async def stop(self):
        self._periodic_fetch_task.cancel()

        try:
            self._logger.warning("Awaiting periodic fetching to finish...")
            await self._periodic_fetch_task
        except asyncio.CancelledError:  # pragma: no cover
            pass
