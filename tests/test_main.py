import sys

import pytest

import postfix_mta_sts_resolver.__main__ as main

class MockCmdline:
    def __init__(self, *args):
        self._cmdline = args

    def __enter__(self):
        self._old_cmdline = sys.argv
        sys.argv = list(self._cmdline)

    def __exit__(self, exc_type, exc_value, traceback):
        sys.argv = self._old_cmdline

def test_parse_args():
    with MockCmdline("mta-sts-query", "example.com"):
        args = main.parse_args()
    assert args.domain == 'example.com'
    assert args.known_version is None

def test_parse_args_with_version():
    with MockCmdline("mta-sts-query", "example.com", "123"):
        args = main.parse_args()
    assert args.domain == 'example.com'
    assert args.known_version == "123"
