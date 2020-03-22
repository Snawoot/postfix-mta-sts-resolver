import asyncio
import logging
import time

from postfix_mta_sts_resolver import constants
from postfix_mta_sts_resolver.base_cache import CacheEntry
from postfix_mta_sts_resolver.resolver import STSResolver, STSFetchResult


# pylint: disable=too-many-instance-attributes
class STSProactiveFetcher:
    def __init__(self, cfg, loop, cache):
        self._shutdown_timeout = cfg['shutdown_timeout']
        self._pf_interval = cfg['proactive_policy_fetching']['interval']
        self._pf_concurrency_limit = cfg['proactive_policy_fetching']['concurrency_limit']
        self._pf_grace_ratio = cfg['proactive_policy_fetching']['grace_ratio']
        self._logger = logging.getLogger("PF")
        self._loop = loop
        self._cache = cache
        self._periodic_fetch_task = None
        self._resolver = STSResolver(loop=loop,
                                     timeout=cfg["default_zone"]["timeout"])

    async def process_domain(self, domain_queue):
        async def update(cached):
            status, policy = await self._resolver.resolve(domain, cached.pol_id)
            if status is STSFetchResult.VALID:
                pol_id, pol_body = policy
                updated = CacheEntry(ts, pol_id, pol_body)
                await self._cache.safe_set(domain, updated, self._logger)
            elif status is STSFetchResult.NOT_CHANGED:
                updated = CacheEntry(ts, cached.pol_id, cached.pol_body)
                await self._cache.safe_set(domain, updated, self._logger)
            else:
                self._logger.warning("Domain %s does not have a valid policy.", domain)

        while True:  # Run until cancelled
            cache_item = await domain_queue.get()
            ts = time.time()  # pylint: disable=invalid-name
            try:
                domain, cached = cache_item
                if ts - cached.ts < self._pf_interval / self._pf_grace_ratio:
                    self._logger.debug("Domain %s skipped (cache recent enough).", domain)
                else:
                    await update(cached)
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
        for _ in range(self._pf_concurrency_limit):
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
        while True:  # Run until cancelled
            next_fetch_ts = await self._cache.get_proactive_fetch_ts() + self._pf_interval
            sleep_duration = max(constants.MIN_PROACTIVE_FETCH_INTERVAL,
                                 next_fetch_ts - time.time() + 1)

            self._logger.debug("Sleeping for %ds until next fetch.", sleep_duration)
            await asyncio.sleep(sleep_duration)
            await self.iterate_domains()

    async def start(self):
        self._periodic_fetch_task = self._loop.create_task(self.fetch_periodically())

    async def stop(self):
        self._periodic_fetch_task.cancel()

        try:
            self._logger.warning("Awaiting periodic fetching to finish...")
            await self._periodic_fetch_task
        except asyncio.CancelledError:  # pragma: no cover
            pass
