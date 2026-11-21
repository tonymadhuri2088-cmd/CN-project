# Real lab setup (Linux only)

The simulated demo runs anywhere with Python. The **real** lab needs a Linux machine
(Kathara/NIKA do not run on Windows) with Docker.

## 1. Install
1. Docker Engine: https://docs.docker.com/engine/install/ , then `sudo usermod -aG docker $USER` and re-login.
2. Kathara: follow https://github.com/KatharaFramework/Kathara (Linux install section). Check: `kathara --version`.
3. Python 3.10+, then in this folder: `pip install -e ".[dev]" && pytest` (93 tests should pass).

## 2. Build the four labs
```
labs/inject.sh dns_failure
labs/inject.sh route_failure
labs/inject.sh port_blocked
labs/inject.sh healthy_false_alarm
```

## 3. Check one lab by hand (important: not yet verified on real Docker)
```
cd labs/healthy_false_alarm && kathara lstart --noterminals
kathara exec -d . h1 -- ping -c 3 10.0.2.10      # expect 0% packet loss
kathara exec -d . h1 -- dig +time=2 web.lab      # expect status: NOERROR, ANSWER: 1 (DNS server is on the h1 side: 10.0.1.53)
kathara exec -d . h1 -- sh -c 'nc -z -w 3 10.0.2.10 80; echo rc=$?'   # expect rc=0
kathara lclean
```
If a command is missing in the `kathara/base` image (dig, nc, traceroute, dnsmasq, iptables),
install it in that device's `.startup`, or tell me the exact error and I will adjust.
If `kathara exec` wants a different argument form, edit `build_exec_cmd` in `netwing/kathara.py`
(its unit test shows the form currently assumed).

## 4. Run
Run one lab at a time. For each scenario: build it, `kathara lstart` it, then run the demo against
that scenario only (`--scenarios <id> --backend kathara`), then `kathara lclean`.

## Quickest check: no Docker needed (netns backend)

If Kathara or Docker gives trouble, the real-network check works with plain Linux (needs root):

```
sudo apt install iproute2 dnsmasq netcat-openbsd dnsutils iputils-ping traceroute iptables
sudo NETWING_REAL_LAB=1 python3 -m pytest tests/test_netns_parity.py -q      # real network == simulator?
```

Expected: `4 passed`. It was run on a real Linux kernel on 2026-11-21 and passed. If a test fails, the assertion
prints which tool, which scenario, what the real network returned and what the simulator expected: send me that.

## Easiest path (Debian/Ubuntu): two scripts

```
bash setup_linux.sh      # installs tools, makes .venv, runs all tests, runs the real-network check (asks for sudo)
bash run_real_lab.sh     # runs the demo on the REAL network; asks for your API key (hidden, not saved)
```
`bash run_real_lab.sh 10 5` = 10 repeats with a $5 cap. Tested end to end on a clean Linux machine on 2026-11-21.
