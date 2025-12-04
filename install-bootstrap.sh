#!/bin/sh
# Bootstrap script to download and run install.sh from GitHub Release
#
# Usage: ./install-bootstrap.sh <release-tag> [install.sh options]
# Example: ./install-bootstrap.sh v1.2.1 --skip-deps

set -e

RELEASE_TAG="${1:-latest}"

if [ "$RELEASE_TAG" = "latest" ]; then
    echo "Downloading latest release..."
    # Get latest release tag from GitHub API
    RELEASE_TAG=$(curl -s https://api.github.com/repos/pommes/HomeConnectCoffee/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -z "$RELEASE_TAG" ]; then
        echo "Error: Could not determine latest release tag"
        exit 1
    fi
    echo "Latest release: $RELEASE_TAG"
fi

INSTALL_SCRIPT_URL="https://github.com/pommes/HomeConnectCoffee/releases/download/$RELEASE_TAG/install.sh"

echo "Downloading install.sh from release $RELEASE_TAG..."
if ! curl -L -f -o /tmp/install.sh "$INSTALL_SCRIPT_URL"; then
    echo "Error: Failed to download install.sh from release $RELEASE_TAG"
    echo "Please verify that the release exists: https://github.com/pommes/HomeConnectCoffee/releases/tag/$RELEASE_TAG"
    exit 1
fi

chmod +x /tmp/install.sh

# Pass all arguments (including release tag) to install.sh
echo "Running install.sh..."
exec /tmp/install.sh "$@"

