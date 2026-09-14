#!/usr/bin/env python3
"""Small Responses API adapter for run_agent_ablation.py (stdlib only)."""
import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path


def main():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set")
    prompt = os.environ["TASK_PROMPT"]
    skill_path = os.environ.get("SKILL_PATH", "")
    if skill_path:
        prompt += "\n\nRead and follow this skill document:\n" + Path(skill_path).read_text(encoding="utf-8")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    style = os.environ.get("OPENAI_API_STYLE", "responses" if "api.openai.com" in base_url else "chat")
    if style == "chat":
        body = {"model": os.environ.get("OPENAI_MODEL", "Qwen/Qwen3-8B"),
                "messages": [{"role": "user", "content": prompt}], "max_tokens": 1200}
        endpoint = base_url + "/chat/completions"
    else:
        body = {"model": os.environ.get("OPENAI_MODEL", "gpt-5-nano"), "input": prompt, "max_output_tokens": 1200}
        endpoint = base_url + "/responses"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE", "/etc/ssl/cert.pem"))
    try:
        with urllib.request.urlopen(request, timeout=90, context=context) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        # Keep ablation logs useful without recording the request or API key.
        message = f"HTTP {exc.code}"
        error_code = None
        try:
            detail = json.loads(exc.read().decode("utf-8", "replace"))
            error = detail.get("error", detail)
            if isinstance(error, dict):
                message = error.get("message") or message
                error_code = error.get("code") or error.get("type")
        except Exception:
            pass
        print(json.dumps({"ok": False, "status": exc.code, "code": error_code,
                          "message": message,
                          "retry_after": exc.headers.get("Retry-After")},
                         ensure_ascii=False))
        raise SystemExit(2)
    except urllib.error.URLError as exc:
        print(json.dumps({"ok": False, "error": "network", "message": str(exc.reason)},
                         ensure_ascii=False))
        raise SystemExit(2)
    text = payload.get("output_text")
    if text is None and style == "chat":
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    if text is None:
        text = "".join(part.get("text", "") for item in payload.get("output", []) for part in item.get("content", []))
    print(text)


if __name__ == "__main__":
    main()
