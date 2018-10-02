postfix-mta-sts-resolver
========================

Daemon which provides TLS client policy for Postfix via socketmap, according to domain MTA-STS policy. Current support of RFC8461 is limited - daemon lacks some minor features:

* Proactive policy fetch
* Fetch error reporting
* Fetch ratelimit

## Dependencies

* Python 3.5.3+
* aiodns
* aiohttp
* pynetstring
* PyYAML
* (optional) uvloop
* pycares>=2.3.0


## Installation

### Method 1. System-wide install

Run in project directory:

```bash
python3 -m pip install .
```

Package scripts shall be available in standard executable locations upon completion.

### Method 2. Running from project directory

Installing dependencies:


```bash
python3 -m pip install -r requirements.txt
```

Now script can be run right from source directory.

#### pip user install

Both previous methods can be run with `--user` option of `pip` installer. In this case superuser privileges are not required and package shall be installed to user home directory. So, for first method script executabled will appear in `~/.local/bin`.

### Method 3. Install into virtualenv

See "Building virtualenv"


## Building virtualenv

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

## Configuration

See example config in source code directory. Default config location is: `/etc/postfix/mta-sts-daemon.yml`

## Postfix configuration

Add line like

```
smtp_tls_policy_maps = socketmap:inet:127.0.0.1:8461:postfix
```

into your `main.cf` config.

## Credits

Inspired by [this forum thread](http://postfix.1071664.n5.nabble.com/MTA-STS-when-td95086.html).
