# SPDX-License-Identifier: GPL-3.0-only
"""Post-seal PK/BPO source explanation using existing native readers/helpers.

This diagnostic never relabels references, selects models/thresholds or computes
an alternative performance metric. Its generic join replaces the old display
runner's fixed six-example scope, preserving that runner's literal/ancestor
logic. Every source row remains identifiable, including NOT and duplicate rows.
"""
import argparse
import ast
from collections import Counter,defaultdict
import csv
import hashlib
import json
import logging
from pathlib import Path

from tools.learned_combination.core import need
from tools.learned_combination.reference import file_sha256
from .prepare import write_json

DEMO_COMMIT='0ab84edbaddf5fef11125dc8adbd19167c3cc038'
DEMO_PINS={'democafa/utils/ontology.py':'730f9c85d991770407cf12956e2ae06869b25e5e292a46e2493fe444b9993eb3',
           'democafa/utils/constants.py':'945ae48cf4f2be290c86960e4b524a5c8e1f2b452b52643ca2766743cb59b46c',
           'democafa/datacollection/retrieve_terms.py':'e5909345e09a076e54435fd485f5262c5efbba9e5a0d954116b7aba279445995'}
READER_SHA='d21dfb6abae206158944479e2584a455193c3c8a3b427f1993a1be75b34eaac8'
NS='biological_process'


