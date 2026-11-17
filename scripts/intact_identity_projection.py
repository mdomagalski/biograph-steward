#!/usr/bin/env python3
"""Post-exposure DEVELOPMENT check of complete qualified interaction identities.

The existing IntAct/IMEx-only record join stays unchanged. Only the alias-set
comparison is projected from all XML identity-qualified database references.
This is a consumed component diagnostic, never a final source-fidelity score.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import io
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from biograph_steward.client import digest,utcnow
from scripts.intact_final_common import RESERVED,sha,seal,save_new,ordinary,load_json,assess_alignment
from scripts.inspect_intact_development import assess
from scripts.inspect_intact_xml_development import compare_study
from scripts.validate_intact_xml_provenance import references,xref_tuple,parse_transport

SUMMARY=ROOT/'docs/evaluations/intact_final_assessment_20261027_summary.json'
ORIGINAL_FREEZE=ROOT/'runs/intact_final_reserved_20261027/execution_freeze.json'
ORIGINAL_FREEZE_SHA='7c1f59b4696bd5b6f4b7760d22405f04f358fc46dfd7ea5f0464a98de3492788'
CAPTURED=ROOT/'runs/intact_final_reserved_20261027/execution'


def complete_identity_ids(evidence):
    """Use existing official-reader qualifiers, never infer identity from a name."""
    return {(database,identifier) for reference in references(evidence)
            for database,identifier,qualifier in [xref_tuple(reference)]
            if database and identifier and (qualifier=='MI:0356'
                or (database=='imex' and qualifier=='MI:0662'))}


def compare_identity_projection(pmid,original_records,xml_records):
    """Preserve the v1 join/field checks; replace only unlike alias-set projection."""
    raw=compare_study(pmid,original_records,xml_records)
    corrected=deepcopy(raw);changes=[];join_errors=[]
    for row in corrected['rows']:
        if row['alignment']!='unique' or len(row['xml_candidates'])!=1:
            join_errors.append({'source':row['source'],'reason':row['alignment']})
            continue
        candidate=xml_records[row['xml_candidates'][0]]
        if candidate['evidence_sequence']!=row.get('xml_evidence_sequence'):
            join_errors.append({'source':row['source'],'reason':'source_evidence_sequence_join_disagrees'})
            continue
        checks=[check for check in row['checks'] if check['field']=='evidence_identity_aliases']
        if len(checks)!=1:
            join_errors.append({'source':row['source'],'reason':'expected_one_original_alias_comparison'})
            continue
        check=checks[0];before=deepcopy(check)
        check['xml']=sorted(complete_identity_ids(candidate['evidence']))
        check['status']='equal' if check['mitab']==check['xml'] else 'different'
        if check!=before:changes.append({'source':row['source'],'original':before,'development':deepcopy(check)})
    corrected['critical_field_counts']=dict(Counter(check['status'] for row in corrected['rows'] for check in row['checks']))
    non_alias=lambda value:[{**row,'checks':[check for check in row['checks'] if check['field']!='evidence_identity_aliases']} for row in value['rows']]
    if non_alias(raw)!=non_alias(corrected):raise ValueError('A non-alias field/join was changed.')
    return {'raw_v1_comparison':raw,'development_identity_comparison':corrected,
            'changed_alias_comparisons':changes,'unchanged_narrow_record_join':True,
            'non_alias_field_comparisons_unchanged':True,'join_errors':join_errors}


def code_bindings():
    return {str(path):sha(path) for path in (Path(__file__).resolve(),
        ROOT/'tests/test_intact_identity_projection.py',ROOT/'scripts/inspect_intact_xml_development.py',
        ROOT/'scripts/validate_intact_xml_provenance.py',ROOT/'scripts/inspect_intact_development.py',
        ROOT/'scripts/intact_final_common.py')}


def freeze(output):
    """Bind expected captured-stream hashes from metadata before opening streams."""
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise ValueError('Choose a new immutable development diagnostic directory.')
    if sha(ordinary(ORIGINAL_FREEZE))!=ORIGINAL_FREEZE_SHA:raise ValueError('Original final freeze changed.')
    summary=load_json(ordinary(SUMMARY))
    if not summary.get('all_four_reserved_studies_now_consumed') or summary['metrics']['status']!='not_computed_pipeline_stopped_not_zero_accuracy':
        raise ValueError('Use only the recorded now-consumed stopped panel, without a final score.')
    expected={str(CAPTURED/(pmid+suffix)) for pmid in RESERVED for suffix in ('_reader.jsonl','_xml_reader.jsonl','_alignment.json')}
    inputs={str(ROOT/item['path']):item['sha256'] for item in summary['artifact_bindings']
            if str(ROOT/item['path']) in expected}
    if set(inputs)!=expected:raise ValueError('Metadata must bind all eight exact consumed reader streams and four original comparisons.')
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_intact_identity_projection.py')
    tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    output.mkdir(parents=True,exist_ok=False)
    (output/'invented_controls.log').write_text(stream.getvalue())
    if not tested.wasSuccessful() or tested.skipped:raise ValueError('Invented component controls must pass without skips.')
    contract=seal({'format':'biograph-steward.intact-identity-projection-development-freeze.v1','created_at':utcnow(),
        'pre_captured_stream_access':True,'assessment_split':'consumed_component_development_only',
        'publication_ids':list(RESERVED),'original_final_freeze_sha256':ORIGINAL_FREEZE_SHA,
        'original_summary_sha256':sha(SUMMARY),'implementation_sha256':code_bindings(),
        'input_sha256':inputs,'identity_rule':'All database references qualified MI:0356; IMEx references qualified MI:0662. Generic see-also/method references excluded.',
        'join_rule':'Unchanged original narrow IntAct/IMEx join and evidence sequence; ambiguity stays a stop.',
        'change_scope':'Only evidence_identity_aliases comparison; preserve raw v1 and all other checks.',
        'stopping_policy':'No record repair, new retrieval, Pharos work, answer/export run or final score. Preserve any remaining mismatch.',
        'scientific_accuracy_measured':False,'source_fidelity_scored':False,
        'invented_controls':{'tests_run':tested.testsRun,'status':'passed','log_sha256':sha(output/'invented_controls.log')}})
    save_new(output/'development_contract.json',contract)
    return contract


def run(contract_path,expected_sha):
    contract_path=ordinary(contract_path)
    if sha(contract_path)!=expected_sha:raise ValueError('External development contract SHA differs.')
    contract=load_json(contract_path)
    def unchanged():
        if sha(contract_path)!=expected_sha or code_bindings()!=contract['implementation_sha256'] or sha(ORIGINAL_FREEZE)!=ORIGINAL_FREEZE_SHA or sha(SUMMARY)!=contract['original_summary_sha256']:
            raise ValueError('Development implementation or original final freeze changed.')
    if (contract.get('format')!='biograph-steward.intact-identity-projection-development-freeze.v1'
            or contract.get('content_sha256')!=digest({k:v for k,v in contract.items() if k!='content_sha256'})
            or contract.get('publication_ids')!=list(RESERVED)):
        raise ValueError('Invalid exact consumed development contract.')
    unchanged();out=contract_path.parent/'diagnostic';out.mkdir(exist_ok=False)
    save_new(out/'started.json',{'created_at':utcnow(),'development_contract_sha256':expected_sha,
        'source_status':'All four studies already consumed by stopped final execution; development only.'})
    source_meta=load_json(ORIGINAL_FREEZE);studies=[]
    for pmid in RESERVED:
        unchanged()
        paths=[ordinary(CAPTURED/(pmid+suffix)) for suffix in ('_reader.jsonl','_xml_reader.jsonl','_alignment.json')]
        for path in paths:
            if sha(path)!=contract['input_sha256'][str(path)]:raise ValueError('Captured official-reader bytes changed.')
        mitab=[json.loads(line) for line in paths[0].read_text().splitlines()]
        xml,_,_=parse_transport(paths[1].read_bytes())
        source_hash=next(item['sha256'] for item in source_meta['source_catalog'] if item['publication_id']=='pubmed:'+pmid)
        original=[]
        for row in mitab:
            ledger={'publication_id':'pubmed:'+pmid,'artifact_sha256':source_hash,'release':'2026-10-17',
                'source_line':row['line_number'],'raw_row_sha256':hashlib.sha256(row['raw_line'].encode()).hexdigest(),**assess(row,pmid)}
            original.append({'ledger':ledger,'reader_record':row})
        comparison=compare_identity_projection(pmid,original,xml)
        if comparison['raw_v1_comparison']!=load_json(paths[2]):
            # JSON round-trip turns tuples into lists; compare canonical bytes.
            from biograph_steward.client import canonical
            if canonical(comparison['raw_v1_comparison'])!=canonical(load_json(paths[2])):
                raise ValueError('Raw v1 replay differs from the preserved original comparison.')
        remaining=assess_alignment(comparison['development_identity_comparison'],original,xml)
        study={'publication_id':pmid,**comparison,'remaining_reference_projection_errors':remaining}
        save_new(out/(pmid+'_diagnostic.json'),study);studies.append(study)
    unchanged()
    for path,pin in contract['input_sha256'].items():
        if sha(ordinary(path))!=pin:raise ValueError('Captured reader stream changed during diagnostic.')
    remaining=sum(len(study['remaining_reference_projection_errors'])+len(study['join_errors']) for study in studies)
    report=seal({'format':'biograph-steward.intact-identity-projection-development-diagnostic.v1','created_at':utcnow(),
        'status':'component_diagnostic_passed' if not remaining else 'remaining_mismatches_preserved',
        'development_contract_sha256':expected_sha,'original_final_freeze_sha256':ORIGINAL_FREEZE_SHA,
        'scope':'Four consumed captured official-reader streams; complete-identity comparator component only.',
        'changed_alias_comparisons':sum(len(study['changed_alias_comparisons']) for study in studies),
        'remaining_projection_error_count':remaining,'studies':studies,
        'implementation_and_inputs_unchanged':True,'original_final_result_changed':False,
        'new_source_calls':0,'new_model_calls':0,'Pharos_calls':0,'source_fidelity_score':None,'scientific_accuracy_score':None,
        'full_flow_rerun':False,'interpretation':'A bounded post-exposure development diagnostic. Original stopped final assessment remains unscored; no independent validation or biological gain.'})
    save_new(out/'report.json',report);return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('freeze');p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--contract',type=Path,required=True);p.add_argument('--expected-sha256',required=True)
    args=parser.parse_args()
    result=freeze(args.output) if args.command=='freeze' else run(args.contract,args.expected_sha256)
    print(json.dumps({'status':result.get('status','development_contract_written'),'content_sha256':result['content_sha256']}))
