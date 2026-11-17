"""Offline curator-reference concordance for source-native protein-pair scores.

The native graph is a functional-association source. Its presence and returned
weights are explicitly evaluated as proxies for physical assay labels; this
does not change graph predicates or create negative gold from absent edges.
Ranking uses scikit-learn, imported only by the optional assessment command.
"""
from collections import Counter
import argparse
import gzip
import json
import math
from pathlib import Path
import re

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha, new_output
from .mitocarta import binary_metrics


FORMAT = 'biograph-steward.public-ppi-reference-concordance.v1'
PRESENCE = 'A_captured_functional_graph_presence_proxy'
WEIGHT = 'B_native_functional_combined_weight_proxy'
ACCESSION = re.compile(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})')


def need(value, message):
    if not value:
        raise ValueError('PPI public reference: ' + message)


def pair_key(values):
    need(isinstance(values, (list, tuple)) and len(values) == 2,
         'exact two protein identifiers required.')
    result = []
    for value in values:
        need(isinstance(value, str) and value.strip() == value and value,
             'literal nonempty protein identifiers required.')
        if value.startswith('UniProtKB:'):
            value = value.split(':', 1)[1]
        need(ACCESSION.fullmatch(value) is not None, 'literal base UniProt accession required; no isoform/alias rescue.')
        result.append(value)
    return tuple(sorted(result))


def graph_index(graph):
    nodes = {pair_key((node, node))[0] for node in graph['nodes']}
    need(len(nodes) == len(graph['nodes']), 'duplicate native nodes.')
    pairs = {}
    for row in graph['pairs']:
        need(isinstance(row, list) and len(row) == 3, 'native pair schema differs.')
        key = pair_key(row[:2])
        value = row[2]
        need(set(key) <= nodes and key not in pairs, 'native endpoints/duplicate pair differ.')
        need(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
             'native source weight must be finite in [0,1].')
        pairs[key] = float(value)
    return nodes, pairs


def gold_rows(rows, profile):
    need(profile in ('canonical_sequence', 'manual_gene_pair'), 'reference profile differs.')
    result, seen = [], set()
    for row in rows:
        key = pair_key(row['base_accessions'] if profile == 'canonical_sequence'
                       else row['base_accession_pair'])
        need(key not in seen, 'duplicate gold protein pair.')
        seen.add(key)
        label = row['reference_label']
        need(label in ('positive', 'negative', 'unknown'), 'unknown label vocabulary.')
        if profile == 'canonical_sequence':
            need(label != 'unknown' and row['eligible_canonical_gold'] is True
                 and row['exact_full_canonical_sequence_match'] == [True, True]
                 and row['inferred_binding_region_sequence'] is False,
                 'canonical sequence/proteoform admission differs.')
            papers = set(row['pubmed_ids'])
        else:
            positive = bool(row['positive_reference_rows'])
            negative = bool(row['negative_reference_rows'])
            expected = 'unknown' if positive and negative else 'positive' if positive else 'negative'
            need((positive or negative) and label == expected,
                 'manual reference conflicts/absence cannot become known gold.')
            need(all(not item.get('generic_functional_association_truth_label', False)
                     for item in (row,)), 'manual assay gold misrepresented as functional truth.')
            papers = set(row['positive_PMIDs']) | set(row['negative_PMIDs'])
        result.append({'pair': key, 'gold': {'positive': 1, 'negative': 0, 'unknown': None}[label],
                       'source_label': label, 'publications': sorted(papers),
                       'reference': row})
    return result


