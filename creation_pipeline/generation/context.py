"""Small source-backed stage handoffs, never a substitute for original evidence."""
def guidance(config):
    return {"user_guidance": config["prompt"], "user_notes": config["notes"],
            "constraints": config["constraints"]}


def candidate_context(session, config, plan):
    from creation_pipeline.artifacts.layout import extract
    context = {**guidance(config), "plan": plan, "sources": session.sources.index(),
            "delivery_layout": extract(config, plan["name"]),
            "evidence": session.sources.validate_evidence(plan["evidence"]),
            "handoff": config.get("_handoff", []),

            "resource_index": session.workspace["resource_index"]}
    spec = {**config.get('runtime_defaults', {}), **config.get('runtime', {}).get(plan['name'], {})}
    if spec.get('tool_compatibility'):
        context['caller_contract_scopes'] = {k: spec[k] for k in ('tool_compatibility', 'skill_contract')}
    if spec.get('shared_tool'):
        context['tool_execution_layout'] = {
            'authority': 'host runtime protocol, not a business oracle or evidence of execution',
            'current_skill_package': {'required_files': context['delivery_layout']['required_files'],
                                      'verification': 'host delivery layout, frozen manifest and final qualification'},
            'tool_image_package': '/opt/skill/package',
            'tool_image_excluded_files': ['SKILL.md'],
            'entrypoint': spec['shared_tool']['interface']['entrypoint'],
            'check_policy': 'Preserve every implementation hash, data assertion and business obligation. '
                'Checks against the tool image must assert implementation files only, not current SKILL.md. '
                'Current Skill prose and complete Skill layout are verified against the actual frozen Skill package '
                'by host gates. Do not manufacture prose in a shared tool image or waive current Skill checks.'}
    return context
