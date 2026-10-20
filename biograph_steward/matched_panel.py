"""Outcome-blind measured-gene panels and matched, explicit-ID Pharos retrieval."""
from collections import Counter
from copy import deepcopy
import csv
from html import escape
import json
from pathlib import Path
import re

from .client import PharosClient, PharosError, VERSION, LICENSES, digest, utcnow, write_json
from .cohort_mapping import verify_mapping
from .crc_pilot import new_output, sha
from .depmap_audit import verify_audit
from .evaluation import engine_fingerprint
from .graph import UNIPROT
from .retrieval import BATCH_SIZE, retrieve_context

POLICY = 'crc-complete-measurement-hash-panel.v1'
LIMITS = {'pathways': 2000, 'go': 500, 'ppis': 2000, 'drugs': 0, 'expressions': 2000, 'publications': 0}
TISSUE = 'colon rectum'
BLOCKED = re.compile(r'depmap|achilles|chronos|ceres|demeter|harmonizome|\bccle\b|\bctd2\b|project[ -]score|co[- ]dependency|gene[_ -]effect|dependency score|gene essentiality profiles', re.I)


def choose_panel(coverage, mappings, crc_count, size=256):
    if type(size) is not int or not 1 <= size <= 256 or type(crc_count) is not int or crc_count < 1:
        raise ValueError('Use a positive screened-model count and 1–256 genes.')
    by_gene = {r['hgnc_id']: r for r in mappings if r['identifier_eligible']}
    if len(by_gene) != sum(bool(r['identifier_eligible']) for r in mappings):
        raise ValueError('The source cohort has duplicate resolved genes.')
    eligible = []
    for row in coverage:
        if not (row['status'] == 'unique_stable_id_match' and row['protein_context_eligible'] and
                row['crc_observed_models'] == crc_count and row['crc_missing_models'] == 0):
            continue
        gene = by_gene.get(row['hgnc_id'])
        if not gene or gene['ncbi_gene_id'] != row['ncbi_gene_id'] or gene['matrix_row'] != row['cptac_matrix_row']:
            raise ValueError('Coverage and frozen gene mapping identities differ.')
        products = [deepcopy(p) for p in gene['protein_candidates'] if p['status'] == 'reviewed_human_hgnc_match']
        if not products or any(not UNIPROT.fullmatch(p['uniprot_id'].removeprefix('UniProtKB:')) for p in products):
            raise ValueError('Eligible gene lacks verified human protein candidates.')
        eligible.append({'hgnc_id': row['hgnc_id'], 'ncbi_gene_id': row['ncbi_gene_id'],
                         'approved_symbol': row['approved_symbol'], 'cptac_matrix_row': row['cptac_matrix_row'],
                         'depmap_matrix_column': row['matrix_column'], 'depmap_release_label': row['release_label'],
                         'protein_candidates': products, 'measurement_granularity': 'gene',
                         'selection_hash': digest({'policy': POLICY, 'hgnc_id': row['hgnc_id']})})
    if len({r['hgnc_id'] for r in eligible}) != len(eligible) or len(eligible) < size:
        raise ValueError('Insufficient or duplicate eligible genes; no replacement selection.')
    eligible.sort(key=lambda r: (r['selection_hash'], r['hgnc_id']))
    return eligible, deepcopy(eligible[:size])


