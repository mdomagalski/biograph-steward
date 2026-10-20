"""Development-only ablations of exposed pilot data and an untouched gene reserve.

Neither command accepts or opens an experimental score matrix. Previously saved
outcomes may explain a completed pilot; they cannot become a fresh test result.
"""
from collections import defaultdict
from copy import deepcopy
from html import escape
import json
import math
from pathlib import Path
import statistics

from .client import digest, utcnow, write_json
from .crc_pilot import new_output, sha
from .evaluation import engine_fingerprint
from .growth_comparison import (ALPHAS, Design, aggregate, gene_key, group_outcomes,
    metrics, predict, ridge_fit, spearman, split_ids, verify_comparison)
from .matched_panel import load_panel

POLICY = 'crc-exposed-development-ablations.v1'
RESERVE_POLICY = 'crc-unexposed-gene-reserve.v1'
BLOCKS = {
    'pathways': ('pathway|',),
    'expression': ('expression|', 'expression_missing|', 'category|'),
    'bioplex': ('bioplex|',),
    'cptac': ('cptac|',),
}
ABLATIONS = {
    'pathways_only': ('pathways',),
    'expression_only': ('expression',),
    'bioplex_only': ('bioplex',),
    'without_pathways': ('expression', 'bioplex'),
    'without_expression': ('pathways', 'bioplex'),
    'without_bioplex': ('pathways', 'expression'),
}
ORIGINAL_ARMS = ['pharos_restricted', 'pharos_restricted_plus_cptac', 'cptac_only', 'coverage_only']
FUSION = 'fixed_half_pharos_half_cptac'
# This order, including baseline first, breaks exact validation ties. Coverage
# is an annotation-availability control, not a proposed biological feature set.
CANDIDATES = [*ORIGINAL_ARMS[:3], *ABLATIONS, FUSION]


def _read(path, name):
    return json.loads((Path(path) / name).read_text())


def block_of(column):
    return next((name for name, prefixes in BLOCKS.items() if column.startswith(prefixes)), None)


def mask_row(row, blocks):
    if not blocks or set(blocks) - set(BLOCKS): raise ValueError('Unknown or empty feature-block mask.')
    return {key: value for key, value in row.items() if block_of(key) in blocks}


def fit_ablation(genes, partitions, outcomes, name):
    """Keep original within-block transforms; remove entire blocks, no renormalization."""
    if name not in ABLATIONS: raise ValueError('Unknown declared ablation.')
    blocks = ABLATIONS[name]
    train = split_ids(partitions, 'genes', {'train'}); validation = split_ids(partitions, 'genes', {'validation'})
    combined = split_ids(partitions, 'genes', {'train', 'validation'}); test = split_ids(partitions, 'genes', {'test'})
    tg = [g for g in partitions['models'] if g['split'] == 'train']
    vg = [g for g in partitions['models'] if g['split'] == 'validation']
    yt = aggregate(group_outcomes(outcomes, tg, train), train)
    yv = aggregate(group_outcomes(outcomes, vg, validation), validation)
    design = Design(genes, train, 'pharos_restricted')
    rows = lambda d, ids: [mask_row(d.row(gid), blocks) for gid in ids]
    xt = rows(design, train); xv = rows(design, validation); choices = []
    for alpha in ALPHAS:
        model = ridge_fit(xt, yt, alpha); values = predict(model, xv)
        choices.append({'alpha': alpha, 'spearman': spearman(values, yv), 'predictions': values})
    chosen = max(choices, key=lambda r: (r['spearman'] is not None, r['spearman'] or 0, r['alpha']))
    final = Design(genes, combined, 'pharos_restricted'); xf = rows(final, combined); xs = rows(final, test)
    yf = aggregate(group_outcomes(outcomes, tg + vg, combined), combined)
    model = ridge_fit(xf, yf, chosen['alpha'])
    return {'arm': name, 'blocks': list(blocks), 'selected_alpha': chosen['alpha'], 'selection': choices,
        'validation_gene_ids': validation, 'validation_target': yv, 'selection_design': design.receipt(),
        'final_design': final.receipt(), 'model': model, 'test_gene_ids': test, 'test_vectors': xs,
        'predictions': predict(model, xs), 'active_columns': sorted({k for row in xf for k in row}),
        'transform_note': 'Inherited train-only transforms; the complete named blocks are masked after transformation. Retained blocks keep their original weights. Unused full-design vocabulary is metadata, not predictor input.'}


