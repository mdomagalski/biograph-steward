"""CPU-only execution of the frozen growth-ranking pilot; no model/service clients."""
import csv
from html import escape
import json
import math
from pathlib import Path
import random
import statistics

from .client import digest, utcnow, write_json
from .comparison_protocol import POLICY, verify_protocol
from .crc_pilot import new_output, sha
from .depmap_audit import load_depmap, MISSING
from .evaluation import engine_fingerprint

ARMS = ['pharos_restricted', 'pharos_restricted_plus_cptac', 'cptac_only', 'coverage_only']
ALPHAS = [0.1, 1.0, 10.0]


def gene_key(gid):
    return int(gid.split(':')[1])


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i]); result = [0.0] * len(values); start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]: end += 1
        for i in order[start:end]: result[i] = (start + end - 1) / 2 + 1
        start = end
    return result


def spearman(a, b):
    if len(a) != len(b) or len(a) < 2: return None
    x = ranks(a); y = ranks(b); mx = statistics.mean(x); my = statistics.mean(y)
    xx = sum((v - mx) ** 2 for v in x); yy = sum((v - my) ** 2 for v in y)
    return sum((u - mx) * (v - my) for u, v in zip(x, y)) / math.sqrt(xx * yy) if xx and yy else None


def percentile(values, probability):
    if not values: return None
    values = sorted(values); pos = (len(values) - 1) * probability; low = int(pos); high = math.ceil(pos)
    return values[low] + (values[high] - values[low]) * (pos - low)


def summary(values):
    available = [v for v in values if v is not None]
    return {'defined': len(available), 'undefined': len(values) - len(available),
            'mean': statistics.mean(available) if available else None,
            'minimum': min(available) if available else None, 'maximum': max(available) if available else None,
            'percentile_2_5': percentile(available, .025), 'percentile_97_5': percentile(available, .975)}


def _dot(a, b):
    if len(a) > len(b): a, b = b, a
    return sum(value * b.get(key, 0.0) for key, value in a.items())


def _unit(values):
    norm = math.sqrt(sum(v * v for v in values.values()))
    return {key: value / norm for key, value in values.items() if value} if norm else {}


def _scaler(values):
    observed = [v for v in values if v is not None]
    if not observed: return None
    median = statistics.median(observed); imputed = [median if v is None else v for v in values]
    mean = statistics.mean(imputed); std = math.sqrt(statistics.mean((v - mean) ** 2 for v in imputed))
    return {'median': median, 'mean': mean, 'std': std or 1.0}


def _scaled(value, scaler):
    return ((scaler['median'] if value is None else value) - scaler['mean']) / scaler['std']