def prepare_panel(audit, mapping, output, *, size=256):
    audit = Path(audit); mapping = Path(mapping)
    result = verify_audit(audit); mapped = verify_mapping(mapping)
    if result['cohort_mapping_result_sha256'] != mapped['result_sha256']:
        raise ValueError('DepMap and measured-cohort control identities differ.')
    models = json.loads((audit / 'model_inventory.json').read_text())
    crc = [r for r in models if r['selected_crc_model']]
    if not crc or any(not r['screen_provenance_eligible_2d'] or not r['patient_sample_group'] for r in crc):
        raise ValueError('Screened colorectal model/condition or sample-group provenance is unresolved.')
    coverage = json.loads((audit / 'gene_coverage.json').read_text())
    mappings = json.loads((mapping / 'mappings.json').read_text())
    population, members = choose_panel(coverage, mappings, len(crc), size)
    out = new_output(output, audit, mapping)
    write_json(out / 'eligible_population.json', population); write_json(out / 'members.json', members)
    write_json(out / 'crc_models.json', crc)
    with (out / 'members.tsv').open('w', newline='') as f:
        writer = csv.writer(f, delimiter='\t'); writer.writerow(['hgnc_id', 'symbol', 'ncbi_gene_id', 'protein_candidates', 'selection_hash'])
        for row in members:
            writer.writerow([row['hgnc_id'], row['approved_symbol'], row['ncbi_gene_id'], '|'.join(p['uniprot_id'] for p in row['protein_candidates']), row['selection_hash']])
    panel = {'format': 'biograph-steward.matched-gene-panel.v1', 'created_at': utcnow(), 'policy': POLICY,
             'selection_rule': 'Exact first N of eligible genes ordered by SHA-256 of canonical JSON {policy,hgnc_id}; no reseeding, disease-label selection or replacement.',
             'eligibility': 'Uniquely mapped measured gene, reviewed human product context and observed in every selected screened colorectal model.',
             'eligible_genes': len(population), 'selected_genes': size, 'crc_models': len(crc),
             'unique_protein_candidates': len({p['uniprot_id'] for g in members for p in g['protein_candidates']}),
             'depmap_audit_sha256': result['result_sha256'], 'depmap_source_sha256': result['source_sha256'],
             'cohort_mapping_result_sha256': mapped['result_sha256'], 'registry_sha256': mapped['registry_sha256'],
             'retrieval_contract': {'limits': LIMITS, 'tissue_words': TISSUE, 'ppi_confidence': 400,
                                    'source_query': 'Explicit UniProt IDs, no disease filter or disease association fields.',
                                    'row_budget_rule': 'Sum of all per-protein caps × requested unique proteins; sufficient reservation for identical caps on every protein.'},
             'outcomes_loaded': False, 'scoring_protocol_frozen': False,
             'selection_scope_note': 'Complete-measurement subset of this historical CPTAC/DepMap intersection; not a random sample of all human genes.',
             'files': {name: sha(out / name) for name in ['eligible_population.json', 'members.json', 'members.tsv', 'crc_models.json']}}
    panel['panel_sha256'] = digest(panel); write_json(out / 'panel.json', panel)
    return panel