def selected_validation(row):
    return next(r for r in row['selection'] if r['alpha'] == row['selected_alpha'])


def fusion(a, b):
    if (a['test_gene_ids'] != b['test_gene_ids'] or a['validation_gene_ids'] != b['validation_gene_ids'] or
            a['validation_target'] != b['validation_target']): raise ValueError('Fusion components have different populations or endpoints.')
    av = selected_validation(a); bv = selected_validation(b)
    average = lambda x, y: [(u + v) / 2 for u, v in zip(x, y)]
    if len(a['predictions']) != len(b['predictions']) or len(av['predictions']) != len(bv['predictions']):
        raise ValueError('Fusion component prediction sizes differ.')
    validation = average(av['predictions'], bv['predictions'])
    return {'arm': FUSION, 'kind': 'fixed_average_of_saved_predictions', 'weights': [.5, .5],
        'components': ['pharos_restricted', 'cptac_only'], 'component_selected_alphas': [a['selected_alpha'], b['selected_alpha']],
        'selected_alpha': None, 'test_gene_ids': a['test_gene_ids'], 'predictions': average(a['predictions'], b['predictions']),
        'validation_gene_ids': a['validation_gene_ids'], 'validation_target': a['validation_target'],
        'validation_predictions': validation, 'validation_spearman': spearman(validation, a['validation_target']),
        'additional_fits': 0, 'component_original_fits': 8,
        'budget_note': 'Fixed half/half averaging in shared dependency units; no outcome-calibrated weight. Reuses two separately tuned component models, so its total component fitting budget is twice a single ridge arm.'}


def validation_score(row):
    return row['validation_spearman'] if row.get('kind') == 'fixed_average_of_saved_predictions' else selected_validation(row)['spearman']


def proposed_candidate(rows):
    winner = max(CANDIDATES, key=lambda name: (validation_score(rows[name]) is not None,
        validation_score(rows[name]) or 0, -CANDIDATES.index(name)))
    return {'candidate': winner, 'validation_spearman': validation_score(rows[winner]),
        'rule': 'Highest original validation Spearman among the predeclared candidate order; exact ties choose the first. Exposed test scores cannot select the proposal. Coverage remains a control.',
        'candidate_order': CANDIDATES, 'fresh_test_executed': False,
        'interpretation': 'Development proposal only; this does not establish improvement. Reusing the original validation set for these new hypotheses is adaptive development.'}


