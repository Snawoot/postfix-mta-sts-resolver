import asyncio
import aiodns
import aiohttp
import enum
from . import defaults
from .utils import parse_mta_sts_record, parse_mta_sts_policy, is_plaintext


class BadSTSPolicy(Exception):
    pass


class STSFetchResult(enum.Enum):
    NONE = 0
    VALID = 1
    FETCH_ERROR = 2
    NOT_CHANGED = 3


class STSResolver(object):
    def __init__(self, *, timeout=defaults.TIMEOUT, loop):
        self._loop = loop
        self._timeout = timeout
        self._resolver = aiodns.DNSResolver(timeout=timeout, loop=loop)
        self._http_timeout = aiohttp.ClientTimeout(total=timeout)

    async def resolve(self, domain, last_known_id=None):
        if domain.startswith('.'):
            return STSFetchResult.NONE, None
        # Cleanup domain name
        domain = domain.rstrip('.')

        # Construct name of corresponding MTA-STS DNS record for domain
        sts_txt_domain = '_mta-sts.' + domain

        # Try to fetch it
        try:
            txt_records = await self._resolver.query(sts_txt_domain, 'TXT')
        except aiodns.error.DNSError as e:
            if e.args[0] == aiodns.error.ARES_ETIMEOUT:
                # It's hard to decide what to do in case of timeout
                # Probably it's better to threat this as fetch error
                # so caller probably shall report such cases.
                return STSFetchResult.FETCH_ERROR, None
            elif e.args[0] == aiodns.error.ARES_ENOTFOUND:
                return STSFetchResult.NONE, None
            elif e.args[0] == aiodns.error.ARES_ENODATA:
                return STSFetchResult.NONE, None
            else:
                return STSFetchResult.NONE, None

        # Exactly one record should exist
        txt_records = [rec for rec in txt_records if rec.text.startswith(b'v=STSv1')]
        if len(txt_records) != 1:
            return STSFetchResult.NONE, None

        # Validate record
        txt_record = txt_records[0].text.decode('latin-1')
        mta_sts_record = parse_mta_sts_record(txt_record)
        if mta_sts_record.get('v', None) != 'STSv1' or 'id' not in mta_sts_record:
            return STSFetchResult.NONE, None

        # Obtain policy ID and return NOT_CHANGED if ID is equal to last known
        if mta_sts_record['id'] == last_known_id:
            return STSFetchResult.NOT_CHANGED, None

        # Construct corresponding URL of MTA-STS policy
        sts_policy_url = 'https://mta-sts.' + domain + '/.well-known/mta-sts.txt'

        # Fetch actual policy
        try:
            async with aiohttp.ClientSession(loop=self._loop, timeout=self._http_timeout) as session:
                async with session.get(sts_policy_url, allow_redirects=False) as resp:
                    if resp.status != 200:
                        raise BadSTSPolicy()
                    if not is_plaintext(resp.headers.get('Content-Type', '')):
                        raise BadSTSPolicy()
                    policy_text = await resp.text()
        except:
            return STSFetchResult.FETCH_ERROR, None

        # Parse policy
        pol = parse_mta_sts_policy(policy_text)

        # Validate policy
        if pol.get('version', None) != 'STSv1':
            return STSFetchResult.FETCH_ERROR, None

        try:
            max_age = int(pol.get('max_age', '-1'))
            pol['max_age'] = max_age
        except:
            return STSFetchResult.FETCH_ERROR, None

        if not (0 <= max_age <= 31557600):
            return STSFetchResult.FETCH_ERROR, None

        if 'mode' not in pol:
            return STSFetchResult.FETCH_ERROR, None

        # No MX check required for 'none' policy:
        if pol['mode'] == 'none':
            return STSFetchResult.VALID, (mta_sts_record['id'], pol)

        if pol['mode'] not in ('none', 'testing', 'enforce'):
            return STSFetchResult.FETCH_ERROR, None

        if not pol['mx']:
            return STSFetchResult.FETCH_ERROR, None

        # Policy is valid. Returning result.
        return STSFetchResult.VALID, (mta_sts_record['id'], pol)
