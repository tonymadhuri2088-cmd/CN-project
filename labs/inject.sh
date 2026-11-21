#!/usr/bin/env bash
# Build one scenario lab from labs/base with exactly one fault.
# Usage: labs/inject.sh <dns_failure|route_failure|port_blocked|healthy_false_alarm>
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
id="${1:?usage: inject.sh <scenario_id>}"
dest="$here/$id"
rm -rf "$dest"
cp -r "$here/base" "$dest"
case "$id" in
  dns_failure)         { echo "touch /etc/netwing-no-dns"; cat "$dest/dns.startup"; } > "$dest/dns.tmp" && mv "$dest/dns.tmp" "$dest/dns.startup" ;;
  route_failure)       echo "ip route del 10.0.2.0/24 dev eth1" >> "$dest/r1.startup" ;;
  port_blocked)        echo "iptables -A INPUT -p tcp --dport 80 -j DROP" >> "$dest/h2.startup" ;;
  healthy_false_alarm) : ;;  # no fault on purpose: the ticket is wrong
  *) echo "unknown scenario: $id" >&2; exit 2 ;;
esac
echo "built $dest"
