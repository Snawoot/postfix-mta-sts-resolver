import sys
import asyncio

import pytest

import postfix_mta_sts_resolver.daemon as daemon
import postfix_mta_sts_resolver.utils as utils

class MockCmdline:
    def __init__(self, *args):
        self._cmdline = args

    def __enter__(self):
        self._old_cmdline = sys.argv
        sys.argv = list(self._cmdline)

    def __exit__(self, exc_type, exc_value, traceback):
        sys.argv = self._old_cmdline

@pytest.mark.asyncio
async def test_heartbeat():
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(daemon.heartbeat(), 5)

def test_parse_args():
    argv = sys.argv
    with MockCmdline("mta-sts-daemon", "-c", "/dev/null"):
        args = daemon.parse_args()
    assert args.config == '/dev/null'
    assert not args.disable_uvloop
    assert args.verbosity == utils.LogLevel.info
    assert args.logfile is None
    assert sys.argv == argv
