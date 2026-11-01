#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]] ||
   ! PYTHONPATH="$ROOT/tooling/vendor" .venv/bin/python -c \
      'import edlclient, usb.core' >/dev/null 2>&1; then
  tooling/scripts/setup.sh
fi

exec .venv/bin/python tooling/scripts/install-release.py --guided
