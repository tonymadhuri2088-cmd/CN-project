# Deploying the public demo

The public demo is the NetWing web UI in **read-only mode**. It shows the recorded investigations, the headline results and the
reproducibility table. It cannot start runs, holds no API key and makes no model calls, so a public link costs nothing and cannot be abused
to spend credit.

What the image contains: the Python package, the frozen run logs (`results/*.jsonl`) and `docs/research/claims.json`. On start-up the server
imports the `run-*.jsonl` logs into a throw-away SQLite history and recomputes every documented number from the raw logs.

## Option A: Render (no credit card for the free plan)

1. Push this repository to GitHub (already done).
2. On <https://render.com> choose **New → Blueprint**, connect the GitHub repository and pick the `main` branch.
   Render reads `render.yaml` and builds the `Dockerfile`.
3. Wait for the first build (about 3 to 5 minutes). Your URL is shown on the service page, in the form `https://netwing-demo-xxxx.onrender.com`.
4. Open the URL. The Overview page should show **42/42** documented numbers reproducing. `/healthz` returns `ok`.

The free plan stops the service after about 15 minutes without traffic; the next visit takes roughly 30 to 60 seconds to wake it. Open the link
once before you present it.

## Option B: Fly.io (needs a card; faster wake-up)

```bash
fly auth login
fly launch --copy-config --no-deploy      # keep the app name and region from fly.toml, or change them
fly deploy
```

## Check it locally first

```bash
docker build -t netwing-demo .
docker run --rm -p 8765:8765 netwing-demo
# open http://127.0.0.1:8765
```

Without Docker: `python -m netwing.webui --results results --read-only`.

## Safety properties (tested in `tests/test_site.py` and `tests/test_security.py`)

* Every `POST` returns 403 in read-only mode, and the Run page shows no form.
* `ANTHROPIC_API_KEY` is never consulted; do not set it on the host.
* No JavaScript is served; the Content-Security-Policy is `default-src 'none'` with inline styles only.
* The container runs as an unprivileged user.

## Updating the demo

Commit and push to `main`. Render redeploys automatically (`autoDeploy: true`); on Fly run `fly deploy`.
