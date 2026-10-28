"""Resolve the installed Codex CLI, including Windows npm distributions."""
import os
import platform
import shutil
from pathlib import Path

# Explicit transport selection. "default" keeps the provider exactly as the user
# configured it; "https" pins the Responses-over-HTTPS transport for controlled
# runs without touching global configuration.
TRANSPORTS = ('default', 'https')


def model_args(transport='default', reasoning=None, tier=None):
    """Child-only overrides for transport, reasoning effort and service tier."""
    args = transport_args(transport)
    if reasoning:
        args += ['-c', 'model_reasoning_effort=' + '"' + reasoning + '"']
    if tier:
        args += ['-c', 'service_tier=' + '"' + tier + '"']
    return args


def transport_args(transport):
    """Child-only CLI overrides for the requested transport."""
    if transport not in TRANSPORTS:
        raise ValueError('Unknown transport: ' + repr(transport))
    if transport == 'default':
        return []
    return ['-c', 'model_provider=planner_https',
            '-c', 'model_providers.planner_https.name="OpenAI over HTTPS"',
            '-c', 'model_providers.planner_https.requires_openai_auth=true',
            '-c', 'model_providers.planner_https.supports_websockets=false',
            '-c', 'model_providers.planner_https.wire_api="responses"']


def codex_command():
    executable = shutil.which("codex")
    if not executable:
        raise ValueError("Codex CLI is not installed or is not on PATH")
    # Windows npm shims are not executable binaries. Invoke their JS entrypoint directly.
    if os.name == "nt":
        script = Path(executable).parent / "node_modules/@openai/codex/bin/codex.js"
        arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
        triple = "aarch64-pc-windows-msvc" if arch == "arm64" else "x86_64-pc-windows-msvc"
        for vendor in (script.parent.parent / f"node_modules/@openai/codex-win32-{arch}/vendor",
                       script.parent.parent / "vendor"):
            binary = vendor / triple / "bin/codex.exe"
            if binary.is_file():
                return [str(binary)]
        node = shutil.which("node")
        if script.exists() and node:
            return [node, str(script)]
    return [executable]
