"""Finite Open Babel adapter and observed Debian image closure, protocol v1.

This is not a general subprocess analyser. Only the source wrapper below is
supported (AST equality permits comments/formatting, never a different program).
The complete immutable image filesystem is the conservative dependency closure:
ELF loaders, transitive libraries, format plugins, data and package metadata.
"""
import ast
import copy
import hashlib
import json
import re
import uuid

ABI = 'shared_tool_image_v2'
POLICY = 'openbabel-debian-image-v1'
CLOSURE = 'debian-image-rootfs-v1'
WRAPPER = '''import argparse, json, shutil, subprocess, sys
p=argparse.ArgumentParser()
p.add_argument('--input', required=True); p.add_argument('--input-format', required=True)
p.add_argument('--output-format', required=True); p.add_argument('--output', required=True)
a=p.parse_args()
if shutil.which('obabel') is None:
    print(json.dumps({'ok':False,'error':'obabel executable not found','status':'blocked_resources'})); raise SystemExit(2)
cmd=['obabel','-i',a.input_format,a.input,'-o',a.output_format,'-O',a.output]
r=subprocess.run(cmd,capture_output=True,text=True)
if r.returncode:
    print(json.dumps({'ok':False,'error':r.stderr.strip() or 'Open Babel conversion failed','exit_code':r.returncode})); raise SystemExit(2)
print(json.dumps({'ok':True,'input':a.input,'output':a.output,'input_format':a.input_format,'output_format':a.output_format,'stderr':r.stderr.strip()}))
'''


