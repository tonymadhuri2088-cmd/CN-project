#!/usr/bin/env bash
# One-time setup for a Debian/Ubuntu Linux machine: installs tools, makes a virtualenv, runs all tests,
# then runs the real-network check (needs sudo). Usage:  bash setup_linux.sh
set -euo pipefail
cd "$(dirname "$0")"
sed -i 's/\r$//' ./*.sh labs/*.sh 2>/dev/null || true   # in case the folder was copied from Windows

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This script supports Debian/Ubuntu (apt). On another distro install: iproute2 dnsmasq netcat-openbsd"
  echo "dnsutils iputils-ping traceroute iptables python3-venv, then run the steps below by hand."
  exit 1
fi
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "== 1/4 installing system tools"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq iproute2 dnsmasq netcat-openbsd dnsutils iputils-ping traceroute iptables \
  python3 python3-venv python3-pip
$SUDO systemctl disable --now dnsmasq >/dev/null 2>&1 || true   # the lab runs its own dnsmasq

echo "== 2/4 python environment"
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[dev]"

echo "== 3/4 unit tests"
python -m pytest -q

echo "== 4/4 real-network check (sudo): real Linux network must agree with the simulator"
$SUDO env "PATH=$PATH" NETWING_REAL_LAB=1 python -m pytest tests/test_netns_parity.py -q

echo
echo "SETUP OK. Next: bash run_real_lab.sh"
