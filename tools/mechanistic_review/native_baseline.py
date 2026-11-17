"""Optional INDRA-native source-count baseline; MIT adapter, no core dependency.

The caller supplies native Statements and DEV-only labels. Reserve labels and
released Statement.belief values are deliberately absent from this interface.
The enclosing frozen runner owns source admission, split construction and files.
"""
from collections import Counter
import hashlib
import importlib.metadata
import inspect
import json
import math
from pathlib import Path
import re
import warnings


FORMAT = 'biograph-steward.indra-native-counts-baseline.v1'
PARAMETERS = {'C': 1.0, 'solver': 'lbfgs', 'max_iter': 1000,
              'random_state': 20261117}
FEATURE_OPTIONS = {'include_more_specific': False, 'use_stmt_type': False,
                   'use_num_members': False, 'use_num_pmids': False,
                   'use_promoter': False, 'use_avg_evidence_len': False,
                   'use_residue_position': False}


def _need(condition, message):
    if not condition:
        raise ValueError('INDRA native baseline: ' + message)


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _runtime():
    # These imports stay in the optional research path, never the application.
    from indra.belief import SimpleScorer
    from indra.belief.skl import CountsScorer
    from indra.statements import Statement
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    _need(importlib.metadata.version('indra') == '1.24.0',
          'this adapter requires the qualified INDRA 1.24.0 API.')
    return CountsScorer, SimpleScorer, Statement, LogisticRegression, ConvergenceWarning


def _inputs(statements, identifiers, statement_class, split):
    _need(isinstance(statements, (list, tuple)) and isinstance(identifiers, (list, tuple)),
          split + ' inputs must be explicit ordered lists or tuples.')
    _need(len(statements) == len(identifiers), split + ' statement/ID lengths differ.')
    _need(all(isinstance(x, str) and x and x.strip() == x for x in identifiers)
          and len(set(identifiers)) == len(identifiers), split + ' IDs are empty or duplicated.')
    rows, keys = [], []
    for identifier, statement in zip(identifiers, statements):
        _need(isinstance(statement, statement_class), 'native INDRA Statements required.')
        # matches_key and Evidence.to_json do not access Statement.belief.
        key = statement.matches_key()
        _need(isinstance(key, str) and key, 'native statement identity is missing.')
        keys.append(key)
        evidence = list(statement.evidence)
        _need(bool(evidence), split + ' statement has no original evidence.')
        sources = [ev.source_api for ev in evidence]
        _need(all(isinstance(s, str) and s and s.strip() == s for s in sources),
              split + ' original evidence has a missing source API.')
        rows.append({'case_id': identifier, 'claim_identity_sha256': _digest(key),
                     'evidence_sha256': _digest([ev.to_json() for ev in evidence]),
                     'original_evidence_count': len(evidence),
                     'source_counts': dict(sorted(Counter(sources).items()))})
    _need(len(set(keys)) == len(keys), split + ' contains duplicate native claims.')
    return rows, set(keys)


def _abstain(row, reason, *, detail=None):
    result = {**row, 'status': 'abstain', 'probability_supported': None,
              'prediction': None, 'review_proposal': 'abstain',
              'reason': reason, 'native_features': None}
    if detail:
        result['error'] = {'type': type(detail).__name__, 'message': str(detail)[:240]}
    return result


def _prediction(row, probability, *, features=None):
    probability = float(probability)
    _need(math.isfinite(probability) and 0 <= probability <= 1,
          'native model returned an invalid probability.')
    return {**row, 'status': 'scored', 'probability_supported': probability,
            'prediction': int(probability >= 0.5),
            'review_proposal': 'prune_candidate' if probability < 0.5 else 'retain_candidate',
            'reason': 'fixed_probability_threshold_0.5', 'native_features': features}


