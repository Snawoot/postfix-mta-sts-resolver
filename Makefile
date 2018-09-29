PYTHON = python3
RM = rm

PRJ_DIR = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV ?= $(PRJ_DIR)venv

install: $(VENV) setup.py
	$(VENV)/bin/pip install -U .

$(VENV):
	$(PYTHON) -m venv $(VENV)

uninstall: $(VENV)
	$(VENV)/bin/pip uninstall -y postfix_mta_sts_resolver

clean:
	$(RM) -rf $(VENV)