def annotate_scores(reference, nodes, pairs):
    result = []
    for row in reference:
        key = row['pair']
        reason = ('self_pair_outside_declared_graph_proxy_domain' if key[0] == key[1]
                  else 'protein_outside_native_graph_universe' if not set(key) <= nodes else None)
        available = reason is None
        # Absence is a stated heuristic prediction, never an author gold label
        # or a source-returned numeric weight. Native numeric zero stays zero.
        presence = int(key in pairs) if available else None
        weight = pairs.get(key) if available else None
        result.append({**row, 'scores': {PRESENCE: presence, WEIGHT: weight},
                       'presence_unavailable_reason': reason,
                       'weight_unavailable_reason': reason or (
                           'no_native_pair_weight_returned' if key not in pairs else None)})
    return result


def ranking_metrics(rows, arm):
    from sklearn.metrics import average_precision_score, roc_auc_score
    eligible = [r for r in rows if r['gold'] is not None and r['scores'][arm] is not None]
    y = [r['gold'] for r in eligible]
    scores = [r['scores'][arm] for r in eligible]
    both = set(y) == {0, 1}
    return {'scored_pairs': len(y), 'positive_pairs': y.count(1), 'negative_pairs': y.count(0),
            'both_classes': both, 'AUROC': float(roc_auc_score(y, scores)) if both else None,
            'average_precision': float(average_precision_score(y, scores)) if both else None,
            'positive_prevalence': sum(y) / len(y) if y else None,
            'ranking_status': 'computed_conditional_on_published_curator_labels' if both else 'undefined_without_both_classes'}


def summary(rows):
    known = [r for r in rows if r['gold'] is not None]
    joint = [r for r in known if all(r['scores'][a] is not None for a in (PRESENCE, WEIGHT))]
    arms = {}
    for arm in (PRESENCE, WEIGHT):
        arms[arm] = {'available_reference_labels': dict(Counter(r['source_label'] for r in known if r['scores'][arm] is not None)),
                     'missing_reference_labels': dict(Counter(r['source_label'] for r in known if r['scores'][arm] is None)),
                     'unavailable_reasons': dict(Counter((r['presence_unavailable_reason'] if arm == PRESENCE else r['weight_unavailable_reason'])
                                                   for r in known if r['scores'][arm] is None)),
                     'ranking': ranking_metrics(known, arm)}
    arms[PRESENCE]['natural_boolean_decision'] = binary_metrics([(r['gold'], r['scores'][PRESENCE]) for r in known])
    # Weight has no tuned or invented binary cutoff. Paired ranking is evaluated
    # only on exactly the same available units for both fixed arms.
    paired = {arm: ranking_metrics(joint, arm) for arm in (PRESENCE, WEIGHT)}
    delta = {metric: (paired[WEIGHT][metric] - paired[PRESENCE][metric]
                      if paired[WEIGHT][metric] is not None else None)
             for metric in ('AUROC', 'average_precision')}
    return {'reference_rows': len(rows), 'reference_labels': dict(Counter(r['source_label'] for r in rows)),
            'unknown_conflict_rows_excluded_from_scoring': len(rows) - len(known),
            'arms': arms, 'same_available_pairs_comparison': {'pairs': len(joint), 'arms': paired,
                                                             'weight_minus_presence': delta},
            'confidence_interval': None, 'independent_experimental_confirmation': False,
            'whole_graph_scientific_accuracy': None, 'graph_improvement_demonstrated': False}


def checked(spec, root):
    path = Path(spec['file'])
    path = path.resolve() if path.is_absolute() else (root / path).resolve()
    need(path.is_relative_to(root) and path.is_file() and not path.is_symlink(), 'input is not an ordinary workspace file.')
    need(sha(path) == spec['sha256'], 'input byte pin differs: ' + path.name)
    return path


