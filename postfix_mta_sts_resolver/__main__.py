#!/usr/bin/env python3

import argparse
import asyncio

from .resolver import STSResolver

def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("domain",
                        help="domain to fetch MTA-STS policy from")
    parser.add_argument("known_version",
                        nargs="?",
                        default=None,
                        help="latest known version")

    return parser.parse_args()


def main():  # pragma: no cover
    args = parse_args()

    loop = asyncio.get_event_loop()
    resolver = STSResolver(loop=loop)
    result = loop.run_until_complete(resolver.resolve(args.domain, args.known_version))
    print(result)


if __name__ == '__main__':  # pragma: no cover
    main()
