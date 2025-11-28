#!/bin/bash
# Shell script to activate the coffee machine
# Can be used in Siri Shortcuts

cd "$(dirname "$0")/.." || exit 1
make wake

