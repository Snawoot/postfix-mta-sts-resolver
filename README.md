postfix-mta-sts-resolver
========================

Daemon which provides TLS client policy for Postfix via socketmap, according to domain MTA-STS policy. Current support of RFC8461 is limited - daemon lacks some minor features:

* Proactive policy fetch
* Fetch error reporting
* Fetch ratelimit

Server has configurable cache backend which allows to store cached STS policies in memory (`internal`), file (`sqlite`) or in Redis database (`redis`).


## Requirements

* Postfix 2.10 and later
* Python 3.5.3+ (see ["Systems without Python 3.5+"](#systems-without-python-35) below if you haven't one)
* aiodns
* aiohttp
* aiosqlite
* aioredis
* pynetstring
* PyYAML
* (optional) uvloop

All dependency packages installed automatically if this package is installed via pip.


## Installation

### Method 1. System-wide install from PyPI (recommended for humans)

Run:

```bash
sudo python3 -m pip install postfix-mta-sts-resolver
```

Package scripts shall be available in standard executable locations upon completion.


### Method 2. System-wide install from project source

Run in project directory:

```bash
sudo python3 -m pip install .
```

Package scripts shall be available in standard executable locations upon completion.


### Method 3. Install into virtualenv

See ["Building virtualenv"](#building-virtualenv)


### Common installation notes

See also [contrib/README.md](contrib/README.md) for RHEL/OEL/Centos and FreeBSD notes.

See [contrib/postfix-mta-sts.service](contrib/postfix-mta-sts.service) for example of systemd unit file suitable to run daemon under systemd control.


#### pip user install

All pip invocations can be run with `--user` option of `pip` installer. In this case superuser privileges are not required and package(s) are getting installed into user home directory. Usually, script executables will appear in `~/.local/bin`.


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

You may find useful systemd unit file to run daemon in [contrib/postfix-mta-sts.service](contrib/postfix-mta-sts.service).

Synopsis:

```
$ mta-sts-daemon --help
usage: mta-sts-daemon [-h] [-v {debug,info,warn,error,fatal}] [-c FILE]
                      [--disable-uvloop]

optional arguments:
  -h, --help            show this help message and exit
  -v {debug,info,warn,error,fatal}, --verbosity {debug,info,warn,error,fatal}
                        logging verbosity (default: info)
  -c FILE, --config FILE
                        config file location (default: /etc/postfix/mta-sts-
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

See [config\_examples/](config_examples/) directory. Default config location is: `/etc/postfix/mta-sts-daemon.yml`, but it can be overriden with command line option `-c FILE`.

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
sudo /opt/bin/pip3 install postfix-mta-sts-resolver
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
