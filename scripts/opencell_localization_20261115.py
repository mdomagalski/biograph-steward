#!/usr/bin/env python3
"""Source-separated OpenCell localization concordance, without invented negatives.

Reuses frozen HOU forecasts, the original OpenCell comparison categories and
grades 2/3, and the existing native GO qualification. This is consumed-reference
development analysis: it cannot certify unseen or study-independent accuracy.
All source tables remain local; only aggregate reports are publication inputs.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import sha
from biograph_steward.go_context_inspection import load_go_context
from biograph_steward.go_native_support import exclusion_reasons
from tools.reference_accuracy.hou import positive_metrics
from tools.reference_accuracy.mitocarta import mitochondrial_terms

ARMS = ('A_raw_Pharos_scope_qualified', 'A_retained_scope_qualified',
        'B_native_location_scope_qualified', 'C_native_experimental_scope_qualified',
        'D_native_without_HPA_or_explicit_OpenCell')
SCHEMAS = {
    'localization': ['target_name', 'ensg_id', 'annotations_grade_3',
                     'annotations_grade_2', 'annotations_grade_1'],
}
EXCLUDED_REFERENCES = {'PMID:35271311', 'PMCID:PMC9119736', 'PMC:PMC9119736',
                       'DOI:10.1126/science.abi6983', 'DOI:10.1101/2021.03.29.437450'}


def need(condition, message):
    if not condition:
        raise ValueError('OpenCell localization: ' + message)


def load_json(path):
    return json.loads(Path(path).read_text())


def pin(path):
    path = Path(path).resolve()
    need(path.is_file() and not path.is_symlink(), 'input must be an ordinary file.')
    return {'file': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def verify(spec):
    path = Path(spec['file'])
    need(path.is_file() and not path.is_symlink() and path.stat().st_size == spec['bytes']
         and sha(path) == spec['sha256'], 'input pin differs: ' + path.name)
    return path


def author_categories(path):
    """Read only literal constants/category lists; never execute author code."""
    tree = ast.parse(Path(path).read_text()); constants = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for statement in node.body:
                if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                        and isinstance(statement.targets[0], ast.Name)
                        and isinstance(statement.value, ast.Constant)
                        and isinstance(statement.value.value, str)):
                    constants[(node.name, statement.targets[0].id)] = statement.value.value

    def literal(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str): return node.value
        if isinstance(node, (ast.Tuple, ast.List)): return [literal(item) for item in node.elts]
        if isinstance(node, ast.Dict): return {literal(k): literal(v) for k,v in zip(node.keys,node.values)}
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            need((node.value.id,node.attr) in constants, 'unknown author constant.')
            return constants[(node.value.id,node.attr)]
        raise ValueError('OpenCell localization: nonliteral author category expression.')

    candidates = [node.value for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id == 'high_res_oc_hpa_labels' for t in node.targets)]
    need(len(candidates) == 1, 'expected one original high-resolution OC/HPA map.')
    rows = literal(candidates[0]); maps = {'oc': {}, 'hpa': {}}
    for row in rows:
        need(set(row) == {'consensus','oc','hpa'}, 'author category schema differs.')
        for kind in maps:
            values = row[kind] if isinstance(row[kind],list) else [row[kind]]
            for value in values:
                need(value not in maps[kind], 'ambiguous original category.')
                maps[kind][value] = row['consensus']
    return maps, sorted({r['consensus'] for r in rows})


def source_label_categories(level1, author):
    """Literal case/space vocabulary matching, never an inverse HOU grouping."""
    candidates = defaultdict(set)
    for name, category in author['hpa'].items():
        candidates[name.casefold().replace(' ', '-')].add(category)
    # Same literal generic comparison category remains generic.
    for category in set(author['hpa'].values()):
        candidates[category.casefold().replace(' ', '-')].add(category)
    mapped = {name: next(iter(candidates[name])) for name in level1 if len(candidates[name]) == 1}
    ambiguous = {name: sorted(candidates[name]) for name in level1 if len(candidates[name]) > 1}
    return mapped, ambiguous, sorted(set(level1)-mapped.keys()-ambiguous.keys())


def read_reference(path):
    """Keep grades and missing categories explicit, with one row per ENSG."""
    result = {}
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == SCHEMAS['localization'], 'localization CSV schema differs.')
        for row in reader:
            ensg = row['ensg_id']
            need(re.fullmatch(r'ENSG[0-9]{11}', ensg) and ensg not in result, 'invalid/duplicate reference ENSG.')
            categories = {}
            for grade in (1,2,3):
                text = row[f'annotations_grade_{grade}']
                values = [value.strip() for value in text.split(';') if value.strip()]
                need(len(values) == len(set(values)), 'duplicate localization category in grade.')
                categories[str(grade)] = values
            result[ensg] = {'target_name': row['target_name'], 'grades': categories}
    return result


def exact_metadata(path):
    """Require unique explicit accession/ENSG identity; retain all construct rows."""
    by_accession = defaultdict(list); by_ensg = defaultdict(list)
    with Path(path).open(newline='') as stream:
        reader=csv.DictReader(stream)
        need({'uniprot_id','ensg_id','enst_id','tagged_terminus','gene_name'} <= set(reader.fieldnames),
             'library identity/construct metadata missing.')
        for row in reader:
            need(row['uniprot_id'] and re.fullmatch(r'ENSG[0-9]{11}',row['ensg_id']), 'incomplete library identity.')
            by_accession[row['uniprot_id']].append(row);by_ensg[row['ensg_id']].append(row)
    good={}
    for accession,rows in by_accession.items():
        ensgs={r['ensg_id'] for r in rows}
        if len(ensgs)!=1: continue
        ensg=next(iter(ensgs))
        if {r['uniprot_id'] for r in by_ensg[ensg]}!={accession}: continue
        good['UniProtKB:'+accession]={'ensg_id':ensg,'construct_rows':rows}
    return good, {'library_rows':sum(map(len,by_accession.values())),
                  'unique_accessions':len(by_accession),'reciprocal_unique_proteins':len(good)}


def source_separated_native(native, subjects, crosswalk, active):
    labels={p:set() for p in subjects}; exclusions=Counter(); providers=Counter(); rows=0;seen=set()
    for row in native:
        if row['subject'] not in subjects: continue
        seen.add(row['subject'])
        reasons=[x for x in exclusion_reasons(row) if x!='not_experimental_evidence_code']
        if row['negated'] or row['aspect']!='C' or row['relation_literal']!='located_in' or row['go_id'] not in active:
            continue
        if reasons or row['go_id'] not in crosswalk: continue
        references=set(row['parsed']['DB:Reference'])
        if row['parsed']['Assigned_By']=='HPA':
            exclusions['HPA_assigned_rows']+=1;continue
        if references & EXCLUDED_REFERENCES:
            exclusions['explicit_OpenCell_reference_rows']+=1;continue
        labels[row['subject']].add(crosswalk[row['go_id']]);providers[row['parsed']['Assigned_By']]+=1;rows+=1
    return {p:sorted(ls) if p in seen else None for p,ls in labels.items()}, {'remaining_supporting_native_rows':rows,'remaining_provider_rows':dict(providers),
                    'excluded_native_rows':dict(exclusions),
                    'hidden_indirect_citation_reuse_excluded':False}


def score_reference(reference, identities, cohort, forecasts, author_map, label_map, classes, grades):
    frame = sorted(set(cohort)&identities.keys()); gold={}; private={}; unmapped=Counter()
    for pid in frame:
        identity=identities[pid];row=reference.get(identity['ensg_id'])
        if row is None: continue
        raw={value for grade in grades for value in row['grades'][str(grade)]}
        labels={author_map[x] for x in raw if x in author_map}
        unmapped.update(raw-author_map.keys())
        if not labels: continue
        gold[pid]=sorted(labels)
        private[pid]={'reference_ENSG':identity['ensg_id'],'raw_categories':sorted(raw),
                      'mapped_categories':sorted(labels),'construct_rows':identity['construct_rows']}
    metrics={};per_protein={}
    for arm,rows in forecasts.items():
        predicted={p: sorted({label_map[x] for x in rows[p] if x in label_map}) if rows[p] is not None else None for p in gold}
        metrics[arm],per_protein[arm]=positive_metrics(gold,predicted,classes)
        for pid in gold:private[pid].setdefault('predictions',{})[arm]=predicted[pid]
    baseline=ARMS[0];paired=[]
    for arm in ARMS[1:]:
        diffs=[per_protein[arm][p]['recovered']-per_protein[baseline][p]['recovered'] for p in gold]
        paired.append({'candidate':arm,'baseline':baseline,'improved_proteins':sum(x>0 for x in diffs),
                       'worse_proteins':sum(x<0 for x in diffs),'unchanged_proteins':sum(x==0 for x in diffs),
                       'net_recovered_labels':sum(diffs)})
    return {'grades':list(grades),'matched_protein_identity_coverage':len(frame),
            'evaluable_positive_reference_proteins':len(gold),'unmapped_reference_categories':dict(unmapped),
            'metrics':metrics,'paired':paired},private


def run(contract_path, expected, output):
    contract_path=Path(contract_path)
    need(sha(contract_path)==expected,'frozen contract hash differs.')
    contract=load_json(contract_path);specs=contract['inputs']
    paths={name:verify(spec) for name,spec in specs.items()}
    need(contract['status']=='fixed_before_OpenCell_cohort_outcome_join'
         and contract['arms']==list(ARMS) and contract['grade_profiles']==[[2,3],[3]], 'unsupported frozen policy.')
    output=Path(output);need(not output.exists(),'output must be new.');output.mkdir(parents=True)
    author,classes=author_categories(paths['author_definitions'])
    source=load_json(paths['HOU_source_readiness']);qualified=load_json(paths['qualified_GO_crosswalk'])
    mapping,ambiguous,unmapped=source_label_categories(source['level1'],author)
    need(not ambiguous,'ambiguous source comparison category.')
    old=load_json(paths['HOU_frozen_predictions'])['forecasts']
    forecasts={arm:{p:ls['level1'] for p,ls in old[arm].items()} for arm in ARMS[:-1]}
    subjects=set(forecasts[ARMS[0]])
    native_context=paths['native_context_report'].parent
    _,native,_=load_go_context(native_context)
    _,active,_,_=mitochondrial_terms(paths['ontology'],specs['ontology']['sha256'],'GO:0005739')
    forecasts[ARMS[-1]],separation=source_separated_native(native,subjects,qualified['qualified_exact_GO_crosswalk'],active)
    seal={'format':'biograph-steward.OpenCell-predictions-before-outcome-join.v1','created_at':utcnow(),
          'contract_sha256':expected,'producer_sha256':sha(__file__),'forecasts':forecasts,
          'author_comparison_classes':classes,'source_label_to_author_comparison':mapping,
          'unmapped_source_labels':unmapped,'source_separation':separation,
          'new_OpenCell_cohort_outcome_join_performed':False}
    write_json(output/'predictions_before_outcome_join.private.json',seal)
    # No original OpenCell localization-table row is read before this seal.
    reference=read_reference(paths['OpenCell_localization'])
    identities,identity_counts=exact_metadata(paths['OpenCell_library_metadata'])
    registry={}
    with paths['HGNC'].open(newline='') as stream:
        for row in csv.DictReader(stream,delimiter='\t'):registry[row['hgnc_id']]=row
    eligibility=load_json(paths['source_eligibility'])
    cohort=[r for r in eligibility['rows'] if r['primary_source_eligible']]
    reconciled={};identity_excluded=Counter()
    for row in cohort:
        pid=row['protein_id']
        if pid not in identities:identity_excluded['no_unique_library_accession']+=1;continue
        source_ENSG=registry.get(row['hgnc_id'],{}).get('ensembl_gene_id')
        if source_ENSG!=identities[pid]['ensg_id']:
            identity_excluded['registry_ENSG_disagreement_or_missing']+=1;continue
        reconciled[pid]=identities[pid]
    results=[];cases={}
    for grades in contract['grade_profiles']:
        report,private=score_reference(reference,reconciled,subjects,forecasts,author['oc'],mapping,classes,grades)
        results.append(report);cases['grades_'+''.join(map(str,grades))]=private
    report={'format':'biograph-steward.OpenCell-localization-source-separated-concordance.v1',
            'created_at':utcnow(),'contract_sha256':expected,'producer_sha256':sha(__file__),
            'cohort_primary_proteins':len(subjects),'reference_rows':len(reference),
            'identity':{**identity_counts,'reciprocal_accession_and_HGNC_ENSG_matches':len(reconciled),
                        'excluded_primary_proteins':dict(identity_excluded),
                        'exact_full_tested_protein_sequence_verified':False,
                        'tagged_transcript_and_terminus_retained':True},
            'source_separation':separation,'profiles':results,
            'reference_exposure':contract['reference_exposure'],
            'independent_whole_graph_accuracy_established':False,
            'blind_or_new_reference_evaluation':False,'biological_negatives_invented':False,
            'model_calls':0,'graph_changes':False,
            'limitations':contract['limitations']}
    write_json(output/'cases.private.json',cases);write_json(output/'report.json',report)
    for spec in specs.values():verify(spec)
    need(sha(contract_path)==expected and sha(__file__)==seal['producer_sha256'],'producer/contract changed.')
    write_json(output/'execution_receipt.json',{'contract_sha256':expected,'producer_sha256':sha(__file__),
        'reference_pins':specs,'source_seal_sha256':sha(output/'predictions_before_outcome_join.private.json'),
        'report_sha256':sha(output/'report.json'),'cases_sha256':sha(output/'cases.private.json'),
        'project_identifiers_sent_externally':False,'new_reference_or_model_selected_using_outcomes':False})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,required=True);parser.add_argument('--contract-sha256',required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(run(args.contract,args.contract_sha256,args.out),indent=2))
