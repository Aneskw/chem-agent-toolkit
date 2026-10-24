"""Resolve the installed Codex CLI, including Windows npm distributions."""
import os
import platform
import shutil
from pathlib import Path


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
