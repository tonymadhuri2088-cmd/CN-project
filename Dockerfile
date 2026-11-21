# Web UI only (reads results/*.jsonl, simulator runs). The Kathara/Linux-namespace real labs need Linux + root
# and are NOT run in this container.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY netwing ./netwing
RUN pip install --no-cache-dir .
VOLUME ["/app/results"]
EXPOSE 8765
# Pass ANTHROPIC_API_KEY at run time (docker run -e ANTHROPIC_API_KEY ...) only if you want real model runs.
CMD ["netwing-ui", "--results", "/app/results", "--host", "0.0.0.0", "--port", "8765"]
