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

.PHONY: init init_venv install_deps auth brew status events wake server dashboard clean_tokens cert cert_install cert_export fix_history migrate_history export_history

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

cert: $(CERT_FILE) $(KEY_FILE)

$(CERT_DIR):
	mkdir -p $(CERT_DIR)

$(CERT_FILE) $(KEY_FILE): $(CERT_DIR)
	@echo "Erstelle selbstsigniertes Zertifikat..."
	openssl req -x509 -newkey rsa:4096 -keyout $(KEY_FILE) -out $(CERT_FILE) \
		-days 3650 -nodes -subj "/CN=HomeConnectCoffee/O=HomeConnect Coffee/C=DE" \
		-addext "subjectAltName=DNS:localhost,DNS:*.local,DNS:elias.local,IP:127.0.0.1"
	@chmod 600 $(KEY_FILE)
	@chmod 644 $(CERT_FILE)
	@echo "Zertifikat erstellt: $(CERT_FILE)"
	@echo "Private Key erstellt: $(KEY_FILE)"

cert_install: $(CERT_FILE)
	@echo "Installiere Zertifikat im Mac Schlüsselbund..."
	security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain-db $(CERT_FILE) || \
	security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain $(CERT_FILE) || \
	security add-trusted-cert -d -r trustRoot $(CERT_FILE)
	@echo "Zertifikat wurde im Schlüsselbund installiert."

cert_export: $(CERT_FILE)
	@echo "Öffne Finder mit Zertifikat für AirDrop..."
	@open -R $(CERT_FILE)
	@echo "Zertifikat-Datei wurde im Finder geöffnet."
	@echo "Du kannst es jetzt per AirDrop zu deinem iOS-Gerät senden."

fix_history:
	@echo "Verarbeite vorhandene Events in der History..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/fix_history.py

migrate_history: init
	@echo "Migriere Events von history.json zu history.db..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/migrate_to_sqlite.py

export_history: init
	@echo "Exportiere Events von history.db zu history.json..."
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/export_to_json.py