class Design:
    """Training-only vocabularies and impute-then-scale transforms, no outcome access."""
    def __init__(self, genes, fit_ids, arm):
        if arm not in ARMS: raise ValueError('Unknown frozen comparison arm.')
        self.genes = genes; self.fit_ids = sorted(fit_ids, key=gene_key); self.arm = arm
        if len(set(self.fit_ids)) != len(self.fit_ids) or not self.fit_ids: raise ValueError('Invalid fit genes.')
        self.pathways = sorted({(p['source'], p['stable_id']) for gid in fit_ids for p in genes[gid]['pathways']})
        self.categories = sorted({(p['source'], p['tissue'], cat) for gid in fit_ids for p in genes[gid]['categorical_expression'] for cat in p['categories']})
        self.tissues = sorted({(s, t) for s, t, _ in self.categories})
        self.numeric = {}; self.numeric_raw = {gid: {(r['source'], r['tissue']): r['value'] for r in gene['numeric_expression']} for gid, gene in genes.items()}
        for key in sorted({k for gid in fit_ids for k in self.numeric_raw[gid]}):
            values = [self.numeric_raw[gid].get(key) for gid in self.fit_ids]
            scaler = _scaler([math.log1p(v) if v is not None else None for v in values])
            if scaler: self.numeric[key] = scaler
        self.cptac = _scaler([genes[gid]['cptac_median_reported_log2_ratio'] for gid in self.fit_ids]) if arm in {'cptac_only', 'pharos_restricted_plus_cptac'} else None
        coverage = [self._coverage(genes[gid]) for gid in self.fit_ids]
        self.coverage_scalers = [_scaler([r[i] for r in coverage]) for i in range(len(coverage[0]))]
        self.columns = self._columns()

    def _columns(self):
        if self.arm == 'coverage_only':
            return ['coverage|Reactome', 'coverage|WikiPathways', 'coverage|BioPlex'] + ['coverage_missing|' + '|'.join(k) for k in [*self.numeric, *self.tissues]]
        columns = []
        if self.arm != 'cptac_only':
            columns += ['pathway|' + '|'.join(k) for k in self.pathways]
            columns += ['bioplex|' + gid for gid in self.fit_ids]
            columns += [prefix + '|' + '|'.join(k) for k in self.numeric for prefix in ['expression', 'expression_missing']]
            columns += ['category|' + '|'.join(k) for k in self.categories]
            columns += ['category|' + '|'.join(k) + '|__unobserved__' for k in self.tissues]
        if self.arm in {'cptac_only', 'pharos_restricted_plus_cptac'} and self.cptac:
            columns += ['cptac|median_ratio', 'cptac|missing']
        return columns

    def _coverage(self, gene):
        values = [math.log1p(sum(p['source'] == source for p in gene['pathways'])) for source in ['Reactome', 'WikiPathways']]
        values.append(math.log1p(len(gene['bioplex_neighbors'])))
        numeric = {(r['source'], r['tissue']): r['value'] for r in gene['numeric_expression']}
        tissues = {(r['source'], r['tissue']) for r in gene['categorical_expression'] if r['categories']}
        return values + [float(numeric.get(k) is None) for k in self.numeric] + [float(k not in tissues) for k in self.tissues]

    def row(self, gid):
        gene = self.genes[gid]; result = {}
        if self.arm == 'coverage_only':
            return {k: v for k, v in zip(self.columns, [_scaled(v, s) for v, s in zip(self._coverage(gene), self.coverage_scalers)]) if v}
        if self.arm != 'cptac_only':
            memberships = {(p['source'], p['stable_id']) for p in gene['pathways']}
            for source in ['Reactome', 'WikiPathways']:
                result.update(_unit({'pathway|' + '|'.join(k): 1.0 for k in self.pathways if k[0] == source and k in memberships}))
            result.update(_unit({'bioplex|' + neighbor: 1.0 for neighbor in self.fit_ids if neighbor != gid and neighbor in gene['bioplex_neighbors']}))
            denominator = math.sqrt(2 * len(self.numeric)) if self.numeric else 1
            for key, scaler in self.numeric.items():
                raw = self.numeric_raw[gid].get(key); value = math.log1p(raw) if raw is not None else None
                result['expression|' + '|'.join(key)] = _scaled(value, scaler) / denominator
                result['expression_missing|' + '|'.join(key)] = float(value is None) / denominator
            observed = {(p['source'], p['tissue']): set(p['categories']) for p in gene['categorical_expression']}
            cat = {'category|' + '|'.join(k): 1.0 for k in self.categories if k[2] in observed.get(k[:2], set())}
            cat.update({'category|' + '|'.join(k) + '|__unobserved__': 1.0 for k in self.tissues if not observed.get(k)})
            result.update(_unit(cat))
        if self.arm in {'cptac_only', 'pharos_restricted_plus_cptac'} and self.cptac:
            value = gene['cptac_median_reported_log2_ratio']; result['cptac|median_ratio'] = _scaled(value, self.cptac)
            result['cptac|missing'] = float(value is None)
        if any(not math.isfinite(v) for v in result.values()): raise ValueError('Nonfinite transformed feature.')
        return {key: value for key, value in result.items() if value}

    def receipt(self):
        return {'arm': self.arm, 'fit_gene_ids': self.fit_ids, 'columns': self.columns,
            'numeric_expression_scalers': [{'source': k[0], 'tissue': k[1], **s} for k, s in self.numeric.items()],
            'cptac_scaler': self.cptac if self.arm in {'cptac_only', 'pharos_restricted_plus_cptac'} else None,
            'coverage_scalers': self.coverage_scalers if self.arm == 'coverage_only' else None,
            'scaling_order': 'Fit observed median; impute fit genes; fit population mean/std on imputed fit values; transform other genes. Numeric expression block divisor includes values and missing-indicator columns.'}


def _solve_spd(matrix, target):
    n = len(matrix); lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            value = matrix[i][j] - sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                if value <= 0 or not math.isfinite(value): raise ValueError('Ridge system is not positive definite.')
                lower[i][j] = math.sqrt(value)
            else: lower[i][j] = value / lower[j][j]
    y = []
    for i in range(n): y.append((target[i] - sum(lower[i][j] * y[j] for j in range(i))) / lower[i][i])
    weights = [0.0] * n
    for i in range(n - 1, -1, -1): weights[i] = (y[i] - sum(lower[j][i] * weights[j] for j in range(i + 1, n))) / lower[i][i]
    return weights


