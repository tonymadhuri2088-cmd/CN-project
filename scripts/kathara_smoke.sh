#!/usr/bin/env bash
# Kathara smoke test: build the four labs, start each, run the three checks the NetWing backend relies on
# (ping, dig, nc) and compare with the expected outcome. Needs Linux (or WSL) with Docker and Kathara.
# Usage (from the repo root):  bash scripts/kathara_smoke.sh   -> writes results/kathara_smoke.txt
set -uo pipefail
cd "$(dirname "$0")/.."
out=results/kathara_smoke.txt
: > "$out"
log() { echo "$*" | tee -a "$out"; }
for t in docker kathara; do
  command -v "$t" >/dev/null || { log "MISSING: $t is not installed (see SETUP_LINUX.md section 1)"; exit 1; }
done
log "kathara: $(kathara --version 2>&1 | head -1)"
fail=0
check() {  # check <lab> <name> <expect: ok|fail> <exit code>
  local want="$3" rc="$4" got=fail
  [ "$rc" -eq 0 ] && got=ok
  if [ "$got" = "$want" ]; then log "  PASS $1 $2 (expected $want)"; else log "  FAIL $1 $2 (expected $want, got $got)"; fail=1; fi
}
# lab | ping expect | dig expect | port expect
run_lab() {
  local lab="$1" p="$2" d="$3" n="$4"
  log "== $lab"
  bash labs/inject.sh "$lab" >>"$out" 2>&1
  ( cd "labs/$lab" || exit 1
    kathara lclean >/dev/null 2>&1
    kathara lstart --noterminals >>"../../$out" 2>&1 || { echo "  FAIL $lab lstart"; exit 3; }
    sleep 20
    kathara exec -d . h1 -- ping -c 3 -W 2 10.0.2.10 >>"../../$out" 2>&1; echo "$?" > /tmp/ks_p
    kathara exec -d . h1 -- sh -c 'dig +time=2 +tries=1 web.lab | grep -q "status: NOERROR"' >>"../../$out" 2>&1; echo "$?" > /tmp/ks_d
    kathara exec -d . h1 -- sh -c 'nc -z -w 3 10.0.2.10 80' >>"../../$out" 2>&1; echo "$?" > /tmp/ks_n
    kathara lclean >/dev/null 2>&1 )
  [ $? -eq 3 ] && { fail=1; return; }
  check "$lab" ping "$p" "$(cat /tmp/ks_p)"
  check "$lab" dns  "$d" "$(cat /tmp/ks_d)"
  check "$lab" port "$n" "$(cat /tmp/ks_n)"
}
run_lab healthy_false_alarm ok   ok   ok
run_lab dns_failure         ok   fail ok
run_lab route_failure       fail fail fail
run_lab port_blocked        ok   ok   fail
[ "$fail" -eq 0 ] && log "ALL CHECKS PASSED" || log "SOME CHECKS FAILED: send results/kathara_smoke.txt"
exit "$fail"
