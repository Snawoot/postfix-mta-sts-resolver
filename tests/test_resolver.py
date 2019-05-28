import collections.abc

import postfix_mta_sts_resolver.resolver
import pytest

@pytest.mark.parametrize("domain", ['vm-0.com', 'vm-0.com.'])
@pytest.mark.asyncio
async def test_simple_resolve(domain):
    resolver = postfix_mta_sts_resolver.resolver.STSResolver(loop=None)
    status, (ver, policy) = await resolver.resolve(domain)
    assert status is postfix_mta_sts_resolver.resolver.STSFetchResult.VALID
    assert 'mx' in policy
    assert isinstance(policy['mx'], collections.abc.Iterable)
    assert all(isinstance(dom, str) for dom in policy['mx'])
    assert policy['version'] == 'STSv1'
    assert policy['mode'] in ('none', 'enforce', 'testing')
    assert isinstance(policy['max_age'], int)
    assert policy['max_age'] > 0
    assert isinstance(ver, str)
    assert ver
    status, body2 = await resolver.resolve(domain, ver)
    assert status is postfix_mta_sts_resolver.resolver.STSFetchResult.NOT_CHANGED
    assert body2 is None

@pytest.mark.parametrize("domain", ['mta-sts.vm-0.com',
                                    '.vm-0.com',
                                    '.vm-0.com.',
                                    '.mta-sts.vm-0.com.'])
@pytest.mark.asyncio
async def test_negative_resolve(domain):
    resolver = postfix_mta_sts_resolver.resolver.STSResolver(loop=None)
    status, body = await resolver.resolve(domain)
    assert status is postfix_mta_sts_resolver.resolver.STSFetchResult.NONE
    assert body is None