def validate_requirements(executables):
    expected = {'name': 'obabel', 'path': '/usr/bin/obabel', 'package': 'openbabel',
                'closure': CLOSURE}
    if (not isinstance(executables, list) or len(executables) != 1 or not isinstance(executables[0], dict)
            or set(executables[0]) != set(expected) | {'version'}
            or any(executables[0].get(k) != v for k, v in expected.items())
            or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', str(executables[0].get('version')))):
        raise ValueError('shared_tool.executables: require one obabel at /usr/bin/obabel, exact upstream version, '
                         'package=openbabel, closure=' + CLOSURE + '; actual=' + repr(executables))


def validate_wrapper(tree, path, entry):
    if path != 'package/' + entry or ast.dump(tree) != ast.dump(ast.parse(WRAPPER)):
        raise ValueError('shared_tool.external_wrapper: unsupported program at ' + path
                         + '; require original fixed-argv Open Babel conversion wrapper; no shell/dynamic subprocess')


class PlanChannelError(ValueError):
    def __init__(self, diagnostic, plan, repairable):
        super().__init__(diagnostic)
        original = copy.deepcopy(plan['tests'])
        self.protected_tests = original
        self.repair_validator = lambda proposed: preserve_tests(proposed, original, repairable)


def preserve_tests(plan, original, repairable):
    """A channel correction may fix the predicate, never delete/weaken the case."""
    current = {test['name']:test for test in plan['tests']}
    for old in original:
        name = old['name']
        new = current.get(name)
        if new is None:
            raise ValueError('Channel repair cannot remove case ' + name)
        old_case, new_case = json.loads(old['case_json']), json.loads(new['case_json'])
        if name not in repairable:
            if ({k:v for k,v in old.items() if k != 'case_json'} !=
                    {k:v for k,v in new.items() if k != 'case_json'} or old_case != new_case):
                raise ValueError('Channel repair cannot change other case ' + name)
        else:
            rule = repairable[name]
            for key in ('layer', 'kind', 'oracle_status'):
                if new.get(key) != old.get(key):
                    raise ValueError('Channel repair cannot demote case ' + name + '.' + key)
            for key, value in old_case.items():
                if rule['kind'] == 'version_prefix' and key == 'stdout_contains':
                    expected = [rule['prefix'] if v in rule['bad_literals'] else v for v in value]
                    if not set(expected) <= set(new_case.get(key, [])):
                        raise ValueError('Version probe repair must retain exact version boundary and other literals: ' + name)
                    continue
                if key != 'acceptance' and new_case.get(key) != value:
                    raise ValueError('Channel repair must retain case ' + name + '.' + key)
            if rule['kind'] == 'version_prefix':
                if new_case.get('acceptance') != old_case.get('acceptance'):
                    raise ValueError('Version probe repair cannot change acceptance: ' + name)
            elif (new_case.get('acceptance') or {}).get('purpose') != old_case['acceptance']['purpose']:
                raise ValueError('Channel repair must retain business purpose of case ' + name)


def raw_version_probe(case):
    """Recognize only a direct JSON dump of three unmodified metadata values.

    Unknown programs are not guessed at. In particular, a program deliberately
    normalizing the version can legitimately print the short quoted string.
    """
    args = case.get('args', [])
    if (not re.fullmatch(r'python(?:[23](?:\.[0-9]+)*)?', str(case.get('entrypoint','')).rsplit('/',1)[-1])
            or len(args) != 2 or args[0] != '-c'):
        return False
    try:
        body = ast.parse(args[1]).body
        imports = [n for n in body if isinstance(n, ast.Import)]
        if (len(imports) + 1 != len(body)
                or any(a.asname for n in imports for a in n.names)
                or {a.name for n in imports for a in n.names} != {'json','shutil','subprocess','sys'}):
            return False
        printed = body[-1].value
        dumped = printed.args[0]
        data = dumped.args[0]
        if (not isinstance(body[-1],ast.Expr) or ast.dump(printed.func) != ast.dump(ast.Name(id='print',ctx=ast.Load()))
                or len(printed.args)!=1 or printed.keywords or len(dumped.args)!=1 or dumped.keywords
                or ast.dump(dumped.func)!=ast.dump(ast.parse('json.dumps',mode='eval').body)
                or not isinstance(data,ast.Dict) or len(data.keys)!=3):
            return False
        values = {k.value: v for k,v in zip(data.keys,data.values) if isinstance(k,ast.Constant)}
        expected = {'python':'sys.version.split()[0]', 'obabel':"shutil.which('obabel')",
                    'obabel_version':"subprocess.check_output(['obabel','-V'], text=True).strip()"}
        return set(values)==set(expected) and all(ast.dump(values[k])==ast.dump(ast.parse(v,mode='eval').body)
                                                  for k,v in expected.items())
    except (SyntaxError,AttributeError,IndexError,TypeError):
        return False


def validate_plan(plan, version=None):
    """Reject the observed stdout/SDF channel contradiction before locking.

    Scope is this known adapter's explicit SDF output flag, not a filename guess.
    Keep the runner's comparator and every existing assertion unchanged.
    """
    from .coverage import business_args
    problems, repairable = [], {}
    for test in plan['tests']:
        case = json.loads(test['case_json'])
        if version and test.get('layer') == 'environment' and raw_version_probe(case):
            header = 'Open Babel ' + version
            bad = [v for v in case.get('stdout_contains',[]) if json.dumps(header) in v]
            if bad:
                prefix = header + ' '
                repairable[test['name']] = {'kind':'version_prefix','prefix':prefix,'bad_literals':bad}
                problems.append('tests[' + test['name'] + '].stdout_contains: raw obabel -V JSON value has a build suffix; '
                    'impossible closed quoted prefix=' + repr(bad) + '. Replace only those literals with '
                    + repr(prefix) + ' (required full version plus space boundary, no closing quote). '
                    'Keep the probe program, Python-series/path checks, expected exit and every other case; '
                    'do not reduce the requirement to an Open Babel banner.')
        args = business_args({'entrypoint': plan['entrypoint']}, case)
        if args is None:
            continue
        formats = [a.split('=', 1)[1] for a in args if a.startswith('--output-format=')]
        formats += [args[i+1] for i,a in enumerate(args[:-1]) if a == '--output-format']
        assertion = (case.get('acceptance') or {}).get('assertion') or {}
        if case.get('output_file') and 'sdf' in formats and (assertion.get('kind') in {'json', 'jsonl'} or case.get('capture_stdout')):
            repairable[test['name']] = {'kind':'channel'}
            problems.append('tests[' + test['name'] + '].acceptance.assertion.kind=' + repr(assertion.get('kind'))
                + ': output_file=' + repr(case['output_file']) + ' with --output-format sdf retains SDF text, '
                'not stdout JSON. Expected source-grounded text_regex for actual SDF; keep stdout metadata '
                'checks separately in json_equals/stdout_contains. Preserve this case, all JSON business '
                'values and SDF structure obligations; do not set capture_stdout to overwrite the SDF.')
    if problems:
        raise PlanChannelError('; '.join(problems), plan, repairable)


# Runs only inside a read-only, network-isolated image container. No chemistry
# input, package installation, host mounts or secrets are supplied. Root is used
# solely to enumerate even private image files; business execution stays non-root.
PROBE = r'''
import hashlib,json,os,stat,subprocess,shutil
excluded={'/proc','/sys','/dev','/run','/tmp','/etc/hosts','/etc/hostname','/etc/resolv.conf','/.dockerenv'}
def sha(path):
    real=os.path.realpath(path)
    if any(real==p or real.startswith(p+'/') for p in excluded):
        raise ValueError('dependency resolves into excluded runtime path: '+path+' -> '+real)
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def call(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=10)
    if p.returncode:raise ValueError(str(args)+': '+p.stderr)
    return p.stdout.strip()
spec=json.loads(__import__('sys').argv[1])[0]
for key in os.environ:
    if key.startswith(('BABEL_','LD_')):raise ValueError('unsupported loader override: '+key)
path=shutil.which(spec['name'])
if path!=spec['path']:raise ValueError('executable path: expected '+spec['path']+', actual '+str(path))
version=call([path,'-V'])
if not version.startswith('Open Babel '+spec['version']+' '):raise ValueError('version: expected '+spec['version']+', actual '+version)
owner=call(['dpkg-query','-S',path])
if owner.split(': ',1)[0]!=spec['package']:raise ValueError('unexpected executable owner: '+owner)
packages=call(['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Status}\n'])
ldd=call(['/usr/bin/ldd',path])
if 'not found' in ldd:raise ValueError('unresolved ELF dependencies: '+ldd)
libraries=[]
for line in ldd.splitlines():
    for token in line.split():
        if token.startswith('/'):
            libraries.append({'path':token,'realpath':os.path.realpath(token),'sha256':sha(token)})
plugins='/usr/lib/x86_64-linux-gnu/openbabel/'+spec['version']
data='/usr/share/openbabel/'+spec['version']
for p in (plugins,data):
    if os.path.realpath(p)!=p:raise ValueError('plugin/data directory must be canonical image path: '+p)
    if not os.path.isdir(p) or not os.listdir(p):raise ValueError('missing plugin/data directory: '+p)
# Docker supplies these runtime mounts independently of immutable image bytes.
# They cannot carry declared dependencies in this finite adapter.
for volatile in ('/run','/tmp'):
    for parent,dirs,files in os.walk(volatile):
        if files or any(os.path.islink(os.path.join(parent,d)) for d in dirs):
            raise ValueError('image dependency in excluded runtime directory: '+parent)
rows=[]
def walk(path):
    if path in excluded:return
    s=os.lstat(path); row={'path':path,'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid}
    if stat.S_ISLNK(s.st_mode):row.update(kind='link',target=os.readlink(path))
    elif stat.S_ISREG(s.st_mode):row.update(kind='file',bytes=s.st_size,sha256=sha(path))
    elif stat.S_ISDIR(s.st_mode):row.update(kind='directory')
    else:raise ValueError('unsupported special image file: '+path)
    rows.append(row)
    if row['kind']=='directory':
        for name in sorted(os.listdir(path)):walk(os.path.join(path,name))
walk('/')
rows.sort(key=lambda r:r['path'])
canonical=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
print(json.dumps({'protocol':'debian-image-rootfs-v1','executable':{'name':spec['name'],'path':path,
 'realpath':os.path.realpath(path),'sha256':sha(path),'version_output':version,'package_owner':owner},
 'packages':packages.splitlines(),'dynamic_libraries':sorted(libraries,key=lambda r:r['path']),
 'plugins':plugins,'data':data,'rootfs':{'sha256':hashlib.sha256(canonical).hexdigest(),'entries':len(rows),
 'files':sum(r['kind']=='file' for r in rows),'links':sum(r['kind']=='link' for r in rows),
 'bytes':sum(r.get('bytes',0) for r in rows),'excluded_runtime_paths':sorted(excluded)}}))
'''


def observe(image_id, executables, process, timeout=30):
    """Live immutable-image observation with owned cleanup on every exit path."""
    validate_requirements(executables)
    name = 'chem-external-identity-' + uuid.uuid4().hex
    command = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--cap-add', 'DAC_READ_SEARCH',
               '--security-opt', 'no-new-privileges', '--user', '0:0',
               '--pids-limit', '64', '--memory', '512m', '--cpus', '1',
               '--entrypoint', 'python', image_id, '-B', '-c', PROBE, json.dumps(executables)]
    try:
        result = process(command, timeout)
        if result['exit_code'] != 0:
            raise ValueError('shared_tool.external_identity: probe failed: ' + result.get('stderr', ''))
        value = json.loads(result['stdout'])
        value['observer_sha256'] = hashlib.sha256(PROBE.encode()).hexdigest()
        validate_identity(value)
        return value
    finally:
        process(['docker', 'rm', '--force', name], 10)


