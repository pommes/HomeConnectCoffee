#!/bin/bash
# Script zum Kopieren der history.db vom Raspberry Pi zur lokalen Entwicklungsumgebung

set -e  # Exit on error

# Load .env file if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
    # Source .env file (shell-typical way)
    # Note: This requires the .env file to be trusted (no malicious code)
    set -a  # Automatically export all variables
    source "$ENV_FILE"
    set +a  # Disable automatic export
fi

# Configuration with defaults (can be overridden via .env)
RASPBERRY_PI="${SYNC_DB_REMOTE_HOST:-user@hostname.local}"
REMOTE_DB_PATH="${SYNC_DB_REMOTE_PATH:-/opt/homeconnect_coffee/history.db}"
LOCAL_DB_PATH="${SYNC_DB_LOCAL_PATH:-$PROJECT_ROOT/history.db}"
LOCAL_BACKUP_PATH="${SYNC_DB_LOCAL_BACKUP_PATH:-$PROJECT_ROOT/history.db.local.backup}"

echo "🔄 Stopping HomeConnect Coffee service on Raspberry Pi..."
ssh -o BatchMode=yes -o ConnectTimeout=10 "$RASPBERRY_PI" "sudo systemctl stop homeconnect_coffee" || {
    echo "⚠️  Warning: Could not stop service (might not be running as service)"
}

echo "📦 Creating local backup..."
if [ -f "$LOCAL_DB_PATH" ]; then
    cp "$LOCAL_DB_PATH" "$LOCAL_BACKUP_PATH"
    echo "✅ Local backup created: $(basename $LOCAL_BACKUP_PATH)"
else
    echo "ℹ️  No local history.db found, skipping local backup"
fi

echo "📦 Creating backup on Raspberry Pi..."
ssh -o BatchMode=yes -o ConnectTimeout=10 "$RASPBERRY_PI" "sudo cp $REMOTE_DB_PATH ${REMOTE_DB_PATH}.backup && sudo chown tim:tim ${REMOTE_DB_PATH}.backup" || {
    echo "❌ Error: Could not create backup on Raspberry Pi"
    exit 1
}
echo "✅ Backup created on Raspberry Pi: history.db.backup"

echo "📥 Copying history.db from Raspberry Pi..."
scp -o BatchMode=yes -o ConnectTimeout=10 "$RASPBERRY_PI:$REMOTE_DB_PATH" "$LOCAL_DB_PATH" || {
    echo "❌ Error: Could not copy database"
    exit 1
}
echo "✅ Database copied successfully"

echo "🔄 Starting HomeConnect Coffee service on Raspberry Pi..."
ssh -o BatchMode=yes -o ConnectTimeout=10 "$RASPBERRY_PI" "sudo systemctl start homeconnect_coffee" || {
    echo "⚠️  Warning: Could not start service (might need manual start)"
}

echo ""
echo "✅ Done! Database copied to: $LOCAL_DB_PATH"
if [ -f "$LOCAL_BACKUP_PATH" ]; then
    echo "📋 Local backup available at: $LOCAL_BACKUP_PATH"
fi

