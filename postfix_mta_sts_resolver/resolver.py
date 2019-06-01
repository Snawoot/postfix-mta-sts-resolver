import asyncio
import enum
from io import BytesIO

import aiodns
import aiodns.error
import aiohttp

from . import defaults
from .utils import parse_mta_sts_record, parse_mta_sts_policy, is_plaintext, filter_text
from .constants import HARD_RESP_LIMIT, CHUNK


class BadSTSPolicy(Exception):
    pass


class STSFetchResult(enum.Enum):
    NONE = 0
    VALID = 1
    FETCH_ERROR = 2
    NOT_CHANGED = 3


_HEADERS = {"User-Agent": defaults.USER_AGENT}

# pylint: disable=too-few-public-methods
class STSResolver:
    def __init__(self, *, timeout=defaults.TIMEOUT, loop):
        self._loop = loop
        self._timeout = timeout
        self._resolver = aiodns.DNSResolver(timeout=timeout, loop=loop)
        self._http_timeout = aiohttp.ClientTimeout(total=timeout)
        self._proxy_info = aiohttp.helpers.proxies_from_env().get('https', None)

        if self._proxy_info is None:
            self._proxy = None
            self._proxy_auth = None
        else:
            self._proxy = self._proxy_info.proxy
            self._proxy_auth = self._proxy_info.proxy_auth

    # pylint: disable=too-many-locals,too-many-branches,too-many-return-statements
    async def resolve(self, domain, last_known_id=None):
        if domain.startswith('.'):
            return STSFetchResult.NONE, None
        # Cleanup domain name
        domain = domain.rstrip('.')

        # Construct name of corresponding MTA-STS DNS record for domain
        sts_txt_domain = '_mta-sts.' + domain

        # Try to fetch it
        try:
            txt_records = await asyncio.wait_for(
                self._resolver.query(sts_txt_domain, 'TXT'),
                timeout=self._timeout)
        except aiodns.error.DNSError as error:
            if error.args[0] == aiodns.error.ARES_ETIMEOUT:  # pragma: no cover pylint: disable=no-else-return,no-member
                # This branch is not covered because of aiodns bug:
                # https://github.com/saghul/aiodns/pull/64
                # It's hard to decide what to do in case of timeout
                # Probably it's better to threat this as fetch error
                # so caller probably shall report such cases.
                return STSFetchResult.FETCH_ERROR, None
            elif error.args[0] == aiodns.error.ARES_ENOTFOUND:  # pylint: disable=no-else-return,no-member
                return STSFetchResult.NONE, None
            elif error.args[0] == aiodns.error.ARES_ENODATA:  # pylint: disable=no-else-return,no-member
                return STSFetchResult.NONE, None
            else:  # pragma: no cover
                return STSFetchResult.NONE, None
        except asyncio.TimeoutError:
            return STSFetchResult.FETCH_ERROR, None

        # workaround for floating return type of pycares
        txt_records = filter_text(rec.text for rec in txt_records)

        # RFC 8461 strictly defines version string as first field
        txt_records = [txt for txt in txt_records
                       if txt.startswith('v=STSv1')]

        # Exactly one record should exist
        if len(txt_records) != 1:
            return STSFetchResult.NONE, None

        # Validate record
        mta_sts_record = parse_mta_sts_record(txt_records[0])
        if (mta_sts_record.get('v', None) != 'STSv1'
                or 'id' not in mta_sts_record):
            return STSFetchResult.NONE, None

        # Obtain policy ID and return NOT_CHANGED if ID is equal to last known
        if mta_sts_record['id'] == last_known_id:
            return STSFetchResult.NOT_CHANGED, None

        # Construct corresponding URL of MTA-STS policy
        sts_policy_url = ('https://mta-sts.' +
                          domain +
                          '/.well-known/mta-sts.txt')

        # Fetch actual policy
        try:
            async with aiohttp.ClientSession(loop=self._loop,
                                             timeout=self._http_timeout) \
                                                 as session:
                async with session.get(sts_policy_url,
                                       allow_redirects=False,
                                       proxy=self._proxy, headers=_HEADERS,
                                       proxy_auth=self._proxy_auth) as resp:
                    if resp.status != 200:
                        raise BadSTSPolicy()
                    if not is_plaintext(resp.headers.get('Content-Type', '')):
                        raise BadSTSPolicy()
                    if (int(resp.headers.get('Content-Length', '0')) >
                            HARD_RESP_LIMIT):
                        raise BadSTSPolicy()
                    policy_file = BytesIO()
                    while policy_file.tell() <= HARD_RESP_LIMIT:
                        chunk = await resp.content.read(CHUNK)
                        if not chunk:
                            break
                        policy_file.write(chunk)
                    else:
                        raise BadSTSPolicy()
                    charset = (resp.charset if resp.charset is not None
                               else 'ascii')
                    policy_text = policy_file.getvalue().decode(charset)
        except Exception:
            return STSFetchResult.FETCH_ERROR, None

        # Parse policy
        pol = parse_mta_sts_policy(policy_text)

        # Validate policy
        if pol.get('version', None) != 'STSv1':
            return STSFetchResult.FETCH_ERROR, None

        try:
            max_age = int(pol.get('max_age', '-1'))
            pol['max_age'] = max_age
        except ValueError:
            return STSFetchResult.FETCH_ERROR, None

        if not 0 <= max_age <= 31557600:
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
