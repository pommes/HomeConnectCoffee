#!/bin/sh
set -e

# ------------------------------
# HomeConnectCoffee Installer
# ------------------------------

# Parse command line arguments
SKIP_DEPS=0
SKIP_RESTART=0
NEW_ARGS=""
SERVER_USER=""
SERVER_HOST=""
SERVER_PORT=""
API_TOKEN=""

while [ $# -gt 0 ]; do
    case "$1" in
        --skip-deps)
            SKIP_DEPS=1
            shift
            ;;
        --skip-restart)
            SKIP_RESTART=1
            shift
            ;;
        --user)
            SERVER_USER="$2"
            shift 2
            ;;
        --host)
            SERVER_HOST="$2"
            shift 2
            ;;
        --port)
            SERVER_PORT="$2"
            shift 2
            ;;
        --api-token)
            API_TOKEN="$2"
            shift 2
            ;;
        *)
            NEW_ARGS="$NEW_ARGS $1"
            shift
            ;;
    esac
done

# Remove leading space and set new arguments
if [ -n "$NEW_ARGS" ]; then
    set -- $(echo "$NEW_ARGS" | sed 's/^ *//')
else
    set --
fi

# Variables
RELEASE_TAG="$1"
if [ -z "$RELEASE_TAG" ]; then
    echo "Usage: $0 <Release-Tag> [--skip-deps] [--skip-restart] [--user USER] [--host HOST] [--port PORT] [--api-token TOKEN]"
    echo "Example: $0 v1.2.1"
    exit 1
fi

INSTALL_DIR="/opt/homeconnect_coffee/$RELEASE_TAG"
VENV_DIR="$INSTALL_DIR/.venv"

# ------------------------------
# Load .env file if present
# ------------------------------
ENV_FILE="/opt/homeconnect_coffee/.env"
if [ -f "$ENV_FILE" ]; then
    # Parse .env file (simple KEY=VALUE parsing, POSIX-compatible)
    while IFS='=' read -r key value || [ -n "$key" ]; do
        # Skip comments and empty lines
        case "$key" in
            \#*|'') continue ;;
        esac
        # Remove leading/trailing whitespace
        key=$(echo "$key" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
        value=$(echo "$value" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
        # Remove quotes if present
        value=$(echo "$value" | sed "s/^['\"]//; s/['\"]$//")
        # Export variable if not already set by command line
        case "$key" in
            COFFEE_SERVER_USER)
                [ -z "$SERVER_USER" ] && export COFFEE_SERVER_USER="$value"
                ;;
            COFFEE_SERVER_HOST)
                [ -z "$SERVER_HOST" ] && export COFFEE_SERVER_HOST="$value"
                ;;
            COFFEE_SERVER_PORT)
                [ -z "$SERVER_PORT" ] && export COFFEE_SERVER_PORT="$value"
                ;;
            COFFEE_API_TOKEN)
                [ -z "$API_TOKEN" ] && export COFFEE_API_TOKEN="$value"
                ;;
            *)
                export "$key=$value"
                ;;
        esac
    done < "$ENV_FILE"
fi

# Set default values (command line args override .env, .env overrides defaults)
SERVER_USER="${SERVER_USER:-${COFFEE_SERVER_USER:-$USER}}"
SERVER_HOST="${SERVER_HOST:-${COFFEE_SERVER_HOST:-0.0.0.0}}"
SERVER_PORT="${SERVER_PORT:-${COFFEE_SERVER_PORT:-8080}}"
API_TOKEN="${API_TOKEN:-${COFFEE_API_TOKEN:-}}"

# ------------------------------
# Install system dependencies (optional)
# ------------------------------
if [ $SKIP_DEPS -eq 0 ]; then
    echo "Installing system dependencies..."
    sudo apt update
    sudo apt install -y python3-venv python3-pip tar curl
else
    echo "Skipping system dependencies (--skip-deps set)."
fi

# ------------------------------
# Prepare installation directory
# ------------------------------
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER:$USER" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# ------------------------------
# Download release
# ------------------------------
TAR_URL="https://github.com/pommes/HomeConnectCoffee/archive/refs/tags/$RELEASE_TAG.tar.gz"
echo "Downloading release $RELEASE_TAG..."
if ! curl -L -f -o release.tar.gz "$TAR_URL"; then
    echo "Error: Failed to download release $RELEASE_TAG"
    echo "Please verify that the release tag exists: https://github.com/pommes/HomeConnectCoffee/releases"
    exit 1
fi

# ------------------------------
# Extract
# ------------------------------
tar -xzf release.tar.gz --strip-components=1
rm release.tar.gz

# ------------------------------
# Create virtual environment
# ------------------------------
python3 -m venv "$VENV_DIR"
. "$VENV_DIR/bin/activate"

# ------------------------------
# Create symlinks to configs and data
# ------------------------------
BASE_DIR="/opt/homeconnect_coffee"
[ -f "$BASE_DIR/tokens.json" ] && ln -sf ../tokens.json tokens.json || true
[ -d "$BASE_DIR/certs" ] && ln -sf ../certs certs || true
[ -f "$BASE_DIR/.env" ] && ln -sf ../.env .env || true
[ -f "$BASE_DIR/history.db" ] && ln -sf ../history.db history.db || true

# ------------------------------
# Update current symlink
# ------------------------------
cd "$BASE_DIR"
rm -f current
ln -sf "$RELEASE_TAG" current

# ------------------------------
# Install Python dependencies
# ------------------------------
cd "$INSTALL_DIR"
if [ -f requirements.txt ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# ------------------------------
# Create systemd service
# ------------------------------
SERVICE_FILE="/etc/systemd/system/homeconnect_coffee.service"
echo "Creating systemd service..."

# Build ExecStart command
EXEC_START="/usr/bin/env PYTHONPATH=/opt/homeconnect_coffee/current/src /opt/homeconnect_coffee/current/.venv/bin/python3 /opt/homeconnect_coffee/current/scripts/server.py --host $SERVER_HOST --port $SERVER_PORT"
if [ -n "$API_TOKEN" ]; then
    EXEC_START="$EXEC_START --api-token $API_TOKEN"
fi
EXEC_START="$EXEC_START --cert certs/server.crt --key certs/server.key"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=HomeConnect Coffee Controller
After=network.target

[Service]
User=$SERVER_USER
WorkingDirectory=/opt/homeconnect_coffee/current
ExecStart=$EXEC_START
Restart=always
StandardOutput=journal+file:/var/log/homeconnect_coffee.log
StandardError=journal+file:/var/log/homeconnect_coffee.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable homeconnect_coffee

if [ $SKIP_RESTART -eq 0 ]; then
    # Check if service is running before restarting
    if systemctl is-active --quiet homeconnect_coffee; then
        echo "Restarting service..."
        sudo systemctl restart homeconnect_coffee
    else
        echo "Starting service..."
        sudo systemctl start homeconnect_coffee
    fi
    sudo systemctl status homeconnect_coffee --no-pager || true
else
    echo "Skipping service restart (--skip-restart set)."
    echo "To start the service manually, run: sudo systemctl start homeconnect_coffee"
fi

echo "----------------------------------------"
echo "Installation completed! Service is running."
echo "For debugging: 'journalctl -u homeconnect_coffee -f'"
echo "Logs: /var/log/homeconnect_coffee.log"
echo ""
echo "To rollback to a previous version, run:"
echo "  cd /opt/homeconnect_coffee"
echo "  rm current && ln -s <previous-version> current"
echo "  sudo systemctl restart homeconnect_coffee"
