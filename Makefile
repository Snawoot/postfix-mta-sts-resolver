PYTHON = python3
RM = rm
PKG_NAME = postfix_mta_sts_resolver

PRJ_DIR = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV ?= $(PRJ_DIR)venv
PKGVENV ?= $(PRJ_DIR)pkg_venv

install: $(VENV) setup.py
	$(VENV)/bin/$(PYTHON) -m pip install -U .

$(VENV):
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/$(PYTHON) -m pip install -U wheel

uninstall: $(VENV)
	$(VENV)/bin/$(PYTHON) -m pip uninstall -y $(PKG_NAME)

clean:
	$(RM) -rf $(VENV) $(PKGVENV) dist/ build/ $(PKG_NAME).egg-info/

$(PKGVENV):
	$(PYTHON) -m venv $(PKGVENV)
	$(PKGVENV)/bin/$(PYTHON) -m pip install -U setuptools wheel twine

pkg: $(PKGVENV)
	$(PKGVENV)/bin/$(PYTHON) setup.py sdist bdist_wheel

$(PKG_NAME).egg-info/PKG-INFO: $(PKGVENV)
	$(PKGVENV)/bin/$(PYTHON) setup.py egg_info

version: $(PKG_NAME).egg-info/PKG-INFO
	@echo Evaluating pagkage version...
	$(eval PKG_VERSION := $(if $(PKG_VERSION),$(PKG_VERSION),$(shell grep -Po '(?<=^Version: ).*' $<)))
	@echo Version = $(PKG_VERSION)

upload: pkg version
	$(PKGVENV)/bin/$(PYTHON) -m twine upload dist/$(PKG_NAME)-$(PKG_VERSION)*

.PHONY: install clean uninstall pkg version
