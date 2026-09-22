#!/usr/bin/env bash
# Generate the five Seedance 2.5 shots, then cut the 20s master.
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

python3 scripts/generate.py "$@"
python3 scripts/assemble.py
