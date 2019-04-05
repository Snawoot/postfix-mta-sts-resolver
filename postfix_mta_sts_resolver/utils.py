import enum
import logging
import asyncio
import yaml
import socket

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

    def __contains__(self, e):
        return e in self.__members__


def setup_logger(name, verbosity, logfile=None):

    logger = logging.getLogger(name)
    logger.setLevel(verbosity)
    if logfile is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(logfile)
    handler.setLevel(verbosity)
    handler.setFormatter(logging.Formatter('%(asctime)s '
                                           '%(levelname)-8s '
                                           '%(name)s: %(message)s',
                                           '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)
    return logger


def check_port(value):
    ivalue = int(value)
    if not (0 < ivalue < 65536):
        raise argparse.ArgumentTypeError(
            "%s is not a valid port number" % value)
    return ivalue


def check_positive_float(value):
    fvalue = float(value)
    if fvalue <= 0:
        raise argparse.ArgumentTypeError(
            "%s is not a valid value" % value)
    return fvalue


def enable_uvloop():
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except:
        return False
    else:
        return True


def populate_cfg_defaults(cfg):
    if not cfg:
        cfg = {}

    cfg['host'] = cfg.get('host', defaults.HOST)
    cfg['port'] = cfg.get('port', defaults.PORT)
    cfg['reuse_port'] = cfg.get('reuse_port', defaults.REUSE_PORT)
    cfg['shutdown_timeout'] = cfg.get('shutdown_timeout',
                                      defaults.SHUTDOWN_TIMEOUT)
    cfg['cache_grace'] = cfg.get('cache_grace', defaults.CACHE_GRACE)

    if 'cache' not in cfg:
        cfg['cache'] = {}

    cfg['cache']['type'] = cfg['cache'].get('type', defaults.CACHE_BACKEND)

    if cfg['cache']['type'] == 'internal':
        if 'options' not in cfg['cache']:
            cfg['cache']['options'] = {}

        cfg['cache']['options']['cache_size'] = cfg['cache']['options'].get('cache_size', defaults.INTERNAL_CACHE_SIZE)

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
    d = dict(field.partition('=')[0::2] for field in
             (field.strip() for field in rec.split(';')) if field)
    return d


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


def is_plaintext(ct):
    return ct.lower().partition(';')[0].strip() == 'text/plain'


def filter_text(strings):
    for S in strings:
        if isinstance(S, str):
            yield S
        elif isinstance(S, bytes):
            try:
                yield S.decode('ascii')
            except UnicodeDecodeError:
                pass
        else:
            raise TypeError('Only bytes or strings are expected.')


async def create_custom_socket(host, port, *,
                               family=socket.AF_UNSPEC,
                               type=socket.SOCK_STREAM,
                               flags=socket.AI_PASSIVE,
                               options=None,
                               loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    res = await loop.getaddrinfo(host, port,
                                 family=family, type=type, flags=flags)
    af, s_typ, proto, cname, sa = res[0]
    sock = socket.socket(af, s_typ, proto)

    if options is not None:
        for level, optname, val in options:
            sock.setsockopt(level, optname, val)

    sock.bind(sa)
    return sock

def create_cache(type, options):
    if type == "internal":
        from . import internal_cache
        cache = internal_cache.InternalLRUCache(**options)
    elif type == "sqlite":
        from . import sqlite_cache
        cache = sqlite_cache.SqliteCache(**options)
    elif type == "redis":
        from . import redis_cache
        cache = redis_cache.RedisCache(**options)
    else:
        raise NotImplementedError("Unsupported cache type!")
    return cache
