"""Backend factory; compatible chat and Ollama use the same mediated protocol."""
import copy
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .model_backend import CodexBackend, RESPONSE_SCHEMA
from .records import redact


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class APIBackend:
    replay = False

    def __init__(self, config):
        self.config = config

    def call(self, prompt, timeout, schema=None):
        config = self.config
        kind = config["backend"]
        base = config.get("base_url", "http://localhost:11434" if kind == "ollama" else "https://api.openai.com/v1").rstrip("/")
        url = urllib.parse.urlsplit(base)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                or url.query or url.fragment or (url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"))):
            raise ValueError("Model endpoint requires HTTPS (HTTP allowed for localhost), without embedded credentials")
        key_name = config.get("api_key_env", "OPENAI_API_KEY" if kind != "ollama" else "")
        key = os.environ.get(key_name) if key_name else None
        if key_name and not key:
            raise ValueError("Model API key environment variable is not set: " + key_name)
        envelope = copy.deepcopy(RESPONSE_SCHEMA)
        if schema:
            envelope["properties"]["payload"] = {"anyOf": [{"type": "null"}, schema]}
        payload = {"model": config["name"], "messages": [{"role": "user", "content": prompt}], "stream": False}
        if kind == "ollama":
            endpoint = base + "/api/chat"
            payload["format"] = envelope
        else:
            endpoint = base + "/chat/completions"
            if config.get("structured", True):
                payload["response_format"] = {"type": "json_schema", "json_schema":
                    {"name": "pipeline_response", "strict": True, "schema": envelope}}
            else:
                payload["response_format"] = {"type": "json_object"}
                payload["messages"][0]["content"] += "\nRESPONSE JSON SCHEMA:\n" + json.dumps(envelope)
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST")
        opener = urllib.request.build_opener(NoRedirect())
        started = time.monotonic()
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(5_000_001)
        except urllib.error.HTTPError as exc:
            raise ValueError(f"Model HTTP {exc.code}: " + redact(exc.read(1500).decode(errors="replace"))) from None
        if len(raw) > 5_000_000:
            raise ValueError("Model response exceeds size limit")
        body = json.loads(raw)
        if kind == "ollama":
            if not body.get("done") or body.get("done_reason") == "length":
                raise ValueError("Incomplete Ollama response")
            message = body["message"]
            usage = {k: body[k] for k in ("prompt_eval_count", "eval_count") if k in body} or None
        else:
            choice = body["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("Model response did not finish normally")
            message, usage = choice["message"], body.get("usage")
        if message.get("tool_calls") or message.get("refusal"):
            raise ValueError("Unexpected tool calls or refusal instead of protocol response")
        answer = json.loads(message["content"])
        if not isinstance(answer, dict):
            raise ValueError("Model response must be a JSON object")
        return answer, {"model": config["name"], "backend": kind, "usage": usage,
                        "elapsed_seconds": round(time.monotonic() - started, 3)}


def backend_for(config, scratch):
    raise ValueError("Direct model transports are closed; use the native Codex Agent pipeline")
