THIS_DIR := $(shell pwd)

VENV_DIR := $(THIS_DIR)/.venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

SCRIPT_AUTH := $(THIS_DIR)/scripts/start_auth_flow.py
SCRIPT_BREW := $(THIS_DIR)/scripts/brew_espresso.py
SCRIPT_STATUS := $(THIS_DIR)/scripts/device_status.py
SCRIPT_EVENTS := $(THIS_DIR)/scripts/events.py

FILL_ML ?= 60
STRENGTH ?= Normal
EVENTS_LIMIT ?= 0

.PHONY: init init_venv install_deps auth brew status events clean_tokens

init: init_venv install_deps

init_venv:
	test -d $(VENV_DIR) || python3 -m venv $(VENV_DIR)

install_deps: init_venv
	$(PIP) install -r requirements.txt

auth: init
	$(PYTHON) $(SCRIPT_AUTH) $(AUTH_ARGS)

brew: init
	$(PYTHON) $(SCRIPT_BREW) --fill-ml $(FILL_ML) --strength $(STRENGTH) $(BREW_ARGS)

status: init
	$(PYTHON) $(SCRIPT_STATUS) $(STATUS_ARGS)

events: init
	$(PYTHON) $(SCRIPT_EVENTS) --limit $(EVENTS_LIMIT) $(EVENTS_ARGS)

clean_tokens:
	rm -f $(HOME_CONNECT_TOKEN_PATH) tokens.json

