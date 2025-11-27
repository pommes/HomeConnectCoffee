#!/bin/bash
# Shell-Script zum Starten eines Espressos
# Kann in Siri Shortcuts verwendet werden

cd "$(dirname "$0")/.." || exit 1

# Optionale Parameter
FILL_ML=${1:-50}  # Standard: 50 ml

make brew FILL_ML="$FILL_ML"

