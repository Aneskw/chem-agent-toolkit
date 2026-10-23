"""Build and test prepared Docker tools independently of extraction."""
import argparse
import json
from pathlib import Path
from runtime_docker import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument('--success-policy', choices=('delivery','creation','execution'), default='delivery',
                        help='execution rechecks current acceptance; creation preserves legacy validation exit semantics')
    parser.add_argument('--repair-from-history',action='store_true',help='Repair an unchanged sealed build failure before rebuilding; never reuse historical passes')
    for name in ('total-seconds','model-timeout','build-seconds','max-attempts','context-chars','max-read-rounds','repair-reserve-seconds','document-seconds'):
        parser.add_argument('--'+name,type=int,default=None,help='Override only this retry budget; prepared inputs and locked tests remain unchanged')
    args = parser.parse_args()
    budget={k:v for k,v in vars(args).items() if k not in {'candidate','repair_from_history','success_policy'} and v is not None}
    kwargs={'budget':budget} if budget else {}
    if args.repair_from_history:kwargs['repair_from_history']=True
    report = validate(args.candidate,**kwargs)
    # Logs can contain any Unicode; keep the CLI's JSON valid under legacy Windows encodings.
    print(json.dumps(report, ensure_ascii=True))
    if args.success_policy in {'delivery','creation'}:
        from delivery import evaluate
        return 0 if evaluate([args.candidate],1)['delivery_accepted'] else 2
    if args.success_policy == 'execution':
        from strict_acceptance import evaluate
        from delivery import evaluate as delivery_evaluate
        return 0 if (report['status'] == 'execution_passed' and evaluate([args.candidate], 1)['current_acceptance_validated']
                     and delivery_evaluate([args.candidate],1)['delivery_accepted']) else 2
    return 0 if report["status"] in {"execution_passed", "not_required"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