def run(plan_path, expected_sha256, output, *, root):
    root = Path(root).resolve()
    plan_path = Path(plan_path).resolve()
    need(sha(plan_path) == expected_sha256, 'score protocol hash differs.')
    plan = json.loads(plan_path.read_text())
    need(plan['format'] == FORMAT and plan['arms'] == [PRESENCE, WEIGHT], 'score contract or parent order differs.')
    need(plan['no_fit_or_threshold_selection'] is True, 'this profile performs no selection.')
    code = checked(plan['adapter_source'], root)
    need(code == Path(__file__).resolve(), 'different adapter source.')
    dependency = checked(plan['binary_metrics_source'], root)
    need(dependency == Path(binary_metrics.__code__.co_filename).resolve(), 'binary metric implementation differs.')
    graph_path = checked(plan['native_graph'], root)
    with gzip.open(graph_path, 'rt') as handle:
        graph = json.load(handle)
    nodes, pairs = graph_index(graph)
    need(len(nodes) == plan['native_graph_nodes'] and len(pairs) == plan['native_graph_pairs'], 'native graph frame differs.')
    references = []
    for spec in plan['reference_panels']:
        path = checked(spec, root)
        reference = gold_rows([json.loads(line) for line in path.read_text().splitlines() if line.strip()], spec['profile'])
        need(len(reference) == spec['expected_reference_rows']
             and dict(Counter(r['source_label'] for r in reference)) == spec['expected_label_counts'],
             'reference denominator or released label counts differ.')
        references.append((spec, path, reference))
    # All admission succeeds before a new output directory is created.
    folder = new_output(output, plan_path.parent, graph_path.parent)
    reports, generated = {}, {}
    for spec, path, reference in references:
        scored = annotate_scores(reference, nodes, pairs)
        key = spec['name']
        report = summary(scored)
        if spec.get('negative_paper_leave_one_out'):
            papers = sorted({p for row in scored if row['gold'] == 0 for p in row['publications']})
            report['negative_paper_leave_one_out'] = [
                {'excluded_paper': paper,
                 'excluded_rows_all_labels': sum(paper in r['publications'] for r in scored),
                 'result': summary([r for r in scored if paper not in r['publications']])}
                for paper in papers]
        if spec['profile'] == 'manual_gene_pair':
            for name, condition in (
                ('unfiltered_manual_negatives', lambda row: row['reference']['negative_unfiltered_manual_available']),
                ('IntAct_filtered_only_negatives', lambda row: row['reference']['negative_only_IntAct_filtered_manual'])):
                report[name] = summary([r for r in scored if r['gold'] != 0 or condition(r)])
        scored_path = folder / (key + '.scored.private.jsonl')
        scored_path.write_text(''.join(json.dumps(
            {**{k: v for k, v in row.items() if k != 'reference'},
             'reference_row_content_sha256': digest(row['reference'])},
            sort_keys=True) + '\n' for row in scored))
        generated[scored_path.name] = {'sha256': sha(scored_path), 'bytes': scored_path.stat().st_size}
        reports[key] = report
        need(sha(path) == spec['sha256'], 'reference changed while scoring.')
    import sklearn
    need(sklearn.__version__ == plan['sklearn_version'], 'ranking metric runtime version differs.')
    receipt = {'format': FORMAT, 'created_at': utcnow(), 'plan_sha256': expected_sha256,
               'adapter_sha256': sha(code), 'sklearn_version': sklearn.__version__,
               'native_nodes': len(nodes), 'native_pairs': len(pairs), 'results': reports,
               'files': generated, 'raw_native_weight_missing_is_not_zero': True,
               'nonedge_used_as_negative_gold': False, 'model_fitting_or_inference': False,
               'graph_changed': False, 'independent_experiment_claimed': False,
               'interpretation': plan['interpretation'], 'limits': plan['limits']}
    need(sha(plan_path) == expected_sha256 and sha(graph_path) == plan['native_graph']['sha256'], 'source changed during assessment.')
    need(sha(code) == plan['adapter_source']['sha256']
         and sha(dependency) == plan['binary_metrics_source']['sha256'], 'assessment source changed.')
    write_json(folder / 'report.private.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = run(args.plan, args.plan_sha256, args.out, root=args.root)
    print(json.dumps({'format': result['format'], 'references': list(result['results'])}))


if __name__ == '__main__':
    main()
