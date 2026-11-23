# Security policy

NetWing is a research prototype. It runs diagnostic commands on a lab network and can call a paid model API, so these
are the properties it aims to keep and the things you should not do.

## Reporting
Open a private security advisory on GitHub (Security tab) or contact the maintainers directly. Please do not put
exploit details or credentials in a public issue.

## Secrets
- The API key is read only from the `ANTHROPIC_API_KEY` environment variable. Never put it in a file, a log, a
  screenshot or a chat. If one is exposed, revoke and replace it at once.
- Run logs contain model transcripts and tool output, not keys. Before committing a log, search it
  (`grep -il "sk-ant" results/*.jsonl`).

## Web UI (`python -m netwing.webui`)
- Binds to `127.0.0.1` by default. Requests with an unrecognised `Host` header are refused (DNS rebinding defence).
- Starting a run needs a per-process token that only the page itself carries, and a same-origin `Origin` header when
  the browser sends one (CSRF defence). Responses send `nosniff`, `X-Frame-Options: DENY` and a restrictive
  Content-Security-Policy.
- A run started from the UI is simulator-only and capped at $0.50.
- Do not expose the UI beyond loopback. The container image binds `0.0.0.0` for Docker port-mapping only; publish it
  to `127.0.0.1` (`-p 127.0.0.1:8765:8765`).

## Network backends
- The simulator touches nothing. The Linux-namespace and Kathara backends run commands against lab devices only, and
  tool arguments are checked against an allow-list of hosts, names and ports before anything runs.
- The namespace backend needs root and edits `/etc/netns`; run it in a disposable VM or WSL instance, not on a host
  you care about.

## Spend limits
`--cap` (total) and `--run-cap` (per run) are hard limits; a run that would exceed them stops and is marked
incomplete. Every record stores its cost.

## Scope
No claim is made that the controller is safe to put between an agent and a production network. It is evaluated on a
simulator and small lab networks.