def load_author(root):
    """Execute unchanged pinned native alias/edge/evidence helper bodies."""
    root=Path(root)
    for name,pin in DEMO_PINS.items():need(file_sha256(root/name)==pin,'changed native reference-construction source: '+name)
    import networkx as nx
    import pandas as pd
    namespace={'logger':logging.getLogger('postseal-source-provenance'),'nx':nx,'pd':pd};asts={}
    selected={'democafa/utils/ontology.py':{'clean_ontology_edges','replace_alternate_GO_terms','propagate_terms'},
              'democafa/datacollection/retrieve_terms.py':{'filter_evidence_codes'}}
    for path,names in selected.items():
        tree=ast.parse((root/path).read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        need({n.name for n in nodes}==names,'missing pinned reference helper.')
        module=ast.Module(body=nodes,type_ignores=[]);exec(compile(module,str(root/path),'exec'),namespace)
        asts[path]=hashlib.sha256(ast.dump(module,include_attributes=False).encode()).hexdigest()
    tree=ast.parse((root/'democafa/utils/constants.py').read_text())
    node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GO_CODES' for t in n.targets))
    codes=ast.literal_eval(node.value);accepted=namespace['filter_evidence_codes'](codes,'Experimental,IC,TAS')['Evidence']
    return namespace,accepted,set(codes['EXPERIMENTAL']),{'commit':DEMO_COMMIT,'source_pins':DEMO_PINS,'native_AST':asts}


def canonical_rows(rows,graph,replace):
    """Native reference aliases may differ from forecast alias expansion.

    Execute the original democafa mapping unchanged: its original graph order
    chooses one primary when an alternative ID is duplicated. Keep original
    native row IDs/fields alongside that reference-construction decision.
    """
    import pandas as pd
    frame=pd.DataFrame({'term':[r['go_id'] for r in rows]})
    if len(frame):frame=replace(frame,graph)
    return [{'native':row,'canonical_term':term,'alias_resolved':term!=row['go_id'],
             'canonical_in_view_graph':term in graph}
            for row,term in zip(rows,frame.term.tolist())]


def evidence_family(code,experimental):
    return ('Experimental' if code in experimental else 'IC' if code=='IC' else 'TAS' if code=='TAS' else 'not_reference_admission')


def support_index(rows,graph,accepted,experimental,*,wanted=None):
    """Child→parent reachability matches display_overlap and native closure."""
    import networkx as nx
    result=defaultdict(list);negative=defaultdict(list);ancestors={}
    wanted_by_protein=defaultdict(set)
    if wanted is not None:
        for protein,term in wanted:wanted_by_protein[protein].add(term)
    for record in rows:
        row=record['native'];term=record['canonical_term'];protein=row['subject'].split(':',1)[1]
        if not record['canonical_in_view_graph']:continue
        if row['negated']:
            negative[(protein,term)].append(row['id']);continue # Never propagate NOT.
        if row['evidence_code'] not in accepted:continue
        if graph.nodes[term].get('namespace')!=NS:continue
        if term not in ancestors:ancestors[term]=nx.descendants(graph,term)
        targets=ancestors[term]|{term}
        if wanted is not None:targets=targets&wanted_by_protein[protein]
        for target in targets:
            if target==term:
                kind='alias_direct' if record['alias_resolved'] else 'literal_direct';path=[term]
            else:kind='admitted_ancestor';path=nx.shortest_path(graph,term,target)
            predicates=[]
            for left,right in zip(path,path[1:]):
                if graph.is_multigraph():predicates.append(sorted(str(k) for k in graph[left][right]))
                else:predicates.append([str(graph[left][right].get('native_predicate','is_a_or_part_of'))])
            result[(protein,target)].append({'native_record_id':row['id'],'source_line':row['source_line'],
                'membership':kind,'source_term':row['go_id'],'canonical_source_term':term,
                'alias_resolved':record['alias_resolved'],'evidence_family':evidence_family(row['evidence_code'],experimental),
                'evidence_code':row['evidence_code'],'references':row['reference_identifiers'],
                'annotation_date':row['annotation_date'],'assigned_by':row['assigned_by'],
                'source_relation':row['relation_literal'],'product_form':row['gene_product_form_id'],
                'extension':row['annotation_extension_raw'],'with_from':row['with_from_raw'],
                'taxa':row['taxon_ids'],'ontology_path':path,'path_predicates':predicates,
                'reference_independence_established':False})
    for key in result:result[key].sort(key=lambda r:(r['source_line'],r['native_record_id']))
    return result,negative


def positive_presence(rows,graph,experimental,propagate):
    """T0 context markers only; no support marker is a new truth verdict."""
    import pandas as pd
    all_positive={};curated={};nonexperimental={}
    codes={r['native']['evidence_code'] for r in rows}
    for name,admission in [('any',codes),('curated',experimental|{'IC','TAS'}),('nonexperimental',codes-experimental-{'IC','TAS'})]:
        selected=[{'EntryID':r['native']['subject'].split(':',1)[1],'term':r['canonical_term'],'aspect':'P'}
                  for r in rows if r['canonical_in_view_graph'] and not r['native']['negated']
                  and r['native']['evidence_code'] in admission
                  and graph.nodes[r['canonical_term']].get('namespace')==NS]
        if not selected:continue
        frame=propagate(pd.DataFrame(selected),{'P':graph})
        index={(p,t):True for p,t in frame[['EntryID','term']].itertuples(index=False,name=None)}
        (all_positive if name=='any' else curated if name=='curated' else nonexperimental).update(index)
    return all_positive,curated,nonexperimental


def explain_pairs(pairs,t1_rows,t0_rows,graph,t0_graph,replace,accepted,experimental,propagate,*,view):
    """Retain every supporting row; unmatched/NOT stay explicitly unknown."""
    first=canonical_rows(t0_rows,t0_graph,replace);second=canonical_rows(t1_rows,graph,replace)
    support,negative=support_index(second,graph,accepted,experimental,wanted=set(pairs))
    old_any,old_curated,old_auto=positive_presence(first,t0_graph,experimental,propagate)
    exact={tuple(r['raw_fields']) for r in t0_rows};without_date={tuple(r['raw_fields'][:13]+r['raw_fields'][14:]) for r in t0_rows}
    by_id={r['id']:r for r in t1_rows};explained=[]
    for protein,term in sorted(set(pairs)):
        matches=[]
        for original in support.get((protein,term),[]):
            match=dict(original);raw=by_id[match['native_record_id']]['raw_fields']
            match['T0_exact_native_row_content_present']=tuple(raw) in exact
            match['T0_native_row_content_except_date_present']=tuple(raw[:13]+raw[14:]) in without_date
            matches.append(match)
        explained.append({'view':view,'accession':protein,'GO_ID':term,'positive_support':matches,
            'exact_NOT_native_record_ids':sorted(negative.get((protein,term),[])),
            'T0_any_positive_membership':bool(old_any.get((protein,term))),
            'T0_reference_admission_membership':bool(old_curated.get((protein,term))),
            'T0_nonexperimental_membership':bool(old_auto.get((protein,term))),
            'no_support_means_false_label':False,'scores_labels_models_or_thresholds_changed':False})
    return explained


def aggregate(explained,native_rows):
    """Separate label-row links, native rows, exact bundles and literal PMIDs."""
    ids={m['native_record_id'] for row in explained for m in row['positive_support']}
    unique={r['id']:r for r in native_rows if r['id'] in ids}
    bundles=Counter(tuple(r['reference_identifiers']) for r in unique.values())
    pmids={ref for r in unique.values() for ref in r['reference_identifiers'] if ref.startswith('PMID:')}
    links=[m for row in explained for m in row['positive_support']]
    return {'labels':len(explained),'labels_with_eligible_support':sum(bool(r['positive_support']) for r in explained),
        'labels_without_eligible_support':sum(not r['positive_support'] for r in explained),
        'label_row_links':len(links),'distinct_native_support_rows':len(unique),
        'membership_link_distribution':dict(Counter(m['membership'] for m in links)),
        'evidence_family_link_distribution':dict(Counter(m['evidence_family'] for m in links)),
        'distinct_row_evidence_code_distribution':dict(Counter(r['evidence_code'] for r in unique.values())),
        'distinct_row_assigner_distribution':dict(Counter(r['assigned_by'] for r in unique.values())),
        'distinct_row_annotation_dates':dict(Counter(r['annotation_date'] for r in unique.values())),
        'distinct_reference_bundles':len(bundles),'distinct_literal_PMID_identifiers':len(pmids),
        'top_reference_bundles_by_distinct_rows':[{'references':list(refs),'native_rows':count}
            for refs,count in sorted(bundles.items(),key=lambda x:(-x[1],x[0]))[:10]],
        'distinct_rows_with_forms':sum(bool(r['gene_product_form_id']) for r in unique.values()),
        'distinct_rows_with_extensions':sum(bool(r['annotation_extension_raw']) for r in unique.values()),
        'distinct_rows_with_with_from':sum(bool(r['with_from_raw']) for r in unique.values()),
        'independent_study_count_established':False,'annotation_date_is_publication_date':False,
        'duplicate_native_lines_preserved':True,'unmatched_predictions_are_biological_negatives':False}


def raw_source_coverage(rows,targets,accepted,experimental):
    """Post-opening descriptive counts before ontology/matching admission.

    These are raw source rows for exact forecast-target identities, across all
    aspects. They are not extra evaluation endpoints, independent studies or
    new biological truth labels. Duplicate lines retain their row identities.
    """
    subjects={r['subject'].split(':',1)[1] for r in rows}
    need(subjects<=set(targets),'native source scope exceeds exact forecast target identities.')
    curated=[r for r in rows if not r['negated'] and r['evidence_code'] in accepted]
    return {'forecast_target_identities':len(targets),'selected_native_rows':len(rows),
        'target_subjects_with_any_native_row':len(subjects),
        'target_subjects_without_native_rows':len(set(targets)-subjects),
        'selected_native_NOT_rows':sum(r['negated'] for r in rows),
        'selected_row_aspects':dict(Counter(r['aspect'] for r in rows)),
        'selected_row_evidence_codes':dict(Counter(r['evidence_code'] for r in rows)),
        'selected_row_evidence_families':dict(Counter(evidence_family(r['evidence_code'],experimental) for r in rows)),
        'reference_admission_positive_rows_before_ontology_projection':len(curated),
        'BPO_reference_admission_positive_rows_before_ontology_projection':sum(r['aspect']=='P' for r in curated),
        'selected_rows_with_forms':sum(bool(r['gene_product_form_id']) for r in rows),
        'selected_rows_with_extensions':sum(bool(r['annotation_extension_raw']) for r in rows),
        'selected_rows_with_with_from':sum(bool(r['with_from_raw']) for r in rows),
        'selected_rows_with_two_taxa':sum(len(r['taxon_ids'])==2 for r in rows),
        'selected_rows_matching_existing_consumed_reference_marker':sum(bool(r['known_consumed_reference_ids']) for r in rows),
        'exact_repeated_native_content_rows':len(rows)-len({r['raw_line_sha256'] for r in rows}),
        'independent_studies_or_complete_study_overlap_established':False,
        'ontology_or_reference_pair_filter_applied':False,
        'post_opening_descriptive_audit_not_performance_or_model_selection':True}


def check_gate(config):
    """Authorization must be checked before ANY source/seal path or hash read."""
    need(config.get('format')=='biograph-steward.postseal-provenance.v1'
         and config.get('parent_authorized_postseal_execution') is True,
         'parent must authorize completed forecast seal and primary assessment before provenance access.')
    from .assessment import open_seal
    cfg,seal=open_seal(config['forecast_seal_directory'])
    path=Path(config['forecast_seal_directory'])/'forecast_seal.json'
    need(file_sha256(path)==config['forecast_seal_sha256'],'accepted forecast seal differs.')
    assessment=Path(config['assessment_directory']);opening=json.loads((assessment/'reference_opening_gate.json').read_text())
    need(opening['forecast_seal_sha256']==config['forecast_seal_sha256']
         and opening['reference_opened_after_forecast_sealing'] is True,
         'existing primary evaluator must open the accepted seal first.')
    need(file_sha256(assessment/'report.json')==config['completed_assessment_report_sha256'],
         'completed immutable primary assessment report required.')
    return cfg,seal


def read_reference_ledger(spec):
    """Join ALL existing native reference-positive pairs; never select a score."""
    import math
    need(spec['all_reference_positive_pairs_retained'] is True and spec['threshold_used'] is None,
         'complete threshold-free evaluator ledger required.')
    need(file_sha256(spec['file'])==spec['sha256'],'changed frozen reference score ledger.')
    scores={}
    with Path(spec['file']).open() as stream:
        reader=csv.DictReader(stream,delimiter='\t')
        need(reader.fieldnames and reader.fieldnames[:2]==['EntryID','term']
             and len(reader.fieldnames)>2,'frozen native reference ledger schema differs.')
        arms=reader.fieldnames[2:]
        need(len(set(reader.fieldnames))==len(reader.fieldnames),'duplicate frozen ledger columns.')
        for row in reader:
            need(set(row)==set(reader.fieldnames),'malformed frozen ledger row.')
            key=(row['EntryID'],row['term']);need(key not in scores,'duplicate frozen reference pair.')
            values={arm:float(row[arm]) for arm in arms}
            need(all(math.isfinite(x) and 0<=x<=1+1e-10 for x in values.values()),'invalid frozen score; no rescaling or thresholding.')
            scores[key]=values
    need(len(scores)==spec['reference_positive_pairs'],'frozen reference-pair scope differs.')
    return sorted(scores),scores


def run(config,output):
    # No reference paths, hashes, helper loads or other files precede this gate.
    cfg,seal=check_gate(config)
    import obonet
    import networkx as nx
    from biograph_steward import go_qualification
    need(file_sha256(go_qualification.__file__)==READER_SHA,'changed qualified native GAF reader.')
    for path,pin in config['input_pins'].items():need(file_sha256(path)==pin,'changed post-seal source: '+path)
    helpers,accepted,experimental,source=load_author(config['democafa_root'])
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    targets=set(Path(cfg['targets']['file']).read_text().splitlines());gafs={};source_receipts={}
    for epoch,spec in config['gafs'].items():
        rows,receipt=go_qualification.read_native_gaf(spec['file'],targets,spec['sha256']);gafs[epoch]=rows;source_receipts[epoch]=receipt
        with (output/(epoch+'_native_selected.jsonl')).open('x') as stream:
            for row in rows:stream.write(json.dumps(row,sort_keys=True)+'\n')
    t0=helpers['clean_ontology_edges'](obonet.read_obo(cfg['references']['fixed_T0']['obo']['file']))
    need(nx.is_directed_acyclic_graph(t0),'native T0 ontology is cyclic.')
    report={'format':'biograph-steward.postseal-PK-BPO-provenance.v1','source_receipts':source_receipts,
        'raw_source_coverage':{epoch:raw_source_coverage(rows,targets,accepted,experimental)
                               for epoch,rows in gafs.items()},
        'raw_source_coverage_chronology':'Selected-target raw-row coverage counts were specified after the admitted forecast seal/reference opening. They are descriptive source audit fields, not an additional performance endpoint or model choice.',
        'forecast_seal_sha256':config['forecast_seal_sha256'],'primary_assessment_report_sha256':config['completed_assessment_report_sha256'],
        'native_reference_helpers':source,'views':{},'scores_labels_models_choices_or_thresholds_changed':False,
        'limitations':['Experimental,IC,TAS admission families are reported separately.','References on one row may alias one single reference; no independent-study count is inferred.','Dates describe annotation curation, not publication or discovery timing.','Ancestor membership is ontology-derived support, not a direct assay for each ancestor.','NOT is retained but never propagated into positive support.','Native rows retain forms/extensions/with-from; these contexts do not repair or backfill graph claims.','No new metric, deployment threshold, label verdict or model selection is performed.']}
    assessment_report=json.loads((Path(config['assessment_directory'])/'report.json').read_text())
    for view in ('native','fixed_T0'):
        graph=helpers['clean_ontology_edges'](obonet.read_obo(cfg['references'][view]['obo']['file']));need(nx.is_directed_acyclic_graph(graph),'native view ontology is cyclic.')
        ledger=assessment_report['views'][view]['cells']['PK/'+NS]['positive_reference_score_ledger']
        pairs,frozen_scores=read_reference_ledger(ledger)
        explained=explain_pairs(pairs,gafs['T1'],gafs['T0'],graph,t0,helpers['replace_alternate_GO_terms'],accepted,experimental,helpers['propagate_terms'],view=view)
        for row in explained:
            row['frozen_model_scores']=frozen_scores[(row['accession'],row['GO_ID'])]
            row['model_score_threshold_used']=None
        path=output/(view+'_all_label_support.jsonl')
        with path.open('x') as stream:
            for row in explained:stream.write(json.dumps(row,sort_keys=True)+'\n')
        cases=output/(view+'_deterministic_cases.tsv')
        with cases.open('x',newline='') as stream:
            writer=csv.writer(stream,delimiter='\t');writer.writerow(['accession','GO_ID','support_rows','membership_kinds','evidence_families','T0_nonexperimental_membership','complete_trace'])
            for row in explained[:12]:writer.writerow([row['accession'],row['GO_ID'],len(row['positive_support']),','.join(sorted({m['membership'] for m in row['positive_support']})),','.join(sorted({m['evidence_family'] for m in row['positive_support']})),row['T0_nonexperimental_membership'],path.name])
        report['views'][view]={'aggregate':aggregate(explained,gafs['T1']),'frozen_reference_score_ledger':ledger,'case_level_scores_are_aggregate_publication':False,'complete_label_support_file':str(path),'sha256':file_sha256(path),'deterministic_cases_file':str(cases),'case_selection':'First12 sorted accession/GO pairs, independent of prediction performance.'}
    write_json(output/'report.json',report);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(json.loads(Path(args.config).read_text()),args.output)


if __name__=='__main__':main()
