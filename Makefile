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
SCRIPT_RELEASE := $(THIS_DIR)/scripts/release.py

FILL_ML ?= 50
STRENGTH ?= Normal
EVENTS_LIMIT ?= 0

.PHONY: init init_venv install_deps auth brew status events wake server dashboard clean_tokens cert cert_install cert_export fix_history migrate_history export_history test test-unit test-cov release-patch release-minor release-major release-dev release-alpha release-beta release-rc

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

dashboard: init
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_SERVER) $(SERVER_ARGS)

clean_tokens:
	rm -f $(HOME_CONNECT_TOKEN_PATH) tokens.json

CERT_DIR := $(THIS_DIR)/certs
CERT_FILE := $(CERT_DIR)/server.crt
KEY_FILE := $(CERT_DIR)/server.key
# Optional: Specific hostname for the certificate (loaded from .env if present)
# Can also be overridden as Make variable: make cert CERT_HOSTNAME=my-hostname.local
CERT_HOSTNAME ?= $(shell grep -E '^CERT_HOSTNAME=' $(THIS_DIR)/.env 2>/dev/null | cut -d '=' -f2- || echo "")

cert: $(CERT_FILE) $(KEY_FILE)

$(CERT_DIR):
	mkdir -p $(CERT_DIR)

$(CERT_FILE) $(KEY_FILE): $(CERT_DIR)
	@echo "Creating self-signed certificate..."
	@if [ -n "$(CERT_HOSTNAME)" ]; then \
		echo "Adding hostname $(CERT_HOSTNAME) to certificate..."; \
		openssl req -x509 -newkey rsa:4096 -keyout $(KEY_FILE) -out $(CERT_FILE) \
			-days 3650 -nodes -subj "/CN=HomeConnectCoffee/O=HomeConnect Coffee/C=DE" \
			-addext "subjectAltName=DNS:localhost,DNS:*.local,DNS:$(CERT_HOSTNAME),IP:127.0.0.1"; \
	else \
		openssl req -x509 -newkey rsa:4096 -keyout $(KEY_FILE) -out $(CERT_FILE) \
			-days 3650 -nodes -subj "/CN=HomeConnectCoffee/O=HomeConnect Coffee/C=DE" \
			-addext "subjectAltName=DNS:localhost,DNS:*.local,IP:127.0.0.1"; \
	fi
	@chmod 600 $(KEY_FILE)
	@chmod 644 $(CERT_FILE)
	@echo "Certificate created: $(CERT_FILE)"
	@echo "Private key created: $(KEY_FILE)"

cert_install: $(CERT_FILE)
	@echo "Installing certificate in Mac keychain..."
	security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain-db $(CERT_FILE) || \
	security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain $(CERT_FILE) || \
	security add-trusted-cert -d -r trustRoot $(CERT_FILE)
	@echo "Certificate has been installed in keychain."

cert_export: $(CERT_FILE)
	@echo "Opening Finder with certificate for AirDrop..."
	@open -R $(CERT_FILE)
	@echo "Certificate file has been opened in Finder."
	@echo "You can now send it to your iOS device via AirDrop."

fix_history:
	@echo "Processing existing events in history..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/fix_history.py

migrate_history: init
	@echo "Migrating events from history.json to history.db..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/migrate_to_sqlite.py

export_history: init
	@echo "Exporting events from history.db to history.json..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/export_to_json.py

test: init
	@echo "Running tests..."
	@PYTHONPATH=$(PYTHONPATH) $(VENV_DIR)/bin/pytest

test-unit: init
	@echo "Running unit tests..."
	@PYTHONPATH=$(PYTHONPATH) $(VENV_DIR)/bin/pytest -m unit

test-cov: init
	@echo "Running tests with coverage report..."
	@PYTHONPATH=$(PYTHONPATH) $(VENV_DIR)/bin/pytest --cov=src/homeconnect_coffee --cov-report=term-missing --cov-report=html

# Release targets
release-patch: init
	@echo "Creating patch release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --patch $(RELEASE_ARGS)

release-minor: init
	@echo "Creating minor release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --minor $(RELEASE_ARGS)

release-major: init
	@echo "Creating major release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --major $(RELEASE_ARGS)

release-dev: init
	@echo "Creating development release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --patch --dev $(RELEASE_ARGS)

release-alpha: init
	@echo "Creating alpha release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --patch --alpha $(RELEASE_ARGS)

release-beta: init
	@echo "Creating beta release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --patch --beta $(RELEASE_ARGS)

release-rc: init
	@echo "Creating release candidate..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --patch --rc $(RELEASE_ARGS)