def ridge_fit(rows, targets, alpha):
    if len(rows) != len(targets) or not rows or alpha not in ALPHAS or any(not math.isfinite(v) for v in targets):
        raise ValueError('Invalid ridge fit inputs.')
    n = len(rows); gram = [[0.0] * n for _ in rows]
    for i in range(n):
        for j in range(i + 1): gram[i][j] = gram[j][i] = _dot(rows[i], rows[j])
    means = [statistics.mean(r) for r in gram]; mean = statistics.mean(means); target_mean = statistics.mean(targets)
    matrix = [[gram[i][j] - means[i] - means[j] + mean + (n * alpha if i == j else 0) for j in range(n)] for i in range(n)]
    dual = _solve_spd(matrix, [v - target_mean for v in targets])
    # Explicit primal coefficients support auditable prediction contributions.
    columns = sorted({k for row in rows for k in row}); coefficients = {}
    column_means = {k: sum(row.get(k, 0.0) for row in rows) / n for k in columns}
    for key in columns: coefficients[key] = sum(w * (row.get(key, 0.0) - column_means[key]) for w, row in zip(dual, rows))
    intercept = target_mean - sum(coefficients[k] * column_means[k] for k in columns)
    return {'alpha': alpha, 'intercept': intercept, 'coefficients': coefficients, 'fit_genes': n}


def predict(model, rows):
    values = [model['intercept'] + _dot(model['coefficients'], row) for row in rows]
    if any(not math.isfinite(v) for v in values): raise ValueError('Nonfinite model prediction.')
    return values


def split_ids(partitions, axis, splits):
    key = 'hgnc_ids' if axis == 'genes' else 'model_ids'
    values = [i for g in partitions[axis] if g['split'] in splits for i in g[key]]
    return sorted(values, key=gene_key if axis == 'genes' else str)


def read_effects(matrix, inputs, gene_ids, model_ids):
    """Read only requested model/gene cells; other numeric values are never parsed."""
    members = {g['hgnc_id']: g for g in inputs['members']}; models = {m['model_id']: m for m in inputs['models']}
    wanted = set(model_ids); seen = set(); output = {}; selected = [members[g] for g in gene_ids]
    with Path(matrix).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f); header = next(reader, [])
        if not header or header[0] not in {'', 'ModelID'} or len(set(header)) != len(header): raise ValueError('Changed gene-effect header.')
        for member in selected:
            column = member['depmap_matrix_column']
            if (not 0 < column < len(header) or header[column] != member['depmap_release_label'] or
                    not header[column].endswith(' (' + member['ncbi_gene_id'] + ')')): raise ValueError('Changed stable gene/column identity.')
        for number, row in enumerate(reader, 2):
            if len(row) != len(header) or row[0] in seen: raise ValueError('Malformed or duplicate matrix row.')
            mid = row[0]; seen.add(mid)
            if mid not in wanted: continue
            if number != models[mid]['matrix_row']: raise ValueError('Changed model/matrix-row identity.')
            values = {}
            for member in selected:
                raw = row[member['depmap_matrix_column']]
                if raw in MISSING: raise ValueError('Unexpected missing outcome in frozen complete-measurement panel.')
                value = float(raw)
                if not math.isfinite(value): raise ValueError('Nonfinite experimental outcome.')
                values[member['hgnc_id']] = -value
            output[mid] = values
    if set(output) != wanted: raise ValueError('Selected models missing from experimental matrix.')
    return output


def group_outcomes(raw, groups, gene_ids):
    return {g['group']: {gid: statistics.median(raw[mid][gid] for mid in g['model_ids']) for gid in gene_ids} for g in groups}


def aggregate(groups, gene_ids):
    if not groups: raise ValueError('No experimental sample groups.')
    return [statistics.median(row[gid] for row in groups.values()) for gid in gene_ids]


def permuted_genes(genes, partitions, seed):
    result = dict(genes); mapping = {}
    for split in ['train', 'validation', 'test']:
        destinations = split_ids(partitions, 'genes', {split})
        donors = sorted(destinations, key=lambda gid: (digest({'policy': POLICY, 'seed': seed, 'hgnc_id': gid}), gene_key(gid)))
        for gid, donor in zip(destinations, donors):
            result[gid] = {**genes[gid], 'cptac_median_reported_log2_ratio': genes[donor]['cptac_median_reported_log2_ratio']}; mapping[gid] = donor
    return result, mapping


