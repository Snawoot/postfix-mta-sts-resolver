#!/usr/bin/env python3

import sys
import argparse
import asyncio

from . import utils
from .resolver import STSResolver

def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-v", "--verbosity",
                        help="logging verbosity",
                        type=utils.LogLevel.__getitem__,
                        choices=list(utils.LogLevel),
                        default=utils.LogLevel.warn)
    parser.add_argument("domain",
                        help="domain to fetch MTA-STS policy from")
    parser.add_argument("known_version",
                        nargs="?",
                        default=None,
                        help="latest known version")

    return parser.parse_args()


def main():
    args = parse_args()
    mainLogger = utils.setup_logger('MAIN', args.verbosity)

    loop = asyncio.get_event_loop()
    R = STSResolver(loop=loop)
    result = loop.run_until_complete(R.resolve(args.domain, args.known_version))
    print(result)


if __name__ == '__main__':
    main()
