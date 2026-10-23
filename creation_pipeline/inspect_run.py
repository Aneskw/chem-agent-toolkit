"""Query a run or stable candidate and continue runtime/publication independently."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import time
from runtime_common import read,write,digest,artifacts
from candidate_identity import load
import runtime_docker

HERE=Path(__file__).resolve().parent


def inspect(run_id,candidate=None,details=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',run_id) or run_id in {'.','..'}:raise ValueError('Unsafe run-id')
    root=HERE/'runs'/run_id
    extraction=read(HERE/'results'/f'{run_id}.json')
    rows=[]
    for folder in sorted((root/'drafts-v03').glob('*')):
        if not (folder/'SKILL.md').is_file():continue
        identity=load(folder) or {}
        if candidate and candidate not in {folder.name,identity.get('candidate_id')}:continue
        prepared=read(folder/'runtime/prepared.json') if (folder/'runtime/prepared.json').exists() else None
        stored=read(folder/'runtime/execution.json') if (folder/'runtime/execution.json').exists() else None
        measured=runtime_docker.evidence(folder) if stored and prepared else stored or prepared or {'status':'not_run'}
        guard_error=None
        if prepared:
            try:
                from runtime_model_lifecycle import current_sources,acceptance_inputs
                if stored and stored.get('requires_prepare'):raise ValueError('Previous integrity failure requires input resolution and explicit prepare')
                if stored and stored.get('prepared_sha256')!=digest(prepared):raise ValueError('Prepared input changed')
                if artifacts(folder)!=(stored or prepared).get('artifacts'):raise ValueError('Generated inputs/evidence changed')
                current_sources(prepared);acceptance_inputs(folder)
                if any(t.get('failure_kind')=='integrity' for t in prepared.get('tools',[])):raise ValueError('Preparation source integrity failed')
            except (ValueError,OSError,KeyError,TypeError) as exc:guard_error=str(exc)
        blocked=bool(guard_error or measured.get('requires_prepare'))
        probe_error=None
        if prepared and not blocked:
            from runtime_model import check_probe_syntax,PlanningError
            package=read(folder/'runtime/package.json')
            for tool in prepared.get('tools',[]):
                for case in tool.get('locked_cases',[]):
                    try:check_probe_syntax(case,package.get('tools',{}).get(tool['tool_id'],{}).get('entrypoint',[]))
                    except PlanningError as exc:probe_error=str(exc)
        commands={}
        if prepared:
            commands['retry_runtime']=[sys.executable,str(HERE/'validate_runtime.py'),str(folder),'--success-policy',extraction.get('success_policy','creation')] if not blocked and not probe_error and prepared['status']=='prepared' else None
            commands['prepare_runtime']=[sys.executable,str(HERE/'prepare_runtime.py'),str(folder),'--job-id',prepared['job_id'],'--tool-bindings',prepared['bindings_path']]
            if prepared['status']=='blocked_resources' and not blocked:
                commands['review_resources']=commands['prepare_runtime']+['--review-blocked-resources']
        elif extraction.get('tool_bindings'):
            commands['prepare_runtime']=[sys.executable,str(HERE/'prepare_runtime.py'),str(folder),'--job-id',extraction['paper_id'],'--tool-bindings',extraction['tool_bindings']]
        rows.append({'candidate':folder.name,'candidate_id':identity.get('candidate_id'),'path':str(folder),
                     'current_acceptance_validated':measured.get('current_acceptance_validated', False),
                     'runtime_status':measured['status'],'validation':measured.get('validation'),
                     'failure_reason':measured.get('error') or [t.get('error') or t.get('blockers') for t in measured.get('tools',[]) if t.get('error') or t.get('blockers')],
                     'requires_input_resolution':blocked,'commands':commands,
                     'report_path':str(folder/'runtime/execution.json' if stored else folder/'runtime/prepared.json')})
        if details:rows[-1]['report']=measured
        rows[-1]['input_guard_error']=guard_error
        rows[-1]['locked_probe_review_required']=probe_error
    if candidate and len(rows)!=1:raise ValueError('Candidate name/identity is missing or ambiguous')
    destination=HERE.parent/'skills/generated'/run_id
    archive=read(destination/'PUBLISHING.json') if (destination/'PUBLISHING.json').exists() else None
    from delivery import evaluate as delivery_evaluate
    all_candidates=sorted(p for p in (root/'drafts-v03').glob('*') if (p/'SKILL.md').is_file())
    delivery_state = delivery_evaluate(all_candidates,extraction.get('candidate_count',len(all_candidates)),extraction.get('creation_mode','delivery'))
    return {**delivery_state,'run_id':run_id,'paper_id':extraction.get('paper_id'),'tool_bindings':extraction.get('tool_bindings'),'extraction_status':extraction.get('extraction_status',extraction.get('status')),
            'success_policy':extraction.get('success_policy','creation'),
            'creation_stage':extraction.get('stage'),'creation_error':extraction.get('error'),'failure_details':extraction.get('failure_details'),
            'candidates':rows,'archive_status':'completed' if archive and archive.get('publication_complete') else 'not_completed',
            'archived_execution_checks':archive.get('execution_checks',{}) if archive else {},
            'retry_publish':[sys.executable,str(HERE/'publish_run.py'),'--run-id',run_id,'--success-policy',
                             'execution' if extraction.get('success_policy') == 'execution' else 'delivery'],
            'publication_note':'Existing targets require explicit --replace-existing; publication never rebuilds.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True);parser.add_argument('--candidate',help='Directory name or stable candidate_id')
    parser.add_argument('--action',choices=('status','retry-runtime','retry-prepare','retry-publish','review-resources'),default='status')
    parser.add_argument('--tool-bindings',type=Path,help='Explicit binding input for retry-prepare; never silently replace a locked runtime')
    parser.add_argument('--replace-existing',action='store_true');parser.add_argument('--total-seconds',type=int)
    parser.add_argument('--repair-from-history',action='store_true')
    parser.add_argument('--success-policy', choices=('delivery','creation','execution'), help='Default requirement-aware delivery, including legacy runs')
    parser.add_argument('--details',action='store_true',help='Include full execution records instead of concise state and report paths')
    args=parser.parse_args()
    if args.total_seconds is not None and args.total_seconds<1:parser.error('--total-seconds must be positive')
    started=time.monotonic()
    try:before=inspect(args.run_id,args.candidate,args.details)
    except (ValueError,OSError,KeyError,TypeError) as exc:parser.error(str(exc))
    policy = 'execution' if args.success_policy == 'execution' else 'delivery'
    deadline=started+args.total_seconds if args.total_seconds else None
    def remaining_budget():
        if deadline is None:return None
        value=int(deadline-time.monotonic())
        if value<1:raise ValueError('Continuation total budget exhausted')
        return value
    record={'action':args.action,'before':before,'budget_seconds':args.total_seconds}
    path=HERE/'runs'/args.run_id/'continuations'/f'{uuid.uuid4().hex}.json'
    if args.action!='status':
        record['state']='running'
        record['started_unix_seconds']=time.time()
        write(path,record)
    code=0
    if policy == 'delivery' and args.action in {'retry-runtime','retry-prepare'}:
        from delivery import retry
        record['results']=[]
        for row in before['candidates']:
            try:
                if row['requires_input_resolution'] or row.get('locked_probe_review_required'):
                    raise ValueError(row.get('input_guard_error') or row.get('locked_probe_review_required') or 'Resolve changed inputs first')
                result=retry(row['path'],prepare=args.action=='retry-prepare',job_id=before['paper_id'],
                             bindings=args.tool_bindings or before.get('tool_bindings'),budget=remaining_budget(),
                             repair_from_history=args.repair_from_history)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                result={'status':'stopped','error':str(exc)}
            record['results'].append(result)
    elif args.action=='review-resources':
        record['results']=[]
        for row in before['candidates']:
            if row['runtime_status']=='execution_passed' and (policy != 'execution' or row['current_acceptance_validated']):continue
            if row['requires_input_resolution'] or not row['commands'].get('review_resources'):
                record['results'].append({'candidate':row['candidate'],'status':'stopped','reason':row.get('input_guard_error') or 'No eligible wholly blocked resource plan'});code=2;continue
            prepared=read(Path(row['path'])/'runtime/prepared.json')
            try:
                result=runtime_docker.prepare(row['path'],prepared['job_id'],prepared['bindings_path'],budget_seconds=remaining_budget(),review_blocked=True)
                if result['status']=='prepared':result=runtime_docker.validate(row['path'])
            except (ValueError,OSError,KeyError,TypeError) as exc:
                result={'candidate':row['candidate'],'status':'stopped','reason':str(exc)}
            record['results'].append(result)
            if result['status']!='execution_passed':code=2
    elif args.action=='retry-runtime':
        record['results']=[]
        for row in before['candidates']:
            if row['runtime_status']=='execution_passed' and (policy != 'execution' or row['current_acceptance_validated']):continue
            if row['requires_input_resolution'] or not row['commands'].get('retry_runtime'):
                reason=('Locked probe requires review: '+row['locked_probe_review_required'] if row.get('locked_probe_review_required') else
                        row.get('input_guard_error') or 'Resolve preparation failure first; no extraction or implicit prepare performed')
                record['results'].append({'candidate':row['candidate'],'status':'stopped','reason':reason});code=2;continue
            kwargs={'repair_from_history':args.repair_from_history}
            try:
                if args.total_seconds:kwargs['budget']={'total_seconds':remaining_budget()}
                result=runtime_docker.validate(row['path'],**kwargs)
            except ValueError as exc:
                result={'candidate':row['candidate'],'status':'stopped','reason':str(exc)}
            record['results'].append(result)
            if result['status']!='execution_passed':code=2
    elif args.action=='retry-publish':
        if any(row['requires_input_resolution'] for row in before['candidates']):
            record['publication']={'status':'stopped','reason':'Resolve changed inputs/integrity first; no publication performed'};code=2
        else:
            command=before['retry_publish']+(['--replace-existing'] if args.replace_existing else [])
            command[command.index('--success-policy') + 1] = policy
            import runtime_package as runner
            try:
                result=runner.process(command,timeout=remaining_budget() or 600,supervise=True)
                record['publication']=result;code=result['exit_code']
            except (ValueError,subprocess.TimeoutExpired) as exc:
                record['publication']={'status':'stopped','reason':str(exc)};code=2
    if args.action!='status':
        if policy == 'delivery':
            from delivery import evaluate as delivery_evaluate
            from strict_acceptance import candidates
            run_root=HERE/'runs'/args.run_id
            status=read(HERE/'results'/f'{args.run_id}.json')
            assessment=delivery_evaluate(candidates(run_root/'drafts-v03'),status.get('candidate_count',0))
            if args.action == 'retry-publish':
                from strict_acceptance import publication_completed
                receipt=record.get('publication',{})
                if receipt.get('exit_code') in {0,2} and publication_completed(receipt.get('stdout')):
                    status['archive_status']='completed'
                    status.pop('archive_error',None)
                else:
                    status['archive_status']='failed'
            if status.get('archive_status') == 'failed' or code:
                assessment.update(delivery_accepted=False,delivery_status='blocked')
            status.update(assessment)
            if not assessment['delivery_accepted']: code=2
            status['exit_code']=code
            status['success_policy']='delivery'
            write(HERE/'results'/f'{args.run_id}.json',status)
            write(run_root/'pipeline_status.json',status)
            record['delivery']=assessment
        if policy == 'execution' and args.action in {'retry-runtime', 'review-resources'} and code == 0:
            from strict_acceptance import evaluate
            record['strict_acceptance'] = evaluate([r['path'] for r in before['candidates']], len(before['candidates']))
            if not record['strict_acceptance']['current_acceptance_validated']: code = 2
        if policy == 'execution':
            from delivery import evaluate as delivery_evaluate
            from strict_acceptance import candidates
            run_root=HERE/'runs'/args.run_id
            status=read(HERE/'results'/f'{args.run_id}.json')
            assessment=delivery_evaluate(candidates(run_root/'drafts-v03'),status.get('candidate_count',0))
            if args.action == 'retry-publish':
                from strict_acceptance import publication_completed
                receipt=record.get('publication',{})
                status['archive_status']='completed' if receipt.get('exit_code') in {0,2} and publication_completed(receipt.get('stdout')) else 'failed'
            if status.get('archive_status') == 'failed' or code:
                assessment.update(delivery_accepted=False,delivery_status='blocked')
            record['delivery']=assessment
            if not assessment['delivery_accepted']: code=2
            status.update(assessment,exit_code=code,success_policy='execution')
            write(HERE/'results'/f'{args.run_id}.json',status)
            write(run_root/'pipeline_status.json',status)
        record['after']=inspect(args.run_id,args.candidate,args.details)
        record['elapsed_seconds']=round(time.monotonic()-started,3)
        record['state']='finished'
        write(path,record);record['continuation_record']=str(path)
    print(json.dumps(record if args.action!='status' else before,ensure_ascii=True,indent=2));return code


if __name__=='__main__':raise SystemExit(main())
