import enum
import logging
import logging.handlers
import asyncio
import socket
import queue

import yaml

from . import defaults


class LogLevel(enum.IntEnum):
    debug = logging.DEBUG
    info = logging.INFO
    warn = logging.WARN
    error = logging.ERROR
    fatal = logging.FATAL
    crit = logging.CRITICAL

    def __str__(self):
        return self.name


class OverflowingQueue(queue.Queue):
    def put(self, item, block=True, timeout=None):
        try:
            return queue.Queue.put(self, item, block, timeout)
        except queue.Full:
            pass

    def put_nowait(self, item):
        return self.put(item, False)


class AsyncLoggingHandler:
    def __init__(self, logfile=None, maxsize=1024):
        _queue = OverflowingQueue(maxsize)
        if logfile is None:
            _handler = logging.StreamHandler()
        else:
            _handler = logging.FileHandler(logfile)
        self._listener = logging.handlers.QueueListener(_queue, _handler)
        self._async_handler = logging.handlers.QueueHandler(_queue)

        _handler.setFormatter(logging.Formatter('%(asctime)s '
                                                '%(levelname)-8s '
                                                '%(name)s: %(message)s',
                                                '%Y-%m-%d %H:%M:%S'))

    def __enter__(self):
        self._listener.start()
        return self._async_handler

    def __exit__(self, exc_type, exc_value, traceback):
        self._listener.stop()


def setup_logger(name, verbosity, handler):
    logger = logging.getLogger(name)
    logger.setLevel(verbosity)
    logger.addHandler(handler)
    return logger


def enable_uvloop():  # pragma: no cover
    try:
        # pylint: disable=import-outside-toplevel
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        return False
    else:
        return True


def populate_cfg_defaults(cfg):
    if not cfg:
        cfg = {}

    if cfg.get('path') is None:
        cfg['host'] = cfg.get('host', defaults.HOST)
        cfg['port'] = cfg.get('port', defaults.PORT)
    cfg['reuse_port'] = cfg.get('reuse_port', defaults.REUSE_PORT)
    cfg['shutdown_timeout'] = cfg.get('shutdown_timeout',
                                      defaults.SHUTDOWN_TIMEOUT)
    cfg['cache_grace'] = cfg.get('cache_grace', defaults.CACHE_GRACE)

    if 'proactive_policy_fetching' not in cfg:
        cfg['proactive_policy_fetching'] = {}
    cfg['proactive_policy_fetching']['enabled'] = cfg['proactive_policy_fetching'].\
        get('enabled', defaults.PROACTIVE_FETCH_ENABLED)
    cfg['proactive_policy_fetching']['interval'] = cfg['proactive_policy_fetching'].\
        get('interval', defaults.PROACTIVE_FETCH_INTERVAL)
    cfg['proactive_policy_fetching']['concurrency_limit'] = cfg['proactive_policy_fetching'].\
        get('concurrency_limit', defaults.PROACTIVE_FETCH_CONCURRENCY_LIMIT)
    cfg['proactive_policy_fetching']['grace_ratio'] = cfg['proactive_policy_fetching'].\
        get('grace_ratio', defaults.PROACTIVE_FETCH_GRACE_RATIO)

    if 'cache' not in cfg:
        cfg['cache'] = {}

    cfg['cache']['type'] = cfg['cache'].get('type', defaults.CACHE_BACKEND)

    if cfg['cache']['type'] == 'internal':
        if 'options' not in cfg['cache']:
            cfg['cache']['options'] = {}

        cfg['cache']['options']['cache_size'] = cfg['cache']['options'].\
            get('cache_size', defaults.INTERNAL_CACHE_SIZE)

    def populate_zone(zone):
        zone['timeout'] = zone.get('timeout', defaults.TIMEOUT)
        zone['strict_testing'] = zone.get('strict_testing', defaults.STRICT_TESTING)
        return zone

    if 'default_zone' not in cfg:
        cfg['default_zone'] = {}

    populate_zone(cfg['default_zone'])

    if 'zones' not in cfg:
        cfg['zones'] = {}

    for zone in cfg['zones'].values():
        populate_zone(zone)

    return cfg


def load_config(filename):
    with open(filename, 'rb') as cfg_file:
        cfg = yaml.safe_load(cfg_file)
    return populate_cfg_defaults(cfg)


def parse_mta_sts_record(rec):
    return dict(field.partition('=')[0::2] for field in
                (field.strip() for field in rec.split(';')) if field)


def parse_mta_sts_policy(text):
    lines = text.splitlines()
    res = dict()
    res['mx'] = list()
    for line in lines:
        line = line.rstrip()
        key, _, value = line.partition(':')
        value = value.lstrip()
        if key == 'mx':
            res['mx'].append(value)
        else:
            res[key] = value
    return res


def is_plaintext(contenttype):
    return contenttype.lower().partition(';')[0].strip() == 'text/plain'


def is_ipaddr(addr):
    try:
        socket.getaddrinfo(addr, None, flags=socket.AI_NUMERICHOST)
        return True
    except socket.gaierror:
        return False


def filter_domain(domain):
    lpart, found_separator, rpart = domain.partition(']')
    res = lpart.lstrip('[')
    if not found_separator:
        lpart, found_separator, rpart = domain.rpartition(':')
        res = lpart if found_separator else rpart

    return res.lower().strip().rstrip('.')


def filter_text(strings):
    for string in strings:
        if isinstance(string, str):
            yield string
        elif isinstance(string, bytes):
            try:
                yield string.decode('ascii')
            except UnicodeDecodeError:
                pass
        else:
            raise TypeError('Only bytes or strings are expected.')


async def create_custom_socket(host, port, *,  # pylint: disable=too-many-locals
                               family=socket.AF_UNSPEC,
                               type=socket.SOCK_STREAM,  # pylint: disable=redefined-builtin
                               flags=socket.AI_PASSIVE,
                               options=None,
                               loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    res = await loop.getaddrinfo(host, port,
                                 family=family, type=type, flags=flags)
    af, s_typ, proto, _, sa = res[0]  # pylint: disable=invalid-name
    sock = socket.socket(af, s_typ, proto)

    if options is not None:
        for level, optname, val in options:
            sock.setsockopt(level, optname, val)

    sock.bind(sa)
    return sock


def create_cache(cache_type, options):
    if cache_type == "internal":
        # pylint: disable=import-outside-toplevel
        from . import internal_cache
        cache = internal_cache.InternalLRUCache(**options)
    elif cache_type == "sqlite":
        # pylint: disable=import-outside-toplevel
        from . import sqlite_cache
        cache = sqlite_cache.SqliteCache(**options)
    elif cache_type == "redis":
        # pylint: disable=import-outside-toplevel
        from . import redis_cache
        cache = redis_cache.RedisCache(**options)
    else:
        raise NotImplementedError("Unsupported cache type!")
    return cache
