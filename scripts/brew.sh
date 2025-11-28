#!/bin/bash
# Shell script to start an espresso
# Can be used in Siri Shortcuts

cd "$(dirname "$0")/.." || exit 1

# Optional parameters
FILL_ML=${1:-50}  # Default: 50 ml

make brew FILL_ML="$FILL_ML"

