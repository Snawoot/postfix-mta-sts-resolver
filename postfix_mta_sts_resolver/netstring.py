import ssl

COLON = b':'
COMMA = b','
ZERO = b'0'
ZERO_ORD = ord(ZERO)

class NetstringException(Exception):
    pass


class WantRead(NetstringException):
    pass


class InappropriateParserState(NetstringException):
    pass


class ParseError(NetstringException):
    pass


class IncompleteNetstring(ParseError):
    pass


class TooLong(ParseError):
    pass


class BadLength(ParseError):
    pass


class BadTerminator(ParseError):
    pass


class SingleNetstringFetcher:
    def __init__(self, incoming, maxlen=-1):
        self._incoming = incoming
        self._maxlen = maxlen
        self._len_known = False
        self._len = None
        self._done = False
        self._length_bytes = b''

    def done(self):
        return self._done

    def pending(self):
        return self._len is not None

    def read(self, nbytes=65536):
        # pylint: disable=too-many-branches
        if not self._len_known:
            # reading length
            while True:
                symbol = self._incoming.read(1)
                if not symbol:
                    raise WantRead()
                if symbol == COLON:
                    if self._len is None:
                        raise BadLength("No netstring length digits seen.")
                    self._len_known = True
                    break
                if not symbol.isdigit():
                    raise BadLength("Non-digit symbol in netstring length.")
                val = ord(symbol) - ZERO_ORD
                self._len = val if self._len is None else self._len * 10 + val
                if self._maxlen != -1 and self._len > self._maxlen:
                    raise TooLong("Netstring length is over limit.")
        # reading data
        if self._len:
            buf = self._incoming.read(min(nbytes, self._len))
            if not buf:
                raise WantRead()
            self._len -= len(buf)
            return buf
        else:
            if not self._done:
                symbol = self._incoming.read(1)
                if not symbol:
                    raise WantRead()
                if symbol == COMMA:
                    self._done = True
                else:
                    raise BadTerminator("Bad netstring terminator.")
            return b''


class StreamReader:
    """ Async Netstring protocol decoder with interface
    alike to ssl.SSLObject BIO interface.

    next_string() method returns SingleNetstringFetcher class which
    fetches parts of netstring.

    SingleNestringFetcher.read() returns b'' in case of string end or raises
    WantRead exception when StreamReader needs to be filled with additional
    data. Parsing errors signalized with exceptions subclassing ParseError"""

    def __init__(self, maxlen=-1):
        """ Creates StreamReader instance.

        Params:

        maxlen - maximal allowed netstring length.
        """
        self._maxlen = maxlen
        self._incoming = ssl.MemoryBIO()
        self._fetcher = None

    def pending(self):
        return self._fetcher is not None and self._fetcher.pending()

    def feed(self, data):
        self._incoming.write(data)

    def next_string(self):
        if self._fetcher is not None and not self._fetcher.done():
            raise InappropriateParserState("next_string() invoked while "
                                           "previous fetcher is not exhausted")
        self._fetcher = SingleNetstringFetcher(self._incoming, self._maxlen)
        return self._fetcher


def encode(data):
    return b'%d:%s,' % (len(data), data)


def decode(data):
    reader = StreamReader()
    reader.feed(data)
    try:
        while True:
            res = []
            string_reader = reader.next_string()
            while True:
                buf = string_reader.read()
                if not buf:
                    break
                res.append(buf)
            yield b''.join(res)
    except WantRead:
        if reader.pending():
            # pylint: disable=raise-missing-from
            raise IncompleteNetstring("Input ends on unfinished string.")