def load_panel(path):
    path = Path(path); panel = json.loads((path / 'panel.json').read_text())
    expected = {'eligible_population.json', 'members.json', 'members.tsv', 'crc_models.json'}
    if panel['panel_sha256'] != digest({k: v for k, v in panel.items() if k != 'panel_sha256'}) or set(panel['files']) != expected:
        raise ValueError('Panel manifest changed.')
    if (panel['policy'] != POLICY or panel['retrieval_contract']['limits'] != LIMITS or
            panel['retrieval_contract']['tissue_words'] != TISSUE or panel['outcomes_loaded'] is not False or
            not 1 <= panel['selected_genes'] <= 256):
        raise ValueError('Panel protocol differs from the frozen outcome-blind contract.')
    for name, value in panel['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('Frozen panel artifact changed.')
    population = json.loads((path / 'eligible_population.json').read_text()); members = json.loads((path / 'members.json').read_text())
    if (len(population) != panel['eligible_genes'] or len(members) != panel['selected_genes'] or
            len({r['hgnc_id'] for r in population}) != len(population) or population[:len(members)] != members or
            sorted(population, key=lambda r: (r['selection_hash'], r['hgnc_id'])) != population or
            any(r['selection_hash'] != digest({'policy': POLICY, 'hgnc_id': r['hgnc_id']}) for r in population)):
        raise ValueError('Panel membership does not reproduce from the fixed hash rule.')
    return panel, members


def identity_query(ids):
    definitions = ', '.join(f'$id{i}: String!' for i in range(len(ids)))
    fields = ' '.join(f't{i}: target(q: {{uniprot: $id{i}}}) {{ uniprot sym name }}' for i in range(len(ids)))
    return f'query ExplicitPanelTargets({definitions}) {{ {fields} }}', {f'id{i}': uid for i, uid in enumerate(ids)}


def feature_view(members, targets):
    """A source-whitelisted provisional view; raw inventories never become features."""
    by_id = {t['uniprot']: (i, t) for i, t in enumerate(targets)}; genes = []; exclusions = []
    for member in members:
        features = []
        for product in member['protein_candidates']:
            uid = product['uniprot_id'].removeprefix('UniProtKB:'); match = by_id.get(uid)
            if not match:
                continue
            target_index, target = match
            for family in ['pathways', 'go', 'ppis', 'expressions']:
                records = target['pathways'] if family == 'pathways' else target['pharos_context'][family]
                for index, record in enumerate(records):
                    locator = f'snapshot.json#/targets/{target_index}/' + ('pathways/' if family == 'pathways' else 'pharos_context/' + family + '/') + str(index)
                    reason = None
                    if product['shared_across_genes']:
                        reason = 'shared_product_gene_specificity_unresolved'
                    elif BLOCKED.search(json.dumps(record, sort_keys=True)):
                        reason = 'dependency_or_unresolved_cell_model_source'
                    elif family == 'pathways' and record.get('type') not in {'Reactome', 'WikiPathways'}:
                        reason = 'pathway_source_not_in_provisional_allowlist'
                    elif family == 'ppis' and record.get('type') not in {'BioPlex', 'Reactome'}:
                        reason = 'integrated_interaction_source_requires_channel_review'
                    elif family == 'go' and record.get('assigned_by') not in {'UniProt', 'UniProtKB', 'Reactome', 'Ensembl', 'GO_Central'}:
                        reason = 'go_assigning_source_not_in_provisional_allowlist'
                    elif family == 'expressions' and record.get('type') not in {'GTEx', 'HPA RNA', 'HPA Protein', 'HPM Protein', 'JensenLab TISSUES'}:
                        reason = 'expression_source_not_in_provisional_allowlist'
                    if reason:
                        exclusions.append({'hgnc_id': member['hgnc_id'], 'protein_id': product['uniprot_id'],
                                           'family': family, 'source_locator': locator, 'record_sha256': digest(record), 'reason': reason})
                        continue
                    keep = {'pathways': ['sourceID', 'type', 'name'], 'go': ['goid', 'type', 'evidence', 'goeco', 'assigned_by'],
                            'ppis': ['type', 'target'], 'expressions': ['expid', 'type', 'tissue', 'value', 'qual', 'btoid', 'uberon', 'pub']}[family]
                    projected = {key: deepcopy(record.get(key)) for key in keep}
                    if family == 'ppis':
                        projected['target'] = {key: record.get('target', {}).get(key) for key in ['uniprot', 'sym']}
                    features.append({'family': family, 'protein_id': product['uniprot_id'], 'source_locator': locator,
                                     'record_sha256': digest(record), 'record': projected,
                                     'status': 'provisional_source_policy_candidate'})
        genes.append({'hgnc_id': member['hgnc_id'], 'symbol': member['approved_symbol'], 'measurement_granularity': 'gene',
                      'protein_candidates': [p['uniprot_id'] for p in member['protein_candidates']], 'features': features})
    return genes, exclusions


def retrieve_panel(panel_path, output, *, client=None, progress=None):
    panel_path = Path(panel_path); panel, members = load_panel(panel_path)
    return retrieve_explicit_panel(panel_path, output, panel, members, client=client, progress=progress)


def retrieve_explicit_panel(panel_path, output, panel, members, *, client=None, progress=None):
    """Shared transport after a caller verifies its own immutable panel contract."""
    panel_path = Path(panel_path)
    out = new_output(output, panel_path)
    client = client or PharosClient(cache_dir=Path('.pharos_cache') / ('matched_' + panel['panel_sha256']), retries=0)
    start = len(client.records); ids = sorted({p['uniprot_id'].removeprefix('UniProtKB:') for g in members for p in g['protein_candidates']})
    if any(not UNIPROT.fullmatch(uid) for uid in ids):
        raise ValueError('Malformed panel protein identity.')
    before = client.execute(VERSION, cache=False).get('dbVersion')
    if not isinstance(before, str) or not before:
        raise PharosError('Pharos version identity is unavailable.')
    targets = []; resolution = []
    for offset in range(0, len(ids), BATCH_SIZE):
        batch = ids[offset:offset + BATCH_SIZE]; request_index = len(client.records) - start
        data = client.execute(*identity_query(batch))
        for i, uid in enumerate(batch):
            row = data.get(f't{i}')
            if f't{i}' not in data or (row is not None and not isinstance(row, dict)):
                raise PharosError('Malformed explicit-ID resolution response.')
            status = 'not_found' if row is None else ('resolved' if row.get('uniprot') == uid else 'identity_mismatch')
            resolution.append({'requested_uniprot': uid, 'status': status, 'returned': deepcopy(row),
                               'request_index': request_index, 'response_pointer': '/data/t' + str(i)})
            if status == 'resolved':
                targets.append(deepcopy(row))
        if progress:
            progress(f'Explicit identities: {min(offset + BATCH_SIZE, len(ids))}/{len(ids)} proteins')
    limits = panel['retrieval_contract']['limits']; row_budget = sum(limits.values()) * len(ids)
    coverage = retrieve_context(client, targets, limits, panel['retrieval_contract']['tissue_words'], progress, row_budget=row_budget) if targets else None
    if coverage:
        for row in coverage['targets']:
            for page in row['pages']:
                page['request_index'] -= start
    licenses = client.execute(LICENSES).get('dataSourceCounts')
    if not isinstance(licenses, list):
        raise PharosError('Source-license catalogue unavailable.')
    after = client.execute(VERSION, cache=False).get('dbVersion')
    snapshot = {'format': 'biograph-steward.explicit-pharos-panel.v1', 'created_at': utcnow(), 'panel_sha256': panel['panel_sha256'],
                'endpoint': client.endpoint, 'db_version_before': before, 'db_version_after': after,
                'target_resolution': resolution, 'targets': targets, 'retrieval_coverage': coverage,
                'source_licenses': licenses, 'requests': deepcopy(client.records[start:]),
                'disease_filter_used': False, 'outcome_values_loaded': False,
                'transport_kind': 'injected_test' if client.transport else 'http'}
    snapshot['snapshot_sha256'] = digest(snapshot); write_json(out / 'snapshot.json', snapshot)
    genes, exclusions = feature_view(members, targets)
    write_json(out / 'feature_candidates.json', genes); write_json(out / 'feature_exclusions.json', exclusions)
    write_json(out / 'panel.json', panel); write_json(out / 'members.json', members)
    write_json(out / 'retrieval_coverage.json', coverage)
    statuses = Counter(r['status'] for r in resolution)
    gene_status = []
    resolution_map = {r['requested_uniprot']: r['status'] for r in resolution}
    for row in genes:
        gene_status.append({'hgnc_id': row['hgnc_id'], 'symbol': row['symbol'],
                            'resolved_products': sum(resolution_map[p.removeprefix('UniProtKB:')] == 'resolved' for p in row['protein_candidates']),
                            'requested_products': len(row['protein_candidates']),
                            'provisional_features_by_family': dict(sorted(Counter(r['family'] for r in row['features']).items()))})
    write_json(out / 'gene_coverage.json', gene_status)
    policy = {'status': 'provisional_source_policy_view_not_scoring_approval', 'limits': limits,
              'excluded_from_predictor_view': ['All raw metadata, source-presence/count fields, target names/descriptions/TDL, disease annotations, drug and publication discovery fields.',
                                                'Dependency/fitness/co-dependency sources and unresolved Harmonizome/CCLE/CTD2 summaries.',
                                                'Integrated STRING/other PPI sources pending source-channel review; PPI score properties are never features.',
                                                'Shared protein products without gene-specific attribution; sources outside the explicit allowlists.'],
              'provisional_allowlists': {'pathways': ['Reactome', 'WikiPathways'], 'ppis': ['BioPlex', 'Reactome'],
                  'go_assigned_by': ['UniProt', 'UniProtKB', 'Reactome', 'Ensembl', 'GO_Central'],
                  'expressions': ['GTEx', 'HPA RNA', 'HPA Protein', 'HPM Protein', 'JensenLab TISSUES']},
              'limits_of_audit': ['A name/field allowlist does not establish independent underlying studies. Remaining upstream provenance review is required before scoring.',
                                  'Source-scale expression observations are preserved without imputation or cross-source aggregation.',
                                  'Multiple products and reciprocal records remain separate source views, not independent gene measurements or additive scores.',
                                  'Missing targets and capped families are not zeros or negative biology. No replacement genes are selected.',
                                  'The retrieved protein annotations are general context, not colorectal-specific associations.']}
    write_json(out / 'feature_policy.json', policy)
    result = {'format': 'biograph-steward.matched-pharos-panel-result.v1', 'created_at': utcnow(),
              'panel_sha256': panel['panel_sha256'], 'source_snapshot_sha256': snapshot['snapshot_sha256'],
              'engine_files': engine_fingerprint(), 'eligible_population': panel['eligible_genes'], 'selected_genes': len(members),
              'requested_proteins': len(ids), 'target_resolution_counts': dict(sorted(statuses.items())),
              'genes_with_any_resolved_product': sum(r['resolved_products'] > 0 for r in gene_status),
              'genes_with_all_products_resolved': sum(r['resolved_products'] == r['requested_products'] for r in gene_status),
              'genes_with_any_provisional_features': sum(bool(r['provisional_features_by_family']) for r in gene_status),
              'provisional_feature_counts': dict(sorted(Counter(f['family'] for g in genes for f in g['features']).items())),
              'excluded_feature_counts': dict(sorted(Counter(r['reason'] for r in exclusions).items())),
              'retrieval': coverage['summary'] if coverage else {}, 'db_version_before': before, 'db_version_after': after,
              'version_consistent': before == after, 'successful_source_envelopes': len(snapshot['requests']),
              'cached_source_envelopes': sum(r.get('loaded_from_cache', False) for r in snapshot['requests']),
              'outcome_values_loaded': False, 'disease_filter_used': False, 'model_requests': 0, 'scoring_run': False,
              'ready_for_prediction_comparison': False, 'scientific_improvement_established': False,
              'remaining_requirements': ['Review source provenance and provisional feature definitions, including missing/capped cases.',
                                         'Freeze gene-level aggregation/deduplication, endpoint, ranking rule, simple baselines and tissue-sample partitions before examining dependency values.'],
              'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_report(result, gene_status), encoding='utf-8')
    return result


def verify_retrieval(path):
    path = Path(path); result = json.loads((path / 'metrics.json').read_text())
    expected = {'snapshot.json', 'feature_candidates.json', 'feature_exclusions.json', 'panel.json', 'members.json',
                'retrieval_coverage.json', 'gene_coverage.json', 'feature_policy.json'}
    if result['result_sha256'] != digest({k: v for k, v in result.items() if k != 'result_sha256'}) or set(result['files']) != expected:
        raise ValueError('Matched retrieval manifest changed.')
    for name, value in result['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('Matched retrieval bytes changed.')
    snapshot = json.loads((path / 'snapshot.json').read_text()); members = json.loads((path / 'members.json').read_text())
    panel = json.loads((path / 'panel.json').read_text())
    if (panel['panel_sha256'] != digest({k: v for k, v in panel.items() if k != 'panel_sha256'}) or
            panel['panel_sha256'] != result['panel_sha256'] or panel['files']['members.json'] != sha(path / 'members.json')):
        raise ValueError('Copied panel identity or membership changed.')
    if (snapshot['snapshot_sha256'] != digest({k: v for k, v in snapshot.items() if k != 'snapshot_sha256'}) or
            snapshot['snapshot_sha256'] != result['source_snapshot_sha256'] or snapshot['panel_sha256'] != result['panel_sha256']):
        raise ValueError('Explicit-ID source snapshot identity changed.')
    for request in snapshot['requests']:
        if digest(request['response']) != request['response_sha256']:
            raise ValueError('Raw Pharos source response changed.')
    requested = {p['uniprot_id'].removeprefix('UniProtKB:') for g in members for p in g['protein_candidates']}
    resolution = snapshot['target_resolution']
    if len(resolution) != len(requested) or {r['requested_uniprot'] for r in resolution} != requested:
        raise ValueError('Explicit-ID resolution does not account for every requested product.')
    for row in resolution:
        request = snapshot['requests'][row['request_index']]
        alias = row['response_pointer'].removeprefix('/data/')
        raw = request['response']['data'][alias]
        status = 'not_found' if raw is None else ('resolved' if raw.get('uniprot') == row['requested_uniprot'] else 'identity_mismatch')
        if ('ExplicitPanelTargets' not in request['request']['query'] or raw != row['returned'] or status != row['status'] or
                request['request']['variables']['id' + alias.removeprefix('t')] != row['requested_uniprot']):
            raise ValueError('Explicit-ID resolution does not reproduce from raw response.')
    if ({t['uniprot'] for t in snapshot['targets']} != {r['requested_uniprot'] for r in resolution if r['status'] == 'resolved'} or
            len({t['uniprot'] for t in snapshot['targets']}) != len(snapshot['targets'])):
        raise ValueError('Retrieved products differ from resolved fixed-panel products.')
    expected_genes, expected_exclusions = feature_view(members, snapshot['targets'])
    if (expected_genes != json.loads((path / 'feature_candidates.json').read_text()) or
            expected_exclusions != json.loads((path / 'feature_exclusions.json').read_text())):
        raise ValueError('Provisional feature view does not reproduce from raw records.')
    if len(members) != result['selected_genes'] or len({g['hgnc_id'] for g in members}) != len(members):
        raise ValueError('Fixed gene population changed.')
    return result


def render_report(result, genes):
    esc = lambda x: escape(str(x), quote=True)
    rows = ''.join('<tr><td>' + esc(r['symbol']) + '</td><td>' + esc(r['hgnc_id']) + '</td><td>' + esc(str(r['resolved_products']) + '/' + str(r['requested_products'])) + '</td><td>' + esc(r['provisional_features_by_family']) + '</td></tr>' for r in genes)
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Matched Pharos gene panel</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{border:1px solid #ccd;padding:8px;text-align:left}table{border-collapse:collapse;width:100%}</style>'
            '<h1>Matched Pharos gene panel</h1><p><strong>Fixed hash-selected measured genes. No dependency values, disease-based selection, model inference or biological ranking.</strong></p>'
            '<p>Raw annotations and the provisional source-policy view are distinct. Exclusions and missing coverage remain visible. Underlying-source independence and scoring readiness are not established.</p>'
            '<h2>Coverage and provenance</h2><pre>' + esc(json.dumps(result, indent=2)) + '</pre>'
            '<h2>Every selected gene</h2><table><tr><th>Gene</th><th>Stable ID</th><th>Resolved products</th><th>Provisional feature records</th></tr>' + rows + '</table></html>')
