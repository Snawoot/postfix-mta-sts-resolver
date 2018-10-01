import enum
import logging
import asyncio


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


def setup_logger(name, verbosity):
    logger = logging.getLogger(name)
    logger.setLevel(verbosity)
    handler = logging.StreamHandler()
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


def parse_mta_sts_record(rec):
    d = dict(field.partition('=')[0::2] for field in (field.strip() for field in rec.split(';')) if field)
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
