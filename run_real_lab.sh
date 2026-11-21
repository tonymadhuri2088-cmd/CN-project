#!/usr/bin/env bash
# Runs the demo against the REAL Linux network (namespaces). Asks for your API key (hidden, never saved).
# Usage:  bash run_real_lab.sh            (3 repeats, $3 cap)
#         bash run_real_lab.sh 10 5       (10 repeats, $5 cap)
set -euo pipefail
cd "$(dirname "$0")"
REPEATS="${1:-3}"; CAP="${2:-3}"
[ -d .venv ] || { echo "Run  bash setup_linux.sh  first."; exit 1; }
# shellcheck disable=SC1091
. .venv/bin/activate
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  read -rsp "Paste your Anthropic API key (hidden): " ANTHROPIC_API_KEY; echo
fi
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
$SUDO env "PATH=$PATH" ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  python -m netwing.demo --backend netns --suite easy --repeats "$REPEATS" --cap "$CAP"