def fit_arm(genes, partitions, fit_outcomes, arm):
    train = split_ids(partitions, 'genes', {'train'}); validation = split_ids(partitions, 'genes', {'validation'})
    combined = split_ids(partitions, 'genes', {'train', 'validation'}); test = split_ids(partitions, 'genes', {'test'})
    train_groups = [g for g in partitions['models'] if g['split'] == 'train']; val_groups = [g for g in partitions['models'] if g['split'] == 'validation']
    y_train = aggregate(group_outcomes(fit_outcomes, train_groups, train), train)
    y_val = aggregate(group_outcomes(fit_outcomes, val_groups, validation), validation)
    design = Design(genes, train, arm); x_train = [design.row(g) for g in train]; x_val = [design.row(g) for g in validation]
    candidates = []; best = None; chosen = None
    for alpha in ALPHAS:
        model = ridge_fit(x_train, y_train, alpha); values = predict(model, x_val); score = spearman(values, y_val)
        candidates.append({'alpha': alpha, 'spearman': score, 'predictions': values})
        key = (score is not None, score if score is not None else 0, alpha)
        if best is None or key > best: best = key; chosen = alpha
    final_design = Design(genes, combined, arm); x_fit = [final_design.row(g) for g in combined]; x_test = [final_design.row(g) for g in test]
    final_target = aggregate(group_outcomes(fit_outcomes, train_groups + val_groups, combined), combined)
    model = ridge_fit(x_fit, final_target, chosen)
    return {'arm': arm, 'selection': candidates, 'selected_alpha': chosen, 'validation_gene_ids': validation,
        'validation_target': y_val, 'selection_design': design.receipt(), 'final_design': final_design.receipt(),
        'model': model, 'test_gene_ids': test, 'predictions': predict(model, x_test), 'test_vectors': x_test}


def metrics(predictions, target, ids, groups, *, ranking_only=False):
    correlation = spearman(predictions, target)
    order = lambda values: sorted(range(len(ids)), key=lambda i: (-values[i], gene_key(ids[i])))
    recall = len(set(order(predictions)[:10]) & set(order(target)[:10])) / 10 if len(ids) >= 10 else None
    return {'spearman': correlation, 'spearman_undefined_reason': 'Constant or insufficient prediction/target ranks.' if correlation is None else None,
        'mae': statistics.mean(abs(a - b) for a, b in zip(predictions, target)) if not ranking_only else None,
        'mae_undefined_reason': 'Hash ranking has no experimental-effect units.' if ranking_only else None,
        'recall_at_10': recall, 'recall_undefined_reason': 'Fewer than ten test genes.' if recall is None else None,
        'per_sample_group_spearman': {group: spearman(predictions, [row[g] for g in ids]) for group, row in groups.items()}}


def paired_bootstrap(base, enriched, groups, ids):
    rng = random.Random(20261020); keys = sorted(groups); differences = []
    for _ in range(2000):
        sampled_groups = [keys[rng.randrange(len(keys))] for _ in keys]
        target = [statistics.median(groups[k][gid] for k in sampled_groups) for gid in ids]
        indices = [rng.randrange(len(ids)) for _ in ids]
        a = spearman([base[i] for i in indices], [target[i] for i in indices])
        b = spearman([enriched[i] for i in indices], [target[i] for i in indices])
        if a is not None and b is not None: differences.append(b - a)
    enough = len(differences) >= 1800
    return {'replicates': 2000, 'valid': len(differences), 'undefined': 2000 - len(differences), 'seed': 20261020,
        'lower_95': percentile(differences, .025) if enough else None, 'upper_95': percentile(differences, .975) if enough else None,
        'interval_unavailable_reason': None if enough else 'Fewer than 1,800 defined paired bootstrap replicates.', 'differences': differences}


def decision(delta, interval):
    signal = delta is not None and delta >= .05 and interval['lower_95'] is not None and interval['lower_95'] > 0
    return {'within_pilot_signal': signal, 'status': 'within_pilot_incremental_signal' if signal else 'no_demonstrated_incremental_gain',
        'interpretation': 'Meets the frozen internal signal rule for this retrospective pilot only.' if signal else 'The frozen pilot does not demonstrate an incremental gain; preserve the result without retuning on this holdout.'}


