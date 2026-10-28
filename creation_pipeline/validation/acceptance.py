"""Content-review receipts, not runtime or scientific certification."""
import json
from creation_pipeline.records import digest

ACCEPTANCE_VERSION = 3


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def payload(record):
    return {key: record.get(key) for key in ("name", "status", "files", "basis", "checks", "review_context")}


def certify(record):
    record["acceptance_version"] = ACCEPTANCE_VERSION
    record["acceptance_scope"] = "source_and_content_review_only"
    record["acceptance_sha256"] = fingerprint(payload(record))
    return record


def require_ready(record):
    if record.get("status") != "ready" or record.get("acceptance_version") != ACCEPTANCE_VERSION:
        raise ValueError("Current source/content review approval required")
    reviews = [c for c in record.get("checks", []) if c.get("name") == "content_review"]
    if not reviews or reviews[-1].get("status") != "pass" or not record.get("basis"):
        raise ValueError("Missing content review or writing basis")
    if any(c.get("required") and c.get("status") != "pass" for c in record.get("checks", [])):
        raise ValueError("Required content/static check has not passed")
    if record.get("acceptance_sha256") != fingerprint(payload(record)):
        raise ValueError("Approved content/records changed; review again")
