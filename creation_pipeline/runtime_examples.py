"""Derive runnable usage examples from the same immutable tool test contracts."""
from pathlib import Path

from runtime_common import read, digest


def identity(tool_id, kind, case_id=None):
    """Names are display text; ownership is the explicit tuple, never its spelling."""
    return {"tool_id": tool_id, "kind": kind, "case_id": case_id,
            "example_id": digest([tool_id, kind, case_id])[:24]}


def counts(observations):
    preparations = sum(len(e.get('preparation', [])) for e in observations)
    executed = lambda e: int(e.get('executed', True))
    return {'groups': len(observations), 'commands': sum(executed(e) for e in observations) + preparations,
            'build_commands': sum(executed(e) for e in observations if e.get('kind') == 'build'),
            'case_commands': sum(executed(e) for e in observations if e.get('kind') == 'case'),
            'preparation_commands': preparations,
            'run_commands': sum(executed(e) for e in observations if e.get('kind') == 'usage'),
            'usage_commands': sum(executed(e) + len(e.get('preparation', [])) for e in observations if e.get('kind') == 'usage')}


def forwarded_args(tool, case):
    from runtime_package import business_args
    return business_args(tool, case)


class NoUsageCase(ValueError):
    """A valid contract may still lack a selectable normal invocation."""


def select_usage_case(tool,cases):
    candidates = [(c, forwarded_args(tool, c)) for c in cases if c.get("oracle_status") == "supported"]
    candidates = [(c, args) for c, args in candidates if c.get('expected_exit', 0) == 0]
    if tool.get('acceptance_version') == 2:
        from runtime_package import acceptance_coverage
        normal = acceptance_coverage(tool, cases)['normal_cases']
        candidates = [(c, args) for c, args in candidates if c['name'] in normal]
    candidates = [(c, args) for c, args in candidates if args is not None and
                  (args or (tool.get('acceptance_version') == 2 and tool.get('acceptance_policy', {}).get('invalid_input') == 'not_applicable'))
                  and not any(a in {"--help", "--version", "-V", "-h"} for a in args)]
    if not candidates:
        raise NoUsageCase("No supported, directly invocable usage example; add a test exercising the configured entrypoint with real input/output")
    candidates.sort(key=lambda item: (item[0].get("expected_exit", 0) != 0, not item[0].get("output_file")))
    return candidates[0]


def usage_example(root, key, tool):
    cases = read(Path(root) / tool["context"] / tool["fixtures"])["cases"]
    case, args = select_usage_case(tool,cases)
    prefix = ["python", "runtime/runner.py"]
    argv = prefix + ["run", "--tool", key, "--timeout-seconds", str(case.get("timeout_seconds", 30))]
    example = {**identity(key, "usage", case["name"]), "name": key + "-usage", "case": case["name"],
               "timeout_seconds": case.get("timeout_seconds", 30),
               "expected_exit": case.get("expected_exit", 0), "input_files": case.get("input_files", {})}
    if case.get("input_files"):
        example["input_dir"] = "../" + Path(root).name + "-" + key + "-example-input"
        argv += ["--input-dir", example["input_dir"]]
    if case.get("output_file"):
        example["output_dir"] = "../" + Path(root).name + "-" + key + "-example-output"
        example["output_file"] = case["output_file"]
        if not case.get('capture_stdout') or tool['behavior'].get('file_io'):
            argv += ["--output-dir", example["output_dir"]]
        if case.get("capture_stdout"):
            example["stdout_file"] = example["output_dir"] + "/" + case["output_file"]
            argv += ["--stdout-file", example["stdout_file"]]
    if case.get("input_files"):
        example["preparation_argv"] = prefix + ["prepare-inputs", "--tool", key, "--example", example["name"]]
    example["argv"] = argv + ["--", *args]
    return example
