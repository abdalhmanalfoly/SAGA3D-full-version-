#!/usr/bin/env bash
# Run every automated test: Python host + contract, then browser-logic tests under Node.
set -uo pipefail
cd "$(dirname "$0")/.."
rc=0
# venv detection: Windows-aware (same fix adopted in run_host.sh, from the phase-2 workspace edit).
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
else
  echo "No usable Python found in .venv. Check your virtual environment." >&2
  exit 1
fi
echo "== Python (host, protocol, JS<->Python contract) =="; "$PY" -m pytest || rc=1
if command -v node >/dev/null; then
  echo "== Node (browser protocol/state/transport) =="; (cd sensor-client && node --test tests/*.test.mjs) || rc=1
else echo "node not found: skipping browser-logic tests (contract test is skipped too)"; fi
exit $rc
