"""External-tool identity checks are offline; never request a model or Docker."""
import ast
import copy
import hashlib
import json
import time
from unittest.mock import patch

from creation_pipeline.contracts import fingerprint
from creation_pipeline.runtime import external_tool as ex, shared_tool as st
from creation_pipeline.runtime.preparation import bind, handoff
from tests.pipeline import test_shared_tool as fixtures


def external_declaration():
    value = fixtures.declaration()
    value['policy'] = ex.POLICY
    value['requirements']['executables'] = [{'name': 'obabel', 'path': '/usr/bin/obabel',
        'package': 'openbabel', 'version': '3.1.1', 'closure': ex.CLOSURE}]
    return value


def identity():
    return {'protocol': ex.CLOSURE, 'observer_sha256': hashlib.sha256(ex.PROBE.encode()).hexdigest(),
            'executable': {'path': '/usr/bin/obabel', 'sha256': 'a'*64},
            'packages': ['openbabel\t3.1.1+dfsg-9+b3\tinstalled'],
            'dynamic_libraries': [{'path': '/lib/ld.so', 'sha256': 'b'*64}],
            'plugins': '/usr/lib/x86_64-linux-gnu/openbabel/3.1.1', 'data': '/usr/share/openbabel/3.1.1',
            'rootfs': {'sha256': 'c'*64, 'files': 1200}}


