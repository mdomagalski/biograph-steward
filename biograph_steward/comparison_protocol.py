"""Freeze source-reviewed features and evaluation rules without opening CRISPR values."""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import statistics

from .client import digest, utcnow, write_json
from .cohort_mapping import verify_mapping
from .crc_pilot import new_output, sha
from .evaluation import engine_fingerprint
from .matched_panel import BLOCKED, load_panel, verify_retrieval

POLICY = 'matched-crc-growth-comparison.v1'
REFERENCES = {
    'pharos_implementation': 'https://github.com/ncats/pharos-graphql-server/blob/master/src/TCRD.js',
    'pharos_schema': 'https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql',
    'bioplex': 'https://bioplex.hms.harvard.edu/explorer/help',
    'bioplex_releases': 'https://bioplex.hms.harvard.edu/interactions.php',
    'go_evidence': 'https://geneontology.org/docs/guide-go-evidence-codes/',
    'hpa': 'https://www.proteinatlas.org/about/help',
    'cptac': 'https://linkedomics.org/data_download/CPTAC-COAD/',
    'chronos': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC8686573/'}


def specification():
    """Rules are fixed here, not inferred from observed labels or comparative scores."""
    return {
        'policy': POLICY, 'status': 'frozen_before_dependency_value_access',
        'question': 'Does adding the frozen CPTAC tumor/normal ratio summary improve ranking of growth dependencies in held-out colorectal cell models and genes?',
        'claim_scope': 'Retrospective feature-enrichment pilot on this measured-gene panel, not a comparison with all of Pharos, CRC selectivity, clinical response, prospective validation or causal target discovery.',
        'arms': ['pharos_restricted', 'pharos_restricted_plus_cptac'],
        'endpoint': {'source': 'Pinned DepMap 24Q4 v1 CRISPRGeneEffect.csv; no common-essential label list.',
            'direction': 'Higher target = stronger growth dependency: negate the processed gene-effect value.',
            'aggregation': 'For each gene and partition, median over model values within each PatientID/tissue-sample group, then median over groups. Groups have equal weight.',
            'missing': 'Fail if any selected value is missing/nonfinite or identities differ from frozen complete-measurement eligibility. Do not drop genes/models, impute outcomes or reinterpret absence as nondependency.',
            'no_binary_labels': True, 'no_other_lineages': True},
        'partition': {'rule': 'Group identities sorted by SHA-256 of canonical JSON {policy,axis,group}; first floor(0.6*N) train, next floor(0.2*N) validation, remainder test. No reseeding.',
            'genes': 'Connected components of genes sharing any requested protein accession; one HGNC gene is one outcome unit.',
            'models': 'All models sharing PatientID/tissue-sample group stay together, regardless of screen/library count.',
            'training': 'Train genes × train model groups only.',
            'validation': 'Validation genes × validation model groups only; select alpha separately per arm with identical budget.',
            'final_fit': 'Refit selected alpha on train+validation genes × train+validation model groups, rebuilding all preprocessing there.',
            'test': 'Test genes × test model groups, once after selection. Other matrix blocks remain unused.'},
        'features': {'shared': ['Binary Reactome stable-ID membership', 'Binary WikiPathways stable-ID membership',
                              'Binary BioPlex-component gene adjacency, p_int >= 0.75',
                              'HPM Protein and HPA RNA observations by exact source/tissue label',
                              'HPA Protein category sets by exact tissue/cell-type label'],
            'enrichment': 'One gene-level median of available source-reported CPTAC log2 tumor/normal ratios across the 96 frozen columns; no assumption that larger ratios imply stronger dependency.',
            'identity': 'HGNC/UniProt/symbols and source locators are join/provenance keys, not raw scalar/categorical predictor columns.',
            'deduplication': 'Union memberships across verified products; strip only Reactome version suffix and WikiPathways _r revision suffix. Keep source namespaces distinct. One undirected BioPlex gene pair, no self edges, all supporting records retained. Exact repeated expression observations collapse; numeric values use median of distinct source/tissue/value observations, categories use sets.',
            'withheld': ['All GO: study references and qualifiers unavailable in retrieved schema.',
                         'STRING-only and Reactome-only/combined PPI contributions without a qualifying BioPlex p_int component.',
                         'JensenLab TISSUES integrated scores; other non-whitelisted expressions.',
                         'Dependency/fitness/co-dependency and unresolved Harmonizome/CCLE/CTD2 content.',
                         'Raw metadata, names/text, disease labels, source-presence/publication/annotation counts, TDL, QC, non-BioPlex PPI scores and CPTAC missing/observation counts.',
                         'CIViC therapy-response evidence and shared products with unresolved gene attribution.']},
        'preprocessing': {'fit_scope': 'Current fit genes only; never fit vocabularies, imputation or scaling on validation/test genes.',
            'pathways': 'Separate Reactome and WikiPathways blocks; binary training-vocabulary incidence; L2-normalize each nonempty gene row. Unknown memberships do not create new columns.',
            'bioplex': 'Binary adjacency columns are current fit genes only; undirected edges, no self loops; L2-normalize each nonempty gene row. No label propagation from held-out genes.',
            'numeric_expression': 'Per exact source/tissue column apply log1p to finite nonnegative values, fit observed-value median imputation and population-mean/std scaling on fit genes; append missing indicator. All-unobserved fit columns omitted; constant std replaced by 1. Scale the combined block by 1/sqrt(its retained column count).',
            'categorical_expression': 'Multi-hot category set over fit-observed exact tissue/category keys; a separate unobserved category for each fit-observed tissue. Not detected is an observed assay category, not missing. L2-normalize each nonempty gene row.',
            'cptac': 'Signed log2-ratio median, no log1p. Fit-gene observed median imputation and population-mean/std scaling; append missing indicator. Omit if no fit observations; constant std replaced by 1.',
            'block_weights': 'All five Pharos blocks and the optional CPTAC block have weight 1; no label-dependent weights or feature selection.'},
        'model': {'kind': 'Ridge regression, unpenalized intercept; objective mean squared error + alpha * squared L2 coefficient norm.',
            'alpha_grid': [0.1, 1.0, 10.0], 'selection': 'Largest validation Spearman; undefined ranks below defined. Exact ties or all undefined choose largest alpha. No additional search.',
            'ranking': 'Descending prediction, HGNC numeric ID ascending for deterministic displayed ties; Spearman uses average ranks, never tie-broken ranks.'},
        'baselines': {'intercept': 'Mean training target, no predictive ordering; Spearman undefined for constant predictions.',
            'random': '100 descending deterministic hash rankings using {policy,seed,hgnc_id}, seeds 0..99; summarize distribution, not independent datasets.',
            'coverage_only': 'Same ridge budget, using log1p distinct Reactome membership count, WikiPathways membership count and BioPlex degree plus missing-indicator-only expression features; fit population-mean/std scaling on fit genes (constant std=1). No source/publication metadata counts.',
            'cptac_only': 'Same ridge budget and transforms, using only the CPTAC summary and missing indicator.',
            'negative_control': '20 CPTAC permutations, seeds 0..19; within each original gene partition, destinations sorted by HGNC numeric ID receive (value,missing) pairs from donors sorted by SHA-256 of {policy,seed,hgnc_id}. Keep this mapping at final refit; same budgets. Descriptive null, not new biological samples.'},
        'metrics': {'primary': 'Spearman correlation across test genes between predictions and the group-balanced aggregate test target; delta = enriched minus restricted Pharos.',
            'secondary': ['Mean absolute error', 'Per-test-sample-group Spearman', 'Recall@10 of the ten highest aggregate dependencies within the test gene set; raw overlap/10, HGNC numeric tie-break, descriptive only'],
            'undefined': 'Return null with reason for constant/insufficient vectors; never silently substitute zero.',
            'uncertainty': '2,000 paired two-axis bootstrap replicates: resample test sample groups and test genes with replacement using Random(20261020); recompute aggregate endpoints and both correlations on the same draws. Fixed trained predictors; no refit. Percentile 2.5/97.5, omit undefined replicates and report their count; interval unavailable if fewer than 1,800 valid.',
            'improvement_rule': 'Within-pilot signal only if primary delta >= 0.05 and paired interval lower bound > 0; otherwise inconclusive/no demonstrated gain. Always show all baselines and permutation controls. No claim of general biological superiority.'},
        'restrictions': ['No outcome-based cohort changes, post-test feature/threshold adjustment or extra model search. Changes require a new protocol and a fresh holdout.',
            'Modern Pharos annotations postdate the 2024 outcomes; this is not temporal or prospective validation. Pathway/assay releases and full study independence are unresolved.',
            'Chronos was jointly processed upstream; holding out models here does not undo shared preprocessing or establish independent laboratory replication.',
            'Sample-group IDs do not prove independent donors. Bootstrap scope excludes training and cohort-selection uncertainty. General growth dependency in CRC models is not CRC-selective dependency.'],
        'dependency_values_loaded': False, 'scientific_improvement_established': False}


def _partition(groups, axis):
    if len(groups) < 5 or len({g['group'] for g in groups}) != len(groups):
        raise ValueError('Need at least five distinct groups on each axis.')
    rows = [{**g, 'hash': digest({'policy': POLICY, 'axis': axis, 'group': g['group']})} for g in groups]
    rows.sort(key=lambda g: (g['hash'], g['group']))
    train = len(rows) * 3 // 5; validation = len(rows) // 5
    for i, row in enumerate(rows): row['split'] = 'train' if i < train else ('validation' if i < train + validation else 'test')
    return rows


def partitions(members, models):
    genes = {g['hgnc_id']: g for g in members}
    if len(genes) != len(members): raise ValueError('Duplicate panel gene.')
    owners = defaultdict(set)
    for gene in members:
        for p in gene['protein_candidates']: owners[p['uniprot_id']].add(gene['hgnc_id'])
    remaining = set(genes); groups = []
    while remaining:
        component = {min(remaining)}; pending = list(component)
        while pending:
            gid = pending.pop()
            for p in genes[gid]['protein_candidates']:
                for other in owners[p['uniprot_id']] - component:
                    component.add(other); pending.append(other)
        ids = sorted(component); remaining -= component
        groups.append({'group': '|'.join(ids), 'hgnc_ids': ids})
    samples = defaultdict(list); seen = set()
    for row in models:
        if (row['model_id'] in seen or not row['patient_sample_group'] or not row['selected_crc_model'] or
                not row['screen_provenance_eligible_2d']): raise ValueError('Unresolved or duplicate screened model.')
        seen.add(row['model_id']); samples[row['patient_sample_group']].append(row['model_id'])
    return {'genes': _partition(groups, 'genes'), 'models': _partition([
        {'group': group, 'model_ids': sorted(ids)} for group, ids in samples.items()], 'models')}


def _number(value):
    if isinstance(value, bool) or value is None: return None
    try: number = float(value)
    except (ValueError, TypeError): return None
    return number if math.isfinite(number) else None


def reviewed_features(inputs):
    members = inputs['members']; targets = inputs['targets']; mappings = {r['hgnc_id']: r for r in inputs['cptac_mapping_rows']}
    if (len(mappings) != len(inputs['cptac_mapping_rows']) or set(mappings) != {g['hgnc_id'] for g in members} or
            len({t['uniprot'] for t in targets}) != len(targets)):
        raise ValueError('Duplicate or unmatched feature-input identities.')
    owner = defaultdict(set)
    for g in members:
        for p in g['protein_candidates']:
            if not p['shared_across_genes']: owner[p['uniprot_id'].removeprefix('UniProtKB:')].add(g['hgnc_id'])
    by_id = {t['uniprot']: (i, t) for i, t in enumerate(targets)}
    genes = []; exclusions = []; edges = defaultdict(list); dispositions = Counter(); duplicates = 0
    for member in members:
        gid = member['hgnc_id']; pathways = defaultdict(list); quantitative = defaultdict(list); qualitative = defaultdict(list)
        for product in member['protein_candidates']:
            uid = product['uniprot_id'].removeprefix('UniProtKB:')
            if uid not in by_id: continue
            ti, target = by_id[uid]
            for family in ['pathways', 'go', 'ppis', 'expressions']:
                records = target['pathways'] if family == 'pathways' else target['pharos_context'][family]
                for ri, record in enumerate(records):
                    suffix = f'/targets/{ti}/' + ('pathways/' if family == 'pathways' else 'pharos_context/' + family + '/') + str(ri)
                    ref = {'source_locator': 'source_inputs.json#' + suffix, 'parent_locator': 'snapshot.json#' + suffix, 'record_sha256': digest(record)}
                    reason = None
                    if product['shared_across_genes'] or len(owner[uid]) != 1: reason = 'shared_product_attribution_unresolved'
                    elif BLOCKED.search(json.dumps(record, sort_keys=True)): reason = 'dependency_or_unresolved_cell_model_source'
                    elif family == 'go': reason = 'go_study_reference_and_qualifier_unavailable'
                    elif family == 'pathways':
                        source = record.get('type'); source_id = record.get('sourceID') or ''
                        match = re.fullmatch(r'(R-HSA-[0-9]+)(?:\.[0-9]+)?', source_id) if source == 'Reactome' else (re.fullmatch(r'(WP[0-9]+)(?:_r[0-9]+)?', source_id) if source == 'WikiPathways' else None)
                        if not match: reason = 'pathway_source_or_stable_id_not_approved'
                        else:
                            key = (source, match[1]); duplicates += bool(pathways[key]); pathways[key].append(ref)
                    elif family == 'ppis':
                        labels = {x.strip() for x in record.get('type', '').split(',')}
                        values = [p['value'] for p in record.get('props', []) if p.get('name') == 'p_int']
                        probability = _number(values[0]) if len(values) == 1 else None
                        partner = (record.get('target') or {}).get('uniprot')
                        if 'BioPlex' not in labels: reason = 'no_separable_bioplex_component'
                        elif probability is None or not 0.75 <= probability <= 1: reason = 'bioplex_probability_missing_ambiguous_or_below_threshold'
                        elif len(owner[partner]) != 1: reason = 'ppi_partner_gene_attribution_unresolved'
                        else:
                            other = next(iter(owner[partner]))
                            if other == gid: reason = 'gene_self_interaction'
                            else: edges[tuple(sorted([gid, other]))].append({**ref, 'reported_source_labels': sorted(labels), 'bioplex_p_int': probability})
                    else:
                        source = record.get('type'); tissue = record.get('tissue', '').strip().casefold()
                        if source in {'HPM Protein', 'HPA RNA'}:
                            allowed = {'adult colon', 'adult rectum'} if source == 'HPM Protein' else {'colon', 'rectum'}
                            value = _number(record.get('value'))
                            if tissue not in allowed: reason = 'expression_tissue_outside_exact_source_scope'
                            elif record.get('value') is not None and (value is None or value < 0): reason = 'expression_numeric_value_invalid'
                            else: quantitative[(source, tissue)].append((value, ref))
                        elif source == 'HPA Protein':
                            if not tissue.startswith(('colon - ', 'rectum - ')): reason = 'expression_tissue_outside_exact_source_scope'
                            elif record.get('qual') not in {'Not detected', 'Low', 'Medium', 'High'}: reason = 'expression_category_unresolved'
                            else: qualitative[(source, tissue)].append((record['qual'], ref))
                        else: reason = 'expression_integrated_or_unreviewed_source'
                    dispositions[reason or ('retained_' + family)] += 1
                    if reason: exclusions.append({'hgnc_id': gid, 'protein_id': product['uniprot_id'], 'family': family, 'reason': reason, **ref})
        measurement = mappings[gid]
        if measurement['matrix_row'] != member['cptac_matrix_row'] or measurement['ncbi_gene_id'] != member['ncbi_gene_id']:
            raise ValueError('CPTAC identity differs from fixed panel.')
        cptac = measurement['median_reported_log2_ratio']
        if cptac is not None and _number(cptac) is None: raise ValueError('CPTAC summary is nonfinite.')
        genes.append({'hgnc_id': gid, 'symbol': member['approved_symbol'],
            'pathways': [{'source': source, 'stable_id': ident, 'support': refs} for (source, ident), refs in sorted(pathways.items())],
            'numeric_expression': [{'source': source, 'tissue': tissue, 'value': statistics.median(sorted({v for v, _ in rows if v is not None})) if any(v is not None for v, _ in rows) else None,
                                    'support': [r for _, r in rows]} for (source, tissue), rows in sorted(quantitative.items())],
            'categorical_expression': [{'source': source, 'tissue': tissue, 'categories': sorted({v for v, _ in rows}), 'support': [r for _, r in rows]} for (source, tissue), rows in sorted(qualitative.items())],
            'cptac_median_reported_log2_ratio': cptac, 'cptac_matrix_row': measurement['matrix_row'], 'cptac_measurement_sha256': measurement['measurement_sha256']})
    neighbors = defaultdict(set); edge_rows = []
    for (a, b), support in sorted(edges.items()):
        neighbors[a].add(b); neighbors[b].add(a); edge_rows.append({'genes': [a, b], 'component': 'BioPlex', 'support': support})
    for gene in genes: gene['bioplex_neighbors'] = sorted(neighbors[gene['hgnc_id']])
    audit = {'record_dispositions': dict(sorted(dispositions.items())), 'collapsed_repeated_or_revision_pathway_memberships': duplicates,
        'unique_gene_pathway_memberships': sum(len(g['pathways']) for g in genes), 'undirected_bioplex_gene_edges': len(edge_rows),
        'bioplex_source_records': sum(len(e['support']) for e in edge_rows),
        'genes_with_pathways': sum(bool(g['pathways']) for g in genes), 'genes_with_bioplex_neighbors': sum(bool(g['bioplex_neighbors']) for g in genes),
        'genes_with_numeric_expression': sum(any(x['value'] is not None for x in g['numeric_expression']) for g in genes),
        'genes_with_categorical_expression': sum(bool(g['categorical_expression']) for g in genes),
        'genes_with_cptac_summary': sum(g['cptac_median_reported_log2_ratio'] is not None for g in genes),
        'human_scientific_adjudications': 0, 'underlying_study_independence_established': False,
        'review_kind': 'AI-authored implementation/source-contract review; not biological gold adjudication'}
    return {'genes': genes, 'bioplex_edges': edge_rows}, exclusions, audit


def reference_binding(code, tree):
    raw = Path(code).read_bytes(); inventory = json.loads(Path(tree).read_text())
    expected = next(r['sha'] for r in inventory['tree'] if r['path'] == 'src/TCRD.js')
    actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if expected != actual: raise ValueError('Published repository tree and implementation bytes differ.')
    return {'git_blob_sha1': actual, 'sha256': hashlib.sha256(raw).hexdigest(), 'repository_tree_sha': inventory['sha'],
            'source_scope': 'Preserved public repository source, not attestation of the deployed Pharos server revision.',
            'ppi_implementation_observation': 'Confidence predicate excludes low-score STRINGDB-only rows; mixed labels retain p_int. p_int is used for component eligibility only, never as a numerical predictor.',
            'go_observation': 'Retrieved GO rows expose no study reference or qualifier. Evidence code alone does not resolve endpoint overlap.',
            'references': REFERENCES}


def freeze_protocol(panel_path, retrieval_path, mapping_path, output, *, pharos_code, repository_tree):
    panel_path = Path(panel_path); retrieval_path = Path(retrieval_path); mapping_path = Path(mapping_path)
    panel, members = load_panel(panel_path); retrieval = verify_retrieval(retrieval_path); mapping = verify_mapping(mapping_path)
    if (retrieval['panel_sha256'] != panel['panel_sha256'] or mapping['result_sha256'] != panel['cohort_mapping_result_sha256'] or
            not retrieval['version_consistent'] or retrieval['outcome_values_loaded'] or retrieval['disease_filter_used']):
        raise ValueError('Matched sources differ or violate outcome-blind retrieval requirements.')
    for family in ['pathways', 'go', 'ppis', 'expressions']:
        if set(retrieval['retrieval'][family]['target_statuses']) != {'complete'}:
            raise ValueError('Resolve incomplete/capped requested-family coverage before freezing this protocol.')
    source = json.loads((retrieval_path / 'snapshot.json').read_text()); ids = {g['hgnc_id'] for g in members}
    rows = json.loads((mapping_path / 'mappings.json').read_text())
    fields = ['hgnc_id', 'ncbi_gene_id', 'matrix_row', 'measurement_sha256', 'median_reported_log2_ratio']
    inputs = {'members': members, 'models': json.loads((panel_path / 'crc_models.json').read_text()),
              'targets': [{'uniprot': t['uniprot'], 'pathways': t['pathways'], 'pharos_context': {
                  f: t['pharos_context'][f] for f in ['go', 'ppis', 'expressions']}} for t in source['targets']],
              'cptac_mapping_rows': [{f: row[f] for f in fields} for row in rows if row['hgnc_id'] in ids]}
    if len(inputs['cptac_mapping_rows']) != len(members): raise ValueError('CPTAC rows do not cover the fixed panel exactly.')
    splits = partitions(members, inputs['models']); features, exclusions, audit = reviewed_features(inputs)
    reference = reference_binding(pharos_code, repository_tree)
    out = new_output(output, panel_path, retrieval_path, mapping_path, pharos_code, repository_tree)
    for name, value in [('source_inputs.json', inputs), ('features.json', features), ('exclusions.json', exclusions),
                        ('source_review.json', audit), ('partitions.json', splits), ('specification.json', specification()), ('references.json', reference)]: write_json(out / name, value)
    (out / 'pharos_TCRD.js').write_bytes(Path(pharos_code).read_bytes()); (out / 'pharos_repository_tree.json').write_bytes(Path(repository_tree).read_bytes())
    result = {'format': 'biograph-steward.frozen-growth-protocol.v1', 'created_at': utcnow(), 'policy': POLICY,
        'panel_sha256': panel['panel_sha256'], 'pharos_result_sha256': retrieval['result_sha256'], 'pharos_snapshot_sha256': retrieval['source_snapshot_sha256'],
        'cohort_mapping_result_sha256': mapping['result_sha256'], 'cptac_matrix_sha256': mapping['matrix_sha256'],
        'depmap_source_sha256': panel['depmap_source_sha256'], 'depmap_audit_sha256': panel['depmap_audit_sha256'],
        'engine_files': engine_fingerprint(), 'genes': len(members), 'models': len(inputs['models']), 'source_review': audit,
        'partition_counts': {axis: dict(sorted(Counter(row['split'] for row in groups).items())) for axis, groups in splits.items()},
        'partition_unit_counts': {'genes': {split: sum(len(g['hgnc_ids']) for g in splits['genes'] if g['split'] == split) for split in ['train', 'validation', 'test']},
                                  'models': {split: sum(len(g['model_ids']) for g in splits['models'] if g['split'] == split) for split in ['train', 'validation', 'test']}},
        'protocol_frozen': True, 'dependency_values_loaded': False, 'model_requests': 0, 'predictor_fit_run': False, 'scientific_improvement_established': False,
        'next_action': 'Implement and test the runner against this exact specification, then execute the frozen two-arm comparison. Do not revise protocol after inspecting held-out outcomes.',
        'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_protocol(result, splits), encoding='utf-8')
    return result


def verify_protocol(path):
    path = Path(path); result = json.loads((path / 'metrics.json').read_text())
    expected = {'source_inputs.json', 'features.json', 'exclusions.json', 'source_review.json', 'partitions.json',
                'specification.json', 'references.json', 'pharos_TCRD.js', 'pharos_repository_tree.json'}
    if (set(result['files']) != expected or result['result_sha256'] != digest({k: v for k, v in result.items() if k != 'result_sha256'}) or
            result['policy'] != POLICY or result['dependency_values_loaded'] or result['predictor_fit_run']): raise ValueError('Protocol manifest changed.')
    for name, value in result['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value: raise ValueError('Frozen protocol bytes changed.')
    inputs = json.loads((path / 'source_inputs.json').read_text()); features, exclusions, audit = reviewed_features(inputs)
    for name, reproduced in [('features.json', features), ('exclusions.json', exclusions), ('source_review.json', audit),
        ('partitions.json', partitions(inputs['members'], inputs['models'])), ('specification.json', specification()),
        ('references.json', reference_binding(path / 'pharos_TCRD.js', path / 'pharos_repository_tree.json'))]:
        if reproduced != json.loads((path / name).read_text()): raise ValueError('Protocol views do not reproduce from frozen inputs.')
    if audit != result['source_review'] or len(features['genes']) != result['genes'] or len(inputs['models']) != result['models']:
        raise ValueError('Protocol inventory differs.')
    return result


def render_protocol(result, splits):
    esc = lambda x: escape(str(x), quote=True)
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Frozen growth comparison protocol</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin:20px 0}</style>'
        '<h1>Frozen growth comparison protocol</h1><p><strong>No dependency values loaded; no predictor fitted; biological improvement untested.</strong></p>'
        '<p>Compare the same frozen genes and grouped models using restricted Pharos versus restricted Pharos plus CPTAC. This is a retrospective feature-enrichment pilot, not clinical validation or a comparison against all Pharos data.</p>'
        '<h2>Source review and coverage</h2><pre>' + esc(json.dumps(result, indent=2)) + '</pre><h2>Frozen experiment rules</h2><pre>' + esc(json.dumps(specification(), indent=2)) + '</pre>'
        '<details><summary>Exact grouped assignments</summary><pre>' + esc(json.dumps(splits, indent=2)) + '</pre></details></html>')
