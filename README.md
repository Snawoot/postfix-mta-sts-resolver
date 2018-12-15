postfix-mta-sts-resolver
========================

Daemon which provides TLS client policy for Postfix via socketmap, according to domain MTA-STS policy. Current support of RFC8461 is limited - daemon lacks some minor features:

* Proactive policy fetch
* Fetch error reporting
* Fetch ratelimit


## Dependencies

* Python 3.5.3+ (see ["Systems without Python 3.5+"](#systems-without-python-35) below if you haven't one)
* aiodns
* aiohttp
* pynetstring
* PyYAML
* (optional) uvloop
* pycares>=2.3.0

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


### Method 3. Running from project directory without installation

Installing dependencies:


```bash
python3 -m pip install -r requirements.txt
```

Now scripts can be run right from source directory.


### Method 4. Install into virtualenv

See ["Building virtualenv"](#building-virtualenv)


### Common installation notes

See also [contrib/README.md](contrib/README.md) for RHEL/OEL/Centos notes.

See [contrib/postfix-mta-sts.service](contrib/postfix-mta-sts.service) for example of systemd unit file suitable to run daemon under systemd control.


#### pip user install

All pip invocations can be run with `--user` option of `pip` installer. In this case superuser privileges are not required and package(s) are getting installed into user home directory. Usually, script executables will appear in `~/.local/bin`.


## Configuration

See example config in source code directory. Default config location is: `/etc/postfix/mta-sts-daemon.yml`


## Postfix configuration

Add line like

```
smtp_tls_policy_maps = socketmap:inet:127.0.0.1:8461:postfix
```

into your `main.cf` config.

## Operability check

Assuming default configuration. Following command:

```bash
/usr/sbin/postmap -q dismail.de socketmap:inet:127.0.0.1:8461:postfix
```

should return something like:

```
secure match=mx1.dismail.de
```


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