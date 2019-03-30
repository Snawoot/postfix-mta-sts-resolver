#!/usr/bin/env python3

import sys
import os
import argparse
import asyncio
import logging
import signal
from functools import partial

from sdnotify import SystemdNotifier
from . import utils
from . import defaults
from .responder import STSSocketmapResponder


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-v", "--verbosity",
                        help="logging verbosity",
                        type=utils.LogLevel.__getitem__,
                        choices=list(utils.LogLevel),
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


def exit_handler(exit_event, signum, frame):
    logger = logging.getLogger('MAIN')
    if exit_event.is_set():
        logger.warning("Got second exit signal! Terminating hard.")
        os._exit(1)
    else:
        logger.warning("Got first exit signal! Terminating gracefully.")
        exit_event.set()


async def heartbeat():
    """ Hacky coroutine which keeps event loop spinning with some interval 
    even if no events are coming. This is required to handle Futures and 
    Events state change when no events are occuring."""
    while True:
        await asyncio.sleep(.5)


async def amain(cfg, loop):
    logger = logging.getLogger("MAIN")
    # Construct request handler instance
    responder = STSSocketmapResponder(cfg, loop)

    await responder.start()
    logger.info("Server started.")

    exit_event = asyncio.Event()
    beat = asyncio.ensure_future(heartbeat())
    sig_handler = partial(exit_handler, exit_event)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    notifier = await loop.run_in_executor(None, SystemdNotifier)
    await loop.run_in_executor(None, notifier.notify, "READY=1")
    await exit_event.wait()
    logger.debug("Eventloop interrupted. Shutting down server...")
    await loop.run_in_executor(None, notifier.notify, "STOPPING=1")
    beat.cancel()
    await responder.stop()


def main():
    # Parse command line arguments and setup basic logging
    args = parse_args()
    mainLogger = utils.setup_logger('MAIN', args.verbosity, args.logfile )
    utils.setup_logger('STS', args.verbosity, args.logfile)
    mainLogger.info("MTA-STS daemon starting...")

    # Read config and populate with defaults
    cfg = utils.load_config(args.config)

    # Construct event loop
    mainLogger.info("Starting eventloop...")
    if not args.disable_uvloop:
        if utils.enable_uvloop():
            mainLogger.info("uvloop enabled.")
        else:
            mainLogger.info("uvloop is not available. "
                            "Falling back to built-in event loop.")
    evloop = asyncio.get_event_loop()
    mainLogger.info("Eventloop started.")


    evloop.run_until_complete(amain(cfg, evloop))
    evloop.close()
    mainLogger.info("Server finished its work.")
