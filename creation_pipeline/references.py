"""Rebuildable, read-only dependency observations over explicitly named roots.

No default roots, catalog recovery, qualification, locks, Docker or persistent index.
Only the existing v2 library layout and direct shared-registry JSON are scanned.
"""
import hashlib
import json
from pathlib import Path
import re

from creation_pipeline.artifacts.package import manifest
from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import has_link, safe_relative, now, sanitized
from creation_pipeline.runtime import shared_tool

PROTOCOL = 'chem-references/v1'
ROOT_FIELDS = ('libraries', 'tool_registries', 'environment_registries')
HEX = r'[0-9a-f]{64}'
IMAGE = 'sha256:' + HEX
READ_ERRORS = (ValueError, OSError, KeyError, TypeError)


class ReferenceError(ValueError):
    def __init__(self, reason, field=None, expected=None, actual=None, code='record_invalid'):
        super().__init__(reason)
        self.code, self.field, self.expected, self.actual = code, field, expected, actual


def require(condition, field, expected, actual):
    if not condition:
        raise ReferenceError('Reference identity/layout mismatch: ' + field, field, expected, actual)


def environment_reference(value):
    require(isinstance(value, dict), 'environment', 'object', type(value).__name__)
    ref = {k: value.get(k) for k in ('recipe_key', 'image_id', 'daemon_id')}
    for field, pattern in (('recipe_key', HEX), ('image_id', IMAGE)):
        require(isinstance(ref[field], str) and re.fullmatch(pattern, ref[field]), 'environment.'+field, pattern, ref[field])
    require(isinstance(ref['daemon_id'], str) and bool(ref['daemon_id']), 'environment.daemon_id', 'nonempty string', ref['daemon_id'])
    return ref


def validate(params):
    """Validate the whole query before observing any record; never supply defaults."""
    try:
        require(isinstance(params, dict) and set(params) == {*ROOT_FIELDS, 'target'}, 'params', [*ROOT_FIELDS, 'target'], params)
        for field in ROOT_FIELDS:
            values = params[field]
            require(isinstance(values, list), field, 'explicit list of absolute directories (possibly empty)', values)
            seen = set()
            for value in values:
                require(isinstance(value, str) and bool(value) and Path(value).is_absolute(), field, 'absolute directory', value)
                require(not has_link(value), field, 'unlinked directory', value)
                key = str(Path(value).absolute()).casefold()
                require(key not in seen, field, 'distinct directories', value)
                seen.add(key)
        target = params['target']
        require(isinstance(target, dict), 'target', 'tool/environment identity', target)
        if target.get('kind') == 'tool':
            require(set(target) == {'kind', 'request_key', 'artifact_id'}, 'target', 'kind/request_key/artifact_id', target)
            shared_tool.validate_reference({k:v for k,v in target.items() if k != 'kind'})
        elif target.get('kind') == 'environment':
            require(set(target) == {'kind', 'recipe_key', 'image_id', 'daemon_id'}, 'target', 'kind/recipe_key/image_id/daemon_id', target)
            environment_reference(target)
        else:
            raise ReferenceError('Unsupported reference target', 'target.kind', ['tool','environment'], target.get('kind'))
    except READ_ERRORS as exc:
        error = ReferenceError(str(exc), getattr(exc,'field','params'), getattr(exc,'expected',None), getattr(exc,'actual',params), 'request_invalid')
        raise error from exc


def _tool_ref(record):
    return {k:record[k] for k in ('request_key', 'artifact_id')}


def _expected_request(delivery, freeze_sha256):
    inputs = delivery['inputs']
    return dict(candidate_id=delivery['candidate_id'], revision_id=delivery['revision_id'],
        **{name+'_fingerprint':fingerprint(inputs[key]) for name,key in
           (('package','files'),('source','sources'),('binding','bindings'),('environment','environment'),('acceptance','acceptance'))},
        freeze_sha256=freeze_sha256, executor_kind='local-docker', target_id='local')


