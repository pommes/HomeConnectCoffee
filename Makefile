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

.PHONY: help init init_venv install_deps auth brew status events wake server dashboard clean_tokens cert cert_install cert_export fix_history migrate_history export_history sync_history_db test test-unit test-cov release release-dev release-alpha release-beta release-rc

help: ## This help
	@echo "----------------------------"
	@echo "Available targets:"
	@grep -Eh '^[0-9a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'


init: init_venv install_deps ## Setup virtual environment and install dependencies

init_venv: ## Create Python virtual environment
	test -d $(VENV_DIR) || python3 -m venv $(VENV_DIR)

install_deps: init_venv ## Install Python dependencies from requirements.txt
	@$(PIP) install -q -r requirements.txt

auth: init ## Start OAuth authentication flow (AUTH_ARGS=...)
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_AUTH) $(AUTH_ARGS)

brew: init ## Brew espresso with specified fill amount (FILL_ML=50, STRENGTH=Normal, BREW_ARGS=...)
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_BREW) --fill-ml $(FILL_ML) --strength $(STRENGTH) $(BREW_ARGS)

status: init ## Show device status (STATUS_ARGS=...)
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_STATUS) $(STATUS_ARGS)

events: init ## Monitor event stream (EVENTS_LIMIT=0, EVENTS_ARGS=...)
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_EVENTS) --limit $(EVENTS_LIMIT) $(EVENTS_ARGS)

wake: init ## Wake device from standby
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_WAKE)

server: init ## Start HTTP server (SERVER_ARGS=...)
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_SERVER) $(SERVER_ARGS)

dashboard: init ## Start HTTP server (alias for server) (SERVER_ARGS=...)
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_SERVER) $(SERVER_ARGS)

clean_tokens: ## Remove token files
	rm -f $(HOME_CONNECT_TOKEN_PATH) tokens.json

CERT_DIR := $(THIS_DIR)/certs
CERT_FILE := $(CERT_DIR)/server.crt
KEY_FILE := $(CERT_DIR)/server.key
# Optional: Specific hostname for the certificate (loaded from .env if present)
# Can also be overridden as Make variable: make cert CERT_HOSTNAME=my-hostname.local
CERT_HOSTNAME ?= $(shell grep -E '^CERT_HOSTNAME=' $(THIS_DIR)/.env 2>/dev/null | cut -d '=' -f2- || echo "")

cert: $(CERT_FILE) $(KEY_FILE) ## Generate self-signed SSL certificate (CERT_HOSTNAME=...)

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

cert_install: $(CERT_FILE) ## Install certificate in Mac keychain
	@echo "Installing certificate in Mac keychain..."
	security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain-db $(CERT_FILE) || \
	security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain $(CERT_FILE) || \
	security add-trusted-cert -d -r trustRoot $(CERT_FILE)
	@echo "Certificate has been installed in keychain."

cert_export: $(CERT_FILE) ## Open certificate in Finder for AirDrop
	@echo "Opening Finder with certificate for AirDrop..."
	@open -R $(CERT_FILE)
	@echo "Certificate file has been opened in Finder."
	@echo "You can now send it to your iOS device via AirDrop."

fix_history: ## Process existing events and add missing program_started events
	@echo "Processing existing events in history..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/fix_history.py

migrate_history: init ## Migrate events from history.json to history.db
	@echo "Migrating events from history.json to history.db..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/migrate_to_sqlite.py

export_history: init ## Export events from history.db to history.json
	@echo "Exporting events from history.db to history.json..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/export_to_json.py

sync_history_db: ## Sync history.db from remote host to local development environment
	@echo "Syncing history.db from Raspberry Pi to local development environment..."
	@$(THIS_DIR)/scripts/sync_history_db.sh

test: init ## Run all tests
	@echo "Running tests..."
	@PYTHONPATH=$(PYTHONPATH) $(VENV_DIR)/bin/pytest

test-unit: init ## Run unit tests only
	@echo "Running unit tests..."
	@PYTHONPATH=$(PYTHONPATH) $(VENV_DIR)/bin/pytest -m unit

test-cov: init ## Run tests with coverage report
	@echo "Running tests with coverage report..."
	@PYTHONPATH=$(PYTHONPATH) $(VENV_DIR)/bin/pytest --cov=src/homeconnect_coffee --cov-report=term-missing --cov-report=html

# Release targets
release: init ## Create release version (remove prerelease suffix) (RELEASE_ARGS=...)
	@echo "Creating release (removing prerelease suffix)..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --release $(RELEASE_ARGS)

release-dev: init ## Create development version (RELEASE_ARGS=...)
	@echo "Creating development version..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --dev $(RELEASE_ARGS)

release-alpha: init ## Create alpha pre-release (RELEASE_ARGS=...)
	@echo "Creating alpha pre-release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --alpha $(RELEASE_ARGS)

release-beta: init ## Create beta pre-release (RELEASE_ARGS=...)
	@echo "Creating beta pre-release..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --beta $(RELEASE_ARGS)

release-rc: init ## Create release candidate (RELEASE_ARGS=...)
	@echo "Creating release candidate..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(SCRIPT_RELEASE) --rc $(RELEASE_ARGS)

