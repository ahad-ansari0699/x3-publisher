#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Setting up X3 Publisher Alpha..."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo
echo "Setup complete. Double-click X3 Publisher.command."
read -n 1 -s -r -p "Press any key to close..."
