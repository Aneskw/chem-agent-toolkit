"""Small source-backed stage handoffs, never a substitute for original evidence."""
def guidance(config):
    return {"user_guidance": config["prompt"], "user_notes": config["notes"],
            "constraints": config["constraints"]}


def candidate_context(session, config, plan):
    return {**guidance(config), "plan": plan, "sources": session.sources.index(),
            "evidence": session.sources.validate_evidence(plan["evidence"]),
            "handoff": config.get("_handoff", []),
            "example_runner": str(__import__("pathlib").Path(__file__).resolve().parents[1] / "examples/verify_python_example.py"),
            "resource_capabilities": ["list", "read", "read_many", "search", "fetch", "repository", "resolve"],
            "limits": {"view_chars": config["limits"]["view_chars"]}}
