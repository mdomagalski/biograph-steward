"""Fixed GO-localization heuristics against the author's MitoCarta inventory.

This is gene-level curator-reference concordance, with explicitly unknown
reference outcomes. It does not re-label historical Pharos annotation-existence
records or claim an independently replicated experiment. The existing native
GO reader verifies every selected row against the complete original GAF.
"""
from collections import Counter, defaultdict
import argparse
import gzip
import json
import math
from pathlib import Path

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.go_context_inspection import load_go_context
from biograph_steward.go_native_support import exclusion_reasons
from biograph_steward.go_ontology_qualification import load_ontology

ARMS = ('A_raw_Pharos', 'A_retained_control', 'B_native_location',
        'C_native_experimental_location')
PART_OF = 'http://purl.obolibrary.org/obo/BFO_0000050'
GO_IRI = 'http://purl.obolibrary.org/obo/GO_'
MIN_MCNEMAR_DISCORDANCE = 6  # smallest exact two-sided test that can reach .05


def need(value, message):
    if not value:
        raise ValueError('MitoCarta assessment: ' + message)


def pinned(path, expected):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and sha(path) == expected,
         'ordinary input or byte pin differs: ' + path.name)
    return path


def gene_key(value):
    """Use literal Entrez identity; symbols/secondary accessions are not rescues."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value)) if math.isfinite(value) and value > 0 and int(value) == value else None
    if isinstance(value, str) and value.isascii() and value.isdecimal() and value[0:1] != '0':
        return value
    return None


def author_labels(rows):
    """Keep zero/unlisted genes unknown, even when old training flags say nonmito."""
    result = {}
    for row in rows:
        key = gene_key(row['HumanGeneID'])
        if key is None:
            continue  # e.g. the publisher's one Ensembl-only entry, not a GeneID
        need(key not in result, 'duplicate author GeneID requires adjudication.')
        value = row['MitoCarta3.0_List']
        result[key] = {'label': 1 if value == 'MitoCarta3.0' else
                       0 if value == 'mito-interacting' else None,
                       'author_category': str(value)}
    return result


def read_author_workbook(path, expected):
    path = pinned(path, expected)
    try:
        import xlrd
    except ImportError as exc:
        raise ValueError('Reading author XLS requires optional xlrd==2.0.2.') from exc
    need(xlrd.__version__ == '2.0.2', 'use qualified xlrd==2.0.2.')
    book = xlrd.open_workbook(path, on_demand=True)
    try:
        sheet = book.sheet_by_name('B Human All Genes')
        headers = sheet.row_values(0)
        need(len(headers) == len(set(headers)) and
             {'HumanGeneID', 'MitoCarta3.0_List'} <= set(headers), 'author workbook schema differs.')
        result = author_labels(dict(zip(headers, sheet.row_values(i))) for i in range(1, sheet.nrows))
    finally:
        book.release_resources()
    pinned(path, expected)
    return result


def mitochondrial_terms(path, expected, root):
    nodes, binding, _ = load_ontology(path, expected)
    raw = Path(path).read_bytes()
    graph = json.loads(gzip.decompress(raw) if raw.startswith(b'\x1f\x8b') else raw)['graphs'][0]
    reverse = defaultdict(set)
    for row in graph['edges']:
        if row['pred'] not in ('is_a', PART_OF):
            continue
        child, parent = (row[key].replace(GO_IRI, 'GO:') for key in ('sub', 'obj'))
        if child in nodes and parent in nodes:
            reverse[parent].add(child)
    need(root in nodes, 'mitochondrion root missing.')
    closure = {root}; todo = [root]
    while todo:
        for child in reverse[todo.pop()] - closure:
            closure.add(child); todo.append(child)
    active = {uid for uid, n in nodes.items() if not n.get('meta', {}).get('deprecated', False)}
    return closure, active, set(nodes), binding


def graph_predictions(graph, subjects, complete, closure, recognized):
    positives = Counter(); unresolved = Counter()
    for edge in graph['edges']:
        if (edge.get('record_kind') != 'go_annotation' or edge['subject'] not in subjects
                or edge.get('aggregator') != 'Pharos'):
            continue
        need(edge['object'] == edge['evidence_record'].get('goid'), 'source GO identity differs.')
        if edge['evidence_record'].get('type') != 'C':
            continue
        term = edge['object']
        if term not in recognized:
            unresolved[edge['subject']] += 1
        if term in closure:
            positives[edge['subject']] += 1
    return {pid: {'prediction': int(positives[pid] > 0) if complete.get(pid, False) else None,
                  'positive_source_rows': positives[pid],
                  'unrecognized_CC_term_rows': unresolved[pid]} for pid in subjects}


def native_predictions(native, subjects, closure, active, *, experimental):
    seen = Counter(); positives = Counter(); exclusions = Counter()
    for row in native:
        pid = row['subject']
        if pid not in subjects:
            continue
        seen[pid] += 1
        reasons = exclusion_reasons(row)
        if not experimental:
            reasons = [r for r in reasons if r != 'not_experimental_evidence_code']
        if row['negated']:
            reasons.append('NOT_not_a_positive_prediction')
        if row['aspect'] != 'C' or row['relation_literal'] != 'located_in':
            reasons.append('outside_positive_CC_located_in_profile')
        if row['go_id'] not in active:
            reasons.append('term_not_active_in_pinned_ontology')
        if reasons:
            exclusions.update(reasons)
        elif row['go_id'] in closure:
            positives[pid] += 1
    return ({pid: {'prediction': int(positives[pid] > 0) if seen[pid] else None,
                    'positive_source_rows': positives[pid], 'native_rows_present': seen[pid]}
             for pid in subjects}, dict(exclusions))


def gene_or(values):
    need(all(v is None or type(v) is int and v in (0, 1) for v in values), 'invalid predictor value.')
    return 1 if 1 in values else None if not values or None in values else 0


def binary_metrics(pairs):
    counts = Counter()
    for y, prediction in pairs:
        need(y in (0, 1) and (prediction is None or type(prediction) is int and prediction in (0, 1)),
             'invalid outcome/prediction.')
        if prediction is None:
            counts['abstain'] += 1
        else:
            counts[{(1, 1): 'TP', (1, 0): 'FN', (0, 1): 'FP', (0, 0): 'TN'}[(y, prediction)]] += 1
    tp, fn, fp, tn = (counts[k] for k in ('TP', 'FN', 'FP', 'TN'))
    ratio = lambda a, b: a / b if b else None
    precision = ratio(tp, tp + fp); recall = ratio(tp, tp + fn); specificity = ratio(tn, tn + fp)
    denom = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    return {**{k: counts[k] for k in ('TP', 'FN', 'FP', 'TN', 'abstain')},
        'scored': tp + fn + fp + tn, 'gold_known': len(pairs), 'precision': precision,
        'recall': recall, 'F1': ratio(2 * tp, 2 * tp + fp + fn), 'specificity': specificity,
        'balanced_accuracy': (recall + specificity) / 2 if recall is not None and specificity is not None else None,
        'MCC': (tp * tn - fp * fn) / math.sqrt(denom) if denom else None,
        'accuracy': ratio(tp + tn, tp + fn + fp + tn)}


def paired_correctness(rows, left, right):
    comparable = [r for r in rows if r['gold'] in (0, 1)
                  and r['predictions'][left] is not None and r['predictions'][right] is not None]
    better = sum(r['predictions'][left] != r['gold'] and r['predictions'][right] == r['gold'] for r in comparable)
    worse = sum(r['predictions'][left] == r['gold'] and r['predictions'][right] != r['gold'] for r in comparable)
    n = better + worse
    both = {r['gold'] for r in comparable} == {0, 1}
    sufficient = n >= MIN_MCNEMAR_DISCORDANCE
    p = min(1., 2 * sum(math.comb(n, k) for k in range(min(better, worse) + 1)) / 2 ** n) if both and sufficient else None
    return {'baseline': left, 'candidate': right, 'paired_known_gold_units': len(comparable),
        'candidate_only_correct': better, 'baseline_only_correct': worse,
        'discordant_units': n, 'both_gold_classes_present': both,
        'minimum_discordance_for_exact_test': MIN_MCNEMAR_DISCORDANCE,
        'exact_McNemar_two_sided_p': p,
        'test_status': 'computed_conditional_on_curator_reference' if p is not None else
                       'not_computed_one_class_or_low_discordance',
        'population_or_independent_experimental_confirmation': False}


def assess(eligibility, protein_predictions, labels):
    groups = defaultdict(list)
    for row in eligibility['rows']:
        if row['primary_source_eligible']:
            groups[row['gene_id']].append(row['protein_id'])
    cases = []
    for gid, pids in sorted(groups.items()):
        gold = labels.get(gid, {'label': None, 'author_category': 'unmatched_GeneID'})
        cases.append({'gene_id': gid, 'protein_ids': pids, 'gold': gold['label'],
            'author_category': gold['author_category'],
            'predictions': {a: gene_or([protein_predictions[a][p]['prediction'] for p in pids]) for a in ARMS}})
    coverage = {}
    for primary in (True, False):
        rs = [r for r in eligibility['rows'] if primary is False or r['primary_target']]
        name = 'primary_protein_nodes' if primary else 'all_workspace_protein_nodes_coverage_only'
        ls = [labels.get(r['gene_id'], {'label': None})['label'] if r['reviewed_canonical_identity_eligible'] else None for r in rs]
        coverage[name] = {'protein_nodes': len(rs), 'gold_positive': ls.count(1),
            'gold_explicit_outside_inventory': ls.count(0), 'gold_unknown': ls.count(None),
            'scientific_accuracy_of_all_graph_claims': None}
    metrics = {a: binary_metrics([(r['gold'], r['predictions'][a]) for r in cases if r['gold'] is not None]) for a in ARMS}
    report = {'format': 'biograph-steward.mitocarta-curator-reference-concordance.v1',
        'scope': 'Frozen original-primary gene-level inventory classification; no historical GO truth relabelling',
        'primary_gene_units': len(cases), 'primary_gene_gold_positive': sum(r['gold'] == 1 for r in cases),
        'primary_gene_gold_explicit_outside_inventory': sum(r['gold'] == 0 for r in cases),
        'primary_gene_gold_unknown': sum(r['gold'] is None for r in cases),
        'coverage': coverage, 'metrics': metrics,
        'paired_comparisons': [paired_correctness(cases, 'A_raw_Pharos', a) for a in ARMS[1:]],
        'gold_is_expert_curator_inventory': True, 'new_independent_experiments': False,
        'study_and_upstream_source_overlap_excluded': False,
        'whole_graph_biological_accuracy_established': False,
        'historical_has_GO_annotation_truth_relabelled': False,
        'unlisted_reference_genes_treated_as_negative': False,
        'WithFrom_exclusion_is_declared_strict_profile_not_GAF_invalidity': True,
        'graph_model_or_app_defaults_changed': False,
        'limits': ['Static2020 gene-level expert inventory; no isoform/cell-state universality.',
            'GO/UniProt literature nominated some curator candidates; study reuse remains possible.',
            'Fixed source/semantic profiles change annotations and coverage together, not an isolated pruning effect.',
            'All zero/unlisted reference values stay unknown. A negative classifier output is a heuristic decision, not proof of biological absence.',
            'Known-label descriptive cohort metrics do not estimate the precision of all graph assertions.']}
    return report, cases


def run(contract_path, contract_sha256, context, output):
    contract_path = pinned(contract_path, contract_sha256)
    contract = json.loads(contract_path.read_text())
    need(contract['format'] == 'biograph-steward.mitocarta-bounded-reference-frozen-contract.v1'
         and contract['status'] == 'frozen_before_cohort_label_join'
         and set(contract['arms']) == set(ARMS), 'a reviewed frozen four-arm contract is required.')
    es = contract['source_eligibility']
    epath = pinned(contract_path.parent / es['file'], es['sha256'])
    eligibility = json.loads(epath.read_text())
    inputs = eligibility['input_pins']
    for entry in inputs.values(): pinned(entry['file'], entry['sha256'])
    need(eligibility['primary_unique_gene_units'] == es['eligible_primary_gene_units']
         and eligibility['primary_source_eligible'] == es['eligible_primary_proteins'], 'frozen frame differs.')
    original = json.loads(Path(inputs['original_graph']['file']).read_text())
    retained = json.loads(Path(inputs['current_graph']['file']).read_text())
    go = contract['ontology']; need(go['sha256'] == inputs['ontology']['sha256'], 'ontology contract pin differs.')
    closure, active, recognized, ontology = mitochondrial_terms(go['file'], go['sha256'], go['root'])
    native_report, native, _ = load_go_context(context)
    need(native_report['source']['gaf_sha256'] == inputs['native_GAF']['sha256']
         and native_report['source_graph_file_sha256'] == inputs['original_graph']['sha256'], 'native source chain differs.')
    subjects = {r['protein_id'] for r in eligibility['rows'] if r['primary_source_eligible']}
    complete = {r['protein_id']: r['Pharos_GO_documented_complete'] for r in eligibility['rows']}
    predictions = {'A_raw_Pharos': graph_predictions(original, subjects, complete, closure, recognized),
        'A_retained_control': graph_predictions(retained, subjects, complete, closure, recognized)}
    exclusions = {}
    for arm, experimental in [('B_native_location', False), ('C_native_experimental_location', True)]:
        predictions[arm], exclusions[arm] = native_predictions(native, subjects, closure, active, experimental=experimental)
    folder = new_output(output, contract_path.parent, context)
    code_sha = sha(__file__)
    seal = {'format': 'biograph-steward.mitocarta-predictions-before-reference-join.v1',
        'created_at': utcnow(), 'frozen_contract_sha256': contract_sha256,
        'source_eligibility_sha256': es['sha256'], 'producer_sha256': code_sha,
        'cohort_reference_labels_opened': False, 'metrics_computed': False,
        'ontology': ontology, 'mitochondrial_closure_terms': len(closure),
        'native_report_sha256': sha(Path(context) / 'go_context_qualification.json'),
        'strict_profile_exclusion_reason_counts': exclusions, 'protein_predictions': predictions}
    write_json(folder / 'predictions_before_reference_join.json', seal)
    seal_sha = sha(folder / 'predictions_before_reference_join.json')
    reference = contract['author_reference']
    # First reference-table read is intentionally below the exclusive prediction seal.
    labels = read_author_workbook(contract_path.parent / reference['file'], reference['sha256'])
    report, cases = assess(eligibility, predictions, labels)
    report.update(created_at=utcnow(), frozen_contract_sha256=contract_sha256,
        source_eligibility_sha256=es['sha256'], reference_file_sha256=reference['sha256'],
        predictions_before_reference_join_sha256=seal_sha, producer_sha256=code_sha,
        reference_global_label_counts=dict(Counter('positive' if x['label'] == 1 else
            'explicit_outside_inventory' if x['label'] == 0 else 'unknown' for x in labels.values())))
    need(sha(folder / 'predictions_before_reference_join.json') == seal_sha, 'prediction seal changed.')
    for entry in inputs.values(): pinned(entry['file'], entry['sha256'])
    pinned(contract_path, contract_sha256); pinned(epath, es['sha256'])
    need(sha(__file__) == code_sha, 'producer changed during execution.')
    with (folder / 'cases.private.jsonl').open('x') as stream:
        for row in cases: stream.write(json.dumps(row, sort_keys=True) + '\n')
    write_json(folder / 'report.json', report)
    write_json(folder / 'execution_receipt.json', {'created_at': utcnow(),
        'format': 'biograph-steward.mitocarta-execution.v1', 'contract_sha256': contract_sha256,
        'predictions_sealed_before_cohort_gold_join': True, 'native_complete_source_replay': True,
        'reference_file_sha256': reference['sha256'], 'producer_sha256': code_sha,
        'input_pins': inputs, 'files': {p.name: sha(p) for p in sorted(folder.iterdir()) if p.is_file()},
        'model_calls': 0, 'new_source_fetches_by_runner': 0, 'graph_or_old_reference_changed': False})
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--contract', type=Path, required=True)
    p.add_argument('--contract-sha256', required=True)
    p.add_argument('--context', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = run(a.contract, a.contract_sha256, a.context, a.out)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
