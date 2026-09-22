#!/usr/bin/env bash
# Full render for one ad:  ./produce.sh hvac-01
set -euo pipefail
cd "$(dirname "$0")"
AD="${1:-hvac-01}"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
python3 engine/generate.py  "$AD"
python3 engine/voiceover.py "$AD"
python3 engine/assemble.py  "$AD"
