#!/usr/bin/env python3

import os
import argparse
import asyncio
import logging
import signal
from functools import partial

from .asdnotify import AsyncSystemdNotifier
from . import utils
from . import defaults
from .proactive_fetcher import STSProactiveFetcher
from .responder import STSSocketmapResponder
from .utils import create_cache


def parse_args():
    def check_loglevel(arg):
        try:
            return utils.LogLevel[arg]
        except (IndexError, KeyError):
            raise argparse.ArgumentTypeError("%s is not valid loglevel" % (repr(arg),))

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-v", "--verbosity",
                        help="logging verbosity",
                        type=check_loglevel,
                        choices=utils.LogLevel,
                        default=utils.LogLevel.info)
    parser.add_argument("-c", "--config",
                        help="config file location",
                        metavar="FILE",
                        default=defaults.CONFIG_LOCATION)
    parser.add_argument("-l", "--logfile",
                        help="log file location",
                        metavar="FILE")
    parser.add_argument("--disable-uvloop",
                        help="do not use uvloop even if it is available",
                        action="store_true")

    return parser.parse_args()


def exit_handler(exit_event, signum, frame):  # pragma: no cover pylint: disable=unused-argument
    logger = logging.getLogger('MAIN')
    if exit_event.is_set():
        logger.warning("Got second exit signal! Terminating hard.")
        os._exit(1)  # pylint: disable=protected-access
    else:
        logger.warning("Got first exit signal! Terminating gracefully.")
        exit_event.set()


async def heartbeat():
    """ Hacky coroutine which keeps event loop spinning with some interval
    even if no events are coming. This is required to handle Futures and
    Events state change when no events are occuring."""
    while True:
        await asyncio.sleep(.5)


async def amain(cfg, loop):  # pragma: no cover
    logger = logging.getLogger("MAIN")

    proactive_fetch_enabled = cfg['proactive_policy_fetching']['enabled']

    # Create policy cache
    cache = create_cache(cfg["cache"]["type"],
                         cfg["cache"]["options"])
    await cache.setup()

    # Construct request handler
    responder = STSSocketmapResponder(cfg, loop, cache)
    await responder.start()
    logger.info("Server started.")

    # Conditionally construct proactive policy fetcher
    proactive_fetcher = None
    if proactive_fetch_enabled:
        proactive_fetcher = STSProactiveFetcher(cfg, loop, cache)
        await proactive_fetcher.start()
        logger.info("Proactive policy fetcher started.")
    else:
        logger.info("Proactive policy fetching is disabled.")

    exit_event = asyncio.Event()
    beat = asyncio.ensure_future(heartbeat())
    sig_handler = partial(exit_handler, exit_event)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    async with AsyncSystemdNotifier() as notifier:
        await notifier.notify(b"READY=1")
        await exit_event.wait()
        logger.debug("Eventloop interrupted. Shutting down server...")
        await notifier.notify(b"STOPPING=1")
    beat.cancel()
    await responder.stop()
    if proactive_fetch_enabled:
        await proactive_fetcher.stop()
    await cache.teardown()


def main():  # pragma: no cover
    # Parse command line arguments and setup basic logging
    args = parse_args()
    with utils.AsyncLoggingHandler(args.logfile) as log_handler:
        logger = utils.setup_logger('MAIN', args.verbosity, log_handler)
        utils.setup_logger('STS', args.verbosity, log_handler)
        utils.setup_logger('PF', args.verbosity, log_handler)
        logger.info("MTA-STS daemon starting...")

        # Read config and populate with defaults
        cfg = utils.load_config(args.config)

        # Construct event loop
        logger.info("Starting eventloop...")
        if not args.disable_uvloop:
            if utils.enable_uvloop():
                logger.info("uvloop enabled.")
            else:
                logger.info("uvloop is not available. "
                            "Falling back to built-in event loop.")
        evloop = asyncio.get_event_loop()
        logger.info("Eventloop started.")


        evloop.run_until_complete(amain(cfg, evloop))
        evloop.close()
        logger.info("Server finished its work.")
