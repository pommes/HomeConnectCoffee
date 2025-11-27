THIS_DIR := $(shell pwd)
SRC_DIR := $(THIS_DIR)/src

VENV_DIR := $(THIS_DIR)/.venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
PYTHONPATH := $(SRC_DIR):$(PYTHONPATH)

SCRIPT_AUTH := $(THIS_DIR)/scripts/start_auth_flow.py
SCRIPT_BREW := $(THIS_DIR)/scripts/brew_espresso.py
SCRIPT_STATUS := $(THIS_DIR)/scripts/device_status.py
SCRIPT_EVENTS := $(THIS_DIR)/scripts/events.py
SCRIPT_WAKE := $(THIS_DIR)/scripts/wake_device.py
SCRIPT_SERVER := $(THIS_DIR)/scripts/server.py

FILL_ML ?= 50
STRENGTH ?= Normal
EVENTS_LIMIT ?= 0

.PHONY: init init_venv install_deps auth brew status events wake server clean_tokens

init: init_venv install_deps

init_venv:
	test -d $(VENV_DIR) || python3 -m venv $(VENV_DIR)

install_deps: init_venv
	@$(PIP) install -q -r requirements.txt

auth: init
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_AUTH) $(AUTH_ARGS)

brew: init
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_BREW) --fill-ml $(FILL_ML) --strength $(STRENGTH) $(BREW_ARGS)

status: init
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_STATUS) $(STATUS_ARGS)

events: init
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_EVENTS) --limit $(EVENTS_LIMIT) $(EVENTS_ARGS)

wake: init
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_WAKE)

server: init
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_SERVER) $(SERVER_ARGS)

clean_tokens:
	rm -f $(HOME_CONNECT_TOKEN_PATH) tokens.json

