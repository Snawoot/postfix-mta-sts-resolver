import asyncio
import pynetstring
import logging
import time
import collections
import weakref

from postfix_mta_sts_resolver.resolver import *


ZoneEntry = collections.namedtuple('ZoneEntry', ('strict', 'resolver'))


CacheEntry = collections.namedtuple('CacheEntry', ('ts', 'pol_id', 'pol_body'))


class STSSocketmapResponder(object):
    def __init__(self, cfg, loop):
        self._logger = logging.getLogger("STS")
        self._loop = loop
        self._host = cfg['host']
        self._port = cfg['port']

        # Construct configurations and resolvers for every socketmap name
        self._default_zone = ZoneEntry(cfg["default_zone"]["strict_testing"],
                                       STSResolver(loop=loop,
                                                   timeout=cfg["default_zone"]["timeout"]))

        self._zones = dict((k, ZoneEntry(zone["strict_testing"],
                                         STSResolver(loop=loop,
                                                     timeout=zone["timeout"])))
                           for k, zone in cfg["zones"].items())

        # Construct cache
        if cfg["cache"]["type"] == "internal":
            import postfix_mta_sts_resolver.internal_cache
            capacity = cfg["cache"]["options"]["cache_size"]
            self._cache = postfix_mta_sts_resolver.internal_cache.InternalLRUCache(capacity)
        else:
            raise NotImplementedError("Unsupported cache type!")
        self._children = weakref.WeakSet()

    async def start(self):
        def _spawn(reader, writer):
            self._children.add(
                self._loop.create_task(self.handler(reader, writer)))

        self._server = await asyncio.start_server(_spawn,
                                                  self._host,
                                                  self._port)

    async def stop(self):
        self._server.close()
        await self._server.wait_closed()
        if self._children:
            self._logger.debug("Cancelling %d client handlers...",
                               len(self._children))
            for task in self._children:
                task.cancel()
            await asyncio.wait(self._children)

    async def sender(self, queue, writer):
        try:
            while True:
                fut = await queue.get()

                # Check for shutdown
                if fut is None:
                    writer.close()
                    return

                self._logger.debug("Got new future from queue")
                try:
                    data = await fut
                except asyncio.CancelledError:
                    writer.close()
                    return
                except Exception as e:
                    self._logger.exception("Unhandled exception from future: %s", e)
                    writer.close()
                    return
                self._logger.debug("Future await complete: data=%s", repr(data))
                writer.write(data)
                self._logger.debug("Wrote: %s", repr(data))
                await writer.drain()
        except asyncio.CancelledError:
            try:
                fut.cancel()
            except:
                pass
            while not queue.empty():
                task = queue.get_nowait()
                task.cancel()

    async def process_request(self, raw_req):
        have_policy = True

        # Parse request and canonicalize domain
        req_zone, _, req_domain = raw_req.decode('latin-1').partition(' ')

        domain = req_domain

        # Skip lookups for parent domain policies
        # Skip lookups to non-recepient domains or non-domains at all
        if domain.startswith('.') or domain.startswith('[') or ':' in domain:
            return pynetstring.encode('NOTFOUND ')

        # Normalize domain name
        domain = req_domain.lower().strip().rstrip('.')

        # Find appropriate zone config
        if req_zone in self._zones:
            zone_cfg = self._zones[req_zone]
        else:
            zone_cfg = self._default_zone

        # Lookup for cached policy
        cached = await self._cache.get(domain)

        # Check if newer policy exists or 
        # retrieve policy from scratch if there is no cached one
        if cached is None:
            latest_pol_id  = None
        else:
            latest_pol_id = cached.pol_id
        status, policy = await zone_cfg.resolver.resolve(domain, latest_pol_id)

        # Update local cache
        ts = time.time()
        if status is STSFetchResult.NOT_CHANGED:
            cached = CacheEntry(ts, cached.pol_id, cached.pol_body)
            await self._cache.set(domain, cached)
        elif status is STSFetchResult.VALID:
            pol_id, pol_body = policy
            cached = CacheEntry(ts, pol_id, pol_body)
            await self._cache.set(domain, cached)
        else:
            if cached is None:
                have_policy = False
            else:
                # Check if cached policy is expired
                if cached.pol_body['max_age'] + cached.ts < ts:
                    have_policy = False


        if have_policy:
            mode = cached.pol_body['mode']
            if mode == 'none' or (mode == 'testing' and not zone_cfg.strict):
                return pynetstring.encode('NOTFOUND ')
            else:
                assert cached.pol_body['mx'], "Empty MX list for restrictive policy!"
                mxlist = [mx.lstrip('*') for mx in set(cached.pol_body['mx'])]
                resp = "OK secure match=" + ":".join(mxlist)
                return pynetstring.encode(resp)
        else:
            return pynetstring.encode('NOTFOUND ')


    def enqueue_request(self, queue, raw_req):
        fut = asyncio.ensure_future(self.process_request(raw_req), loop=self._loop)
        queue.put_nowait(fut)

    async def handler(self, reader, writer):
        # Construct netstring parser
        self._decoder = pynetstring.Decoder()

        # Construct queue for responses ordering
        queue = asyncio.Queue(0, loop=self._loop)

        # Create coroutine which awaits for steady responses and sends them
        sender = asyncio.ensure_future(self.sender(queue, writer), loop=self._loop)

        def cleanup():
            sender.cancel()
            writer.close()

        while True:
            try:
                part = await reader.read(4096)
                self._logger.debug("Read: %s", repr(part))
            except asyncio.CancelledError as e:
                cleanup()
                return
            except ConnectionError as e:
                cleanup()
                return
            if not part:
                cleanup()
                return

            try:
                requests = self._decoder.feed(part)
            except:
                # Bad protocol. Do shutdown
                queue.put_nowait(None)
                await sender
            else:
                for req in requests:
                    self._logger.debug("Enq request: %s", repr(req))
                    self.enqueue_request(queue, req)
