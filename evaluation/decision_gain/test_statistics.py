import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('decision_gain_run',Path(__file__).with_name('run.py'))
run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)


class StatisticsTests(unittest.TestCase):
    def test_paired_task_wins_not_repeat_pseudoreplication(self):
        rows=[]
        for task in range(4):
            for repeat in range(5):
                for condition,correct in [('no-skill',False),('with-skill',True)]:
                    rows.append({'task_id':str(task),'repeat':repeat,'condition':condition,'correct':correct})
        report=run.paired(rows,'no-skill','with-skill')
        self.assertEqual(report['task_wins'],4)
        self.assertEqual(report['two_sided_exact_p'],.125)

    def test_zero_gain_is_not_positive_evidence(self):
        tasks=[{'id':str(i),'tags':['scope-negative'] if i == 0 else []} for i in range(16)]
        rows=[{'task_id':t['id'],'condition':c,'repeat':0,'correct':True,'ok':True}
              for t in tasks for c in run.CONDITIONS]
        report=run.summarize(rows,tasks,1)
        self.assertFalse(report['efficacy_vs_no_skill'])
        self.assertFalse(report['advantage_beyond_source_access'])
        with self.assertRaisesRegex(ValueError,'incomplete'):run.summarize(rows[:-1],tasks,1)

    def test_failed_calls_block_efficacy(self):
        tasks=[{'id':str(i)} for i in range(16)]
        rows=[{'task_id':t['id'],'condition':c,'repeat':0,'correct':c=='with-skill','ok':True}
              for t in tasks for c in run.CONDITIONS]
        rows[0]['ok']=False
        self.assertFalse(run.summarize(rows,tasks,1)['efficacy_vs_no_skill'])

    def test_scope_negative_tasks_come_from_tags(self):
        tasks=[{'id':str(i),'tags':['scope-negative'] if i in {2,7} else []} for i in range(16)]
        rows=[{'task_id':t['id'],'condition':c,'repeat':0,'correct':True,'ok':True}
              for t in tasks for c in run.CONDITIONS]
        report=run.summarize(rows,tasks,1)
        self.assertEqual(report['conditions']['with-skill']['scope_attempts'],2)

    def test_plan_validates_and_hashes_all_three_arms_without_model_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            tasks=root/'tasks.json';oracle=root/'oracle.json';protocol=root/'protocol.md'
            bundle=root/'bundle.json';skills=root/'skills';skill=skills/'decision-rule'/'SKILL.md'
            materials=root/'materials.json';lock=root/'lock.json';out=root/'plan'
            tasks.write_text(json.dumps([{'id':'t1','family':'paper-a','request':'Choose a method.',
                'options':{'A':'first','B':'second','C':'third'},'tags':['scope-negative']}]), encoding='utf-8')
            oracle.write_text(json.dumps({'t1':'B'}), encoding='utf-8')
            protocol.write_text('frozen protocol', encoding='utf-8')
            source_text='raw source ﬁ 中文'
            bundle.write_text(json.dumps({'sources':[{'id':'paper','role':'paper','lines':[source_text]}]},
                ensure_ascii=False), encoding='utf-8')
            skill.parent.mkdir(parents=True)
            skill.write_text('---\nname: decision-rule\n---\n使用 distilled rule ﬁ。', encoding='utf-8')
            materials.write_text(json.dumps({'paper-a':{'bundle':'bundle.json','skills':'skills'}}),
                encoding='utf-8')
            run.freeze(tasks,oracle,protocol,lock,model='gpt-5.6-sol',seed=193,repeats=1)
            args=argparse.Namespace(lock=lock,tasks=tasks,oracle=oracle,protocol=protocol,
                materials=materials,model='gpt-5.6-sol',repeats=1,out=out)
            self.assertEqual(run.write_plan(args),0)
            manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['status'],'planned_no_model_calls')
            self.assertEqual(manifest['scheduled_attempts'],3)
            hashes=manifest['prompt_sha256']
            self.assertEqual(len(hashes),3)
            self.assertEqual(len(set(hashes.values())),3)
            expected='SOURCE paper (paper):\n'+source_text
            self.assertEqual(manifest['material_hashes']['paper-a']['source_text_chars'],len(expected))

if __name__=='__main__':unittest.main()
