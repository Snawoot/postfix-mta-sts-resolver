import asyncio
import aiodns
import aiohttp
import enum
from . import defaults
from .utils import parse_mta_sts_record


class STSResult(enum.Enum):
    NONE = 0
    TESTING = 1
    ENFORCE = 2
    FETCH_ERROR = 3
    NOT_CHANGED = 4


class STSResolver(object):
    def __init__(self, *, timeout=defaults.TIMEOUT, loop):
        self._loop = loop
        self._timeout = timeout
        self._resolver = aiodns.DNSResolver(loop=loop)

    async def resolve(self, domain, last_known_id=None):
        sts_txt_domain = '_mta-sts.' + domain.strip('.')
        txt_records = await self._resolver.query(sts_txt_domain, 'TXT')
        txt_records = [ rec for rec in txt_records if rec.text.startswith('v=STSv1') ]
        if len(txt_records) != 1:
            return (STSResult.NONE, None)

        txt_record = txt_records[0].text
        mta_sts_record = parse_mta_sts_record(txt_record)
        if mta_sts_record.get('v', None) != 'STSv1' or 'id' not in mta_sts_record:
            return (STSResult.NONE, None)

        if mta_sts_record['id'] == last_known_id:
            return (STSResult.NOT_CHANGED, None)
