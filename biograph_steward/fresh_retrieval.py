"""Verified development/reserve union and common-scope Pharos retrieval; no outcomes."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import re

from .client import PharosClient, digest, utcnow, write_json
from .comparison_protocol import partitions
from .crc_pilot import new_output, sha
from .evaluation import engine_fingerprint
from .growth_comparison import gene_key, split_ids
from .growth_diagnostics import select_reserve, verify_diagnostics, verify_reserve
from .matched_panel import load_panel, retrieve_explicit_panel, verify_retrieval, TISSUE
from .retrieval import MAX_LIMITS, reported_count

POLICY = 'crc-reserved-growth-comparison.v1'
LIMITS = {name: MAX_LIMITS[name] if name in {'pathways', 'go', 'ppis', 'expressions'} else 0 for name in MAX_LIMITS}
COHORT_FILES = {'eligible_population.json', 'members.json', 'crc_models.json', 'partitions.json', 'prior_panel.json',
    'reservation_metrics.json', 'diagnostic_metrics.json', 'prior_exposure.json', 'prior_model_partitions.json'}


def read(path, name):
    return json.loads((Path(path) / name).read_text())


def manifest(path, filename='metrics.json', key='result_sha256', expected=None):
    path = Path(path); r = read(path, filename)
    if r[key] != digest({k: v for k, v in r.items() if k != key}) or (expected is not None and set(r['files']) != set(expected)):
        raise ValueError('Fresh comparison manifest changed.')
    for name, value in r['files'].items():
        if Path(name).name != name or (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('Fresh comparison artifact changed.')
    return r


def union_partitions(members, models, exposure, old_models):
    train = set(exposure['fit_gene_ids']); validation = set(exposure['exposed_test_gene_ids'])
    if train & validation: raise ValueError('Development gene roles overlap.')
    all_ids = {g['hgnc_id'] for g in members}
    if not train or not validation or not (train | validation) < all_ids: raise ValueError('Missing development or reserved genes.')
    grouped = partitions(members, models)
    for row in grouped['genes']:
        roles = {'train' if gid in train else ('validation' if gid in validation else 'test') for gid in row['hgnc_ids']}
        if len(roles) != 1: raise ValueError('Reviewed protein component crosses development/reserve roles.')
        row['split'] = roles.pop(); row['hash'] = digest({'policy': POLICY, 'axis': 'genes', 'group': row['group']})
    old = [g for g in members if g['hgnc_id'] in train | validation]
    original = partitions(old, models)
    if (set(split_ids(original, 'genes', {'train', 'validation'})) != train or
            set(split_ids(original, 'genes', {'test'})) != validation or original['models'] != old_models):
        raise ValueError('Original grouped roles do not reproduce.')
    grouped['models'] = deepcopy(old_models)
    return grouped


def prepare_union(panel_path, reservation_path, diagnostics_path, output):
    panel_path = Path(panel_path); reservation_path = Path(reservation_path); diagnostics_path = Path(diagnostics_path)
    old, members = load_panel(panel_path); reserve = verify_reserve(reservation_path); diagnostic = verify_diagnostics(diagnostics_path)
    if (reserve['previous_panel_sha256'] != old['panel_sha256'] or reserve['parent_result_sha256'] != diagnostic['parent_result_sha256'] or
            reserve['depmap_source_sha256'] != old['depmap_source_sha256']): raise ValueError('Development/reservation sources differ.')
    exposed = read(reservation_path, 'prior_exposure.json'); reserved = read(reservation_path, 'reserved_members.json')
    population = read(panel_path, 'eligible_population.json'); models = read(panel_path, 'crc_models.json')
    combined = members + reserved; old_models = read(reservation_path, 'model_partitions.json')
    grouped = union_partitions(combined, models, exposed, old_models)
    out = new_output(output, panel_path, reservation_path, diagnostics_path)
    values = {'eligible_population.json': population, 'members.json': combined, 'crc_models.json': models, 'partitions.json': grouped,
        'prior_panel.json': old, 'reservation_metrics.json': reserve, 'diagnostic_metrics.json': diagnostic,
        'prior_exposure.json': exposed, 'prior_model_partitions.json': old_models}
    for name, value in values.items(): write_json(out / name, value)
    result = {'format': 'biograph-steward.fresh-union-panel.v1', 'created_at': utcnow(), 'policy': POLICY,
        'eligible_genes': old['eligible_genes'], 'selected_genes': len(combined), 'development_genes': len(members), 'reserved_genes': len(reserved),
        'requested_proteins': len({p['uniprot_id'] for g in combined for p in g['protein_candidates']}),
        'previous_panel_sha256': old['panel_sha256'], 'reservation_result_sha256': reserve['result_sha256'],
        'diagnostic_result_sha256': diagnostic['result_sha256'], 'previous_result_sha256': reserve['parent_result_sha256'],
        'cohort_mapping_result_sha256': old['cohort_mapping_result_sha256'], 'depmap_source_sha256': old['depmap_source_sha256'],
        'engine_files': engine_fingerprint(), 'retrieval_contract': {'limits': LIMITS, 'tissue_words': TISSUE, 'ppi_confidence': 400,
            'source_query': 'Explicit IDs over the development + reserved union; no disease filter; retain PPI partners in this same full resolved union.',
            'completeness': 'Every requested family must reconcile to complete, with one database version before/after; no replacement genes.',
            'freshness': 'Refresh all HTTP requests in a unique cohort cache; no older snapshot mixing.'},
        'development_roles': 'Previous train+validation genes become training; previous test genes become development validation. All are already exposed genes. Reserved genes alone are final test.',
        'sample_roles': 'Preserve all original recorded sample-group assignments; these are not new laboratory cohorts.',
        'fresh_dependency_values_loaded': False, 'files': {name: sha(out / name) for name in sorted(values)}}
    result['panel_sha256'] = digest(result); write_json(out / 'panel.json', result)
    (out / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Full-cohort Pharos scope</title><h1>Full-cohort Pharos scope</h1><p>No reserved outcomes loaded.</p><pre>' + escape(json.dumps(result, indent=2)) + '</pre></html>', encoding='utf-8')
    return result


def load_union(path):
    path = Path(path); r = manifest(path, 'panel.json', 'panel_sha256', COHORT_FILES)
    if r['policy'] != POLICY or r['fresh_dependency_values_loaded'] or r['retrieval_contract']['limits'] != LIMITS or r['retrieval_contract']['tissue_words'] != TISSUE:
        raise ValueError('Union source contract changed.')
    old = read(path, 'prior_panel.json'); reserve = read(path, 'reservation_metrics.json'); diagnostic = read(path, 'diagnostic_metrics.json')
    for record, key in [(old, 'panel_sha256'), (reserve, 'result_sha256'), (diagnostic, 'result_sha256')]:
        if record[key] != digest({k: v for k, v in record.items() if k != key}): raise ValueError('Union parent manifest changed.')
    if (old['panel_sha256'] != r['previous_panel_sha256'] or old['files']['eligible_population.json'] != sha(path / 'eligible_population.json') or
            old['files']['crc_models.json'] != sha(path / 'crc_models.json') or reserve['result_sha256'] != r['reservation_result_sha256'] or
            diagnostic['result_sha256'] != r['diagnostic_result_sha256'] or reserve['parent_result_sha256'] != diagnostic['parent_result_sha256'] or
            reserve['previous_panel_sha256'] != old['panel_sha256'] or old['depmap_source_sha256'] != r['depmap_source_sha256'] or
            diagnostic['parent_result_sha256'] != r['previous_result_sha256'] or
            old['cohort_mapping_result_sha256'] != r['cohort_mapping_result_sha256']): raise ValueError('Union source bindings differ.')
    for name, original in [('prior_exposure.json', 'prior_exposure.json'), ('prior_model_partitions.json', 'model_partitions.json')]:
        if reserve['files'][original] != sha(path / name): raise ValueError('Union exposure or model roles changed.')
    exposure = read(path, 'prior_exposure.json'); population = read(path, 'eligible_population.json')
    old_members = population[:old['selected_genes']]
    used = set(exposure['fit_gene_ids']) | set(exposure['exposed_test_gene_ids'])
    if used != {g['hgnc_id'] for g in old_members}: raise ValueError('Exposure inventory differs from original selected genes.')
    reserved, _, _ = select_reserve(population, used, reserve['requested_reserve_genes'])
    members = read(path, 'members.json')
    if (members != old_members + reserved or len(members) != r['selected_genes'] or len(reserved) != r['reserved_genes'] or
            len(old_members) != r['development_genes'] or len({p['uniprot_id'] for g in members for p in g['protein_candidates']}) != r['requested_proteins']):
        raise ValueError('Union membership does not reproduce.')
    if union_partitions(members, read(path, 'crc_models.json'), exposure, read(path, 'prior_model_partitions.json')) != read(path, 'partitions.json'):
        raise ValueError('Union grouped partitions changed.')
    return r, members


def retrieve_union(cohort, output, *, client=None, progress=None):
    panel, members = load_union(cohort)
    client = client or PharosClient(cache_dir=Path('.pharos_cache') / ('fresh_union_' + panel['panel_sha256']), refresh=True, retries=2)
    result = retrieve_explicit_panel(cohort, output, panel, members, client=client, progress=progress)
    verify_union_retrieval(output)
    return result


def verify_union_retrieval(path):
    """Reconstruct every scoped family from the retained raw source envelopes."""
    path = Path(path); r = verify_retrieval(path); panel = read(path, 'panel.json'); source = read(path, 'snapshot.json')
    if (panel['policy'] != POLICY or panel['retrieval_contract']['limits'] != LIMITS or not r['version_consistent'] or
            r['db_version_before'] != r['db_version_after'] or r['outcome_values_loaded'] or r['disease_filter_used'] or
            (source['transport_kind'] == 'http' and r['cached_source_envelopes'])):
        raise ValueError('Union retrieval scope or version is inconsistent.')
    targets = {t['uniprot']: t for t in source['targets']}; cohort = set(targets)
    coverage = source['retrieval_coverage']
    if not coverage or set(coverage['scope']['seed_uniprots']) != cohort or coverage['limits_per_target'] != LIMITS:
        raise ValueError('Interaction partner scope differs from the full resolved cohort.')
    seen = set()
    for row in coverage['targets']:
        family = row['family']
        if family not in {'pathways', 'go', 'ppis', 'expressions'}: continue
        key = (row['uniprot'], family)
        if key in seen or row['status'] != 'complete' or row['issues']: raise ValueError('Resolve capped/inconsistent family coverage before scoring.')
        seen.add(key); raw = []
        for page in row['pages']:
            request = source['requests'][page['request_index']]; alias = page['response_pointer'].split('/')[2]; index = alias.removeprefix('t')
            record = request['response']['data'][alias]; variables = request['request']['variables']
            if (f'Scoped_{family}(' not in request['request']['query'] or record['uniprot'] != row['uniprot'] or
                    variables['id' + index] != row['uniprot'] or variables['skip' + index] != page['skip'] or
                    variables['top' + index] != page['requested'] or len(record['rows']) != page['returned'] or
                    reported_count(record['reported'], family) != row['available']): raise ValueError('Union page does not match raw source envelope.')
            raw.extend(record['rows'])
        retained = raw
        if family == 'ppis': retained = [p for p in raw if p['target']['uniprot'] in cohort]
        if family == 'expressions': retained = [p for p in raw if any(re.search(r'\b' + re.escape(w) + r'\b', p['tissue'], re.I) for w in TISSUE.split())]
        actual = targets[row['uniprot']]['pathways'] if family == 'pathways' else targets[row['uniprot']]['pharos_context'][family]
        if (actual != retained or len(raw) != row['retrieved'] or len(raw) != row['available'] or
                len(retained) != row['retained']): raise ValueError('Scoped rows do not reproduce from complete source pages.')
    if seen != {(uid, family) for uid in cohort for family in ['pathways', 'go', 'ppis', 'expressions']}:
        raise ValueError('A resolved product lacks complete family accounting.')
    return r
