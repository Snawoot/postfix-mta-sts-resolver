python-cli-tool-boilerplate
===========================

Boilerplate of python3 package which provides command line tool capable to:

* be installed in venv
* be installed using `setup.py`
* be runned directly from source directory if environment dependencies already satisfied

In order to convert this boilerplate to real project you have to:

1. Edit setup.py: version, name, dependencies
2. Rename `clitoolboilerplate` module directory
3. Adjust imports
4. (Optional) Add dependencies to `requirements.txt`


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

#### Пользовательская установка pip

Both previous methods can be run with `--user` option of `pip` installer. In this case superuser privileges are not required and package shall be installed to user home directory. So, for first method script executabled will appear in `~/.local/bin`.

### Method 3. Install into virtualenv

See "Building virtualenv"


## Building virtualenv

Run `make` in project directory in order to build virtualenv. As result of it, new directory `venv` shall appear. `venv` contains interpreter and all required dependencies, i.e. encloses package with depencencies in separate environment. It is possible to specify alternative path where virtualenv directory shall be placed. Specify VENV variable for `make` command. Example:

```bash
make VENV=~/myapp-venv
```

Such virtual environment can be moved to another machine of similar type (as far python interpreter is compatible with new environment). If virtualenv is placed into same location on new machine, application can be runned this way:

```bash
venv/bin/cli-tool
```

Otherwise, some hacks required. First option - explicitly call virtualenv interpreter:

```bash
venv/bin/python venv/bin/cli-tool
```

Second option - specify new path in shebang of scripts installed in virtualenv. It is recommended to build virtualenv at same location which app shall occupy on target system.

