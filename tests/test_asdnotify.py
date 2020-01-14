import contextlib
import socket
import asyncio
import os
import sys

import pytest

from postfix_mta_sts_resolver.asdnotify import AsyncSystemdNotifier

@contextlib.contextmanager
def set_env(**environ):
    old_environ = dict(os.environ)
    os.environ.update(environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)

class UnixDatagramReceiver:
    def __init__(self, loop):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._sock.setblocking(0)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind('')
        self._name = self._sock.getsockname()
        self._incoming = asyncio.Queue()
        self._loop = loop
        loop.add_reader(self._sock.fileno(), self._read_handler)

    def _read_handler(self):
        try:
            while True:
                msg = self._sock.recv(4096)
                self._incoming.put_nowait(msg)
        except BlockingIOError:  # pragma: no cover
            pass

    async def recvmsg(self):
        return await self._incoming.get()

    @property
    def name(self):
        return self._name

    @property
    def asciiname(self):
        sockname = self.name
        if isinstance(sockname, bytes):
            sockname = sockname.decode('ascii')
        if sockname.startswith('\x00'):
            sockname = '@' + sockname[1:]
        return sockname

    def close(self):
        self._loop.remove_reader(self._sock.fileno())
        self._sock.close()
        self._sock = None

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")

@pytest.fixture(scope="module")
def unix_dgram_receiver(event_loop):
    udr = UnixDatagramReceiver(event_loop)
    yield udr
    udr.close()

@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_message_sent(unix_dgram_receiver):
    sockname = unix_dgram_receiver.asciiname
    msg = b"READY=1"
    with set_env(NOTIFY_SOCKET=sockname):
        async with AsyncSystemdNotifier() as notifier:
            await notifier.notify(msg)
            assert await unix_dgram_receiver.recvmsg() == msg

@pytest.mark.timeout(5)
@pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")
@pytest.mark.asyncio
async def test_message_flow(unix_dgram_receiver):
    sockname = unix_dgram_receiver.asciiname
    msgs = [b"READY=1", b'STOPPING=1'] * 500
    with set_env(NOTIFY_SOCKET=sockname):
        async with AsyncSystemdNotifier() as notifier:
            for msg in msgs:
                await notifier.notify(msg)
                assert await unix_dgram_receiver.recvmsg() == msg

@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_not_started():
    async with AsyncSystemdNotifier() as notifier:
        assert not notifier.started

@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_started(unix_dgram_receiver):
    with set_env(NOTIFY_SOCKET=unix_dgram_receiver.asciiname):
        async with AsyncSystemdNotifier() as notifier:
            assert notifier.started

@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_send_never_fails():
    with set_env(NOTIFY_SOCKET='abc'):
        async with AsyncSystemdNotifier() as notifier:
            await notifier.notify(b'!!!')


@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_socket_create_failure(monkeypatch):
    class mocksock:
        def __init__(self, *args, **kwargs):
            raise OSError()
    monkeypatch.setattr(socket, "socket", mocksock)
    with set_env(NOTIFY_SOCKET='abc'):
        async with AsyncSystemdNotifier() as notifier:
            await notifier.notify(b'!!!')