def _source_pin(obj):
    path = Path(inspect.getsourcefile(obj)).resolve()
    return {'module': obj.__module__, 'class': obj.__qualname__,
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def fit_predict_native(dev_statements, dev_labels_by_id, dev_ids,
                       reserve_statements, reserve_ids, *, include_simple=True):
    """Fit native CountsScorer on DEV and predict reserve without its labels.

    ``dev_labels_by_id`` must map exactly the DEV IDs to integer 0/1 labels.
    No source evidence is dropped or deduplicated. The vocabulary is DEV-only;
    a reserve row with unseen sources abstains because native CountsScorer
    otherwise logs and silently ignores those sources. No fallback prediction
    replaces that abstention. SimpleScorer is a separately reported fixed-prior
    comparator. Neither comparator applies its review proposals to a graph.
    """
    CountsScorer, SimpleScorer, Statement, LogisticRegression, ConvergenceWarning = _runtime()
    _need(type(include_simple) is bool, 'include_simple must be Boolean.')
    dev_rows, dev_keys = _inputs(dev_statements, dev_ids, Statement, 'DEV')
    reserve_rows, reserve_keys = _inputs(reserve_statements, reserve_ids, Statement, 'reserve')
    _need(bool(dev_rows), 'DEV is empty.')
    _need(not (set(dev_ids) & set(reserve_ids)), 'DEV and reserve IDs overlap.')
    _need(not (dev_keys & reserve_keys), 'DEV and reserve native claims overlap.')
    _need(isinstance(dev_labels_by_id, dict) and set(dev_labels_by_id) == set(dev_ids),
          'labels must be keyed by exactly DEV IDs; reserve/unknown labels are forbidden.')
    labels = [dev_labels_by_id[identifier] for identifier in dev_ids]
    _need(all(type(y) is int and y in (0, 1) for y in labels) and set(labels) == {0, 1},
          'DEV requires explicit integer labels for both classes; unknown is not negative.')
    source_list = sorted(CountsScorer.get_all_sources(
        dev_statements, include_more_specific=False, include_less_specific=False))
    _need(bool(source_list), 'DEV has no source-count columns.')
    scorer = CountsScorer(LogisticRegression(**PARAMETERS), source_list, **FEATURE_OPTIONS)
    dev_matrix = scorer.stmts_to_matrix(dev_statements)
    _need(dev_matrix.shape == (len(dev_rows), len(source_list)), 'native feature shape differs.')
    result = {'format': FORMAT, 'status': 'completed',
              'versions': {name: importlib.metadata.version(name) for name in
                           ('indra', 'scikit-learn', 'numpy', 'pandas', 'scipy')},
              'feature_policy': {'native_class': 'indra.belief.skl.CountsScorer',
                                 'source_list': source_list, 'source_vocabulary_split': 'DEV_only',
                                 'transform': 'native_raw_evidence_counts',
                                 'options': dict(FEATURE_OPTIONS),
                                 'released_belief_used': False, 'reserve_labels_used': False,
                                 'all_original_evidence_retained': True},
              'model': {'class': 'sklearn.linear_model.LogisticRegression',
                        'fixed_parameters': dict(PARAMETERS),
                        'effective_parameters': scorer.model.get_params(),
                        'threshold': 0.5, 'fit_split': 'DEV_only'},
              'development': [{**row, 'native_features': values.tolist()}
                              for row, values in zip(dev_rows, dev_matrix)],
              'development_label_counts': {'supported': labels.count(1),
                                           'unsupported': labels.count(0)},
              'reserve': [], 'simple_prior_comparator': None,
              'source_implementation': {'counts_scorer': _source_pin(CountsScorer),
                                        'classifier': _source_pin(LogisticRegression)},
              'graph_changes': 0, 'proposals_applied': False,
              'interpretation': 'Agreement with supplied curator labels; no whole-graph or clinical accuracy claim.'}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            scorer.fit(dev_statements, labels)
        _need(scorer.model.classes_.tolist() == [0, 1], 'native probability class ordering differs.')
        result['model'].update(classes=scorer.model.classes_.tolist(),
                               coefficients=scorer.model.coef_.tolist(),
                               intercept=scorer.model.intercept_.tolist(),
                               n_iter=scorer.model.n_iter_.tolist())
        for row, statement in zip(reserve_rows, reserve_statements):
            missing = sorted(set(row['source_counts']) - set(source_list))
            if missing:
                result['reserve'].append({**_abstain(row, 'source_not_seen_in_DEV'),
                                          'unseen_sources': missing})
                continue
            try:
                features = scorer.stmts_to_matrix([statement])[0].tolist()
                probability = scorer.predict_proba([statement])[0, 1]
                result['reserve'].append(_prediction(row, probability, features=features))
            except Exception as error:
                result['reserve'].append(_abstain(row, 'native_prediction_error', detail=error))
    except Exception as error:
        result['status'] = 'abstained_model_error'
        result['reserve'] = [_abstain(row, 'native_fit_error', detail=error) for row in reserve_rows]
    if include_simple:
        simple = SimpleScorer()
        comparator = {'class': 'indra.belief.SimpleScorer', 'fit': False,
                      'default_source_priors': simple.prior_probs,
                      'default_subtype_priors': simple.subtype_probs,
                      'threshold': 0.5, 'released_belief_used': False, 'reserve': []}
        result['source_implementation']['simple_scorer'] = _source_pin(SimpleScorer)
        for row, statement in zip(reserve_rows, reserve_statements):
            try:
                simple.check_prior_probs([statement])
                comparator['reserve'].append(_prediction(row, simple.score_statements([statement])[0]))
            except Exception as error:
                comparator['reserve'].append(_abstain(row, 'native_prior_unavailable_or_error', detail=error))
        result['simple_prior_comparator'] = comparator
    # Native feature/scoring calls must not change the supplied evidence/IDs.
    after_dev, after_dev_keys = _inputs(dev_statements, dev_ids, Statement, 'DEV')
    after_reserve, after_reserve_keys = _inputs(reserve_statements, reserve_ids, Statement, 'reserve')
    _need(after_dev == dev_rows and after_reserve == reserve_rows
          and after_dev_keys == dev_keys and after_reserve_keys == reserve_keys,
          'source statements/evidence changed during native scoring.')
    result['input_source_bindings_sha256'] = _digest({'DEV': dev_rows, 'reserve': reserve_rows})
    result['source_inputs_unchanged'] = True
    result['content_sha256'] = _digest(result)
    return result


def _pinned_file(spec, *, root, supplied=None):
    path = Path(spec['file'])
    path = path if path.is_absolute() else root / path
    path = path.absolute()
    _need(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
          'ordinary pinned file required: ' + path.name)
    if supplied is not None:
        _need(Path(supplied).absolute() == path, 'CLI path differs from frozen protocol.')
    _need(hashlib.sha256(path.read_bytes()).hexdigest() == spec['sha256'],
          'frozen file SHA256 differs: ' + path.name)
    return path


def run_frozen_protocol(protocol_path, protocol_sha256, source_cases_path,
                        dev_labels_path, output):
    """CLI bridge for one already frozen frame; never opens reserve labels."""
    root = Path(__file__).resolve().parents[2]
    protocol_path = _pinned_file({'file': str(Path(protocol_path).absolute()),
                                  'sha256': protocol_sha256}, root=root)
    protocol = json.loads(protocol_path.read_text())
    spec = protocol['native_baseline']
    source_path = _pinned_file(spec['source_cases'], root=root, supplied=source_cases_path)
    label_path = _pinned_file(spec['development_labels'], root=root, supplied=dev_labels_path)
    code_path = _pinned_file(spec['code'], root=root)
    _need(code_path == Path(__file__).resolve(), 'frozen native baseline code path differs.')
    _need(spec['parameters'] == PARAMETERS, 'frozen classifier parameters differ.')
    _need(type(spec['include_simple']) is bool, 'frozen comparator flag differs.')
    destination = Path(output).absolute()
    _need(not destination.exists() and not destination.is_symlink(), 'new output directory required.')
    _need(not any(p.is_symlink() for p in destination.parents), 'ordinary output parents required.')
    cases = [json.loads(line) for line in source_path.read_text().splitlines() if line.strip()]
    _need(all(row['split'] in ('development', 'test') for row in cases), 'unknown frozen split.')
    _need(len({row['case_id'] for row in cases}) == len(cases), 'duplicate frozen case ID.')
    _need(all(isinstance(row['statement'], dict) and 'belief' not in row['statement']
              for row in cases), 'model inputs must be exact label-free Statement JSON without released belief.')
    _need(all(re.fullmatch('[0-9a-f]{64}', row.get('input_sha256', '')) for row in cases),
          'frozen case input bindings are missing.')
    dev = [row for row in cases if row['split'] == 'development']
    reserve = [row for row in cases if row['split'] == 'test']
    _need(type(spec['development_count']) is int and len(dev) == spec['development_count']
          and type(spec['reserve_count']) is int and len(reserve) == spec['reserve_count'],
          'frozen split counts differ.')
    _need(all(isinstance(row['group_id'], str) and row['group_id'] for row in cases),
          'frozen source-group identities are missing.')
    _need(not ({row['group_id'] for row in dev} & {row['group_id'] for row in reserve}),
          'DEV and reserve source groups overlap.')
    label_rows = [json.loads(line) for line in label_path.read_text().splitlines() if line.strip()]
    _need(len({row['case_id'] for row in label_rows}) == len(label_rows), 'duplicate DEV label ID.')
    _need({row['case_id'] for row in label_rows} == {row['case_id'] for row in dev},
          'DEV-only label file must match exactly development IDs.')
    _need(all(row['gold'] in ('supported', 'unsupported') for row in label_rows),
          'unknown DEV curation is not a negative label.')
    labels = {row['case_id']: int(row['gold'] == 'supported') for row in label_rows}
    # Parsing retains original Statement fields/evidence; no projection or repair.
    from indra.statements import stmt_from_json
    dev_stmts = [stmt_from_json(row['statement']) for row in dev]
    reserve_stmts = [stmt_from_json(row['statement']) for row in reserve]
    result = fit_predict_native(dev_stmts, labels, [row['case_id'] for row in dev],
                                reserve_stmts, [row['case_id'] for row in reserve],
                                include_simple=spec['include_simple'])
    for row, actual in zip(dev, result['development']):
        _need(row['source_counts'] == actual['source_counts'], 'DEV source-count projection differs.')
    for row, actual in zip(reserve, result['reserve']):
        _need(row['source_counts'] == actual['source_counts'], 'reserve source-count projection differs.')
    # Recheck the same bytes after execution before publishing any output.
    for file_spec, path in ((spec['source_cases'], source_path),
                            (spec['development_labels'], label_path), (spec['code'], code_path)):
        _pinned_file(file_spec, root=root, supplied=path)
    _pinned_file({'file': str(protocol_path), 'sha256': protocol_sha256}, root=root)
    envelope = {'protocol_sha256': protocol_sha256,
                'source_cases_sha256': spec['source_cases']['sha256'],
                'input_bindings': {row['case_id']: row['input_sha256'] for row in reserve},
                'native_result': result}
    envelope['content_sha256'] = _digest(envelope)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / 'native_results.json').open('x') as handle:
        handle.write(json.dumps(envelope, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return envelope


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True, type=Path)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--source-cases', required=True, type=Path)
    parser.add_argument('--dev-labels', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    envelope = run_frozen_protocol(args.protocol, args.protocol_sha256, args.source_cases,
                                   args.dev_labels, args.out)
    result = envelope['native_result']
    print(json.dumps({'status': result['status'], 'reserve_cases': len(result['reserve']),
                      'scored': sum(r['status'] == 'scored' for r in result['reserve']),
                      'content_sha256': envelope['content_sha256'],
                      'reserve_label_file_opened': False, 'graph_changes': 0}))


if __name__ == '__main__':
    main()
