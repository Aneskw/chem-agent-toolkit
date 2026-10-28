"""Small source-backed stage handoffs, never a substitute for original evidence."""
def guidance(config):
    return {"user_guidance": config["prompt"], "user_notes": config["notes"],
            "constraints": config["constraints"]}


def candidate_context(session, config, plan):
    context = {**guidance(config), "plan": plan, "sources": session.sources.index(),
            "evidence": session.sources.validate_evidence(plan["evidence"]),
            "handoff": config.get("_handoff", []),

            "resource_index": session.workspace["resource_index"]}
    return context
