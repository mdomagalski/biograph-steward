"""Synthetic diagnostic selection only; no reference-source access."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from . import first_search as f
from .first_search import first_attempt


def search(status,ids,query):
    return {'action':{'action':'search_pubmed','query':query},'tool_result':{'status':status,
        'candidates':[{'pmid':x}for x in ids],'cache':{'result_content_sha256':'synthetic'}}}


class FirstAttemptTests(unittest.TestCase):
    def test_score_cli_normalizes_output_path_with_synthetic_released_references(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp)
            refs=[{'case_id':str(i),'reference_pmids':['101'],'arms':{
                'unskilled_agent':{'recall_at_10':0.},'procedure_skill_agent':{'recall_at_10':0.}}}for i in range(24)]
            write_json(root/'case_scores.private.json',refs)
            main=f.seal({'format':'biograph-steward.source-search-reference-comparison.v1',
                'lineage':{'prediction_seal_file_sha256':'synthetic_prediction'},
                'raw_case_scores_sha256':sha(root/'case_scores.private.json'),
                'metrics':{arm:{'mean_reference_recall_at_10':0.}for arm in f.ARMS}})
            write_json(root/'report.json',main)
            policy=f.seal({'format':'biograph-steward.first-search-diagnostic-policy.v1','rule':f.RULE,
                'implementation_sha256':sha(f.__file__),'metric_helper_sha256':sha(Path(f.__file__).with_name('evaluate.py'))})
            write_json(root/'policy.json',policy)
            derived=f.seal({'format':'biograph-steward.first-search-derived-forecasts.v1',
                'diagnostic_policy_file_sha256':sha(root/'policy.json'),'prediction_seal_file_sha256':'synthetic_prediction',
                'rows':{arm:[{'case_id':str(i),'status':'completed','ranked_pmids':['101']}for i in range(24)]for arm in f.ARMS}})
            write_json(root/'derived.json',derived)
            command=[sys.executable,'-m','tools.source_search.first_search','score',
                '--main-report',str(root/'report.json'),'--main-report-sha256',sha(root/'report.json'),
                '--derived',str(root/'derived.json'),'--derived-sha256',sha(root/'derived.json'),
                '--policy',str(root/'policy.json'),'--policy-sha256',sha(root/'policy.json'),
                '--output',str(root/'cli_diagnostic.json')]
            result=subprocess.run(command,cwd=Path(__file__).parents[2],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            value=json.loads((root/'cli_diagnostic.json').read_text())
            self.assertEqual(value['metrics']['unskilled_agent']['first_attempt_mean_reference_recall_at_10'],1.)
            self.assertEqual(value['metrics']['procedure_skill_agent']['final_output_mean_reference_recall_at_10'],0.)

    def test_empty_or_failed_first_search_is_never_replaced_by_a_later_one(self):
        for status in ['unavailable','completed_empty','partial']:
            result=first_attempt({'history':[search(status,[],'first'),search('completed',['101'],'later')]})
            self.assertEqual(result['ranked_pmids'],[]);self.assertEqual(result['status'],status);self.assertEqual(result['query'],'first')

    def test_native_order_and_ten_candidate_cutoff_are_preserved(self):
        ids=[str(x)for x in range(120,100,-1)]
        self.assertEqual(first_attempt({'history':[search('partial',ids,'first')]} )['ranked_pmids'],ids[:10])

    def test_no_executed_search_retains_empty_output(self):
        self.assertEqual(first_attempt({'history':[{'controller_error':'synthetic'}]})['status'],'no_search')
        self.assertEqual(first_attempt({'history':[]})['ranked_pmids'],[])


if __name__=='__main__':unittest.main()
