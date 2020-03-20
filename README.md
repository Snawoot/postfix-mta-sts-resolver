postfix-mta-sts-resolver
========================

[![Build Status](https://travis-ci.org/Snawoot/postfix-mta-sts-resolver.svg?branch=master)](https://travis-ci.org/Snawoot/postfix-mta-sts-resolver) [![Coverage](https://img.shields.io/badge/coverage-97%25-4dc71f.svg)](https://travis-ci.org/Snawoot/postfix-mta-sts-resolver) [![PyPI - Downloads](https://img.shields.io/pypi/dm/postfix-mta-sts-resolver.svg?color=4dc71f&label=PyPI%20downloads)](https://pypistats.org/packages/postfix-mta-sts-resolver) [![PyPI](https://img.shields.io/pypi/v/postfix-mta-sts-resolver.svg)](https://pypi.org/project/postfix-mta-sts-resolver/) [![PyPI - Status](https://img.shields.io/pypi/status/postfix-mta-sts-resolver.svg)](https://pypi.org/project/postfix-mta-sts-resolver/) [![PyPI - License](https://img.shields.io/pypi/l/postfix-mta-sts-resolver.svg?color=4dc71f)](https://pypi.org/project/postfix-mta-sts-resolver/)

Daemon which provides TLS client policy for Postfix via socketmap, according to domain MTA-STS policy. Current support of RFC8461 is limited - daemon lacks some minor features:

* Fetch error reporting
* Fetch ratelimit (but actual fetch rate partially restricted with `cache_grace` config option).

Server has configurable cache backend which allows to store cached STS policies in memory (`internal`), file (`sqlite`) or in Redis database (`redis`).


## Requirements

* Postfix 2.10 and later
* Python 3.5.3+ (see ["Systems without Python 3.5+"](#systems-without-python-35) below if you haven't one, or use Docker installation method)
* aiodns
* aiohttp
* aiosqlite
* aioredis
* PyYAML
* (optional) uvloop

All dependency packages installed automatically if this package is installed via pip.


## Installation

### Method 1. System-wide install from PyPI (recommended for humans)

Run:

```bash
sudo python3 -m pip install postfix-mta-sts-resolver[redis,sqlite]
```

If you don't need `redis` or `sqlite` support, you may omit one of them in square brackets. If you don't need any of them and you plan to use internal cache without persistence, you should also omit square brackets.

Package scripts shall be available in standard executable locations upon completion.

#### pip user install

All pip invocations can be run with `--user` option of `pip` installer. In this case superuser privileges are not required and package(s) are getting installed into user home directory. Usually, script executables will appear in `~/.local/bin`.

### Method 2. System-wide install from project source

Run in project directory:

```bash
sudo python3 -m pip install .[redis,sqlite]
```

If you don't need `redis` or `sqlite` support, you may omit one of them in square brackets. If you don't need any of them and you plan to use internal cache without persistence, you should also omit square brackets.

Package scripts shall be available in standard executable locations upon completion.


### Method 3. Install into virtualenv

See ["Building virtualenv"](#building-virtualenv)

### Method 4. Docker

Run

```bash
docker volume create mta-sts-cache
docker run -d \
    --security-opt no-new-privileges \
    -v mta-sts-cache:/var/lib/mta-sts \
    -p 127.0.0.1:8461:8461 \
    --restart unless-stopped \
    --name postfix-mta-sts-resolver \
    yarmak/postfix-mta-sts-resolver
```

Daemon will be up and running, listening on local interface on port 8461. Default configuration baked into docker image uses SQLite for cache stored in persistent docker volume. You may override this configuration with your own config file by mapping it into container with option `-v my_config.yml:/etc/mta-sta-daemon.yml`.

### Common installation notes

See also [contrib/README.md](https://github.com/Snawoot/postfix-mta-sts-resolver/tree/master/contrib/README.md) for RHEL/OEL/Centos and FreeBSD notes.

See [contrib/](https://github.com/Snawoot/postfix-mta-sts-resolver/tree/master/contrib) for example of systemd unit file suitable to run daemon under systemd control.

## Running

This package provides two executables available after installation in respective locations.


### mta-sts-query

`mta-sts-query` is a command line tool which fetches and outputs domain MTA-STS policies. Intended to be used for debug purposes.

Synopsis:

```
$ mta-sts-query --help
usage: mta-sts-query [-h] [-v {debug,info,warn,error,fatal}]
                     domain [known_version]

positional arguments:
  domain                domain to fetch MTA-STS policy from
  known_version         latest known version (default: None)

optional arguments:
  -h, --help            show this help message and exit
  -v {debug,info,warn,error,fatal}, --verbosity {debug,info,warn,error,fatal}
                        logging verbosity (default: warn)
```

### mta-sts-daemon

`mta-sts-daemon` is a daemon which provides external [TLS policy for Postfix SMTP client](http://www.postfix.org/TLS_README.html#client_tls_policy) via [socketmap interface](http://www.postfix.org/socketmap_table.5.html).

You may find useful systemd unit file to run daemon in [contrib/](https://github.com/Snawoot/postfix-mta-sts-resolver/tree/master/contrib).

Synopsis:

```
$ mta-sts-daemon --help
usage: mta-sts-daemon [-h] [-v {debug,info,warn,error,fatal}] [-c FILE]
                      [-l FILE] [--disable-uvloop]

optional arguments:
  -h, --help            show this help message and exit
  -v {debug,info,warn,error,fatal}, --verbosity {debug,info,warn,error,fatal}
                        logging verbosity (default: info)
  -c FILE, --config FILE
                        config file location (default: /etc/mta-sts-
                        daemon.yml)
  -l FILE, --logfile FILE
                        log file location (default: None)
  --disable-uvloop      do not use uvloop even if it is available (default:
                        False)
```

#### Seamless restart/upgrade/reload and load balancing

By default mta-sts-daemon allows its multiple instances to share same port (on Linux/FreeBSD/Windows). Therefore, restart or upgrade of daemon can be performed seamlessly. Set of unit files for systemd in [contrib/](contrib/) directory implements "reload" by mean of running backup instance when main instance is getting restarted.

Also on Linux and FreeBSD, load distribited across all processes (with SO\_REUSEPORT and SO\_REUSEPORT\_LB respectively).


## MTA-STS Daemon configuration

See [configuration man page](https://github.com/Snawoot/postfix-mta-sts-resolver/blob/master/man/mta-sts-daemon.yml.5.adoc) and [config\_examples/](https://github.com/Snawoot/postfix-mta-sts-resolver/tree/master/config_examples) directory. Default config location is: `/etc/mta-sts-daemon.yml`, but it can be overriden with command line option `-c FILE`.

All options is self-explanatory, only exception is `strict_testing` option. If set to `true`, STS policy will be enforced even if domain announces `testing` MTA-STS mode. Useful for premature incorporation of MTA-STS against domains hesistating to go `enforce`. Please use with caution.


## Postfix configuration

SMTP client of your Postfix instance must be able to validate peer certificates. In order to achieve that, you have to ensure [`smtp_tls_CAfile`](http://www.postfix.org/postconf.5.html#smtp_tls_CAfile) or [`smtp_tls_CApath`](http://www.postfix.org/postconf.5.html#smtp_tls_CApath) points to system CA bundle. Otherwise you'll get `Unverified TLS connection` even for peers with valid certificate, and delivery failures for MTA-STS-enabled destinations. Also note: even enabled [`tls_append_default_CA`](http://www.postfix.org/postconf.5.html#tls_append_default_CA) will not work alone if both `smtp_tls_CAfile` and `smtp_tls_CApath` are empty.

Once certificate validation is enabled and your Postfix log shows "Trusted TLS connection ... " for destinations with valid certificates signed by public CA, you may enable MTA-STS by adding following line to `main.cf`:

```
smtp_tls_policy_maps = socketmap:inet:127.0.0.1:8461:postfix
```

If your configuration already has some TLS policy maps, just add MTA-STS socketmap to list of configured maps accordingly to [`smtp_tls_policy_maps`](http://www.postfix.org/postconf.5.html#smtp_tls_policy_maps) syntax. TLS policy tables are searched in the specified order until a match is found, so you may have table with local overrides of TLS policy prior to MTA-STS socketmap. This may be useful for skipping network lookup for well-known destinations or relaxing security for broken destinations, announcing MTA-STS support.

Reload Postfix after reconfiguration.


## Operability check

Assuming default MTA-STA daemon configuration. Following command:

```bash
/usr/sbin/postmap -q dismail.de socketmap:inet:127.0.0.1:8461:postfix
```

should return something like:

```
secure match=mx1.dismail.de
```

Postfix log should show `Verified TLS connection established to ...` instead of `Untrusted ...` or `Trusted TLS connection established to ...` when mail is getting sent to MTA-STS-enabled domain.


## Special cases of deployment


### Systems without Python 3.5+

Some people may find convenient to install latest python from source into `/opt` directory. This way you can have separate python installation not interferring with system packages by any means. Download latest python source from [python.org](https://www.python.org/), unpack and run in unpacked source directory:

```bash
./configure --prefix=/opt --enable-optimizations && make -j $[ $(nproc) + 1 ] && make test && sudo make install
```

Python binaries will be available in `/opt/bin`, including `pip3`. You may install `postfix-mta-sts-resolver` using `/opt/bin/pip3` without interference with any system packages:

```bash
sudo /opt/bin/pip3 install postfix-mta-sts-resolver[sqlite,redis]
```

Executable files of `postfix-mta-sts-resolver` will be available in `/opt/bin/mta-sts-query` and `/opt/bin/mta-sts-daemon`


### Building virtualenv

Run `make` in project directory in order to build virtualenv. As result of it, new directory `venv` shall appear. `venv` contains interpreter and all required dependencies, i.e. encloses package with depencencies in separate environment. It is possible to specify alternative path where virtualenv directory shall be placed. Specify VENV variable for `make` command. Example:

```bash
make VENV=~/postfix-mta-sts-resolver
```

Such virtual environment can be moved to another machine of similar type (as far python interpreter is compatible with new environment). If virtualenv is placed into same location on new machine, application can be runned this way:

```bash
venv/bin/mta-sts-daemon
```

Otherwise, some hacks required. First option - explicitly call virtualenv interpreter:

```bash
venv/bin/python venv/bin/mta-sts-daemon
```

Second option - specify new path in shebang of scripts installed in virtualenv. It is recommended to build virtualenv at same location which app shall occupy on target system.


## Credits

Inspired by [this forum thread](http://postfix.1071664.n5.nabble.com/MTA-STS-when-td95086.html).
