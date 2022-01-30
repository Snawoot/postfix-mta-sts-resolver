#!/bin/sh

set -e

PYTHON="${PYTHON:-python3}"

# run under travis, but not under autopkgtest
if [ -z "${AUTOPKGTEST_TMP+x}" ] ; then
    apt-get update
    apt-get install -y redis-server dnsmasq lsof nginx-extras tinyproxy \
		build-essential libssl-dev libffi-dev python3-dev cargo
    systemctl start redis-server || { journalctl -xe ; false ; }
    "$PYTHON" -m pip install cryptography
    "$PYTHON" -m pip install tox
fi

install -m 644 tests/resolv.conf /etc/resolv-dnsmasq.conf
cat tests/dnsmasq.conf.appendix >> /etc/dnsmasq.conf
echo 'nameserver 127.0.0.1' > /etc/resolv.conf
systemctl restart dnsmasq || { journalctl -xe ; false ; }


# certificates for the test cases
mkdir -p /tmp/certs /tmp/bad-certs
"$PYTHON" tests/mkcerts.py -o /tmp/certs \
  -D good.loc mta-sts.good.loc \
  -D bad-policy1.loc mta-sts.bad-policy1.loc \
  -D bad-policy2.loc mta-sts.bad-policy2.loc \
  -D bad-policy3.loc mta-sts.bad-policy3.loc \
  -D bad-policy4.loc mta-sts.bad-policy4.loc \
  -D bad-policy5.loc mta-sts.bad-policy5.loc \
  -D bad-policy6.loc mta-sts.bad-policy6.loc \
  -D bad-policy7.loc mta-sts.bad-policy7.loc \
  -D bad-policy8.loc mta-sts.bad-policy8.loc \
  -D bad-cert2.loc \
  -D valid-none.loc mta-sts.valid-none.loc \
  -D mta-sts.testing.loc \
  -D chunked-overlength.loc mta-sts.chunked-overlength.loc \
  -D static-overlength.loc mta-sts.static-overlength.loc \
  -D fast-expire.loc '*.fast-expire.loc'
# problematic certificates
"$PYTHON" tests/mkcerts.py -o /tmp/bad-certs -D bad-cert1.loc mta-sts.bad-cert1.loc


mkdir -p /usr/local/share/ca-certificates/test
install -m 644 -o root -g root /tmp/certs/ca.pem /usr/local/share/ca-certificates/test/test-ca.crt
update-ca-certificates 2>&1


install -m 644 tests/nginx.conf /etc/nginx/nginx.conf
systemctl restart nginx || { journalctl -xe ; false ; }


# run under travis, but not under autopkgtest
if [ -z "${AUTOPKGTEST_TMP+x}" ] ; then
    install -m 644 -o root -g root tests/tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
    systemctl restart tinyproxy || { journalctl -xe ; false ; }
    tests/expedite_proxy_startup.sh || { journalctl -xe ; false ; }
else
    systemctl restart postfix-mta-sts-resolver
fi
