"""Score frozen source-faithfulness proposals; never modify an app workspace.

All methods share the complete reserve frame. Abstentions remain in each
retained reference graph. Confidence intervals resample existing connected
source groups together, with identical multiplicities for every method.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sys

from biograph_steward.client import digest


FORMAT = 'biograph-steward.mechanistic-claim-assessment.v1'
METHODS = ('retain_all', 'native_counts', 'native_simple', 'nemotron', 'consensus')
PROPOSALS = frozenset(('retain_candidate', 'prune_candidate', 'abstain'))
MODEL_STATUSES = frozenset(('completed', 'model_error', 'invalid_output', 'context_abstain'))
DRAWS, SEED = 10000, 20261117


def need(condition, message):
    if not condition:
        raise ValueError('Mechanistic score: ' + message)


def _sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def _sealed(value, name):
    need(isinstance(value, dict), name + ' must be an object.')
    seal = value.get('content_sha256')
    need(isinstance(seal, str) and re.fullmatch('[0-9a-f]{64}', seal), name + ' lacks a content seal.')
    need(seal == digest({k: v for k, v in value.items() if k != 'content_sha256'}),
         name + ' content seal differs.')


def _indexed(rows, expected_ids, name):
    need(isinstance(rows, list), name + ' must be a list.')
    result = {}
    for row in rows:
        need(isinstance(row, dict), name + ' has a non-object row.')
        identifier = row.get('case_id')
        need(isinstance(identifier, str) and identifier in expected_ids,
             name + ' has an unexpected/missing case ID.')
        need(identifier not in result, name + ' duplicates a case ID.')
        result[identifier] = row
    need(set(result) == set(expected_ids), name + ' does not cover the complete expected frame.')
    return result


def _case_index(cases):
    need(isinstance(cases, list) and cases, 'source cases must be a nonempty list.')
    result, group_splits = {}, {}
    for case in cases:
        need(isinstance(case, dict), 'source case must be an object.')
        identifier, group, split = (case.get(k) for k in ('case_id', 'group_id', 'split'))
        need(isinstance(identifier, str) and identifier and identifier not in result,
             'source case IDs are missing or duplicated.')
        need(isinstance(group, str) and group and split in ('development', 'test'),
             'source group/split missing.')
        need(group not in group_splits or group_splits[group] == split,
             'a source group crosses development/reserve.')
        group_splits[group] = split
        statement = case.get('statement')
        need(isinstance(statement, dict) and 'belief' not in statement,
             'source Statement missing or released belief still present.')
        actual_sha = hashlib.sha256(json.dumps(statement, sort_keys=True, ensure_ascii=False,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        need(case.get('input_sha256') == actual_sha, 'source Statement input binding differs.')
        evidence = statement.get('evidence')
        need(isinstance(evidence, list) and evidence, 'complete original evidence missing.')
        need(case.get('all_original_evidence_admitted') is True
             and type(case.get('original_evidence_count')) is int
             and case['original_evidence_count'] == len(evidence),
             'source evidence admission/count differs.')
        need(all(isinstance(e, dict) and isinstance(e.get('source_api'), str)
                 and e['source_api'] for e in evidence), 'source API missing.')
        need(case.get('source_counts') == dict(Counter(e['source_api'] for e in evidence)),
             'source counts omit or change original evidence.')
        result[identifier] = case
    reserve = {key: value for key, value in result.items() if value['split'] == 'test'}
    need(bool(reserve), 'reserve frame is empty.')
    return result, reserve


def _envelope(artifact, reserve, protocol_sha256, source_cases_sha256, name):
    _sealed(artifact, name)
    need(artifact.get('protocol_sha256') == protocol_sha256, name + ' protocol binding differs.')
    need(artifact.get('source_cases_sha256') == source_cases_sha256,
         name + ' complete source-case file binding differs.')
    expected = {key: case['input_sha256'] for key, case in reserve.items()}
    need(artifact.get('input_bindings') == expected, name + ' reserve input bindings differ.')


def _native_rows(rows, reserve, name):
    indexed = _indexed(rows, reserve, name)
    normalized = {}
    for identifier, row in indexed.items():
        proposal = row.get('review_proposal')
        need(proposal in PROPOSALS, name + ' has an invalid proposal.')
        status = row.get('status')
        need(status in ('scored', 'abstain'), name + ' has an invalid native status.')
        need(row.get('source_counts') == reserve[identifier]['source_counts']
             and row.get('original_evidence_count') == reserve[identifier]['original_evidence_count'],
             name + ' native evidence/count input differs.')
        probability = row.get('probability_supported')
        if status == 'abstain':
            need(proposal == 'abstain' and probability is None,
                 name + ' invalid/error row must abstain.')
        else:
            need(type(probability) in (int, float) and math.isfinite(probability)
                 and 0 <= probability <= 1, name + ' invalid native probability.')
            expected = 'prune_candidate' if probability < 0.5 else 'retain_candidate'
            need(proposal == expected, name + ' changes the fixed0.5 threshold.')
        normalized[identifier] = {'case_id': identifier, 'proposal': proposal,
                                  'status': status, 'probability_supported': probability}
    return normalized


def _model_rows(rows, reserve):
    from .model_review import aggregate, request_for

    indexed = _indexed(rows, reserve, 'Nemotron rows')
    result = {}
    for identifier, row in indexed.items():
        need(row.get('input_sha256') == reserve[identifier]['input_sha256'],
             'Nemotron row input binding differs.')
        status, proposal = row.get('status'), row.get('proposal')
        need(status in MODEL_STATUSES and proposal in PROPOSALS,
             'Nemotron row status/proposal is invalid.')
        trace = row.get('trace')
        need(isinstance(trace, dict) or (status == 'context_abstain' and trace is None),
             'Nemotron row trace missing.')
        if status != 'completed':
            need(proposal == 'abstain', 'model/context/output failure must abstain.')
        if 'content_sha256' in row:
            _sealed(row, 'Nemotron individual row')
        prompt, schema, _ = request_for(reserve[identifier])
        for key, value in (('prompt_sha256', digest(prompt)), ('schema_sha256', digest(schema))):
            if key in row:
                need(row[key] == value, 'Nemotron row prompt/schema differs from complete source request.')
        if status == 'completed':
            need(trace.get('status') == 'completed', 'completed row has no completed transport result.')
            need(aggregate(trace.get('output'), schema) == proposal,
                 'Nemotron proposal differs from complete per-evidence output aggregation.')
            if 'input_sha256' in trace:
                need(trace['input_sha256'] == reserve[identifier]['input_sha256'],
                     'Nemotron trace source binding differs.')
            if 'schema_sha256' in trace:
                need(trace['schema_sha256'] == digest(schema), 'Nemotron trace schema binding differs.')
        need(not (proposal == 'prune_candidate' and (trace or {}).get('partial_source_inspection') is True),
             'partial-source inspection must not prune.')
        result[identifier] = {'case_id': identifier, 'proposal': proposal, 'status': status}
    return result


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def metrics(gold_by_id, predictions):
    """All denominators include abstentions; only explicit prune excludes a case."""
    need(set(gold_by_id) == set(predictions), 'metric frames differ.')
    counts = Counter({'claims': len(gold_by_id), 'gold_supported': 0,
                      'gold_unsupported': 0, 'removed_supported': 0,
                      'removed_unsupported': 0, 'abstained': 0})
    for identifier, gold in gold_by_id.items():
        need(gold in ('supported', 'unsupported'), 'unknown reference is not a negative.')
        proposal = predictions[identifier]['proposal']
        need(proposal in PROPOSALS, 'metric proposal invalid.')
        counts['gold_' + gold] += 1
        counts['removed_' + gold] += proposal == 'prune_candidate'
        counts['abstained'] += proposal == 'abstain'
    counts['removed'] = counts['removed_supported'] + counts['removed_unsupported']
    counts['remaining'] = counts['claims'] - counts['removed']
    counts['remaining_supported'] = counts['gold_supported'] - counts['removed_supported']
    counts['remaining_unsupported'] = counts['gold_unsupported'] - counts['removed_unsupported']
    counts['effective_retention_policy_correct'] = counts['remaining_supported'] + counts['removed_unsupported']
    counts['effective_retention_policy_incorrect'] = counts['remaining_unsupported'] + counts['removed_supported']
    positive_retention = _ratio(counts['remaining_supported'], counts['gold_supported'])
    incorrect_recall = _ratio(counts['removed_unsupported'], counts['gold_unsupported'])
    return {**dict(counts),
        'pruning_precision': _ratio(counts['removed_unsupported'], counts['removed']),
        'incorrect_claim_removal_recall': incorrect_recall,
        'gold_supported_retention_fraction': positive_retention,
        'retained_graph_supported_precision': _ratio(counts['remaining_supported'], counts['remaining']),
        'effective_retention_policy_reference_accuracy': _ratio(counts['effective_retention_policy_correct'], counts['claims']),
        'effective_retention_policy_balanced_accuracy': ((positive_retention + incorrect_recall) / 2
            if positive_retention is not None and incorrect_recall is not None else None),
        'accuracy_scope': 'Effective retain/prune policy against curator labels; abstentions retained, not counted as resolved model decisions.',
        'coverage': _ratio(counts['claims'] - counts['abstained'], counts['claims']),
        'abstentions_retained': True}


def _percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def paired_group_bootstrap(reserve, gold, methods, *, draws=DRAWS, seed=SEED):
    """Standard paired nonparametric cluster percentile bootstrap.

    Sample G existing connected source groups G times with replacement. Every
    member of each sampled group receives the same multiplicity, across arms.
    Intervals describe this frozen reference corpus, not new biological studies.
    """
    need(type(draws) is int and draws == DRAWS and type(seed) is int and seed == SEED,
         'predeclared10000draws/20261117seed required.')
    groups = defaultdict(list)
    for identifier in sorted(reserve):
        groups[reserve[identifier]['group_id']].append(identifier)
    names = sorted(groups)
    base = {'method': 'paired_connected_source_group_percentile_bootstrap',
            'draws': draws, 'seed': seed, 'groups': len(names),
            'same_group_multiplicities_across_all_methods': True,
            'source_group_membership_sha256': digest(dict(groups)),
            'sampling': 'G whole groups sampled G times with replacement; all group members retained together.',
            'interval_policy': 'Pointwise prespecified comparisons; not multiplicity-adjusted simultaneous confidence intervals.',
            'interpretation': 'Conditional reference-corpus variability; not independent biological replication or whole-Pharos accuracy.',
            'comparisons': []}
    if len(names) < 2:
        return {**base, 'status': 'unavailable_fewer_than_two_groups'}
    # Each entry holds (remaining supported, remaining claims), by group.
    contributions = {method: [(sum(gold[i] == 'supported' and rows[i]['proposal'] != 'prune_candidate'
                                    for i in groups[group]),
                                sum(rows[i]['proposal'] != 'prune_candidate' for i in groups[group]))
                               for group in names] for method, rows in methods.items()}
    comparison_keys = [(candidate, comparator) for candidate in METHODS
                       for comparator in ('retain_all', 'native_counts')
                       if candidate != comparator]
    differences = {key: [] for key in comparison_keys}
    point = {name: metrics(gold, rows)['retained_graph_supported_precision']
             for name, rows in methods.items()}
    rng = random.Random(seed)
    multiplicity_hash = hashlib.sha256()
    for _ in range(draws):
        weights = Counter(rng.randrange(len(names)) for _ in names)
        multiplicity_hash.update(json.dumps(sorted(weights.items()), separators=(',', ':')).encode() + b'\n')
        values = {}
        for method, entries in contributions.items():
            numerator = sum(entries[index][0] * count for index, count in weights.items())
            denominator = sum(entries[index][1] * count for index, count in weights.items())
            values[method] = _ratio(numerator, denominator)
        for key in comparison_keys:
            candidate, comparator = key
            if values[candidate] is not None and values[comparator] is not None:
                differences[key].append(values[candidate] - values[comparator])
    for (candidate, comparator), values in differences.items():
        observed = (point[candidate] - point[comparator]
                    if point[candidate] is not None and point[comparator] is not None else None)
        base['comparisons'].append({
            'candidate': candidate, 'comparator': comparator,
            'metric': 'retained_graph_supported_precision',
            'observed_difference': observed,
            'percentile_95_interval': ([_percentile(values, .025), _percentile(values, .975)] if values else None),
            'defined_paired_draws': len(values), 'undefined_paired_draws': draws - len(values),
            'interval_scope': ('all_paired_draws' if len(values) == draws else
                               'conditional_on_both_resampled_retained_graphs_nonempty'),
            'fraction_defined_draws_above_zero': _ratio(sum(x > 0 for x in values), len(values)),
            'fraction_above_zero_is_not_a_p_value': True,
        })
    return {**base, 'status': 'completed', 'sample_multiplicities_sha256': multiplicity_hash.hexdigest(),
            'random_generator': 'Python random.Random(MT19937)', 'python_version': sys.version.split()[0]}


def score_predictions(cases, labels, native_artifact, model_artifact, *,
                      protocol_sha256, source_cases_sha256):
    """Validate both sealed predictions before joining their curator labels."""
    all_cases, reserve = _case_index(cases)
    for pin in (protocol_sha256, source_cases_sha256):
        need(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin), 'invalid protocol/source file pin.')
    _envelope(native_artifact, reserve, protocol_sha256, source_cases_sha256, 'native predictions')
    _envelope(model_artifact, reserve, protocol_sha256, source_cases_sha256, 'model predictions')
    native = native_artifact.get('native_result')
    _sealed(native, 'native result')
    need(native.get('source_inputs_unchanged') is True
         and native.get('graph_changes') == 0 and native.get('proposals_applied') is False,
         'native result source-preservation contract missing.')
    need(native.get('model', {}).get('fit_split') == 'DEV_only'
         and native.get('model', {}).get('threshold') == 0.5
         and native.get('feature_policy', {}).get('reserve_labels_used') is False
         and native.get('feature_policy', {}).get('released_belief_used') is False,
         'native baseline fit/threshold/source policy differs.')
    development_ids = {key for key, case in all_cases.items() if case['split'] == 'development'}
    _indexed(native.get('development'), development_ids, 'native DEV rows')
    simple = native.get('simple_prior_comparator')
    need(isinstance(simple, dict) and simple.get('threshold') == 0.5
         and simple.get('released_belief_used') is False,
         'native fixed-prior comparator missing or policy differs.')
    counts = _native_rows(native.get('reserve'), reserve, 'native CountsScorer')
    prior = _native_rows(simple.get('reserve'), reserve, 'native SimpleScorer')
    model = _model_rows(model_artifact.get('rows'), reserve)
    retain = {key: {'case_id': key, 'status': 'deterministic', 'proposal': 'retain_candidate'} for key in reserve}
    consensus = {}
    for identifier in reserve:
        left, right = counts[identifier]['proposal'], model[identifier]['proposal']
        proposal = ('prune_candidate' if left == right == 'prune_candidate' else
                    'abstain' if 'abstain' in (left, right) else 'retain_candidate')
        consensus[identifier] = {'case_id': identifier, 'status': 'deterministic_intersection',
                                 'proposal': proposal, 'components': [left, right]}
    methods = dict(zip(METHODS, (retain, counts, prior, model, consensus)))
    # Labels are used only after frozen predictions and input contracts validate.
    label_rows = _indexed(labels, all_cases, 'curator reference labels')
    need(all(row.get('gold') in ('supported', 'unsupported')
             and row.get('all_original_evidence_curator_reviewed') is True
             for row in label_rows.values()), 'unknown/unreviewed reference is not a negative.')
    gold = {key: label_rows[key]['gold'] for key in reserve}
    result = {'format': FORMAT, 'status': 'completed',
              'protocol_sha256': protocol_sha256, 'source_cases_sha256': source_cases_sha256,
              'native_prediction_seal': native_artifact['content_sha256'],
              'model_prediction_seal': model_artifact['content_sha256'],
              'frame': {'reserve_claims': len(reserve),
                        'connected_source_groups': len({c['group_id'] for c in reserve.values()}),
                        'gold_supported': sum(v == 'supported' for v in gold.values()),
                        'gold_unsupported': sum(v == 'unsupported' for v in gold.values())},
              'methods': {name: metrics(gold, rows) for name, rows in methods.items()},
              'bootstrap': paired_group_bootstrap(reserve, gold, methods),
              'policy': {'abstentions_retained': True, 'native_threshold': 0.5,
                         'consensus': 'Prune only if native CountsScorer AND Nemotron explicitly propose pruning; retain disagreement; any abstention remains retained.',
                         'threshold_or_prompt_sweeps': False,
                         'corpus_previously_exposed_new_endpoint': True,
                         'whole_graph_biological_accuracy_claim': False,
                         'current_app_or_Pharos_graph_changed': False,
                         'truth_scope': 'Expert-relative source-claim faithfulness on a complete-source reference frame; not universal biological truth.'}}
    result['content_sha256'] = digest(result)
    return result, methods


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n')


def write_reference_views(output, cases, labels, methods):
    """Materialize typed native assessment views, preserving every retained source."""
    reserve = {case['case_id']: case for case in cases if case['split'] == 'test'}
    gold = {row['case_id']: row['gold'] for row in labels}
    files = {}
    for method in METHODS:
        folder = Path(output) / method
        folder.mkdir()
        ledger, kept_ids, kept = [], [], []
        for identifier in sorted(reserve):
            case, prediction = reserve[identifier], methods[method][identifier]
            excluded = prediction['proposal'] == 'prune_candidate'
            ledger.append({'case_id': identifier, 'group_id': case['group_id'],
                'input_sha256': case['input_sha256'], 'proposal': prediction['proposal'],
                'prediction_status': prediction['status'],
                'disposition': 'excluded_from_reference_view' if excluded else 'retained_in_reference_view',
                'curator_reference_label': gold[identifier],
                'original_evidence_count': case['original_evidence_count'],
                'original_source_hashes': [str(ev['source_hash']) for ev in case['statement']['evidence']],
                'applied_to_reference_assessment_view_only': True,
                'applied_to_app_or_Pharos_workspace': False})
            if not excluded:
                kept_ids.append(identifier)
                kept.append(deepcopy(case['statement']))
        graph = {'format': 'biograph-steward.retained-native-mechanistic-reference.v1',
            'method': method, 'statement_case_ids': kept_ids, 'statements': kept,
            'complete_original_evidence_preserved_for_retained_statements': True,
            'n_ary_complexes_and_native_conditions_preserved': True,
            'source_input_released_belief_excluded': True,
            'assessment_reference_view_only': True, 'app_or_Pharos_workspace_changed': False}
        graph['content_sha256'] = digest(graph)
        _write_json(folder / 'retained_reference_graph.json', graph)
        with (folder / 'dispositions.jsonl').open('w') as stream:
            for row in ledger:
                stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n')
        for path in folder.iterdir():
            files[str(path.relative_to(output))] = {'sha256': _sha(path), 'bytes': path.stat().st_size}
    return files


def run(protocol, protocol_sha256, source_cases, labels, native_predictions,
        model_predictions, output):
    paths = {key: Path(value) for key, value in (
        ('protocol', protocol), ('source_cases', source_cases), ('labels', labels),
        ('native_predictions', native_predictions), ('model_predictions', model_predictions))}
    need(all(p.is_file() and not p.is_symlink() for p in paths.values()),
         'ordinary frozen input files required.')
    pins = {key: _sha(path) for key, path in paths.items()}
    need(pins['protocol'] == protocol_sha256, 'frozen protocol raw SHA256 differs.')
    protocol_value = json.loads(paths['protocol'].read_text())
    need(isinstance(protocol_value, dict), 'frozen protocol must be an object.')
    protocol_inputs = protocol_value.get('input_files_sha256', {})
    need(protocol_inputs.get('source_cases') == pins['source_cases']
         and protocol_inputs.get('labels') == pins['labels'],
         'source cases/curator labels differ from frozen protocol pins.')
    scoring = protocol_value.get('scoring', {})
    need(scoring.get('bootstrap_replicates') == DRAWS and scoring.get('seed') == SEED,
         'frozen bootstrap settings differ.')
    scoring_code = scoring.get('code', {})
    need(scoring_code.get('sha256') == _sha(__file__)
         and isinstance(scoring_code.get('file'), str)
         and Path(scoring_code['file']).resolve() == Path(__file__).resolve(),
         'frozen scoring implementation differs.')
    with paths['source_cases'].open() as stream:
        cases = [json.loads(line) for line in stream]
    with paths['labels'].open() as stream:
        curator_labels = [json.loads(line) for line in stream]
    native, model = (json.loads(paths[name].read_text()) for name in ('native_predictions', 'model_predictions'))
    result, methods = score_predictions(cases, curator_labels, native, model,
        protocol_sha256=protocol_sha256, source_cases_sha256=pins['source_cases'])
    output = Path(output)
    need(not output.exists(), 'assessment output must be new.')
    output.mkdir(parents=True)
    result.pop('content_sha256')
    result['reference_view_files'] = write_reference_views(output, cases, curator_labels, methods)
    need(all(_sha(path) == pins[key] for key, path in paths.items()),
         'a frozen input changed during assessment.')
    result['input_files_sha256'] = pins
    result['scorer_sha256'] = _sha(__file__)
    result['all_frozen_inputs_unchanged'] = True
    result['content_sha256'] = digest(result)
    _write_json(output / 'report.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'protocol-sha256', 'source-cases', 'labels',
                 'native-predictions', 'model-predictions', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    report = run(args.protocol, args.protocol_sha256, args.source_cases, args.labels,
                 args.native_predictions, args.model_predictions, args.output)
    print(json.dumps({'status': report['status'], 'frame': report['frame'],
                      'content_sha256': report['content_sha256']}, sort_keys=True))