def _seal_predictions(out, protocol, fitted, random_scores, intercept, permutations):
    seal = {'format': 'biograph-steward.pre-test-predictions.v1', 'created_at': utcnow(), 'protocol_sha256': protocol['result_sha256'],
        'predictions': {name: {'test_gene_ids': row['test_gene_ids'], 'predictions': row['predictions'], 'selected_alpha': row['selected_alpha']} for name, row in fitted.items()},
        'random_rankings': random_scores, 'intercept': intercept, 'permutation_donors': permutations,
        'test_values_accessed': False, 'engine_files': engine_fingerprint(),
        'pre_test_files': {name: sha(out / name) for name in ['fit_outcomes.json', 'fitted_models.json']}}
    seal['seal_sha256'] = digest(seal); write_json(out / 'sealed_predictions.json', seal)
    return seal


def claim_test_access(protocol_path, out, seal):
    lock = Path(protocol_path).parent / ('.growth_test_access_' + seal['protocol_sha256'] + '.json')
    record = {'created_at': utcnow(), 'protocol_sha256': seal['protocol_sha256'], 'prediction_seal_sha256': seal['seal_sha256'], 'output': str(Path(out).resolve())}
    # Sibling ledger, never a mutation of the frozen packet. Failure is retained.
    with lock.open('x', encoding='utf-8') as f: f.write(json.dumps(record, indent=2) + '\n')
    write_json(Path(out) / 'test_access_receipt.json', record)


