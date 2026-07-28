#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  osascript -e 'display alert "Setup required" message "Please double-click Setup.command first."'
  exit 1
fi
source .venv/bin/activate
python browser_app.py
