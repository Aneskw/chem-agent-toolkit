"""Isolated, tool-free structured model calls shared by creation and evaluation."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from network_env import model_environment


class ModelExecutionError(ValueError):
    """The model process failed, rather than returning an invalid plan."""


def call(prompt, schema, model, timeout=900, audit_dir=None):
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='chem-decision-') as directory:
        root=Path(directory)
        # Put only the answer schema in the child's working directory. Source
        # documents, skills and test oracles are never discoverable in ancestors.
        target=root/'schema.json'
        target.write_text(json.dumps(schema, ensure_ascii=False), encoding='utf-8')
        command=['codex','exec','--ephemeral','--skip-git-repo-check','--sandbox','read-only',
                 '--model',model,'--output-schema',str(target),'--json','-']
        try:
            proc=subprocess.run(command,input='Use only the supplied text. Do not call tools or read files.\n'+prompt,
                                text=True,encoding='utf-8',capture_output=True,cwd=root,
                                timeout=timeout,env=model_environment())
        except subprocess.TimeoutExpired as exc:
            if audit_dir:
                destination=Path(audit_dir);destination.mkdir(parents=True,exist_ok=True)
                for name,value in [('stdout',exc.stdout),('stderr',exc.stderr)]:
                    (destination/(name+'.txt')).write_text(value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or '',encoding='utf-8')
                (destination/'timeout.json').write_text(json.dumps({'timeout_seconds':timeout}),encoding='utf-8')
            raise
        if audit_dir:
            destination=Path(audit_dir);destination.mkdir(parents=True,exist_ok=True)
            (destination/'stdout.txt').write_text(proc.stdout,encoding='utf-8')
            (destination/'stderr.txt').write_text(proc.stderr,encoding='utf-8')
    answer=None;usage={};tools=[]
    for line in proc.stdout.splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if event.get('type')=='turn.completed':usage=event.get('usage',{})
        if event.get('type')!='item.completed':continue
        item=event.get('item',{})
        if item.get('type')=='agent_message':
            try:answer=json.loads(item['text'])
            except ValueError:pass
        elif item.get('type')!='reasoning':tools.append(item.get('type','unknown'))
    if proc.returncode or answer is None or tools:
        error=f'Model call failed: exit={proc.returncode}, answer={answer is not None}, tool_events={tools}; {proc.stderr[-600:]}'
        if proc.returncode:
            raise ModelExecutionError(error)
        raise ValueError(error)
    receipt={'model':model,'usage':usage,'tool_events':tools,'elapsed_seconds':round(time.monotonic()-started,3),
             'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
             'response_sha256':hashlib.sha256(json.dumps(answer,sort_keys=True).encode()).hexdigest()}
    return answer,receipt
