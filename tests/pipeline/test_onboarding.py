"""Portable configuration and zero-model client diagnosis, no live provider calls."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from creation_pipeline import onboarding,doctor
from creation_pipeline.models import load_legacy_config as load_config
from creation_pipeline.records import read_json,file_digest
from creation_pipeline.paths import ROOT

FLAGS='--json --output-schema --skip-git-repo-check --sandbox --enable --disable --config --model --ignore-user-config --ephemeral'
FEATURES='skip_host_skill_discovery apps plugins multi_agent hooks shell_tool respect_system_proxy'


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.pipeline/test-tmp';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_init_rebases_sources_and_sets_both_models_without_changing_template(self):
        template=ROOT/'examples/descriptor-screening/input.json';before=file_digest(template)
        output=self.root/'nested/config.json';result=onboarding.initialize(output,'my-account-model')
        config=load_config(output)
        self.assertEqual(config['model']['name'],'my-account-model')
        self.assertEqual(config['runtime_defaults']['options']['model'],'my-account-model')
        self.assertEqual(config['limits']['model_calls'],16);self.assertEqual(result['model_calls'],0)
        self.assertFalse(Path(read_json(output)['sources'][0]['path']).is_absolute())
        self.assertEqual(Path(config['sources'][0]['path']),ROOT/'validation/sibling-json/source')
        self.assertEqual(file_digest(template),before)

    def test_example_is_identical_in_implementation_requirements_and_business_obligations(self):
        old=read_json(ROOT/'validation/scoped-contracts/skill-a.json');new=read_json(ROOT/'examples/descriptor-screening/input.json')
        for field in ('prompt','limits','execution'):
            self.assertEqual(old[field],new[field])
        for field in ('shared_tool','tool_compatibility','skill_contract'):
            self.assertEqual(old['runtime_defaults'][field],new['runtime_defaults'][field])
        self.assertNotIn('name',new['model']);self.assertNotIn('model',new['runtime_defaults']['options'])

    def test_config_and_sources_relocate_together_with_no_old_checkout_dependency(self):
        relocated=self.root/'other user checkout with spaces'
        for name in ('examples/descriptor-screening','validation/sibling-json/source'):
            shutil.copytree(ROOT/name,relocated/name)
        with patch.object(onboarding,'ROOT',relocated):
            output=relocated/'.pipeline/configs/user.json';onboarding.initialize(output,'my-model')
        config=load_config(output)
        self.assertTrue(Path(config['sources'][0]['path']).is_relative_to(relocated))
        self.assertNotIn(str(ROOT),output.read_text(encoding='utf-8'))

    def test_existing_configuration_is_never_overwritten(self):
        target=self.root/'config.json';target.write_text('operator data')
        with self.assertRaisesRegex(ValueError,'new and unlinked'):onboarding.initialize(target,'model')
        self.assertEqual(target.read_text(),'operator data')

    def test_model_and_extension_errors_do_not_create_configurations(self):
        for model in ('','--flag','model\nsecret','sk-123456789012345678901234567890123456'):
            with self.assertRaises(ValueError):onboarding.initialize(self.root/'bad.json',model)
        with self.assertRaisesRegex(ValueError,'.json'):onboarding.initialize(self.root/'bad.yaml','model')
        self.assertFalse((self.root/'bad.json').exists())

    def probe(self,argv,**kwargs):
        args=argv[1:]
        if args==['--version']:value='codex-cli test-client'
        elif args in (['exec','--help'],['exec','resume','--help']):value=FLAGS
        elif args==['features','list']:value='\n'.join(f+' stable false' for f in FEATURES.split())
        else:raise AssertionError('A capability probe attempted inference/authentication: '+str(args))
        return SimpleNamespace(returncode=0,stdout=value,stderr='')

    def test_capability_check_uses_only_help_version_and_features_never_inference(self):
        with patch.object(doctor,'codex_command',return_value=['test-client']),patch.object(doctor.subprocess,'run',side_effect=self.probe) as run:
            result=doctor.client_capabilities()
        self.assertEqual(result['status'],'compatible');self.assertEqual(run.call_count,4)
        self.assertEqual(result['authentication'],'not_checked');self.assertEqual(result['model_entitlement'],'not_checked')

    def test_missing_flags_and_features_are_named_without_fallback(self):
        def old(argv,**kwargs):
            p=self.probe(argv,**kwargs);p.stdout=p.stdout.replace('--ignore-user-config','').replace('shell_tool','old_feature');return p
        with patch.object(doctor,'codex_command',return_value=['test-client']),patch.object(doctor.subprocess,'run',side_effect=old):
            result=doctor.client_capabilities()
        self.assertEqual(result['status'],'incompatible')
        self.assertTrue(any(x['field']=='exec.--ignore-user-config' for x in result['missing']))
        self.assertTrue(any(x['field']=='features.shell_tool' for x in result['missing']))

    def test_client_timeout_is_a_named_compatibility_problem(self):
        with patch.object(doctor,'codex_command',return_value=['test-client']),patch.object(doctor.subprocess,'run',side_effect=subprocess.TimeoutExpired('test-client',15)):
            result=doctor.client_capabilities()
        self.assertEqual(result['status'],'incompatible');self.assertTrue(result['missing'])

    def test_doctor_adds_blocker_but_never_grants_qualification(self):
        output=self.root/'config.json';onboarding.initialize(output,'model')
        observation={'status':'deferred','gaps':[],'model_calls':0,'build_calls':0,'qualification':'not_granted'}
        with patch.object(doctor,'check',return_value=observation),patch.object(doctor,'client_capabilities',return_value={'status':'incompatible','missing':['flag']}):
            result=doctor.from_config(output,offline=True)
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['gaps'][0]['code'],'model_client_incompatible')
        self.assertEqual(result['qualification'],'not_granted')

    def test_unused_codex_runtime_does_not_block_native_api_draft(self):
        config={'model':{'backend':'deepseek_api'},'runtime_defaults':{},'runtime':{},'draft_only':True}
        with patch.object(doctor,'load_config',return_value=config),patch.object(doctor,'check',return_value={'status':'ready','gaps':[]}), \
             patch.object(doctor,'client_capabilities',side_effect=AssertionError('Unused Codex')):
            self.assertEqual(doctor.from_config('config')['status'],'ready')

    def test_doctor_names_missing_git_without_installing_it(self):
        config={'model':{'backend':'deepseek_api'},'runtime_defaults':{},'runtime':{},'draft_only':True}
        with patch.object(doctor,'load_config',return_value=config), \
             patch.object(doctor,'check',return_value={'status':'ready','gaps':[]}), \
             patch.object(doctor.shutil,'which',return_value=None):
            result=doctor.from_config('config')
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['gaps'][0]['code'],'host_git_missing')
        self.assertEqual(result['gaps'][0]['path'],'git')

    def test_bootstrap_rejects_unrelated_directory_before_any_install(self):
        path=ROOT/'scripts/bootstrap.py';spec=importlib.util.spec_from_file_location('bootstrap_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch.object(module.subprocess,'run',side_effect=AssertionError('No process')):
            with self.assertRaisesRegex(ValueError,'non-venv'):module.bootstrap(self.root)

    def test_bootstrap_refuses_global_interpreter_prefix(self):
        path=ROOT/'scripts/bootstrap.py';spec=importlib.util.spec_from_file_location('bootstrap_prefix_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        target=self.root/'venv';target.mkdir();(target/'pyvenv.cfg').write_text('test fixture')
        with patch.object(module.venv.EnvBuilder,'create'),patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=str(self.root))) as run:
            with self.assertRaisesRegex(ValueError,'prefix mismatch'):module.bootstrap(target)
        self.assertEqual(run.call_count,1)

    def test_bootstrap_reuses_venv_without_overwriting_its_running_python(self):
        path=ROOT/'scripts/bootstrap.py';spec=importlib.util.spec_from_file_location('bootstrap_reuse_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        target=self.root/'venv';target.mkdir();(target/'pyvenv.cfg').write_text('test fixture')
        with patch.object(module.venv.EnvBuilder,'create') as create, \
             patch.object(module.subprocess,'run',side_effect=[SimpleNamespace(returncode=0,stdout=str(target)),SimpleNamespace(returncode=0)]) as run:
            result=module.bootstrap(target)
        create.assert_not_called();self.assertEqual(run.call_count,2)
        self.assertEqual(result['status'],'environment_prepared')


if __name__=='__main__':unittest.main()
