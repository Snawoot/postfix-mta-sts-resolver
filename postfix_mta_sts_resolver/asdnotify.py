import os
import socket

class AsyncSystemdNotifier:
    """ Boilerplate for proper implementation. This one, however,
    also will work. """

    def __init__(self):
        env_var = os.getenv('NOTIFY_SOCKET')
        self._addr = ('\0' + env_var[1:]
                      if env_var is not None and env_var.startswith('@')
                      else env_var)
        self._sock = None
        self._started = False

    async def start(self):
        if self._addr is None:
            return False
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self._sock.setblocking(0)
            self._started = True
        except socket.error:
            return False
        return True

    async def notify(self, status):
        if self._started:
            try:
                self._sock.sendto(status, socket.MSG_NOSIGNAL, self._addr)
            except socket.error:
                pass

    async def stop(self):
        if self._started:
            self._sock.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.stop()