def audit_genes(genes, ids, target, models):
    order = lambda values: {ids[i]: n + 1 for n, i in enumerate(sorted(range(len(ids)), key=lambda i: (-values[i], gene_key(ids[i]))))}
    base = models['pharos_restricted']; enriched = models['pharos_restricted_plus_cptac']
    br = order(base['predictions']); er = order(enriched['predictions']); measured = order(target)
    fit_ids = set(base['final_design']['fit_gene_ids']); vocabulary = set(base['final_design']['columns']); output = []
    for i, gid in enumerate(ids):
        g = genes[gid]; by_arm = {}
        for name, row in [('pharos_restricted', base), ('pharos_restricted_plus_cptac', enriched)]:
            parts = {block: 0.0 for block in BLOCKS}
            for key, value in row['test_vectors'][i].items():
                block = block_of(key)
                if block is None: raise ValueError('Unrecognized original model feature block.')
                parts[block] += value * row['model']['coefficients'].get(key, 0.0)
            if not math.isclose(row['model']['intercept'] + sum(parts.values()), row['predictions'][i], abs_tol=1e-9):
                raise ValueError('Block contributions do not reconcile with saved prediction.')
            by_arm[name] = {'intercept': row['model']['intercept'], 'block_contributions': parts, 'prediction': row['predictions'][i]}
        error_before = abs(br[gid] - measured[gid]); error_after = abs(er[gid] - measured[gid])
        output.append({'hgnc_id': gid, 'symbol': g['symbol'], 'pharos_rank': br[gid], 'enriched_rank': er[gid],
            'measured_rank': measured[gid], 'rank_change_up': br[gid] - er[gid], 'absolute_rank_error_before': error_before,
            'absolute_rank_error_after': error_after, 'rank_error_reduction': error_before - error_after,
            'pathway_memberships': len(g['pathways']),
            'pathways_seen_in_fit_vocabulary': sum('pathway|' + p['source'] + '|' + p['stable_id'] in vocabulary for p in g['pathways']),
            'bioplex_fit_neighbors': sorted(fit_ids & set(g['bioplex_neighbors']), key=gene_key),
            'numeric_expression_observed': sum(p['value'] is not None for p in g['numeric_expression']),
            'categorical_expression_observations': len(g['categorical_expression']),
            'cptac_median_reported_log2_ratio': g['cptac_median_reported_log2_ratio'], 'decomposition': by_arm,
            'source_evidence': {'protocol_feature_locator': 'original/protocol_features.json#/genes/' + str(list(genes).index(gid)),
                'original_passport_hgnc_id': gid, 'cptac_matrix_row': g['cptac_matrix_row'], 'cptac_measurement_sha256': g['cptac_measurement_sha256']}})
    return sorted(output, key=lambda r: (-abs(r['rank_change_up']), gene_key(r['hgnc_id'])))


