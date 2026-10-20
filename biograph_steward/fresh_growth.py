"""Freeze and execute the single primary pathway hypothesis on reserved genes."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import statistics
import tempfile

from .client import digest, utcnow, write_json
from .cohort_mapping import verify_mapping
from .comparison_protocol import reference_binding, reviewed_features, specification as original_specification, verify_protocol
from .crc_pilot import new_output, sha
from .depmap_audit import load_depmap
from .evaluation import engine_fingerprint
from .fresh_retrieval import (POLICY, COHORT_FILES, load_union, manifest, read, verify_union_retrieval)
from .growth_comparison import (aggregate, decision, fit_arm, gene_key, group_outcomes, metrics,
    paired_bootstrap, predict, read_effects, split_ids, summary)
from .growth_diagnostics import ABLATIONS, ORIGINAL_ARMS, FUSION, fit_ablation, fusion, block_of

PRIMARY = 'pathways_only'
BASELINE = 'pharos_restricted'
ARMS = ORIGINAL_ARMS + list(ABLATIONS) + [FUSION]
PROTOCOL_FILES = {'source_inputs.json', 'features.json', 'exclusions.json', 'source_review.json', 'partitions.json',
    'specification.json', 'references.json', 'source_licenses.json', 'cohort_panel.json', 'cohort_inputs.json',
    'retrieval_manifest.json', 'pharos_TCRD.js', 'pharos_repository_tree.json'}
RESULT_FILES = {'protocol_' + name for name in PROTOCOL_FILES | {'metrics.json'}} | {
    'experimental_source_manifest.json', 'development_outcomes.json', 'fitted_models.json', 'sealed_predictions.json',
    'test_access_receipt.json', 'test_outcomes.json', 'scores.json', 'paired_bootstrap.json', 'gene_passports.json'}


def specification():
    old = original_specification()
    return {'policy': POLICY, 'status': 'frozen_before_reserved_outcome_access',
        'question': 'Does the development-motivated pathway-only representation improve growth-dependency ranking over full restricted Pharos on the reserved genes?',
        'primary': {'candidate': PRIMARY, 'baseline': BASELINE, 'metric': 'Test Spearman(candidate) minus Spearman(baseline)',
            'signal_rule': 'Delta >= 0.05 and the paired 95% interval lower bound > 0; otherwise no demonstrated gain. Exactly one primary contrast.'},
        'secondary': {'arms': ARMS, 'interpretation': 'All other source ablations, CPTAC-only, early/late combinations and coverage contrasts are descriptive/exploratory; no post-test winner selection or multiplicity-adjusted claims.',
            'development_nominee': 'CPTAC-only, nominated by the preceding original validation set, is retained as a named control rather than replaced by the exposed test winner.'},
        'endpoint': old['endpoint'], 'features': old['features'], 'preprocessing': old['preprocessing'], 'model': old['model'],
        'partitions': {'genes': 'Original train+validation (204) -> development train; original test (52) -> development validation; all 256 reserved genes -> final test. Whole shared-product components stay together.',
            'samples': 'Preserve the original 36/12/13 recorded sample-group roles (38/12/13 models). These sample cohorts and the historical release are reused.',
            'training': 'Development train genes × original train sample groups.',
            'validation': 'Development validation genes × original validation sample groups; separate alpha selection per representation.',
            'final_fit': 'All original development genes × original train+validation sample groups, rebuilding all preprocessing there.',
            'test': 'Reserved genes × original test sample groups, once after sealing all predictions. No other reserved-gene outcome cells are parsed.'},
        'budgets': {'alpha_grid': [.1, 1., 10.], 'base_ridge_representations': 10, 'cptac_permutations': 20,
            'pathway_permutations': 20, 'ridge_fits_total': 200, 'fixed_fusion_additional_fits': 0,
            'fusion': 'Fixed 0.5 Pharos + 0.5 CPTAC-only predicted effects, no fitted weight. Two component fitting budgets, not a budget-matched single ridge model.'},
        'controls': {'intercept': old['baselines']['intercept'], 'coverage_only': old['baselines']['coverage_only'],
            'cptac_only': old['baselines']['cptac_only'], 'random': '100 descending hash rankings using {policy,seed,hgnc_id}, seeds 0..99.',
            'permutations': 'For each seed 0..19 and field (pathways or CPTAC ratio), permute the entire field within each original new-protocol gene role. Destinations use HGNC numeric order; donors sort by SHA-256 of {policy,field,seed,hgnc_id}. Keep donors at final refit. Pathway controls fit pathways-only; CPTAC controls fit full Pharos+CPTAC. All have the same three-alpha budget and one refit. Descriptive controls, not independent experiments.'},
        'metrics': {'primary': 'One paired Spearman difference: pathways-only minus full restricted Pharos.',
            'secondary': old['metrics']['secondary'], 'undefined': old['metrics']['undefined'],
            'uncertainty': old['metrics']['uncertainty'], 'bootstrap_scope': 'Only the one primary contrast receives this nominal 95% interval. It excludes training/selection uncertainty; secondary arms are not selected using test outcomes.'},
        'access_control': 'Seal every model, preprocessing receipt, prediction, donor mapping and random ranking before an exclusive source-bound gene-exposure ledger. Reject overlapping reserved genes recorded in any such prior ledger, even under a new protocol.',
        'restrictions': old['restrictions'] + ['All 256 old genes and previous validation judgments are development. Hypotheses were informed by exposed pilot results; this fresh-gene test is conditional on that development.',
            'This is a fixed retrospective ranking experiment, not a GNN/link-prediction/pruning benchmark or prospective independent laboratory replication.',
            'Do not delete or reject evidence records merely because their representation underperformed.'],
        'fresh_dependency_values_loaded': False, 'scientific_improvement_established': False}


def freeze_fresh(cohort_path, retrieval_path, mapping_path, reference_protocol, output):
    cohort_path = Path(cohort_path); retrieval_path = Path(retrieval_path); mapping_path = Path(mapping_path); reference_protocol = Path(reference_protocol)
    cohort, members = load_union(cohort_path); retrieval = verify_union_retrieval(retrieval_path)
    mapping = verify_mapping(mapping_path); reference = verify_protocol(reference_protocol)
    if (retrieval['panel_sha256'] != cohort['panel_sha256'] or mapping['result_sha256'] != cohort['cohort_mapping_result_sha256'] or
            reference['depmap_source_sha256'] != cohort['depmap_source_sha256'] or
            reference['cohort_mapping_result_sha256'] != mapping['result_sha256']): raise ValueError('Fresh protocol parent identities differ.')
    source = read(retrieval_path, 'snapshot.json')
    if any(row['status'] == 'identity_mismatch' for row in source['target_resolution']): raise ValueError('Resolve changed protein identities before freezing.')
    ids = {m['hgnc_id'] for m in members}; fields = ['hgnc_id', 'ncbi_gene_id', 'matrix_row', 'measurement_sha256', 'median_reported_log2_ratio']
    inputs = {'members': members, 'models': read(cohort_path, 'crc_models.json'),
        'targets': [{'uniprot': t['uniprot'], 'pathways': t['pathways'], 'pharos_context': {f: t['pharos_context'][f] for f in ['go', 'ppis', 'expressions']}} for t in source['targets']],
        'cptac_mapping_rows': [{f: row[f] for f in fields} for row in read(mapping_path, 'mappings.json') if row['hgnc_id'] in ids]}
    features, exclusions, audit = reviewed_features(inputs)
    out = new_output(output, cohort_path, retrieval_path, mapping_path, reference_protocol)
    values = {'source_inputs.json': inputs, 'features.json': features, 'exclusions.json': exclusions, 'source_review.json': audit,
        'partitions.json': read(cohort_path, 'partitions.json'), 'specification.json': specification(),
        'references.json': reference_binding(reference_protocol / 'pharos_TCRD.js', reference_protocol / 'pharos_repository_tree.json'),
        'source_licenses.json': source['source_licenses'], 'cohort_panel.json': cohort,
        'cohort_inputs.json': {name: read(cohort_path, name) for name in sorted(COHORT_FILES)}, 'retrieval_manifest.json': retrieval}
    for name, value in values.items(): write_json(out / name, value)
    for name in ['pharos_TCRD.js', 'pharos_repository_tree.json']: (out / name).write_bytes((reference_protocol / name).read_bytes())
    result = {'format': 'biograph-steward.reserved-growth-protocol.v1', 'created_at': utcnow(), 'policy': POLICY,
        'cohort_panel_sha256': cohort['panel_sha256'], 'reservation_result_sha256': cohort['reservation_result_sha256'],
        'diagnostic_result_sha256': cohort['diagnostic_result_sha256'], 'depmap_source_sha256': cohort['depmap_source_sha256'],
        'pharos_result_sha256': retrieval['result_sha256'], 'pharos_snapshot_sha256': retrieval['source_snapshot_sha256'],
        'pharos_version': retrieval['db_version_before'], 'mapping_result_sha256': mapping['result_sha256'],
        'engine_files': engine_fingerprint(), 'genes': len(members), 'source_review': audit,
        'partition_counts': {axis: {split: sum(len(g['hgnc_ids' if axis == 'genes' else 'model_ids']) for g in rows if g['split'] == split) for split in ['train', 'validation', 'test']} for axis, rows in values['partitions.json'].items()},
        'primary_candidate': PRIMARY, 'primary_baseline': BASELINE, 'fresh_dependency_values_loaded': False,
        'predictor_fit_run': False, 'scientific_improvement_established': False, 'model_service_requests': 0,
        'files': {name: sha(out / name) for name in sorted(PROTOCOL_FILES)}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(html('Frozen reserved-gene comparison', '<p><strong>No reserved outcomes loaded; no predictor fitted.</strong></p><pre>' + escape(json.dumps(result, indent=2)) + '</pre><h2>Predeclared rules</h2><pre>' + escape(json.dumps(specification(), indent=2)) + '</pre>'), encoding='utf-8')
    verify_fresh_protocol(out)
    return result


def verify_fresh_protocol(path):
    path = Path(path); r = manifest(path, expected=PROTOCOL_FILES)
    if r['policy'] != POLICY or r['fresh_dependency_values_loaded'] or r['predictor_fit_run'] or read(path, 'specification.json') != specification():
        raise ValueError('Fresh protocol rules or outcome-blind scope changed.')
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp); write_json(folder / 'panel.json', read(path, 'cohort_panel.json'))
        for name, value in read(path, 'cohort_inputs.json').items():
            if name not in COHORT_FILES: raise ValueError('Unexpected frozen cohort file.')
            write_json(folder / name, value)
        cohort, members = load_union(folder)
        if read(folder, 'partitions.json') != read(path, 'partitions.json'): raise ValueError('Frozen grouped assignments differ from union.')
    source = read(path, 'source_inputs.json'); retrieval = read(path, 'retrieval_manifest.json')
    if (members != source['members'] or read(path, 'cohort_inputs.json')['crc_models.json'] != source['models'] or
            cohort['panel_sha256'] != r['cohort_panel_sha256'] or cohort['reservation_result_sha256'] != r['reservation_result_sha256'] or
            cohort['depmap_source_sha256'] != r['depmap_source_sha256'] or retrieval['panel_sha256'] != cohort['panel_sha256'] or
            retrieval['result_sha256'] != r['pharos_result_sha256'] or retrieval['source_snapshot_sha256'] != r['pharos_snapshot_sha256'] or
            not retrieval['version_consistent'] or retrieval['db_version_before'] != r['pharos_version'] or
            cohort['cohort_mapping_result_sha256'] != r['mapping_result_sha256'] or
            retrieval['result_sha256'] != digest({k: v for k, v in retrieval.items() if k != 'result_sha256'})):
        raise ValueError('Frozen cohort/retrieval bindings changed.')
    features, exclusions, audit = reviewed_features(source)
    for name, value in [('features.json', features), ('exclusions.json', exclusions), ('source_review.json', audit),
        ('references.json', reference_binding(path / 'pharos_TCRD.js', path / 'pharos_repository_tree.json'))]:
        if read(path, name) != value: raise ValueError('Frozen source views do not reconstruct.')
    if audit != r['source_review']: raise ValueError('Frozen source coverage changed.')
    return r


def permute_field(genes, parts, field, seed):
    if field not in {'pathways', 'cptac_median_reported_log2_ratio'} or seed not in range(20): raise ValueError('Unknown frozen permutation.')
    changed = dict(genes); donors = {}
    for split in ['train', 'validation', 'test']:
        ids = split_ids(parts, 'genes', {split})
        order = sorted(ids, key=lambda gid: (digest({'policy': POLICY, 'field': field, 'seed': seed, 'hgnc_id': gid}), gene_key(gid)))
        for gid, donor in zip(ids, order): changed[gid] = {**genes[gid], field: deepcopy(genes[donor][field])}; donors[gid] = donor
    return changed, donors


def check_access(source, source_sha, ids):
    for path in Path(source).parent.glob('.reserved_gene_test_access_*.json'):
        if path.is_symlink(): raise ValueError('Untrusted test-access ledger.')
        record = json.loads(path.read_text())
        if record['source_sha256'] == source_sha and set(ids) & set(record['test_gene_ids']):
            raise ValueError('Reserved genes already accessed in a preserved source-bound ledger; replay the sealed result instead of another test.')


def claim_access(source, out, protocol, seal, ids):
    check_access(source, protocol['depmap_source_sha256'], ids)
    key = digest({'source_sha256': protocol['depmap_source_sha256'], 'test_gene_ids': ids})
    path = Path(source).parent / ('.reserved_gene_test_access_' + key + '.json')
    receipt = {'created_at': utcnow(), 'source_sha256': protocol['depmap_source_sha256'], 'test_gene_ids': ids,
        'protocol_sha256': protocol['result_sha256'], 'prediction_seal_sha256': seal['seal_sha256'], 'output': str(Path(out).resolve())}
    with path.open('x', encoding='utf-8') as f: f.write(json.dumps(receipt, indent=2) + '\n')
    write_json(Path(out) / 'test_access_receipt.json', receipt)


def random_rankings(ids):
    result = []
    for seed in range(100):
        order = sorted(ids, key=lambda gid: (digest({'policy': POLICY, 'seed': seed, 'hgnc_id': gid}), gene_key(gid)))
        lookup = {gid: i for i, gid in enumerate(order)}; result.append([lookup[gid] for gid in ids])
    return result


def passports(genes, models, ids, target):
    rank = lambda v: {ids[i]: n + 1 for n, i in enumerate(sorted(range(len(ids)), key=lambda i: (-v[i], gene_key(ids[i]))))}
    base = models[BASELINE]; primary = models[PRIMARY]; a = rank(base['predictions']); b = rank(primary['predictions']); actual = rank(target)
    output = []
    for i, gid in enumerate(ids):
        gene = genes[gid]; terms = []
        for key, value in primary['test_vectors'][i].items():
            coefficient = primary['model']['coefficients'].get(key, 0)
            terms.append({'feature': key, 'transformed_value': value, 'coefficient': coefficient, 'contribution': value * coefficient,
                'source_evidence': [p for p in gene['pathways'] if key == 'pathway|' + p['source'] + '|' + p['stable_id']]})
        if abs(primary['model']['intercept'] + sum(t['contribution'] for t in terms) - primary['predictions'][i]) > 1e-9:
            raise ValueError('Primary source contributions do not reconcile.')
        output.append({'hgnc_id': gid, 'symbol': gene['symbol'], 'pharos_rank': a[gid], 'primary_pathway_rank': b[gid],
            'rank_change_up': a[gid] - b[gid], 'measured_rank': actual[gid], 'measured_target': target[i],
            'pharos_prediction': base['predictions'][i], 'primary_prediction': primary['predictions'][i],
            'primary_intercept': primary['model']['intercept'], 'largest_absolute_contributions': sorted(terms, key=lambda t: (-abs(t['contribution']), t['feature']))[:8],
            'pathway_memberships': gene['pathways'], 'bioplex_neighbors': gene['bioplex_neighbors'],
            'cptac_median_reported_log2_ratio': gene['cptac_median_reported_log2_ratio'], 'cptac_matrix_row': gene['cptac_matrix_row'],
            'cptac_measurement_sha256': gene['cptac_measurement_sha256'],
            'interpretation': 'Saved statistical prediction and source provenance; not a causal or clinical target-validity finding.'})
    return sorted(output, key=lambda g: (-abs(g['rank_change_up']), gene_key(g['hgnc_id'])))


def run_fresh(protocol_path, source_path, output, *, progress=None):
    protocol_path = Path(protocol_path); source_path = Path(source_path); protocol = verify_fresh_protocol(protocol_path)
    if protocol['engine_files'] != engine_fingerprint(): raise ValueError('Execution code differs from the frozen protocol; resolve before any outcome access.')
    parts = read(protocol_path, 'partitions.json'); ids = split_ids(parts, 'genes', {'test'})
    check_access(source_path, protocol['depmap_source_sha256'], ids)
    source = load_depmap(source_path)
    if source['source_sha256'] != protocol['depmap_source_sha256']: raise ValueError('Experimental source differs from the frozen protocol.')
    inputs = read(protocol_path, 'source_inputs.json'); genes = {g['hgnc_id']: g for g in read(protocol_path, 'features.json')['genes']}
    out = new_output(output, protocol_path, source_path)
    for name in PROTOCOL_FILES | {'metrics.json'}: (out / ('protocol_' + name)).write_bytes((protocol_path / name).read_bytes())
    write_json(out / 'experimental_source_manifest.json', source)
    dev_ids = split_ids(parts, 'genes', {'train', 'validation'}); dev_models = split_ids(parts, 'models', {'train', 'validation'})
    if set(dev_ids) & set(ids): raise ValueError('Development and reserved genes overlap.')
    if progress: progress('Verified source bytes and freeze. Reading old development genes × fit/validation model groups only.')
    outcomes = read_effects(source_path / 'CRISPRGeneEffect.csv', inputs, dev_ids, dev_models)
    write_json(out / 'development_outcomes.json', outcomes); fitted = {}; donors = {}
    for arm in ORIGINAL_ARMS:
        fitted[arm] = fit_arm(genes, parts, outcomes, arm)
        if progress: progress('Fitted declared arm: ' + arm)
    for arm in ABLATIONS:
        fitted[arm] = fit_ablation(genes, parts, outcomes, arm)
        if progress: progress('Fitted declared ablation: ' + arm)
    fitted[FUSION] = fusion(fitted[BASELINE], fitted['cptac_only'])
    for family, field in [('cptac', 'cptac_median_reported_log2_ratio'), ('pathway', 'pathways')]:
        for seed in range(20):
            changed, mapping = permute_field(genes, parts, field, seed); name = family + '_permutation_' + str(seed)
            fitted[name] = fit_arm(changed, parts, outcomes, 'pharos_restricted_plus_cptac') if family == 'cptac' else fit_ablation(changed, parts, outcomes, PRIMARY)
            donors[name] = mapping
            if progress: progress('Fitted ' + family + ' permutation ' + str(seed + 1) + '/20.')
    groups = [g for g in parts['models'] if g['split'] in {'train', 'validation'}]
    intercept = [statistics.mean(aggregate(group_outcomes(outcomes, groups, dev_ids), dev_ids))] * len(ids)
    random = random_rankings(ids); write_json(out / 'fitted_models.json', fitted)
    seal = {'format': 'biograph-steward.reserved-pretest-predictions.v1', 'created_at': utcnow(), 'protocol_sha256': protocol['result_sha256'],
        'reservation_result_sha256': protocol['reservation_result_sha256'], 'primary_candidate': PRIMARY, 'primary_baseline': BASELINE,
        'models': {name: {k: row[k] for k in ['test_gene_ids', 'predictions', 'selected_alpha']} for name, row in fitted.items()},
        'random_rankings': random, 'intercept': intercept, 'permutation_donors': donors, 'fresh_dependency_values_loaded': False,
        'pretest_files': {name: sha(out / name) for name in ['development_outcomes.json', 'fitted_models.json']}, 'engine_files': engine_fingerprint()}
    seal['seal_sha256'] = digest(seal); write_json(out / 'sealed_predictions.json', seal)
    claim_access(source_path, out, protocol, seal, ids)
    if progress: progress('Every prediction sealed; exclusive source-bound ledger created. Opening reserved test genes × test sample groups once.')
    test_models = split_ids(parts, 'models', {'test'}); raw = read_effects(source_path / 'CRISPRGeneEffect.csv', inputs, ids, test_models)
    grouped = group_outcomes(raw, [g for g in parts['models'] if g['split'] == 'test'], ids); target = aggregate(grouped, ids)
    test = {'by_model': raw, 'by_sample_group': grouped, 'gene_ids': ids, 'aggregate': target}; write_json(out / 'test_outcomes.json', test)
    scored = {name: metrics(row['predictions'], target, ids, grouped) for name, row in fitted.items()}; scored['intercept'] = metrics(intercept, target, ids, grouped)
    random_scores = [metrics(p, target, ids, grouped, ranking_only=True) for p in random]
    write_json(out / 'scores.json', {'arms_and_permutations': scored, 'random_rankings': random_scores})
    interval = paired_bootstrap(fitted[BASELINE]['predictions'], fitted[PRIMARY]['predictions'], grouped, ids)
    write_json(out / 'paired_bootstrap.json', interval)
    rows = passports(genes, fitted, ids, target); write_json(out / 'gene_passports.json', rows)
    a = scored[BASELINE]['spearman']; b = scored[PRIMARY]['spearman']; delta = b - a if a is not None and b is not None else None
    result = {'format': 'biograph-steward.reserved-growth-result.v1', 'created_at': utcnow(), 'policy': POLICY,
        'protocol_sha256': protocol['result_sha256'], 'reservation_result_sha256': protocol['reservation_result_sha256'],
        'source_sha256': source['source_sha256'], 'prediction_seal_sha256': seal['seal_sha256'], 'engine_files': engine_fingerprint(),
        'development_genes': len(dev_ids), 'test_genes': len(ids), 'test_models': len(test_models), 'test_sample_groups': len(grouped),
        'ridge_fit_count': 200, 'primary_candidate': PRIMARY, 'primary_baseline': BASELINE, 'primary_spearman_delta': delta,
        'paired_interval': {k: v for k, v in interval.items() if k != 'differences'}, 'decision': decision(delta, interval),
        'arms': {name: {'selected_alpha': fitted[name]['selected_alpha'], **scored[name]} for name in ARMS},
        'intercept': scored['intercept'], 'random_baseline_spearman': summary([r['spearman'] for r in random_scores]),
        'random_baseline_recall_at_10': summary([r['recall_at_10'] for r in random_scores]),
        'cptac_permutation_spearman': summary([scored['cptac_permutation_' + str(i)]['spearman'] for i in range(20)]),
        'pathway_permutation_spearman': summary([scored['pathway_permutation_' + str(i)]['spearman'] for i in range(20)]),
        'fresh_dependency_values_loaded': True, 'fresh_gene_holdout_executed': True, 'fresh_laboratory_cohort': False,
        'model_service_requests': 0, 'scientific_improvement_established': False,
        'claim_scope': 'One predeclared primary comparison on previously reserved genes in a historical processed release, conditional on adaptive development; no claim of full-Pharos, clinical, GNN/link-prediction or pruning superiority.',
        'limitations': specification()['restrictions'] + ['Secondary arm scores and permutation distributions are descriptive. Do not select a test winner or reinterpret its score as another primary result.'],
        'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_result(result, rows), encoding='utf-8')
    return result


def verify_fresh_result(path):
    path = Path(path); r = manifest(path, expected=RESULT_FILES)
    if r['policy'] != POLICY or r['primary_candidate'] != PRIMARY or r['primary_baseline'] != BASELINE: raise ValueError('Primary comparison changed.')
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name in PROTOCOL_FILES | {'metrics.json'}: (folder / name).write_bytes((path / ('protocol_' + name)).read_bytes())
        protocol = verify_fresh_protocol(folder)
    seal = read(path, 'sealed_predictions.json'); models = read(path, 'fitted_models.json'); test = read(path, 'test_outcomes.json')
    if (seal['seal_sha256'] != digest({k: v for k, v in seal.items() if k != 'seal_sha256'}) or seal['seal_sha256'] != r['prediction_seal_sha256'] or
            seal['protocol_sha256'] != r['protocol_sha256'] or seal['fresh_dependency_values_loaded'] or
            protocol['result_sha256'] != r['protocol_sha256'] or protocol['reservation_result_sha256'] != r['reservation_result_sha256'] or
            seal['reservation_result_sha256'] != r['reservation_result_sha256'] or seal['engine_files'] != protocol['engine_files'] or
            r['engine_files'] != seal['engine_files'] or read(path, 'experimental_source_manifest.json')['source_sha256'] != r['source_sha256'] or
            r['source_sha256'] != protocol['depmap_source_sha256']): raise ValueError('Prediction seal or frozen source binding changed.')
    for name, value in seal['pretest_files'].items():
        if sha(path / name) != value: raise ValueError('Pretest fitting file changed.')
    expected = set(ARMS) | {family + '_permutation_' + str(i) for family in ['cptac', 'pathway'] for i in range(20)}
    if set(models) != expected or set(seal['models']) != expected: raise ValueError('Declared model/control set changed.')
    for name, row in models.items():
        if seal['models'][name] != {k: row[k] for k in ['test_gene_ids', 'predictions', 'selected_alpha']}: raise ValueError('Model differs from sealed predictions.')
        if name != FUSION and predict(row['model'], row['test_vectors']) != row['predictions']: raise ValueError('Stored model does not reproduce prediction.')
        block_arm = name if name in ABLATIONS else (PRIMARY if name.startswith('pathway_permutation_') else None)
        if block_arm and any(block_of(k) not in ABLATIONS[block_arm] for k in row['model']['coefficients']): raise ValueError('Ablated source block reintroduced.')
    if models[FUSION] != fusion(models[BASELINE], models['cptac_only']): raise ValueError('Fixed fusion changed.')
    parts = read(path, 'protocol_partitions.json'); ids = split_ids(parts, 'genes', {'test'})
    if ids != test['gene_ids'] or any(row['test_gene_ids'] != ids for row in models.values()): raise ValueError('Reserved gene identities changed.')
    grouped = group_outcomes(test['by_model'], [g for g in parts['models'] if g['split'] == 'test'], ids)
    if grouped != test['by_sample_group'] or aggregate(grouped, ids) != test['aggregate']: raise ValueError('Experimental aggregation changed.')
    scored = {name: metrics(row['predictions'], test['aggregate'], ids, grouped) for name, row in models.items()}
    scored['intercept'] = metrics(seal['intercept'], test['aggregate'], ids, grouped)
    random = [metrics(v, test['aggregate'], ids, grouped, ranking_only=True) for v in seal['random_rankings']]
    if seal['random_rankings'] != random_rankings(ids): raise ValueError('Fixed random rankings changed.')
    if {'arms_and_permutations': scored, 'random_rankings': random} != read(path, 'scores.json'): raise ValueError('Saved scores do not reproduce.')
    interval = paired_bootstrap(models[BASELINE]['predictions'], models[PRIMARY]['predictions'], grouped, ids)
    delta = scored[PRIMARY]['spearman'] - scored[BASELINE]['spearman'] if scored[PRIMARY]['spearman'] is not None and scored[BASELINE]['spearman'] is not None else None
    if (interval != read(path, 'paired_bootstrap.json') or {k: v for k, v in interval.items() if k != 'differences'} != r['paired_interval'] or
            delta != r['primary_spearman_delta'] or decision(delta, interval) != r['decision'] or
            {name: {'selected_alpha': models[name]['selected_alpha'], **scored[name]} for name in ARMS} != r['arms']):
        raise ValueError('Primary metric/interval/decision or displayed arm scores changed.')
    genes = {g['hgnc_id']: g for g in read(path, 'protocol_features.json')['genes']}
    for family, field in [('cptac', 'cptac_median_reported_log2_ratio'), ('pathway', 'pathways')]:
        for seed in range(20):
            if seal['permutation_donors'][family + '_permutation_' + str(seed)] != permute_field(genes, parts, field, seed)[1]:
                raise ValueError('Predeclared permutation donors changed.')
    expected_controls = {'intercept': scored['intercept'], 'random_baseline_spearman': summary([v['spearman'] for v in random]),
        'random_baseline_recall_at_10': summary([v['recall_at_10'] for v in random]),
        'cptac_permutation_spearman': summary([scored['cptac_permutation_' + str(i)]['spearman'] for i in range(20)]),
        'pathway_permutation_spearman': summary([scored['pathway_permutation_' + str(i)]['spearman'] for i in range(20)])}
    if any(r[k] != v for k, v in expected_controls.items()): raise ValueError('Displayed control summaries do not reproduce.')
    if r['test_genes'] != len(ids) or r['test_sample_groups'] != len(grouped) or r['test_models'] != len(test['by_model']) or r['ridge_fit_count'] != 200:
        raise ValueError('Reported test/fitting counts changed.')
    if passports(genes, models, ids, test['aggregate']) != read(path, 'gene_passports.json'): raise ValueError('Gene evidence passports do not reproduce.')
    receipt = read(path, 'test_access_receipt.json')
    if (receipt['prediction_seal_sha256'] != seal['seal_sha256'] or receipt['protocol_sha256'] != r['protocol_sha256'] or receipt['test_gene_ids'] != ids or
            receipt['created_at'] < seal['created_at']): raise ValueError('Test access does not follow the sealed prediction boundary.')
    return r


def html(title, body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(title) + '</title><style>body{max-width:1150px;margin:30px auto;padding:20px;font:16px/1.6 system-ui;color:#173047}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ccd;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}.outcome{padding:20px;background:#eef4f6;border-left:5px solid #147c83}</style><h1>' + escape(title) + '</h1>' + body + '</html>'


def render_result(result, rows):
    num = lambda v: 'undefined' if v is None else f'{v:.4f}'
    table = ''.join('<tr><td>' + escape(name) + '</td><td>' + num(row['spearman']) + '</td><td>' + num(row['mae']) + '</td><td>' + num(row['recall_at_10']) + '</td></tr>' for name, row in result['arms'].items())
    genes = ''.join('<tr><td><details><summary>' + escape(g['symbol'] + ' (' + g['hgnc_id'] + ')') + '</summary><pre>' + escape(json.dumps(g, indent=2)) + '</pre></details></td><td>' + str(g['pharos_rank']) + '</td><td>' + str(g['primary_pathway_rank']) + '</td><td>' + str(g['measured_rank']) + '</td></tr>' for g in rows)
    ci = result['paired_interval']
    return html('Fresh reserved-gene comparison: pathway-only vs Pharos',
        '<div class="outcome"><strong>' + escape(result['decision']['status'].replace('_', ' ')) + '</strong><p>Primary Spearman change: ' + num(result['primary_spearman_delta']) + '; paired 95% interval [' + num(ci['lower_95']) + ', ' + num(ci['upper_95']) + '].</p></div>'
        '<p>One predeclared primary contrast on ' + str(result['test_genes']) + ' reserved genes and ' + str(result['test_sample_groups']) + ' reused tissue-sample groups. Every prediction was sealed before first reserved-outcome access. This is a fresh gene holdout, not a new laboratory cohort.</p>'
        '<h2>Primary and predeclared secondary representations</h2><p>Only pathway-only minus full restricted Pharos is the primary hypothesis. Other arms are descriptive; CPTAC-only retains the prior validation nomination. Fixed late averaging uses two component budgets.</p><table><tr><th>Representation</th><th>Spearman ↑</th><th>Mean absolute error ↓</th><th>Recall@10 ↑</th></tr>' + table + '</table>'
        '<h2>Predeclared controls</h2><pre>' + escape(json.dumps({k: result[k] for k in ['intercept', 'random_baseline_spearman', 'cptac_permutation_spearman', 'pathway_permutation_spearman', 'paired_interval']}, indent=2)) + '</pre>'
        '<h2>Every reserved gene and its pathway evidence</h2><p>Ranks descend with predicted/measured dependency; stronger dependency means larger negated gene effect. Model contributions are statistical, not causal.</p><table><tr><th>Gene / evidence</th><th>Full Pharos rank</th><th>Pathway-only rank</th><th>Measured rank</th></tr>' + genes + '</table>'
        '<p>Experimental outcomes: Broad Institute, <a href="https://doi.org/10.25452/figshare.plus.27993248.v1">DepMap 24Q4 Public v1</a>, <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>; values negated and grouped as specified. Source manifests, licenses, raw feature rows and references are preserved in the export.</p>'
        '<h2>Scope and reproducibility</h2><pre>' + escape(json.dumps(result, indent=2)) + '</pre>')
