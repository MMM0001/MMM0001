#!/bin/bash
# Double-click this file (Mac) to start the arbitrage dashboard.
# It sets everything up the first time, then opens the dashboard in your browser.

cd "$(dirname "$0")" || exit 1

echo "Starting the arbitrage dashboard..."
echo "Folder: $(pwd)"

# Guard: are the project files actually here? If not, the ZIP probably
# wasn't extracted before running this.
if [ ! -f "requirements.txt" ]; then
  echo
  echo "  I can't find the project files in this folder."
  echo "  Make sure you UNZIPPED the download first, then double-click this"
  echo "  launcher from inside the extracted folder."
  echo
  read -r -p "Press Enter to close."
  exit 1
fi

# Find Python 3.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo
  echo "  Python is not installed yet."
  echo "  Install it from https://www.python.org/downloads/ (the big yellow button),"
  echo "  then double-click this file again."
  echo
  read -r -p "Press Enter to close."
  exit 1
fi

# Create an isolated environment the first time, then reuse it.
if [ ! -d ".venv" ]; then
  echo "First-time setup (this takes a minute)..."
  "$PY" -m venv .venv || { echo "Setup failed."; read -r -p "Press Enter to close."; exit 1; }
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip >/dev/null 2>&1
pip install -q -r requirements.txt || { echo "Install failed."; read -r -p "Press Enter to close."; exit 1; }

python -m src.arb.webapp --open