class ExternalIdentityTests(__import__('unittest').TestCase):
    setUp = fixtures.SharedToolTests.setUp
    tearDown = fixtures.SharedToolTests.tearDown
    artifact = fixtures.SharedToolTests.artifact
    probe = fixtures.SharedToolTests.probe
    publish = fixtures.SharedToolTests.publish

    def request(self):
        for path in (self.package/'main.py', self.source/'main.py'):
            path.write_text(ex.WRAPPER, encoding='utf-8')
        # Refresh public source inventory, as normal source acquisition would.
        from creation_pipeline.artifacts.package import manifest
        self.sources[0]['inventory'] = manifest(self.source)
        source = self.root/'handoff'
        handoff(self.package, self.sources, source)
        return st.describe(source, bind(self.package, self.sources), external_declaration())

    def test_versioned_request_and_readonly_exact_reuse(self):
        req = self.request()
        self.assertEqual(req['abi'], ex.ABI)
        artifact = self.artifact(req)
        artifact['abi'] = ex.ABI
        artifact['external_identity'] = identity()
        artifact['artifact_id'] = fingerprint({k:v for k,v in artifact.items() if k!='artifact_id'})
        root = self.publish(artifact)
        with patch.object(ex, 'observe', return_value=identity()):
            self.assertEqual(st.resolve(req, {'engine_id':'daemon'}, self.probe(artifact), root)[1]['status'], 'hit')
        changed = identity(); changed['rootfs']['sha256'] = 'd'*64
        with patch.object(ex, 'observe', return_value=changed):
            result, reason = st.resolve(req, {'engine_id':'daemon'}, self.probe(artifact), root)
        self.assertIsNone(result)
        self.assertIn('external_identity', reason['candidates'][0]['reason'])
        self.assertIn('rootfs', reason['candidates'][0]['reason'])

    def test_unreviewed_process_programs_and_missing_declarations_fail(self):
        self.request()
        for text in (ex.WRAPPER.replace("['obabel','-i'", "['sh','-i'"),
                     ex.WRAPPER.replace('capture_output=True', 'shell=True,capture_output=True'),
                     ex.WRAPPER+'\nsubprocess.run(["other"])\n'):
            with self.assertRaisesRegex(ValueError, 'external_wrapper'):
                ex.validate_wrapper(ast.parse(text), 'package/main.py', 'main.py')
        for declaration_ in ([], ['obabel'], [dict(external_declaration()['requirements']['executables'][0], version='latest')]):
            with self.assertRaisesRegex(ValueError, 'executables'):
                ex.validate_requirements(declaration_)

    def test_source_dependency_interface_and_policy_change_requests(self):
        req = self.request()
        for field in ('version', 'path', 'closure'):
            d = external_declaration(); d['requirements']['executables'][0][field] = 'invalid'
            with self.assertRaises(ValueError): st.validate_declaration(d)
        d = external_declaration(); d['requirements']['executables'][0]['version'] = '3.1.2'
        changed = st.describe(self.root/'handoff', bind(self.package,self.sources), d)
        self.assertNotEqual(fingerprint(req), fingerprint(changed))
        (self.root/'handoff/package/main.py').write_text('# changed bytes\n'+ex.WRAPPER,encoding='utf-8')
        self.assertNotEqual(req, st.describe(self.root/'handoff',bind(self.package,self.sources),external_declaration()))

    def test_cleanup_on_failed_or_timed_out_observation(self):
        calls=[];cleanup_timeouts=[]
        def process(command, timeout):
            calls.append(command)
            if command[:2]==['docker','run']: raise TimeoutError('cancelled')
            cleanup_timeouts.append(timeout)
            return {'exit_code':0,'stdout':''}
        with self.assertRaises(TimeoutError):
            ex.observe('sha256:'+'1'*64, external_declaration()['requirements']['executables'], process, timeout=.001)
        self.assertEqual(calls[-1][:3], ['docker','rm','--force'])
        self.assertEqual(calls[0][calls[0].index('--name')+1], calls[-1][-1])
        self.assertEqual(cleanup_timeouts,[10])

    def metadata_plan(self):
        from tests.pipeline.test_runtime_build import plan
        p=plan()
        code="import json, shutil, subprocess, sys; print(json.dumps({'python': sys.version.split()[0], 'obabel': shutil.which('obabel'), 'obabel_version': subprocess.check_output(['obabel','-V'], text=True).strip()}))"
        p['tests'][0]['case_json']=json.dumps({'entrypoint':'python','args':['-c',code],'expected_exit':0,
            'stdout_contains':['"obabel": "/usr/bin/obabel"','"Open Babel 3.1.1"','"python": "3.11']})
        return p

    def test_raw_version_json_probe_correction_keeps_exact_component_requirement(self):
        bad=self.metadata_plan()
        with self.assertRaises(ex.PlanChannelError) as caught:ex.validate_plan(bad,'3.1.1')
        fixed=copy.deepcopy(bad);case=json.loads(fixed['tests'][0]['case_json'])
        case['stdout_contains'][1]='Open Babel 3.1.1 '
        fixed['tests'][0]['case_json']=json.dumps(case)
        caught.exception.repair_validator(fixed);ex.validate_plan(fixed,'3.1.1')
        from creation_pipeline.runtime.runner import output_matches
        stdout='{"python": "3.11.18", "obabel": "/usr/bin/obabel", "obabel_version": "Open Babel 3.1.1 -- Jan 4 2023"}\n'
        self.assertFalse(output_matches(json.loads(bad['tests'][0]['case_json']),{'stdout':stdout},stdout))
        self.assertTrue(output_matches(case,{'stdout':stdout},stdout))
        other=stdout.replace('3.1.1 --','3.1.10 --')
        self.assertFalse(output_matches(case,{'stdout':other},other))
        for mode in ('delete','banner','remove_path','change_program'):
            candidate=copy.deepcopy(fixed)
            if mode=='delete':candidate['tests'].pop(0)
            else:
                c=json.loads(candidate['tests'][0]['case_json'])
                if mode=='banner':c['stdout_contains'][1]='Open Babel'
                elif mode=='remove_path':c['stdout_contains'].pop(0)
                else:c['args'][1]+='; print("extra")'
                candidate['tests'][0]['case_json']=json.dumps(c)
            with self.subTest(mode=mode),self.assertRaises(ValueError):caught.exception.repair_validator(candidate)

    def test_normalized_or_unknown_version_program_is_not_guessed_at(self):
        value=self.metadata_plan();case=json.loads(value['tests'][0]['case_json'])
        case['args'][1]=case['args'][1].replace("text=True).strip()", "text=True).strip().split(' -- ')[0]")
        value['tests'][0]['case_json']=json.dumps(case)
        self.assertFalse(ex.raw_version_probe(case));ex.validate_plan(value,'3.1.1')

    def test_build_deadline_never_prevents_owned_probe_cleanup(self):
        calls, logs, counts = [], [], {'environment':0,'tool':0}
        def process(args,timeout):
            calls.append((args,timeout))
            return {'exit_code':None if args[1]=='run' else 0,'stdout':'','stderr':'timed out'}
        def bounded(args,timeout):
            return st.build_process(args,timeout,1,process,logs,counts)
        with patch('creation_pipeline.runtime.shared_tool.time.monotonic',side_effect=[0,2]):
            with self.assertRaisesRegex(ValueError,'probe failed'):
                ex.observe('sha256:'+'1'*64,external_declaration()['requirements']['executables'],bounded)
        self.assertEqual([c[0][1] for c in calls],['run','rm'])
        self.assertLessEqual(calls[-1][1],10)
        self.assertEqual(counts,{'environment':0,'tool':0})
        with self.assertRaisesRegex(ValueError,'deadline'):
            st.build_process(['docker','rm','--force','foreign'],1,time.monotonic()-1,process,logs,counts)

    def channel_plan(self):
        from tests.pipeline.test_runtime_build import plan
        p=plan()
        case=json.loads(p['tests'][1]['case_json'])
        case.pop('stdout_equals',None)
        case.update(args=['--input','/input/input.smi','--input-format','smi','--output-format','sdf',
                          '--output','/output/ethanol.sdf'],output_file='ethanol.sdf',
                    input_files={'input.smi':'CCO\r\n'},stdout_contains=['"ok": true'])
        case['acceptance']['assertion'].update(kind='json',path=['ok'],allowed_values=[True])
        p['tests'][1]['case_json']=json.dumps(case)
        return p

    def fixed_channel_plan(self,p):
        result=copy.deepcopy(p);case=json.loads(result['tests'][1]['case_json'])
        case['acceptance']['assertion'].update(kind='text_regex',pattern=r'(?s).+V2000.+M  END\n\$\$\$\$\n')
        result['tests'][1]['case_json']=json.dumps(case)
        return result

    def test_channel_correction_preserves_failed_case_and_other_obligations(self):
        bad=self.channel_plan()
        with self.assertRaises(ex.PlanChannelError) as caught:ex.validate_plan(bad)
        self.assertIn('ethanol.sdf',str(caught.exception))
        fixed=self.fixed_channel_plan(bad)
        caught.exception.repair_validator(fixed);ex.validate_plan(fixed)
        from creation_pipeline.runtime.runner import output_matches
        sdf='ethanol\n  3  2 V2000\nM  END\n$$$$\n'
        self.assertFalse(output_matches(json.loads(bad['tests'][1]['case_json']),{'stdout':'{"ok": true}'},sdf))
        self.assertTrue(output_matches(json.loads(fixed['tests'][1]['case_json']),{'stdout':'{"ok": true}'},sdf))
        for mode in ('delete','weaken','change_other','overwrite'):
            changed=copy.deepcopy(fixed)
            if mode=='delete':changed['tests'].pop()
            elif mode=='change_other':changed['tests'][0]['basis']='changed'
            else:
                case=json.loads(changed['tests'][1]['case_json'])
                if mode=='weaken':case.pop('stdout_contains')
                else:case['capture_stdout']=True
                changed['tests'][1]['case_json']=json.dumps(case)
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                caught.exception.repair_validator(changed);ex.validate_plan(changed)

    def test_channel_feedback_stays_in_existing_planning_loop(self):
        from creation_pipeline.runtime.preparation import propose
        bad=self.channel_plan();fixed=self.fixed_channel_plan(bad);index={'files':{},'read_files':[]}
        with patch('creation_pipeline.runtime.preparation.planner.plan',side_effect=[(bad,index,[]),(fixed,index,[])]) as model, \
             patch('creation_pipeline.runtime.preparation.validate',return_value=[]):
            result,_,_=propose(self.root,{'entry':'main.py'},self.root/'channel-audit',
                {'total_seconds':30,'max_attempts':2},plan_validator=ex.validate_plan)
        self.assertEqual(result,fixed);self.assertEqual(model.call_count,2)
        feedback=model.call_args_list[1].kwargs['feedback']
        self.assertEqual(feedback['channel_repair_cases'],bad['tests'])
        self.assertIn('not stdout JSON',feedback['diagnostic'])

    def test_observer_and_manifest_corruption_fail_closed(self):
        for field in ('protocol','observer_sha256','rootfs','executable','packages','dynamic_libraries'):
            value=identity();value[field]=None
            with self.assertRaises(ValueError):ex.validate_identity(value)
        for field in ('executable','packages','dynamic_libraries','plugins','data','rootfs'):
            value=identity();value[field]=copy.deepcopy(value[field])
            if isinstance(value[field],dict):value[field]['changed']='different'
            elif isinstance(value[field],list):value[field].append('different')
            else:value[field]+='different'
            with self.assertRaisesRegex(ValueError, field):ex.verify(identity(),value)
