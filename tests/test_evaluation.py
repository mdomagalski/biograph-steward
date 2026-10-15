"""Comparison metrics must not turn missing reviews or abstentions into success."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.graph import save_run
from biograph_steward.evaluation import freeze_suite,load_suite,run_evaluation,score_result,score_evaluation,validate_cases,evaluation_html
from biograph_steward.planning import RecordedPlanner,catalogue
from biograph_steward.__main__ import main
from test_civic import fixture,CivicAPI
from test_planning import civic_plan,abstain_plan,ModelPlanner,response


def cases():
    return [{'id':'candidate-case','question':'Inspect candidate therapy evidence for the full invented KRAS profile and cetuximab in DOID:9256.',
             'group':'profile-81','split':'development','reference_plan':civic_plan()},
            {'id':'unsupported-case','question':'Accept the source assertions and prescribe a drug.','group':'unsupported','split':'test','reference_plan':abstain_plan()}]


def edit_sheet(path,edit):
    with Path(path).open(newline='') as f:
        reader=csv.DictReader(f,delimiter='\t');columns=reader.fieldnames;rows=list(reader)
    edit(rows)
    with Path(path).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,delimiter='\t');writer.writeheader();writer.writerows(rows)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        api=CivicAPI();excluded=api.row(104,'RESISTANCE');excluded['openRevisionCount']=1;api.rows.append(excluded)
        self.p,self.c=fixture(api);self.base=self.root/'base';self.enriched=self.root/'enriched'
        save_run(self.p,self.base);save_run(self.p,self.enriched,civic_snapshot=self.c)
        self.suite=self.root/'suite';freeze_suite(self.base,self.enriched,self.suite,cases=cases())
    def tearDown(self):self.tmp.cleanup()

    def run_comparison(self,planner=None):
        result,metrics=run_evaluation(self.suite,self.root/'results',planner=planner)
        return result,metrics

    def test_suite_freezes_both_sources_and_rejects_changed_bytes(self):
        suite,g=load_suite(self.suite);self.assertEqual(suite['sources']['pharos']['pharos_snapshot_sha256'],suite['sources']['enriched']['pharos_snapshot_sha256'])
        self.assertEqual(g['pharos']['snapshot_sha256'],g['enriched']['snapshot_sha256'])
        p=self.suite/'sources'/'enriched'/'civic_snapshot.json';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'bytes changed'):load_suite(self.suite)

    def test_frozen_engine_mismatch_requires_a_new_suite(self):
        with patch('biograph_steward.evaluation.engine_fingerprint',return_value={}):
            with self.assertRaisesRegex(ValueError,'code changed'):load_suite(self.suite)

    def test_case_identity_and_group_split_validation(self):
        cs=cases();cs[1]['id']=cs[0]['id']
        with self.assertRaises(ValueError):validate_cases(cs)
        cs=cases();cs[1]['group']=cs[0]['group']
        with self.assertRaisesRegex(ValueError,'cannot cross'):validate_cases(cs)
        cs=cases();cs[0]['expected_answer']='Leaked gold'
        with self.assertRaises(ValueError):validate_cases(cs)

    def test_different_primary_snapshot_and_changed_baseline_reviews_are_not_comparable(self):
        p=deepcopy(self.p);p['created_at']='changed';p.pop('content_sha256');p['content_sha256']=digest(p)
        path=self.root/'other';save_run(p,path,civic_snapshot=self.c)
        with self.assertRaisesRegex(ValueError,'exact same Pharos'):freeze_suite(self.base,path,self.root/'bad',cases=cases())

    def test_no_reviewer_judgments_means_no_scientific_accuracy_or_fake_agent_run(self):
        r,m=self.run_comparison()
        self.assertEqual(m['status'],'review_pending');self.assertFalse(m['scientific_improvement_established'])
        self.assertEqual(r['planner_kind'],'not_run');self.assertEqual(m['arms']['planner']['executed_cases'],0)
        for arm in m['arms'].values():
            self.assertIsNone(arm['judged_precision']);self.assertIsNone(arm['review_pool_recall']);self.assertIsNone(arm['approved_plan_agreement'])
        self.assertEqual(m['arms']['pharos']['statuses']['source_gap'],1)
        self.assertEqual(m['arms']['enriched']['answered_cases'],1)
        self.assertTrue(any(u['filter_state']=='excluded' for u in r['pool']))
        self.assertEqual(sum(u['kind']=='civic_evidence_item' for u in r['pool']),5)
        for filename in ['case_reviews.tsv','answer_reviews.tsv','evidence_reviews.tsv','report.html','metrics.json']:
            self.assertTrue((self.root/'results'/filename).exists())

    def test_recorded_wrong_plan_is_not_hidden_by_a_correct_abstention(self):
        _,graphs=load_suite(self.suite);g=graphs['enriched']
        records={digest({'question':c['question'],'catalogue':catalogue(g)}):abstain_plan() for c in cases()}
        r,m=self.run_comparison(RecordedPlanner(records))
        self.assertEqual(r['planner_kind'],'recorded_replay');self.assertEqual(m['arms']['planner']['draft_plan_agreement'],.5)
        self.assertEqual(m['arms']['planner']['model_calls'],0);self.assertEqual(m['arms']['planner']['answered_cases'],0)
        self.assertIsNone(m['arms']['planner']['judged_precision'])

    def test_injected_model_is_not_a_live_result_and_receives_no_gold(self):
        requests=[]
        def transport(p):requests.append(p);return response(civic_plan())
        r,m=self.run_comparison(ModelPlanner(model='test',endpoint='http://localhost:9999',transport=transport))
        self.assertEqual(r['planner_kind'],'injected_test_model');self.assertEqual(len(requests),2)
        self.assertNotIn('reference_plan',json.dumps(requests));self.assertNotIn('reference_plan_correct',json.dumps(requests))
        self.assertTrue(all(o['tool_calls']<=1 for o in r['observations']))

    def test_invalid_model_proposals_remain_failures_in_plan_agreement_denominator(self):
        calls=[]
        bad=civic_plan();bad['tool']='shell'
        def transport(p):
            calls.append(p);return response(bad if len(calls)==1 else abstain_plan())
        _,m=self.run_comparison(ModelPlanner(model='test',endpoint='http://localhost:9999',transport=transport))
        self.assertEqual(m['arms']['planner']['draft_plan_comparisons'],2)
        self.assertEqual(m['arms']['planner']['draft_plan_agreement'],.5)
        self.assertEqual(m['arms']['planner']['statuses']['invalid_plan'],1)

    def test_reviewed_pool_precision_recall_and_filter_loss_need_actual_labels(self):
        r,_=self.run_comparison();path=self.root/'results'
        returned=next(o['returned_units'] for o in r['observations'] if o['arm']=='enriched' and o['case_id']=='candidate-case')
        def review_units(rows):
            for row in rows:
                row.update(reviewer='Software QA',notes='Invented fixture only')
                row['verdict']='relevant_supported' if row['unit_id']==returned[0] or row['filter_state']=='excluded' else 'irrelevant'
                if row['verdict']=='relevant_supported':row.update(source_check='abstract',evidence_locator='INVENTED test span')
                if row['filter_state']=='excluded':row['filter_decision']='incorrect'
        edit_sheet(path/'evidence_reviews.tsv',review_units)
        edit_sheet(path/'case_reviews.tsv',lambda rows:[row.update(reference_plan_correct='yes',reviewer='Software QA',notes='Invented scope test') for row in rows])
        m=score_result(r,case_reviews=path/'case_reviews.tsv',evidence_reviews=path/'evidence_reviews.tsv')
        self.assertEqual(m['arms']['enriched']['judged_precision'],round(1/len(returned),6))
        self.assertEqual(m['arms']['enriched']['review_pool_recall'],.5)
        self.assertEqual(m['filter_review']['excluded']['incorrect_decision_rate'],1)
        self.assertEqual(m['arms']['enriched']['approved_plan_agreement'],1)
        self.assertIsNone(m['arms']['planner']['approved_plan_agreement'])
        self.assertEqual(m['source_addition']['paired_reviewed_cases'],0)

    def test_supported_claim_requires_underlying_source_not_just_civic_label(self):
        r,_=self.run_comparison();path=self.root/'results'/'evidence_reviews.tsv'
        edit_sheet(path,lambda rows:rows[0].update(verdict='relevant_supported',source_check='record_only',reviewer='QA',notes='Test'))
        with self.assertRaisesRegex(ValueError,'underlying abstract'):score_result(r,evidence_reviews=path)

    def test_review_tampering_duplicate_ids_missing_reviewer_and_unknown_values_fail(self):
        r,_=self.run_comparison();path=self.root/'results'/'case_reviews.tsv';original=path.read_text()
        for change in [lambda rows:rows[0].update(case_sha256='changed'),lambda rows:rows.append(deepcopy(rows[0])),
                       lambda rows:rows[0].update(reference_plan_correct='yes'),lambda rows:rows[0].update(reference_plan_correct='TRUE')]:
            path.write_text(original);edit_sheet(path,change)
            with self.assertRaises(ValueError):score_result(r,case_reviews=path)

    def test_unexecuted_agent_cannot_receive_an_answer_accuracy_grade(self):
        r,_=self.run_comparison();path=self.root/'results'/'answer_reviews.tsv'
        missing={o['observation_id'] for o in r['observations'] if o['arm']=='planner'}
        edit_sheet(path,lambda rows:[row.update(answer_correct='yes',reviewer='QA',notes='Test') for row in rows if row['observation_id'] in missing])
        with self.assertRaisesRegex(ValueError,'no answer to grade'):score_result(r,answer_reviews=path)

    def test_scoring_and_reexecution_never_overwrite_sources_or_results(self):
        r,_=self.run_comparison();path=self.root/'results';before=(path/'evaluation.json').read_bytes()
        score_evaluation(path,self.root/'scored',case_reviews=path/'case_reviews.tsv')
        self.assertEqual(before,(path/'evaluation.json').read_bytes())
        with self.assertRaises(ValueError):score_evaluation(path,path)
        with self.assertRaises(ValueError):run_evaluation(self.suite,path)

    def test_html_escapes_source_text_and_readiness_recognizes_enrichment(self):
        r,m=self.run_comparison();r['observations'][0]['reason']='</script><img src=x onerror=alert(1)>'
        html=evaluation_html(r,m);self.assertNotIn('<img src=x',html);self.assertIn('&lt;img',html)
        _,graphs=load_suite(self.suite);codes={c['code'] for c in graphs['enriched']['benchmark_readiness']['required_actions']}
        self.assertNotIn('external_enrichment_missing',codes);self.assertIn('enrichment_independence_unresolved',codes)

    def test_cli_freeze_run_score_and_missing_model_are_explicit(self):
        with redirect_stdout(StringIO()):
            self.assertEqual(main(['evaluation-run','--suite',str(self.suite),'--out',str(self.root/'cli')]),0)
            self.assertEqual(main(['evaluation-score','--result',str(self.root/'cli'),'--out',str(self.root/'cli-scored')]),0)
        self.assertTrue((self.root/'cli-scored'/'metrics.json').exists())


if __name__=='__main__':unittest.main()
