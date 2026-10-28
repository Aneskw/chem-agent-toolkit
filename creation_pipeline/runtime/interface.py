"""Bound build/execution request; remote transport remains unimplemented."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RuntimeRequest:
    candidate_id: str
    revision_id: str
    package_fingerprint: str
    source_fingerprint: str
    binding_fingerprint: str
    environment_fingerprint: str
    acceptance_fingerprint: str
    frozen_directory: str
    freeze_sha256: str
    attempt_directory: str
    executor_kind: str = "local-docker"
    target_id: str = "local"


class RuntimeExecutor(Protocol):
    """Implementations must enforce immutable inputs and return verifiable evidence.

    Runtime records include environment and image identity, logs, actual delivered
    entrypoints, business assertions and current host observations. A future
    remote adapter must use only an explicitly configured/authorized endpoint.
    LocalExecutor implements preflight, build, business validation and current evidence checks.
    """
    def preflight(self, request: RuntimeRequest) -> dict: ...
    def build(self, request: RuntimeRequest) -> dict: ...
    def validate(self, request: RuntimeRequest, build_receipt: dict | None = None) -> dict: ...
    def verify_current(self, request: RuntimeRequest, evidence: dict) -> dict: ...