def run_diagnostics(comparison, output, *, progress=None):
    comparison = Path(comparison); previous = verify_comparison(comparison)
    genes = {g['hgnc_id']: g for g in _read(comparison, 'protocol_features.json')['genes']}
    partitions = _read(comparison, 'protocol_partitions.json'); outcomes = _read(comparison, 'fit_outcomes.json')
    test = _read(comparison, 'test_outcomes.json'); ids = test['gene_ids']; original = _read(comparison, 'fitted_models.json')
    out = new_output(output, comparison); copies = ['protocol_features.json', 'protocol_source_inputs.json', 'protocol_partitions.json',
        'fit_outcomes.json', 'test_outcomes.json', 'fitted_models.json', 'sealed_predictions.json', 'gene_passports.json',
        'experimental_source_manifest.json', 'protocol_references.json', 'protocol_source_review.json', 'metrics.json']
    for name in copies: (out / 'original' / name).parent.mkdir(parents=True, exist_ok=True); (out / 'original' / name).write_bytes((comparison / name).read_bytes())
    models = {name: original[name] for name in ORIGINAL_ARMS}
    for name in ABLATIONS:
        models[name] = fit_ablation(genes, partitions, outcomes, name)
        if progress: progress('Development-only ablation fitted: ' + name)
    models[FUSION] = fusion(models['pharos_restricted'], models['cptac_only'])
    scored = {name: {**metrics(row['predictions'], test['aggregate'], ids, test['by_sample_group']),
        'validation_spearman': validation_score(row), 'selected_alpha': row['selected_alpha']} for name, row in models.items()}
    audit = audit_genes(genes, ids, test['aggregate'], models); proposal = proposed_candidate(models)
    for name, value in [('models.json', models), ('scores.json', scored), ('rank_audit.json', audit), ('development_proposal.json', proposal)]: write_json(out / name, value)
    result = {'format': 'biograph-steward.growth-development-diagnostics.v1', 'created_at': utcnow(), 'policy': POLICY,
        'parent_result_sha256': previous['result_sha256'], 'protocol_sha256': previous['protocol_sha256'],
        'engine_files': engine_fingerprint(), 'exposed_gene_count': previous['test_genes'],
        'fresh_test_executed': False, 'original_score_matrix_opened': False, 'fresh_dependency_values_loaded': False,
        'scientific_improvement_established': False, 'additional_ridge_fits': len(ABLATIONS) * 4,
        'ranking_error': {'improved_genes': sum(g['rank_error_reduction'] > 0 for g in audit),
            'worsened_genes': sum(g['rank_error_reduction'] < 0 for g in audit), 'unchanged_genes': sum(g['rank_error_reduction'] == 0 for g in audit),
            'pharos_mean_absolute_rank_error': statistics.mean(g['absolute_rank_error_before'] for g in audit),
            'enriched_mean_absolute_rank_error': statistics.mean(g['absolute_rank_error_after'] for g in audit)},
        'coverage': {'test_genes_with_pathways': sum(g['pathway_memberships'] > 0 for g in audit),
            'test_genes_with_pathways_seen_in_fit': sum(g['pathways_seen_in_fit_vocabulary'] > 0 for g in audit),
            'test_genes_with_bioplex_fit_neighbors': sum(bool(g['bioplex_fit_neighbors']) for g in audit)},
        'arms': scored, 'development_proposal': proposal, 'model_service_requests': 0,
        'limits': ['Every reported test-block score reuses the already exposed 52-gene holdout and is exploratory development, not fresh validation.',
            'Six new ablations each use the original three-alpha validation budget plus one refit. The same validation set is reused adaptively.',
            'Fixed fusion uses two component fitting budgets, no additional fits and no tuned weight. It is not a budget-matched single ridge arm.',
            'Block-contribution decompositions are statistical, not causal. Annotation availability, sparse BioPlex coverage and source overlap remain limitations.',
            'Reserved genes require Pharos retrieval, frozen source/split/endpoint rules and a sealed prediction packet before any final outcome access.'],
        'files': {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_diagnostics(result, audit), encoding='utf-8')
    return result


def _verify_files(path, expected):
    path = Path(path); result = _read(path, 'metrics.json')
    if set(result['files']) != set(expected) or result['result_sha256'] != digest({k: v for k, v in result.items() if k != 'result_sha256'}):
        raise ValueError('Diagnostic/reservation manifest changed.')
    for name, value in result['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value: raise ValueError('Diagnostic/reservation artifact changed.')
    return result


def verify_diagnostics(path):
    path = Path(path)
    original = ['protocol_features.json', 'protocol_source_inputs.json', 'protocol_partitions.json', 'fit_outcomes.json',
        'test_outcomes.json', 'fitted_models.json', 'sealed_predictions.json', 'gene_passports.json',
        'experimental_source_manifest.json', 'protocol_references.json', 'protocol_source_review.json', 'metrics.json']
    r = _verify_files(path, ['original/' + n for n in original] + ['models.json', 'scores.json', 'rank_audit.json', 'development_proposal.json'])
    if r['policy'] != POLICY or r['fresh_test_executed'] or r['original_score_matrix_opened'] or r['fresh_dependency_values_loaded']:
        raise ValueError('Development-only scope changed.')
    parent = _read(path / 'original', 'metrics.json')
    if parent['result_sha256'] != r['parent_result_sha256'] or parent['result_sha256'] != digest({k: v for k, v in parent.items() if k != 'result_sha256'}):
        raise ValueError('Original result binding changed.')
    for name in original:
        if name != 'metrics.json' and sha(path / 'original' / name) != parent['files'][name]: raise ValueError('Original packet file changed.')
    models = _read(path, 'models.json'); test = _read(path / 'original', 'test_outcomes.json')
    old = _read(path / 'original', 'fitted_models.json')
    if set(models) != set(ORIGINAL_ARMS + list(ABLATIONS) + [FUSION]): raise ValueError('Declared diagnostic arms changed.')
    for name in ORIGINAL_ARMS:
        if models[name] != old[name]: raise ValueError('Original fitted model changed.')
    for name in ABLATIONS:
        row = models[name]
        if predict(row['model'], row['test_vectors']) != row['predictions'] or any(block_of(k) not in ABLATIONS[name] for k in row['model']['coefficients']):
            raise ValueError('Ablation prediction or block mask changed.')
    if models[FUSION] != fusion(models['pharos_restricted'], models['cptac_only']): raise ValueError('Fixed fusion changed.')
    scores = {name: {**metrics(row['predictions'], test['aggregate'], test['gene_ids'], test['by_sample_group']),
        'validation_spearman': validation_score(row), 'selected_alpha': row['selected_alpha']} for name, row in models.items()}
    genes = {g['hgnc_id']: g for g in _read(path / 'original', 'protocol_features.json')['genes']}
    if scores != _read(path, 'scores.json') or scores != r['arms']: raise ValueError('Diagnostic scores do not reproduce.')
    if proposed_candidate(models) != r['development_proposal'] or proposed_candidate(models) != _read(path, 'development_proposal.json'):
        raise ValueError('Development proposal no longer follows validation-only rule.')
    if audit_genes(genes, test['gene_ids'], test['aggregate'], models) != _read(path, 'rank_audit.json'): raise ValueError('Rank audit does not reproduce.')
    return r


def select_reserve(population, exposed, size=256):
    """Whole reviewed-product components; continue the original outcome-blind hash order."""
    if type(size) is not int or not 1 <= size <= 256: raise ValueError('Reserve size must be 1–256 genes.')
    by_gene = {r['hgnc_id']: r for r in population}
    if len(by_gene) != len(population) or not exposed or not set(exposed) <= set(by_gene): raise ValueError('Invalid eligible population/exposure set.')
    owners = defaultdict(set)
    for row in population:
        for p in row['protein_candidates']: owners[p['uniprot_id']].add(row['hgnc_id'])
    components = []; remaining = set(by_gene)
    while remaining:
        start = min(remaining, key=gene_key); seen = {start}; pending = [start]
        while pending:
            gid = pending.pop()
            for p in by_gene[gid]['protein_candidates']:
                for other in owners[p['uniprot_id']] - seen: seen.add(other); pending.append(other)
        remaining -= seen
        components.append({'genes': sorted(seen, key=gene_key), 'selection_hash': min(by_gene[g]['selection_hash'] for g in seen)})
    components.sort(key=lambda c: (c['selection_hash'], [gene_key(g) for g in c['genes']]))
    selected = []; exclusions = []; skipped = 0
    for component in components:
        if set(component['genes']) & set(exposed):
            exclusions.append({**component, 'reason': 'previously_exposed_gene_or_shared_reviewed_product_component'}); continue
        if len(selected) < size: selected.extend(component['genes'])
        else: skipped += len(component['genes'])
    if len(selected) < size: raise ValueError('Insufficient untouched genes; no replacement or reseeding.')
    members = sorted((deepcopy(by_gene[g]) for g in selected), key=lambda r: (r['selection_hash'], gene_key(r['hgnc_id'])))
    return members, exclusions, skipped


def reserve_fresh(panel_path, comparison, output):
    panel_path = Path(panel_path); comparison = Path(comparison)
    panel, old_members = load_panel(panel_path); previous = verify_comparison(comparison)
    protocol = _read(comparison, 'protocol_metrics.json')
    if protocol['panel_sha256'] != panel['panel_sha256'] or protocol['depmap_source_sha256'] != panel['depmap_source_sha256']:
        raise ValueError('Previous experiment and source population differ.')
    models = _read(comparison, 'fitted_models.json'); test = _read(comparison, 'test_outcomes.json')
    fit_ids = models['pharos_restricted']['final_design']['fit_gene_ids']; test_ids = test['gene_ids']
    exposed = set(fit_ids) | set(test_ids)
    if exposed != {g['hgnc_id'] for g in old_members} or set(fit_ids) & set(test_ids): raise ValueError('Previous outcome exposure inventory is incomplete.')
    population = _read(panel_path, 'eligible_population.json'); members, exclusions, remaining = select_reserve(population, exposed)
    exposure = {'parent_result_sha256': previous['result_sha256'], 'previous_panel_sha256': panel['panel_sha256'],
        'depmap_source_sha256': panel['depmap_source_sha256'], 'fit_gene_ids': fit_ids, 'exposed_test_gene_ids': test_ids,
        'bound_files': {name: previous['files'][name] for name in ['fit_outcomes.json', 'test_outcomes.json', 'fitted_models.json']},
        'scope': 'All CRISPR gene values used by this bound pilot. This is not an attestation about outside analyses or genuinely new laboratory cohorts.'}
    out = new_output(output, panel_path, comparison)
    for name, value in [('eligible_population.json', population), ('reserved_members.json', members), ('component_exclusions.json', exclusions),
        ('prior_panel.json', panel), ('prior_exposure.json', exposure), ('model_partitions.json', _read(comparison, 'protocol_partitions.json')['models'])]: write_json(out / name, value)
    result = {'format': 'biograph-steward.untouched-gene-reservation.v1', 'created_at': utcnow(), 'policy': RESERVE_POLICY,
        'parent_result_sha256': previous['result_sha256'], 'previous_panel_sha256': panel['panel_sha256'],
        'depmap_source_sha256': panel['depmap_source_sha256'], 'engine_files': engine_fingerprint(),
        'eligible_genes': len(population), 'previously_exposed_genes': len(exposed),
        'excluded_component_genes': sum(len(c['genes']) for c in exclusions), 'requested_reserve_genes': 256,
        'reserved_genes': len(members), 'remaining_unreserved_genes': remaining,
        'gene_overlap_with_previous': len({m['hgnc_id'] for m in members} & exposed),
        'protein_overlap_with_previous': len({p['uniprot_id'] for m in members for p in m['protein_candidates']} & {p['uniprot_id'] for m in old_members for p in m['protein_candidates']}),
        'selection_rule': 'Continue the original stable-ID hash order after excluding every component containing a previously exposed gene; include whole reviewed-product components until at least 256 genes. No reseeding, label-based selection or replacement.',
        'fresh_dependency_values_loaded': False, 'new_pharos_features_retrieved': False, 'scoring_protocol_frozen': False,
        'fresh_model_groups': False, 'scientific_improvement_established': False, 'model_service_requests': 0,
        'limits': ['Reservation only, not a scored benchmark or biological result. No experimental score-matrix argument or reader is used.',
            'Genes are new to the bound pilot outcome files; the historical release and recorded model groups are reused, not independent new laboratory data.',
            'Pharos retrieval must cover development plus reserved genes with consistent partner scope and database version; reusing a fresh-only PPI subgraph would omit links to development genes.',
            'Freeze the candidate, final splits, source policy, tuning/fusion budget, endpoints and controls before sealed prediction and first reserved-outcome access.',
            'No reserved-gene substitutions after inspecting annotations, missing products or outcomes. This cohort remains a complete-measurement intersection, not all human genes.'],
        'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_reserve(result, members), encoding='utf-8')
    return result


def verify_reserve(path):
    path = Path(path); expected = ['eligible_population.json', 'reserved_members.json', 'component_exclusions.json', 'prior_panel.json', 'prior_exposure.json', 'model_partitions.json']
    r = _verify_files(path, expected); panel = _read(path, 'prior_panel.json'); exposure = _read(path, 'prior_exposure.json')
    population = _read(path, 'eligible_population.json')
    if (r['policy'] != RESERVE_POLICY or r['fresh_dependency_values_loaded'] or r['new_pharos_features_retrieved'] or r['scoring_protocol_frozen'] or
            panel['panel_sha256'] != digest({k: v for k, v in panel.items() if k != 'panel_sha256'}) or
            panel['files']['eligible_population.json'] != sha(path / 'eligible_population.json') or
            r['parent_result_sha256'] != exposure['parent_result_sha256'] or r['previous_panel_sha256'] != panel['panel_sha256'] or
            r['depmap_source_sha256'] != panel['depmap_source_sha256']): raise ValueError('Reservation scope/source identity changed.')
    exposed = set(exposure['fit_gene_ids']) | set(exposure['exposed_test_gene_ids'])
    members, exclusions, remaining = select_reserve(population, exposed)
    if (members != _read(path, 'reserved_members.json') or exclusions != _read(path, 'component_exclusions.json') or
            len(members) != r['reserved_genes'] or remaining != r['remaining_unreserved_genes'] or r['gene_overlap_with_previous'] or r['protein_overlap_with_previous']):
        raise ValueError('Untouched membership does not reproduce.')
    return r


def _html(title, body):
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + escape(title) + '</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.6 system-ui;color:#173047}'
        'table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #ccd;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}.notice{padding:20px;background:#fff4db;border-left:5px solid #c28108}</style><h1>' + escape(title) + '</h1>' + body + '</html>')


def render_diagnostics(result, audit):
    num = lambda v: 'undefined' if v is None else f'{v:.4f}'
    table = ''.join('<tr><td>' + escape(name) + '</td><td>' + num(row['validation_spearman']) + '</td><td>' + num(row['spearman']) + '</td><td>' + num(row['recall_at_10']) + '</td></tr>' for name, row in result['arms'].items())
    genes = ''.join('<tr><td><details><summary>' + escape(g['symbol']) + '</summary><pre>' + escape(json.dumps(g, indent=2)) + '</pre></details></td><td>' + str(g['pharos_rank']) + '</td><td>' + str(g['enriched_rank']) + '</td><td>' + str(g['measured_rank']) + '</td><td>' + str(g['rank_error_reduction']) + '</td></tr>' for g in audit)
    return _html('Why did enrichment fail in the pilot?', '<div class="notice"><strong>Development diagnostics: the original test set is already exposed.</strong><p>These ablations do not establish improvement. No fresh dependency values were opened.</p></div>'
        '<h2>Source blocks and fixed late combination</h2><p>Every ablation removes complete feature blocks and keeps the original training-only transforms and three-alpha budget. Fusion averages saved Pharos and CPTAC-only predictions with fixed equal weights; it reuses two component budgets.</p>'
        '<table><tr><th>Variant</th><th>Original validation Spearman</th><th>Exposed test Spearman (exploratory)</th><th>Exposed Recall@10</th></tr>' + table + '</table>'
        '<h2>Validation-selected development proposal</h2><pre>' + escape(json.dumps(result['development_proposal'], indent=2)) + '</pre>'
        '<h2>Rank errors and coverage</h2><pre>' + escape(json.dumps({k: result[k] for k in ['ranking_error', 'coverage']}, indent=2)) + '</pre>'
        '<h2>All 52 exposed genes</h2><p>Positive rank-error reduction means that the enriched rank moved closer to the measured rank. Contributions sum to saved predictions; they are not biological causes.</p>'
        '<table><tr><th>Gene / recorded decomposition</th><th>Pharos rank</th><th>Enriched rank</th><th>Measured rank</th><th>Error reduction</th></tr>' + genes + '</table>'
        '<p>Saved experimental values: Broad Institute, <a href="https://doi.org/10.25452/figshare.plus.27993248.v1">DepMap 24Q4 Public v1</a>, '
        '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Values are negated and grouped as specified by the original protocol. '
        'The export retains the publisher source manifest and original source-review/reference records for Pharos, CPTAC and BioPlex.</p>'
        '<h2>Limits and reproducibility</h2><pre>' + escape(json.dumps(result, indent=2)) + '</pre>')


def render_reserve(result, members):
    return _html('Untouched genes reserved for the next test', '<div class="notice"><strong>Reservation only: no new test outcomes opened.</strong><p>These genes are excluded from development. Features and the final comparison protocol still need to be frozen before testing.</p></div>'
        '<p>Reserved ' + str(result['reserved_genes']) + ' genes, with zero gene or protein-product overlap with the previous pilot. The original stable-ID hash order is continued; shared-product components stay together.</p>'
        '<h2>Reserved members</h2><table><tr><th>Stable gene ID</th><th>Symbol</th></tr>' + ''.join('<tr><td>' + escape(g['hgnc_id']) + '</td><td>' + escape(g['approved_symbol']) + '</td></tr>' for g in members) + '</table>'
        '<h2>Selection, sources and limits</h2><pre>' + escape(json.dumps(result, indent=2)) + '</pre>')
