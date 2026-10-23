"""Keep source extraction, container acceptance and local archival independent."""
CREATED={'method_drafts_created','atomic_resource_hints_only','repo_only_hints_created'}


def counts(records):
    return {'runs':len(records),'extraction_succeeded_runs':sum(r.get('extraction_succeeded',r.get('status') in CREATED|{'no_supported_skill'}) for r in records),
            'creation_failed_runs':sum(r.get('status') not in CREATED|{'no_supported_skill'} for r in records),
            'extracted_candidates':sum(r.get('candidate_count',0) or 0 for r in records if r.get('extraction_succeeded',r.get('status') in CREATED)),
            'archived_candidates':sum(r.get('archived_candidate_count',r.get('candidate_count',0)) or 0 for r in records if r.get('publish_status')=='published_locally'),
            'execution_passed_candidates':sum(sum(s=='execution_passed' for s in r.get('execution_checks',{}).values()) for r in records)}


def batch_exit(records,policy,target=None):
    from strict_acceptance import record_passes
    tally=counts(records)
    if tally['creation_failed_runs'] or any(r.get('publish_status')=='failed' for r in records):return 1
    if policy in {'delivery', 'creation'}:
        from delivery import record_passes as delivery_passes
        if not records or not all(delivery_passes(r) for r in records): return 2
    if policy=='execution' and (not tally['extracted_candidates'] or tally['execution_passed_candidates']!=tally['extracted_candidates']
                               or not all(record_passes(r) for r in records)):return 2
    if target is not None and tally['archived_candidates']<target:return 2
    return 0
