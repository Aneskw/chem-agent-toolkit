"""Small source-backed stage handoffs, never a substitute for original evidence."""
def guidance(config):
    return {"user_guidance": config["prompt"], "user_notes": config["notes"],
            "constraints": config["constraints"]}


def candidate_context(session, config, plan, independent_review=False):
    # Review gets the declared capability, not the writer's benefit/rationale verdict.
    declared = {k: plan[k] for k in ("name", "task", "scope", "entrypoint", "construction") if k in plan} if independent_review else plan
    context = {**guidance(config), "plan": declared, "sources": session.sources.index(),
            "evidence": session.sources.validate_evidence(plan["evidence"]),
            "handoff": config.get("_handoff", []),

            "resource_index": session.workspace["resource_index"]}
    return context
