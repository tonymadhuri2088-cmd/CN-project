"""API check: tries Haiku and Sonnet with 5 tokens each and prints the raw error. Key is read hidden, never printed."""
import getpass
import os

import anthropic

key = (os.environ.get("ANTHROPIC_API_KEY") or getpass.getpass("Paste API key (hidden): ")).strip()
print("key length:", len(key), "| prefix ok:", key.startswith("sk-ant-"))
client = anthropic.Anthropic(api_key=key, max_retries=0)
print("base_url:", client.base_url)
for model in ("claude-haiku-5-5", "claude-sonnet-5-5"):
    try:
        r = client.messages.create(model=model, max_tokens=5, messages=[{"role": "user", "content": "hi"}])
        print("OK  ", model, r.usage.input_tokens, r.usage.output_tokens)
    except anthropic.APIStatusError as e:
        resp = e.response
        print("FAIL", model, "status", e.status_code, "| request-id:", resp.headers.get("request-id"),
              "| content-type:", resp.headers.get("content-type"), "| server:", resp.headers.get("server"))
        print("     raw text:", repr(resp.text[:300]))
    except Exception as e:
        print("FAIL", model, type(e).__name__, str(e)[:200])
