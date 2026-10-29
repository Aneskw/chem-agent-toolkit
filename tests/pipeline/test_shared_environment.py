import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from creation_pipeline.contracts import fingerprint
from creation_pipeline.records import read_json, write_json
from creation_pipeline.runtime.shared_environment import describe, resolve, inheritance_matches


class SharedEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.materials = self.root / 'materials'
        context = self.materials / 'context'
        (context / 'package').mkdir(parents=True)
        (context / 'package/requirements.txt').write_text('numpy==1.26.4\n')
        self.base = 'python@sha256:' + 'a' * 64
        self.prefix = 'FROM ' + self.base + '\nWORKDIR /opt/skill\nCOPY ["package/requirements.txt", "./package/requirements.txt"]\nRUN pip install -r package/requirements.txt\n'
        self.suffix = 'COPY . ./\nUSER 10001:10001\nENTRYPOINT ["python", "/opt/skill/package/main.py"]\n'
        (context / 'Dockerfile').write_text(self.prefix + self.suffix)
        (context / 'package/main.py').write_text('print("first")')
        self.plan = {'platform': 'linux/amd64', 'build_layout': {'prefix_steps': 1,
                                                               'dependency_files': ['package/requirements.txt']}}
        self.recipe = describe(context, self.plan, {'repo_digest': self.base}, self.prefix)
        write_json(self.materials / 'shared-environment.json', self.recipe)
        self.cache = self.root / 'registry'
        self.builds = 0
        self.image = 'sha256:' + 'b' * 64
        self.labels = {'chem.shared.recipe': fingerprint(self.recipe)}
        self.missing = False
        self.fail = False

    def process(self, argv, timeout):
        if argv[:2] == ['docker', 'tag']:
            return {'exit_code': 0, 'stdout': '', 'stderr': ''}
        if '--format' in argv:
            return {'exit_code': 0, 'stdout': self.image+'\n', 'stderr': ''}
        if argv[:2] == ['docker', 'build']:
            self.builds += 1
            if self.fail:
                return {'exit_code': 1, 'stdout': '', 'stderr': 'install failed'}
            Path(argv[argv.index('--iidfile')+1]).write_text(self.image)
            self.labels = {'chem.shared.recipe': argv[argv.index('--label')+1].split('=',1)[1]}
            return {'exit_code': 0, 'stdout': '', 'stderr': ''}
        self.assertEqual(argv[:3], ['docker', 'image', 'inspect'])
        return {'exit_code': 1 if self.missing else 0,
                'stdout': json.dumps([{'Id': self.image, 'Os': 'linux', 'Architecture': 'amd64',
                                      'RootFS': {'Layers': ['sha256:'+'d'*64]},
                                      'Config': {'Labels': self.labels}}]), 'stderr': ''}

    def resolve(self, name, host=None):
        attempt = self.root / name
        attempt.mkdir()
        return resolve(self.materials, self.cache, host or {'engine_id': 'daemon-a'},
                       self.process, time.monotonic()+30, attempt)

    def test_two_distinct_tools_share_environment_but_keep_own_sources(self):
        first, a, _ = self.resolve('one')
        original = (self.materials/'context/Dockerfile').read_bytes()
        (self.materials/'context/package/main.py').write_text('print("second")')
        second, b, _ = self.resolve('two')
        self.assertEqual((a['status'], b['status'], self.builds), ('built', 'hit', 1))
        self.assertEqual(a['image_id'], b['image_id'])
        self.assertNotEqual((first/'package/main.py').read_bytes(), (second/'package/main.py').read_bytes())
        self.assertEqual((self.materials/'context/Dockerfile').read_bytes(), original)
        self.assertEqual((second/'Dockerfile').read_text(), 'FROM '+b['reference']+'\n'+self.suffix)

    def test_daemon_change_does_not_reuse_local_identity(self):
        self.resolve('one')
        _, observation, _ = self.resolve('two', {'engine_id': 'daemon-b'})
        self.assertEqual((observation['status'], self.builds), ('built', 2))

    def test_drifted_image_label_cannot_hit(self):
        self.resolve('one')
        self.labels = {'chem.shared.recipe': 'other'}
        _, observation, _ = self.resolve('two')
        self.assertEqual(observation['status'], 'built')
        self.assertEqual(self.builds, 2)

    def test_dependency_drift_stops_before_build(self):
        (self.materials/'context/package/requirements.txt').write_text('numpy==2.0\n')
        with self.assertRaisesRegex(ValueError, 'input drift'):
            self.resolve('one')
        self.assertEqual(self.builds, 0)

    def test_recipe_identity_changes_for_version_base_and_install_order(self):
        for field, value in [('base', 'python@sha256:'+'c'*64), ('platform','linux/arm64'),
                             ('prefix_text',self.prefix+'RUN pip check\n')]:
            changed = copy.deepcopy(self.recipe); changed[field] = value
            self.assertNotEqual(fingerprint(changed),fingerprint(self.recipe))

    def test_failed_build_does_not_publish_and_releases_lock(self):
        self.fail = True
        with self.assertRaisesRegex(ValueError, 'build failed'):
            self.resolve('one')
        self.assertEqual(list(self.cache.glob('*.json')), [])
        self.assertEqual(list(self.cache.glob('*.lock')), [])
        self.fail = False
        self.resolve('two')

    def test_live_or_crashed_lock_never_allows_duplicate_builder(self):
        self.cache.mkdir()
        lock = self.cache/(fingerprint(self.recipe)+'.lock')
        lock.write_text('1234')
        with patch('creation_pipeline.runtime.shared_environment.time.monotonic', side_effect=[0, 0, 30]), \
                patch('creation_pipeline.runtime.shared_environment.time.sleep') as sleep, \
                self.assertRaisesRegex(ValueError, 'deadline reached while acquiring lock') as raised:
            self.resolve('one')
        sleep.assert_called_once_with(.1)
        self.assertIn(str(lock), str(raised.exception))
        self.assertEqual(lock.read_text(), '1234')
        self.assertEqual(self.builds,0)

    def test_waiter_rechecks_completed_entry_and_reuses_owner_image(self):
        self.resolve('owner')
        lock = self.cache/(fingerprint(self.recipe)+'.lock')
        lock.write_text('owner')
        def release(_):
            self.assertEqual(self.builds, 1)
            self.assertEqual(lock.read_text(), 'owner')
            lock.unlink()  # Simulate the owner releasing its completed build.
        with patch('creation_pipeline.runtime.shared_environment.time.sleep', side_effect=release):
            _, observation, _ = self.resolve('waiter')
        self.assertEqual((observation['status'], self.builds), ('hit', 1))
        self.assertTrue(observation['waited_for_builder'])
        self.assertEqual(observation['image_id'], self.image)
        self.assertFalse(lock.exists())

    def test_waiter_can_build_after_owner_failure_without_partial_entry(self):
        self.cache.mkdir()
        lock = self.cache/(fingerprint(self.recipe)+'.lock')
        lock.write_text('failed-owner')
        with patch('creation_pipeline.runtime.shared_environment.time.sleep', side_effect=lambda _: lock.unlink()):
            _, observation, _ = self.resolve('waiter')
        self.assertEqual((observation['status'], self.builds), ('built', 1))
        self.assertTrue(observation['waited_for_builder'])
        self.assertEqual(read_json(self.cache/(fingerprint(self.recipe)+'.json'))['image_id'], self.image)

    def test_cancelled_waiter_never_releases_another_builders_lock(self):
        self.cache.mkdir()
        lock = self.cache/(fingerprint(self.recipe)+'.lock')
        lock.write_text('owner')
        with patch('creation_pipeline.runtime.shared_environment.time.sleep', side_effect=KeyboardInterrupt), \
                self.assertRaises(KeyboardInterrupt):
            self.resolve('cancelled')
        self.assertEqual(lock.read_text(), 'owner')
        self.assertEqual(self.builds, 0)

    def test_corrupt_entry_is_miss_not_success(self):
        self.cache.mkdir()
        (self.cache/(fingerprint(self.recipe)+'.json')).write_text('{broken')
        _, observation, _ = self.resolve('one')
        self.assertEqual(observation['status'],'built')

    def test_no_explicit_prefix_or_pin_is_not_shared(self):
        plan=copy.deepcopy(self.plan); plan['build_layout']['prefix_steps']=0
        self.assertIsNone(describe(self.materials/'context',plan,{'repo_digest':self.base},self.prefix))
        self.assertIsNone(describe(self.materials/'context',self.plan,None,self.prefix))

    def test_image_layers_are_bound_and_not_replaced_by_transport_tag(self):
        _, observation, _ = self.resolve('one')
        self.assertEqual(observation['layers'], ['sha256:'+'d'*64])
        self.assertEqual(observation['image_id'], self.image)
        self.assertTrue(observation['reference'].startswith('chem-shared-env:'))

    def test_transport_tag_cannot_substitute_another_image(self):
        original = self.process
        def process(argv, timeout):
            if '--format' in argv:
                return {'exit_code': 0, 'stdout': 'sha256:'+'f'*64, 'stderr': ''}
            return original(argv,timeout)
        self.process = process
        with self.assertRaisesRegex(ValueError, 'transport tag'):
            self.resolve('one')

    def test_same_layers_do_not_waive_environment_configuration_identity(self):
        shared={'status':'hit','layers':['layer-a'],
                'inherited_config':{'Env':['PATH=/trusted/bin'],'WorkingDir':'/opt/skill'}}
        image={'RootFS':{'Layers':['layer-a','tool-layer']},
               'Config':{'Env':['PATH=/trusted/bin'],'WorkingDir':'/opt/skill'}}
        self.assertTrue(inheritance_matches(shared,image))
        for key,value in [('Env',['PATH=/other/bin']),('WorkingDir','/tmp')]:
            changed=copy.deepcopy(image); changed['Config'][key]=value
            self.assertFalse(inheritance_matches(shared,changed))
        image['RootFS']['Layers']=['other-layer','tool-layer']
        self.assertFalse(inheritance_matches(shared,image))