def run_comparison(protocol_path, source_path, output, *, progress=None):
    protocol_path = Path(protocol_path); source_path = Path(source_path); protocol = verify_protocol(protocol_path)
    lock = protocol_path.parent / ('.growth_test_access_' + protocol['result_sha256'] + '.json')
    if lock.exists(): raise ValueError('This protocol already opened test outcomes; verify its preserved result instead of rerunning the holdout.')
    source = load_depmap(source_path)
    if source['source_sha256'] != protocol['depmap_source_sha256']: raise ValueError('Experimental source differs from frozen protocol.')
    inputs = json.loads((protocol_path / 'source_inputs.json').read_text()); partitions = json.loads((protocol_path / 'partitions.json').read_text())
    features = json.loads((protocol_path / 'features.json').read_text()); genes = {g['hgnc_id']: g for g in features['genes']}
    out = new_output(output, protocol_path, source_path)
    for name in ['metrics.json', 'specification.json', 'features.json', 'partitions.json', 'references.json', 'source_review.json', 'source_inputs.json']:
        (out / ('protocol_' + name)).write_bytes((protocol_path / name).read_bytes())
    write_json(out / 'experimental_source_manifest.json', source)
    combined = split_ids(partitions, 'genes', {'train', 'validation'}); test = split_ids(partitions, 'genes', {'test'})
    fit_models = split_ids(partitions, 'models', {'train', 'validation'}); test_models = split_ids(partitions, 'models', {'test'})
    if progress: progress('Verified frozen inputs. Reading fit/validation model × gene block only.')
    fit_outcomes = read_effects(source_path / 'CRISPRGeneEffect.csv', inputs, combined, fit_models)
    write_json(out / 'fit_outcomes.json', fit_outcomes)
    fitted = {}; donors = {}
    for arm in ARMS:
        fitted[arm] = fit_arm(genes, partitions, fit_outcomes, arm)
        if progress: progress('Fitted ' + arm + ' using the three-alpha validation budget.')
    for seed in range(20):
        permuted, mapping = permuted_genes(genes, partitions, seed); name = 'cptac_permutation_' + str(seed)
        fitted[name] = fit_arm(permuted, partitions, fit_outcomes, 'pharos_restricted_plus_cptac'); donors[name] = mapping
        if progress: progress('Fitted CPTAC permutation ' + str(seed + 1) + '/20.')
    final_groups = [g for g in partitions['models'] if g['split'] in {'train', 'validation'}]
    intercept_value = statistics.mean(aggregate(group_outcomes(fit_outcomes, final_groups, combined), combined))
    intercept = [intercept_value] * len(test)
    random_scores = []
    for seed in range(100):
        order = sorted(test, key=lambda gid: (digest({'policy': POLICY, 'seed': seed, 'hgnc_id': gid}), gene_key(gid)))
        lookup = {gid: i for i, gid in enumerate(order)}; random_scores.append([lookup[gid] for gid in test])
    write_json(out / 'fitted_models.json', fitted)
    seal = _seal_predictions(out, protocol, fitted, random_scores, intercept, donors)
    claim_test_access(protocol_path, out, seal)
    if progress: progress('All predictions sealed. Opening the fixed test block once.')
    test_outcomes = read_effects(source_path / 'CRISPRGeneEffect.csv', inputs, test, test_models)
    test_groups = group_outcomes(test_outcomes, [g for g in partitions['models'] if g['split'] == 'test'], test)
    target = aggregate(test_groups, test)
    write_json(out / 'test_outcomes.json', {'by_model': test_outcomes, 'by_sample_group': test_groups, 'gene_ids': test, 'aggregate': target})
    scores = {name: metrics(row['predictions'], target, test, test_groups) for name, row in fitted.items()}
    scores['intercept'] = metrics(intercept, target, test, test_groups)
    random_metrics = [metrics(values, target, test, test_groups, ranking_only=True) for values in random_scores]
    write_json(out / 'scores.json', {'arms_and_permutations': scores, 'random_rankings': random_metrics})
    a = scores['pharos_restricted']['spearman']; b = scores['pharos_restricted_plus_cptac']['spearman']
    delta = b - a if a is not None and b is not None else None
    interval = paired_bootstrap(fitted['pharos_restricted']['predictions'], fitted['pharos_restricted_plus_cptac']['predictions'], test_groups, test)
    write_json(out / 'paired_bootstrap.json', interval)
    passports = gene_passports(genes, test, target, fitted, features['bioplex_edges']); write_json(out / 'gene_passports.json', passports)
    result = {'format': 'biograph-steward.growth-comparison-result.v1', 'created_at': utcnow(),
        'protocol_sha256': protocol['result_sha256'], 'prediction_seal_sha256': seal['seal_sha256'], 'source_sha256': source['source_sha256'],
        'engine_files': engine_fingerprint(), 'runtime': 'Python standard library, deterministic CPU linear algebra; no external dependencies or model service.',
        'test_genes': len(test), 'test_models': len(test_models), 'test_sample_groups': len(test_groups),
        'fit_genes': len(combined), 'fit_models': len(fit_models), 'ridge_fit_count': len(fitted) * 4,
        'arms': {name: {'selected_alpha': fitted[name]['selected_alpha'], **scores[name]} for name in ARMS},
        'intercept': scores['intercept'], 'random_baseline_spearman': summary([r['spearman'] for r in random_metrics]),
        'random_baseline_recall_at_10': summary([r['recall_at_10'] for r in random_metrics]),
        'permutation_spearman': summary([scores['cptac_permutation_' + str(seed)]['spearman'] for seed in range(20)]),
        'primary_spearman_delta': delta, 'paired_interval': {k: v for k, v in interval.items() if k != 'differences'},
        'decision': decision(delta, interval), 'dependency_values_loaded': True, 'predictor_fit_run': True,
        'model_service_requests': 0, 'scientific_improvement_established': False,
        'claim_scope': 'One frozen retrospective growth-ranking pilot, not all-Pharos superiority, clinical response or the challenge graph-link/pruning benchmark.',
        'limitations': [str(len(test)) + '-gene holdout; bootstrap excludes fit/cohort-selection uncertainty.',
            'CPTAC and Pharos upstream-study independence is unresolved; modern annotations postdate historical outcomes.',
            'Upstream Chronos joint processing is not undone by these grouped splits; tissue-sample groups are not independently verified donors.',
            'Ridge on the frozen feature representation is not a GNN or an agent/pruning accuracy evaluation.',
            'A gain over restricted Pharos alone does not establish graph value beyond the CPTAC-only control.'],
        'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_report(result, passports), encoding='utf-8')
    return result


def gene_passports(genes, ids, target, fitted, edges=()):
    base = fitted['pharos_restricted']; enriched = fitted['pharos_restricted_plus_cptac']
    rank = lambda values: {ids[i]: n + 1 for n, i in enumerate(sorted(range(len(ids)), key=lambda i: (-values[i], gene_key(ids[i]))))}
    a_rank = rank(base['predictions']); b_rank = rank(enriched['predictions']); measured = rank(target)
    result = []
    for i, gid in enumerate(ids):
        gene = genes[gid]; contributions = []
        for arm, row in [('pharos_restricted', base), ('pharos_restricted_plus_cptac', enriched)]:
            terms = [{'feature': k, 'transformed_value': v, 'coefficient': row['model']['coefficients'].get(k, 0),
                      'contribution': v * row['model']['coefficients'].get(k, 0)} for k, v in row['test_vectors'][i].items()]
            if abs(sum(t['contribution'] for t in terms) + row['model']['intercept'] - row['predictions'][i]) > 1e-9:
                raise ValueError('Prediction contributions do not reconcile.')
            largest = sorted(terms, key=lambda t: (-abs(t['contribution']), t['feature']))[:8]
            for term in largest:
                key = term['feature']
                if key.startswith('pathway|'):
                    term['source_evidence'] = [p for p in gene['pathways'] if key == 'pathway|' + p['source'] + '|' + p['stable_id']]
                elif key.startswith('bioplex|'):
                    pair = sorted([gid, key.split('|', 1)[1]])
                    term['source_evidence'] = [edge for edge in edges if edge['genes'] == pair]
                elif key.startswith(('expression|', 'expression_missing|')):
                    term['source_evidence'] = [p for p in gene['numeric_expression'] if key.split('|', 1)[1] == p['source'] + '|' + p['tissue']]
                elif key.startswith('category|'):
                    term['source_evidence'] = [p for p in gene['categorical_expression'] if key.startswith('category|' + p['source'] + '|' + p['tissue'] + '|')]
                elif key.startswith('cptac|'):
                    term['source_evidence'] = {'matrix_row': gene['cptac_matrix_row'], 'measurement_sha256': gene['cptac_measurement_sha256']}
            contributions.append({'arm': arm, 'intercept': row['model']['intercept'], 'largest_absolute_contributions': largest})
        result.append({'hgnc_id': gid, 'symbol': gene['symbol'], 'pharos_rank': a_rank[gid], 'enriched_rank': b_rank[gid],
            'rank_change_up': a_rank[gid] - b_rank[gid], 'measured_rank': measured[gid], 'measured_target': target[i],
            'pharos_prediction': base['predictions'][i], 'enriched_prediction': enriched['predictions'][i],
            'pathway_memberships': len(gene['pathways']), 'bioplex_neighbors': gene['bioplex_neighbors'],
            'cptac_median_reported_log2_ratio': gene['cptac_median_reported_log2_ratio'], 'cptac_matrix_row': gene['cptac_matrix_row'],
            'cptac_measurement_sha256': gene['cptac_measurement_sha256'], 'example_pathway_evidence': gene['pathways'][:4],
            'expression_evidence': gene['numeric_expression'] + gene['categorical_expression'], 'model_contributions': contributions,
            'interpretation': 'Statistical model contributions and rank changes, not causal explanations, clinical target validity or independently verified evidence support.'})
    return sorted(result, key=lambda r: (-abs(r['rank_change_up']), gene_key(r['hgnc_id'])))


def verify_comparison(path):
    path = Path(path); result = json.loads((path / 'metrics.json').read_text())
    expected = {'protocol_metrics.json', 'protocol_specification.json', 'protocol_features.json', 'protocol_partitions.json', 'protocol_references.json',
        'protocol_source_review.json', 'protocol_source_inputs.json', 'experimental_source_manifest.json', 'fit_outcomes.json', 'fitted_models.json', 'sealed_predictions.json',
        'test_access_receipt.json', 'test_outcomes.json', 'scores.json', 'paired_bootstrap.json', 'gene_passports.json'}
    if set(result['files']) != expected or result['result_sha256'] != digest({k: v for k, v in result.items() if k != 'result_sha256'}):
        raise ValueError('Comparison result manifest changed.')
    for name, value in result['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value: raise ValueError('Comparison artifact bytes changed.')
    seal = json.loads((path / 'sealed_predictions.json').read_text()); test = json.loads((path / 'test_outcomes.json').read_text())
    if (seal['seal_sha256'] != digest({k: v for k, v in seal.items() if k != 'seal_sha256'}) or seal['seal_sha256'] != result['prediction_seal_sha256'] or
            seal['protocol_sha256'] != result['protocol_sha256'] or seal['test_values_accessed']): raise ValueError('Pre-test prediction seal changed.')
    if any(sha(path / name) != value for name, value in seal['pre_test_files'].items()): raise ValueError('Pre-test fitting artifacts changed.')
    models = json.loads((path / 'fitted_models.json').read_text())
    for name, row in models.items():
        sealed = seal['predictions'][name]
        if (sealed != {k: row[k] for k in ['test_gene_ids', 'predictions', 'selected_alpha']} or
                predict(row['model'], row['test_vectors']) != row['predictions']): raise ValueError('Model predictions differ from pre-test seal.')
    partitions = json.loads((path / 'protocol_partitions.json').read_text())
    reconstructed_groups = group_outcomes(test['by_model'], [g for g in partitions['models'] if g['split'] == 'test'], test['gene_ids'])
    if reconstructed_groups != test['by_sample_group']: raise ValueError('Sample-group outcomes differ from experimental model values.')
    ids = test['gene_ids']; target = aggregate(test['by_sample_group'], ids)
    if target != test['aggregate']: raise ValueError('Experimental group aggregation differs.')
    scores = {name: metrics(row['predictions'], target, ids, test['by_sample_group']) for name, row in seal['predictions'].items()}
    scores['intercept'] = metrics(seal['intercept'], target, ids, test['by_sample_group'])
    actual = json.loads((path / 'scores.json').read_text())
    if scores != actual['arms_and_permutations'] or [metrics(v, target, ids, test['by_sample_group'], ranking_only=True) for v in seal['random_rankings']] != actual['random_rankings']:
        raise ValueError('Scores do not reproduce from sealed predictions and outcomes.')
    interval = paired_bootstrap(seal['predictions']['pharos_restricted']['predictions'], seal['predictions']['pharos_restricted_plus_cptac']['predictions'], test['by_sample_group'], ids)
    if interval != json.loads((path / 'paired_bootstrap.json').read_text()): raise ValueError('Paired uncertainty does not reproduce.')
    return result


def render_report(result, passports):
    esc = lambda v: escape(str(v), quote=True)
    number = lambda v: 'undefined' if v is None else f'{v:.4f}'
    table = ''.join('<tr><td>' + esc(name) + '</td><td>' + number(row['spearman']) + '</td><td>' + number(row['mae']) + '</td><td>' + number(row['recall_at_10']) + '</td></tr>' for name, row in result['arms'].items())
    genes = ''.join('<tr><td><details><summary>' + esc(g['symbol'] + ' (' + g['hgnc_id'] + ')') + '</summary><pre>' + esc(json.dumps(g, indent=2)) + '</pre></details></td><td>' + str(g['pharos_rank']) + '</td><td>' + str(g['enriched_rank']) + '</td><td>' + str(g['rank_change_up']) + '</td><td>' + str(g['measured_rank']) + '</td></tr>' for g in passports)
    interval = result['paired_interval']
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Frozen growth-ranking comparison</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.6 system-ui;color:#173047}table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #ccd;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:950px}summary{cursor:pointer}.outcome{padding:20px;background:#eef4f6;border-left:5px solid #147c83}</style>'
        '<h1>Does CPTAC improve the frozen Pharos ranking?</h1><div class="outcome"><strong>' + esc(result['decision']['status'].replace('_', ' ')) + '</strong><p>Spearman change: ' + number(result['primary_spearman_delta']) + '; paired 95% interval: [' + number(interval['lower_95']) + ', ' + number(interval['upper_95']) + '].</p></div>'
        '<p>One retrospective pilot on ' + str(result['test_genes']) + ' held-out genes and ' + str(result['test_sample_groups']) + ' tissue-sample groups. All predictions were sealed before reading test outcomes. Higher target means stronger measured growth dependency.</p>'
        '<h2>Identical splits and tuning budgets</h2><table><tr><th>Representation</th><th>Spearman ↑</th><th>Mean absolute error ↓</th><th>Recall@10 ↑</th></tr>' + table + '</table>'
        '<p>CPTAC-only is the control for whether the graph adds information beyond the measurement summary. Correlation is ranking agreement, not a probability or clinical validation.</p>'
        '<p>Experimental outcome: <a href="https://doi.org/10.25452/figshare.plus.27993248.v1">DepMap 24Q4 Public v1</a>. Publisher attribution, source licenses and checksums are retained in the download.</p>'
        '<h2>Controls and uncertainty</h2><pre>' + esc(json.dumps({k: result[k] for k in ['intercept', 'random_baseline_spearman', 'random_baseline_recall_at_10', 'permutation_spearman', 'paired_interval']}, indent=2)) + '</pre>'
        '<h2>Every held-out gene and its evidence</h2><p>Sorted by magnitude of rank change. Positive change means moving up. Open a gene for source locators and model contributions; these are statistical explanations, not causal findings.</p><table><tr><th>Gene / evidence</th><th>Pharos rank</th><th>Enriched rank</th><th>Change up</th><th>Measured rank</th></tr>' + genes + '</table>'
        '<h2>Scope</h2><p>' + esc(result['claim_scope']) + '</p><ul>' + ''.join('<li>' + esc(v) + '</li>' for v in result['limitations']) + '</ul>'
        '<details><summary>Full reproducibility record</summary><pre>' + esc(json.dumps(result, indent=2)) + '</pre></details></html>')
