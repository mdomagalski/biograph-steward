#!/usr/bin/env python3
"""Execute invented final-flow controls and seal the unchanged implementation."""
import argparse
import io
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from biograph_steward.client import utcnow
from scripts.intact_final_common import save_new,seal,sha
from scripts.run_intact_final_evaluation import implementation_paths


def validate(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    before={str(p):sha(p) for p in implementation_paths() if p.is_file()}
    names=['tests.test_intact_final_execution','tests.test_intact_final_publication']
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames(names)
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (output/'unittest.log').write_text(stream.getvalue())
    after={str(p):sha(p) for p in implementation_paths() if p.is_file()}
    report=seal({'format':'biograph-steward.intact-final-synthetic-checks.v1','created_at':utcnow(),
        'status':'passed' if result.wasSuccessful() and before==after and not result.skipped else 'failed',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skipped':result.skipped,'implementation_sha256':before,
        'tests_sha256':{str(ROOT/(name.replace('.','/')+'.py')):sha(ROOT/(name.replace('.','/')+'.py')) for name in names},
        'log_sha256':sha(output/'unittest.log'),'reserved_bodies_accessed':False,
        'scope':'Invented fields, lineage, empty/missing/repeated rows, original runtime/default guards, ordinary attachment/answer/export. Not source scoring or scientific truth.'})
    save_new(output/'report.json',report);return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=validate(args.output)
    print(report['status']);raise SystemExit(0 if report['status']=='passed' else 1)