def validate_identity(value):
    observer = hashlib.sha256(PROBE.encode()).hexdigest()
    if isinstance(value, dict) and value.get('observer_sha256') != observer:
        raise ValueError('shared_tool.external_identity.observer_sha256: expected=' + observer
                         + ', actual=' + repr(value.get('observer_sha256')) + '; prepare a verified new version')
    if (not isinstance(value, dict) or set(value) != {'protocol', 'observer_sha256', 'executable', 'packages', 'dynamic_libraries',
                                                    'plugins', 'data', 'rootfs'}
            or value.get('protocol') != CLOSURE or not isinstance(value.get('rootfs'), dict)
            or value.get('observer_sha256') != observer
            or not re.fullmatch(r'[0-9a-f]{64}', str(value['rootfs'].get('sha256')))
            or not isinstance(value.get('executable'), dict)
            or not re.fullmatch(r'[0-9a-f]{64}', str(value['executable'].get('sha256')))
            or type(value['rootfs'].get('files')) is not int or value['rootfs']['files'] <= 0
            or not isinstance(value.get('packages'), list) or not value['packages']
            or any(not isinstance(p, str) for p in value['packages'])
            or not isinstance(value.get('dynamic_libraries'), list) or not value['dynamic_libraries']):
        raise ValueError('shared_tool.external_identity: incomplete executable/rootfs/package/library observation')


def verify(expected, observed):
    validate_identity(expected)
    if expected != observed:
        differences = [k for k in sorted(set(expected) | set(observed)) if expected.get(k) != observed.get(k)]
        raise ValueError('shared_tool.external_identity: changed objects=' + repr(differences)
                         + '; mismatches=' + repr([{ 'field': k, 'expected': expected.get(k), 'actual': observed.get(k)}
                                                  for k in differences]))