class _Scan:
    def __init__(self, params):
        self.params = params
        self.evidence, self.issues, self.scopes = {}, [], []
        self.tools, self.environments, self.bindings, self.attempts = {}, {}, {}, []
        self.unresolved = []
        self._inventories = []
        self._frozen_trees = []

    def ref(self, path, kind):
        path = Path(path)
        if str(path) not in self.evidence:
            self.evidence[str(path)] = {'path':str(path),'kind':kind,'sha256':None}
        return dict(self.evidence[str(path)], kind=kind)

    def issue(self, path, code, reason, *, field=None, expected=None, actual=None):
        ref = self.ref(path, 'problem_record')
        self.issues.append({'code':code,'path':str(path),'field':field,'expected':expected,'actual':actual,
                            'reason':str(reason),'evidence':[ref]})

    def error(self, path, exc):
        path = getattr(exc,'reference_path',None) or getattr(exc,'filename',None) or path
        self.issue(path, getattr(exc,'code','record_missing' if isinstance(exc,FileNotFoundError) else 'record_invalid'),
                   type(exc).__name__+': '+str(exc),field=getattr(exc,'field',None),
                   expected=getattr(exc,'expected',None),actual=getattr(exc,'actual',None))

    def read(self, path, kind):
        if has_link(path):
            raise ReferenceError('Linked record is outside supported read boundary', code='linked_path')
        try:
            data = path.read_bytes()
            self.evidence[str(path)] = {'path':str(path),'kind':kind,'sha256':hashlib.sha256(data).hexdigest()}
            value = json.loads(data)
            require(isinstance(value, dict), str(path), 'JSON object', type(value).__name__)
            return value
        except READ_ERRORS as exc:
            exc.reference_path = str(path)
            raise

    def children(self, path):
        # Record directory membership so arrivals/removals during the query are visible.
        if has_link(path):
            raise ReferenceError('Linked scan directory', code='linked_path')
        items = sorted(path.iterdir())
        self._inventories.append((path, [p.name for p in items]))
        return items

    def tree(self, root, folder):
        """Only <folder>/<candidate>/<version>; do not discover inside source trees."""
        path = safe_relative(root, folder)
        if not path.exists():
            return []
        found = []
        for candidate in self.children(path):
            if has_link(candidate) or not candidate.is_dir():
                self.issue(candidate,'unsupported_layout','Expected unlinked candidate directory')
                continue
            for version in self.children(candidate):
                if has_link(version) or not version.is_dir():
                    self.issue(version,'unsupported_layout','Expected unlinked version/attempt directory')
                else:
                    found.append(version)
        return found

    def environment(self, observed, evidence, origin):
        require(isinstance(observed,dict), 'environment', 'object', observed)
        if observed.get('status') == 'not_applicable':
            return None
        require(observed.get('status') in {'built','hit'}, 'environment.status', ['built','hit','not_applicable'], observed.get('status'))
        ref = environment_reference(observed)
        key = fingerprint(ref)
        row = self.environments.setdefault(key, {'reference':ref,'evidence':[],'origins':[],'registry_paths':[]})
        self.merge(row, evidence, origin)
        return ref

    @staticmethod
    def merge(row, evidence, origin):
        for ref in evidence:
            if ref not in row['evidence']: row['evidence'].append(ref)
        if origin not in row['origins']: row['origins'].append(origin)

    def tool(self, record, evidence, origin):
        shared_tool.validate_record(record)
        ref = _tool_ref(record)
        env = self.environment(record['environment'], evidence, 'tool_embedded_environment')
        row = self.tools.setdefault(fingerprint(ref), {'reference':ref,'recipe_key':record['recipe_key'],
            'image_id':record['image_id'],'daemon_id':record['daemon_id'],'environment_reference':env,
            'evidence':[],'origins':[],'registry_paths':[]})
        self.merge(row,evidence,origin)
        return ref, env

    def binding(self, revision, tool, environment, evidence, basis):
        identity = {'library':revision['library'],'freeze_path':revision['freeze_path'],
                    'revision_id':revision['revision_id'],'freeze_sha256':revision['freeze_sha256'],
                    'tool_reference':tool,'environment_reference':environment}
        key = fingerprint(identity)
        row = self.bindings.setdefault(key, dict(identity,binding_id=key, name=revision['name'],candidate_id=revision['candidate_id'],
            catalog_roles=revision['catalog_roles'],evidence=[],origins=[],attempt_paths=[],
            integrity='frozen_identity_and_reference_verified'))
        self.merge(row,evidence,basis)
        return key

    def catalog(self, root):
        anchors = {}
        catalog_path = safe_relative(root,'catalog.json')
        try:
            catalog = self.read(catalog_path,'catalog_observation')
            require(catalog.get('version') == 2 and isinstance(catalog.get('skills'),list), 'catalog', 'version 2 skills array', catalog.get('version'))
            def anchor(entry, slot, name):
                try:
                    require(isinstance(entry,dict), slot, 'revision object', entry)
                    relative = entry['evidence']
                    require(isinstance(relative,str) and re.fullmatch(r'evidence/[^/]+/[^/]+',relative),slot+'.evidence','evidence/<candidate>/<version>',relative)
                    path = safe_relative(root,relative)
                    anchors.setdefault(str(path),[]).append({'entry':entry,'role':slot,'name':name})
                    history = entry.get('history',[])
                    require(isinstance(history,list), slot+'.history','array',history)
                    for number, prior in enumerate(history): anchor(prior,slot+'.history['+str(number)+']',name)
                except READ_ERRORS as exc:
                    self.error(catalog_path,exc)
            for number, entry in enumerate(catalog['skills']):
                anchor(entry,'skills['+str(number)+']',entry.get('name') if isinstance(entry,dict) else None)
        except READ_ERRORS as exc:
            self.error(catalog_path,exc)
        return anchors

    def frozen(self, root, path, anchors):
        freeze_path = safe_relative(path,'freeze.json')
        freeze = self.read(freeze_path,'freeze_receipt')
        digest = self.evidence[str(freeze_path)]['sha256']
        require(freeze.get('version') == 1 and isinstance(freeze.get('files'),list), 'freeze','version 1 file manifest',freeze.get('version'))
        full_manifest = manifest(path)
        actual = [f for f in full_manifest if f['path'] != 'freeze.json']
        ordered = lambda values: sorted(values,key=lambda f:f['path'])
        require(ordered(actual) == ordered(freeze['files']), 'freeze.files',freeze['files'],actual)
        self._frozen_trees.append((path,full_manifest))
        record_path = safe_relative(path,'record.json')
        record = self.read(record_path,'frozen_record')
        delivery = record['delivery']
        require(isinstance(delivery,dict),'delivery','delivery object',type(delivery).__name__)
        require(delivery.get('protocol') in {1,2},'delivery.protocol','existing delivery protocol 1/2',delivery.get('protocol'))
        require(delivery['revision_id'] == 'rev-'+fingerprint(delivery['inputs']), 'revision_id','rev-'+fingerprint(delivery['inputs']),delivery['revision_id'])
        require(freeze['revision_id'] == delivery['revision_id'],'freeze.revision_id',delivery['revision_id'],freeze['revision_id'])
        require(path.parent.name == delivery['candidate_id'],'freeze.candidate_directory',delivery['candidate_id'],path.parent.name)
        inputs = delivery['inputs']
        for field in ('bindings','environment','acceptance','layout','tool_compatibility','skill_contract'):
            if field not in inputs: continue
            envelope = inputs[field]
            require(isinstance(envelope,dict) and set(envelope) == {'version','payload','sha256'}
                    # preparation.update increments this content revision counter.
                    # It is not the delivery/tool schema protocol number.
                    and type(envelope['version']) is int and envelope['version'] >= 1
                    and envelope['sha256'] == fingerprint(envelope['payload']), 'inputs.'+field,'versioned content identity',envelope)
        keys = ('files','sources','bindings','environment','acceptance') + (('layout',) if 'layout' in inputs else ())
        require(delivery['fingerprints'] == {k:fingerprint(inputs[k]) for k in keys},'delivery.fingerprints','current input fingerprints',delivery['fingerprints'])
        require(isinstance(record['name'],str) and bool(record['name']), 'name','nonempty string',record['name'])
        row = {'library':str(root),'name':record['name'],'candidate_id':delivery['candidate_id'],
               'revision_id':delivery['revision_id'],'freeze_sha256':digest,'freeze_path':str(path),
               'catalog_roles':[a['role'] for a in anchors], 'delivery':delivery,'binding':None,'binding_id':None,
               'evidence':[self.ref(freeze_path,'freeze_receipt'),self.ref(record_path,'frozen_record')]}
        for anchor in anchors:
            for field, expected in (('revision_id',row['revision_id']),('freeze_sha256',digest)):
                if anchor['entry'].get(field) != expected:
                    self.issue(root/'catalog.json','catalog_reference_mismatch',anchor['role']+'.'+field,
                               field=field,expected=expected,actual=anchor['entry'].get(field))
            if anchor['name'] != row['name'] or anchor['entry'].get('delivery') != delivery:
                self.issue(root/'catalog.json','catalog_reference_mismatch',anchor['role']+': catalog name/delivery differs from frozen revision')
        env = delivery['inputs']['environment']['payload']
        require(env is None or isinstance(env,dict),'environment.payload','object or unprepared null',type(env).__name__)
        if isinstance(env,dict) and env.get('shared_tool'):
            require(isinstance(env['shared_tool'],dict),'shared_tool','binding object',type(env['shared_tool']).__name__)
            binding = shared_tool.verify_binding(env,path/'runtime')
            row['binding'] = binding
            if binding.get('artifact'):
                tool, environment = self.tool(binding['artifact'],row['evidence'],'frozen_concrete_tool')
                row['binding_id'] = self.binding(row,tool,environment,row['evidence'],'frozen_concrete_tool')
        return row

    def attempt(self, root, path, revisions):
        receipt_path = safe_relative(path,'receipt.json')
        receipt = self.read(receipt_path,'attempt_receipt')
        request = receipt['request']
        require(isinstance(request,dict),'attempt.request','bound request object',type(request).__name__)
        require(path.parent.name == request['candidate_id'],'attempt.candidate_directory',request['candidate_id'],path.parent.name)
        matching = [r for r in revisions if request == _expected_request(r['delivery'],r['freeze_sha256'])]
        require(bool(matching),'attempt.request','a verified frozen revision in this explicit library',request)
        log_path = safe_relative(path,'build-log.json')
        # Observe bytes without interpreting the native log schema.
        if has_link(log_path): raise ReferenceError('Linked build log',code='linked_path')
        data = log_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        self.evidence[str(log_path)] = {'path':str(log_path),'kind':'build_log','sha256':digest}
        require(receipt.get('log_sha256') == digest,'receipt.log_sha256',receipt.get('log_sha256'),digest)
        evidence = [self.ref(receipt_path,'attempt_receipt'),self.ref(log_path,'build_log')]
        report_path = safe_relative(path,'execution/report.json')
        report = None
        if report_path.exists():
            report = self.read(report_path,'execution_report')
            for key in ('request','image_id','tag'):
                require(report.get(key) == receipt.get(key),'execution.'+key,receipt.get(key),report.get(key))
            evidence.append(self.ref(report_path,'execution_report'))
        binding_ids = []
        for revision in matching:
            frozen_binding = revision['binding']
            if receipt.get('tool_artifact'):
                require(bool(frozen_binding),'receipt.tool_artifact','frozen shared_tool binding',None)
                artifact = receipt['tool_artifact']
                shared_tool.validate_record(artifact,frozen_binding['request'])
                env = revision['delivery']['inputs']['environment']['payload']
                require(artifact['plan'] == shared_tool.environment_plan(env['plan']) and artifact['base_image'] == env.get('base_image'),
                        'tool.recipe','frozen environment recipe',artifact['recipe_key'])
                if frozen_binding.get('artifact'):
                    require(artifact == frozen_binding['artifact'],'tool.version',_tool_ref(frozen_binding['artifact']),_tool_ref(artifact))
                require(receipt['image_id'] == artifact['image_id'],'receipt.image_id',artifact['image_id'],receipt['image_id'])
                tool, environment = self.tool(artifact,evidence,'attempt_concrete_tool')
                binding_id = self.binding(revision,tool,environment,revision['evidence']+evidence,'attempt_concrete_tool')
            elif frozen_binding:
                # A blocked/incomplete attempt may only prove its frozen requirement.
                binding_id = revision['binding_id']
                if receipt.get('status') == 'built':
                    raise ReferenceError('Built shared tool attempt lacks concrete ToolArtifact',field='receipt.tool_artifact')
            else:
                observed = receipt.get('shared_environment',{'status':'not_applicable'})
                require(isinstance(observed,dict),'receipt.shared_environment','environment observation object',type(observed).__name__)
                if observed.get('status') == 'not_requested_tool_hit':
                    raise ReferenceError('Tool-hit environment wrapper without concrete ToolArtifact')
                environment = self.environment(observed,evidence,'self_contained_attempt_environment')
                binding_id = self.binding(revision,None,environment,revision['evidence']+evidence,'self_contained_attempt_environment') if environment else None
            if binding_id:
                binding_ids.append(binding_id)
                self.bindings[binding_id]['attempt_paths'].append(str(path))
        self.attempts.append({'path':str(path),'library':str(root),'revision_id':request['revision_id'],
            'freeze_sha256':request['freeze_sha256'],'candidate_id':request['candidate_id'],'binding_ids':sorted(set(binding_ids)),
            'recorded_build_status':receipt.get('status'),'recorded_execution_status':report.get('status') if report else None,
            'concrete_tool_observed':bool(receipt.get('tool_artifact')),'evidence':evidence})

    def library(self, root):
        self.children(root)
        anchors = self.catalog(root)
        frozen_paths = {str(p):p for p in self.tree(root,'evidence')}
        frozen_paths.update({p:Path(p) for p in anchors})
        revisions = []
        for key,path in sorted(frozen_paths.items()):
            try: revisions.append(self.frozen(root,path,anchors.get(key,[])))
            except READ_ERRORS as exc:
                self.error(path/'freeze.json',exc)
                for anchor in anchors.get(key,[]):
                    entry = anchor['entry']
                    self.unresolved.append({'library':str(root),'name':anchor['name'],
                        'revision_id':entry.get('revision_id'),'freeze_sha256':entry.get('freeze_sha256'),
                        'freeze_path':str(path),'reason':'frozen_record_unverified','catalog_claim_only':True,
                        'evidence':[self.ref(root/'catalog.json','catalog_claim'),self.ref(path/'freeze.json','unverified_freeze')]})
        attempt_paths = {str(p):p for p in self.tree(root,'runtime')}
        attempt_manifests = {}
        for versions in anchors.values():
            for anchor in versions:
                entry = anchor['entry']
                for field in ('runtime','pending_runtime','runtime_history','interrupted_attempts'):
                    values = entry.get(field,[])
                    if field in {'runtime','pending_runtime'}: values = [values] if values else []
                    if not isinstance(values,list):
                        self.issue(root/'catalog.json','record_invalid','Expected attempt reference array: '+field)
                        continue
                    for ref in values:
                        try:
                            relative = ref['path']
                            require(isinstance(relative,str) and re.fullmatch(r'runtime/[^/]+/[^/]+',relative),field+'.path','runtime/<candidate>/<attempt>',relative)
                            path = safe_relative(root,relative)
                            attempt_paths[str(path)] = path
                            if 'files' in ref: attempt_manifests.setdefault(str(path),[]).append(ref['files'])
                        except READ_ERRORS as exc: self.error(root/'catalog.json',exc)
        for path in sorted(attempt_paths.values()):
            try:
                for expected in attempt_manifests.get(str(path),[]):
                    observed = manifest(path)
                    require(observed == expected,'catalog.attempt.files',expected,observed)
                self.attempt(root,path,revisions)
            except READ_ERRORS as exc: self.error(path/'receipt.json',exc)
        for revision in revisions:
            if revision['binding'] and not any(b['freeze_path']==revision['freeze_path'] for b in self.bindings.values()):
                self.unresolved.append(dict({k:revision[k] for k in ('library','name','revision_id','freeze_sha256','freeze_path','evidence')},
                    request_key=revision['binding']['request_key'],reason='no_verified_concrete_tool_version_observed'))

    def registry(self, root, kind):
        for path in self.children(root):
            if path.suffix != '.json':
                if path.name.endswith(('.lock','.tmp')):
                    self.issue(path,'publication_pending','Transient registry entry observed; not read or repaired')
                else:
                    self.issue(path,'unsupported_layout','Only direct published JSON records are indexed')
                continue
            try:
                value = self.read(path,kind+'_record')
                ref = self.ref(path,kind+'_record')
                if kind == 'tool':
                    shared_tool.validate_record(value)
                    tool = _tool_ref(value)
                    require(path.name == tool['request_key']+'-'+tool['artifact_id']+'.json','tool.filename',tool['request_key']+'-'+tool['artifact_id']+'.json',path.name)
                    self.tool(value,[ref],'tool_registry')
                    self.tools[fingerprint(tool)]['registry_paths'].append(str(path))
                else:
                    require(set(value) == {'recipe','image_id','daemon_id','complete_rebuild_lock'},'environment.record','native environment record v1 fields',sorted(value))
                    recipe = value['recipe']
                    require(isinstance(recipe,dict) and set(recipe) == {'abi','base','platform','prefix_text','files'},'environment.recipe','native recipe v1 fields',recipe)
                    require(type(recipe['abi']) is int and recipe['abi'] == 1 and recipe['platform'] == 'linux/amd64' and isinstance(recipe['files'],list)
                            and isinstance(recipe['prefix_text'],str) and re.fullmatch(r'[^\s]+@sha256:'+HEX,str(recipe['base']))
                            and value['complete_rebuild_lock'] is False,'environment.recipe','supported native recipe v1',recipe)
                    for item in recipe['files']:
                        require(set(item) == {'path','sha256','mode'} and re.fullmatch(HEX,str(item['sha256'])) and type(item['mode']) is int,
                                'environment.recipe.files','path/sha256/mode',item)
                        safe_relative(Path(__file__).parent/'__schema_only__',item['path'])
                    key = fingerprint(recipe)
                    require(path.name == key+'.json','environment.filename',key+'.json',path.name)
                    environment = self.environment(dict(value,status='built',recipe_key=key),[ref],'environment_registry')
                    self.environments[fingerprint(environment)]['registry_paths'].append(str(path))
            except READ_ERRORS as exc: self.error(path,exc)

    def run(self):
        for field in ROOT_FIELDS:
            for value in self.params[field]:
                root = Path(value).absolute()
                start = len(self.issues)
                scope = {'kind':field,'path':str(root),'status':'scanned'}
                self.scopes.append(scope)
                try:
                    require(root.is_dir(),'root','existing directory',str(root))
                    if field == 'libraries':
                        for marker in ('.catalog.lock','.transaction.json','.lock-recovery.guard'):
                            path = safe_relative(root,marker)
                            if path.exists(): self.issue(path,'catalog_pending','Catalog lock/journal present; observation may be in progress, no recovery performed')
                        self.library(root)
                    else: self.registry(root,'tool' if field=='tool_registries' else 'environment')
                except READ_ERRORS as exc:
                    self.error(root,exc)
                scope['status'] = 'partial' if len(self.issues) != start else 'scanned'
        # Do not trust a derived index after input membership/content changed during its creation.
        for path,names in self._inventories:
            try:
                require(not has_link(path) and sorted(p.name for p in path.iterdir()) == sorted(names), 'directory.members',names,'changed')
            except READ_ERRORS as exc: self.issue(path,'scan_changed',str(exc))
        for path, expected in self._frozen_trees:
            try: require(manifest(path) == expected,'freeze.files',expected,'changed during scan')
            except READ_ERRORS as exc: self.issue(path,'scan_changed',str(exc))
        for path,ref in list(self.evidence.items()):
            if ref['sha256'] is not None:
                try:
                    require(not has_link(path) and hashlib.sha256(Path(path).read_bytes()).hexdigest() == ref['sha256'], 'record.sha256',ref['sha256'],'changed')
                except READ_ERRORS as exc: self.issue(path,'scan_changed',str(exc))
        for kind, rows, field in (('tool',self.tools,'tool_registries'),('environment',self.environments,'environment_registries')):
            if not self.params[field]: continue
            for row in rows.values():
                if not row['registry_paths']:
                    self.issue(self.params[field][0],kind+'_record_not_found_in_scope','Embedded concrete reference has no verified matching registration in specified roots',actual=row['reference'])
        target = {k:v for k,v in self.params['target'].items() if k!='kind'}
        tool_target = self.params['target']['kind'] == 'tool'
        tools = [row for row in self.tools.values() if (row['reference'] == target if tool_target else row['environment_reference'] == target)]
        bindings = [row for row in self.bindings.values() if (row['tool_reference'] == target if tool_target else row['environment_reference'] == target)]
        binding_ids = {b['binding_id'] for b in bindings}
        attempts = [row for row in self.attempts if binding_ids.intersection(row['binding_ids'])]
        target_nodes = self.tools if tool_target else self.environments
        registered = target_nodes.get(fingerprint(target),{}).get('registry_paths',[])
        registry_field = 'tool_registries' if tool_target else 'environment_registries'
        filename = target['request_key']+'-'+target['artifact_id']+'.json' if tool_target else target['recipe_key']+'.json'
        result = {'protocol':PROTOCOL,'observed_at':now(),'target':self.params['target'],
            'scope':{'requested':{k:self.params[k] for k in ROOT_FIELDS},'roots':self.scopes,
                     'unscanned_categories':[k for k in ROOT_FIELDS if not self.params[k]],'global_complete':False,
                     'complete_within_declared_layouts':not self.issues and not self.unresolved,
                     'layouts':{'libraries':'catalog v2; evidence/<candidate>/<version>; runtime/<candidate>/<attempt>',
                                'registries':'direct published *.json only; no implicit roots or referenced external paths'},
                     'not_scanned':'all other libraries/registries, installed envelopes, native build outputs and external paths'},
            'target_registration':{'status':'found_in_scope' if registered else 'not_found_in_scanned_roots' if self.params[registry_field] else 'not_scanned',
                                   'paths':registered,'expected_paths':[str(Path(p)/filename) for p in self.params[registry_field]]},
            'matches':{'tools':tools,'bindings':bindings,'attempts':attempts},'unresolved_bindings':self.unresolved,'issues':self.issues,
            'index':{'storage':'ephemeral_rebuilt_each_query','tool_versions':len(self.tools),'environment_versions':len(self.environments),
                     'bindings':len(self.bindings),'attempts':len(self.attempts)},
            'interpretation':'Observed dependency references only, not availability, qualification, deletion safety or proof of no references elsewhere. Missing environment registration does not prove a derived tool image cannot run.',
            'qualification':None,'availability':None}
        return sanitized(result), sanitized(list(self.evidence.values()))


def query(params):
    validate(params)
    return _Scan(params).run()
