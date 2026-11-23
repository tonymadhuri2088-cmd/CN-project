# NetWing web UI. Read-only public demo by default: it cannot start runs and never reads an API key.
# The Kathara / Linux-namespace real labs need Linux + root and are NOT run in this container.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 NETWING_READONLY=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY netwing ./netwing
RUN pip install .

# The frozen run logs and the claims file that the Overview and Reproducibility pages recompute from.
COPY results/*.jsonl ./results/
COPY docs/research/claims.json ./docs/research/claims.json

RUN useradd --system --no-create-home --uid 10001 netwing && chown netwing /app/results
USER netwing

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8765'),timeout=4)" || exit 1

# PORT is set by Render and similar hosts; 8765 otherwise. --read-only comes from NETWING_READONLY=1 above.
CMD ["sh", "-c", "exec netwing-ui --results /app/results --root /app --host 0.0.0.0 --port ${PORT:-8765}"]
