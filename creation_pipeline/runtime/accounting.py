"""Attach observed provider receipts to already admitted calls, never admit twice."""
import copy


def admit(guard,phase,backend,model):
    ticket=guard() if guard is not None else None
    if isinstance(ticket,dict):
        ticket.update(phase=phase,backend=backend,model=model,status='attempted',usage=None)
    return ticket


def observe(ticket,receipt):
    if not isinstance(ticket,dict) or not isinstance(receipt,dict):
        return
    # Do not copy request headers, endpoints, prompts or arbitrary provider data.
    for key in ('backend','model','usage','elapsed_seconds','prompt_sha256',
                'schema_sha256','request_count'):
        if key in receipt:
            ticket[key]=copy.deepcopy(receipt[key])
    completion=receipt.get('completion')
    ticket['status']=(receipt.get('status')
                      or (completion.get('status') if isinstance(completion,dict) else None)
                      or 'completed')
