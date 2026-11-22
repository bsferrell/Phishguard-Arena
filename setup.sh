#!/bin/sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ ! -e .venv ]; then
    if ! command -v python3.13 >/dev/null 2>&1; then
        echo "Python 3.13 was not found. Install it from https://www.python.org/downloads/ and try again." >&2
        exit 1
    fi
    python3.13 -m venv .venv
fi

python=.venv/bin/python
if [ ! -x "$python" ]; then
    echo "The existing .venv does not contain a usable macOS Python interpreter." >&2
    exit 1
fi

"$python" -c 'import sys; sys.exit("The existing .venv must use Python 3.13.") if sys.version_info[:2] != (3, 13) else None'
"$python" -m pip install --upgrade pip
"$python" -m pip install -r requirements.txt
"$python" check_fts5.py

if [ -e data/phishguard.db ]; then
    echo "Existing database kept unchanged; skipping seed."
else
    "$python" seed_db.py
fi

echo "Setup complete. Start the game with:"
echo "  .venv/bin/python -m streamlit run app.py"
