#!/bin/bash
# Shell-Script zum Aktivieren der Kaffeemaschine
# Kann in Siri Shortcuts verwendet werden

cd "$(dirname "$0")/.." || exit 1
make wake

