"""Release-pinned CRISPR coverage and source-leakage inventory, without ranking."""
from collections import Counter, defaultdict
import csv
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import shutil

from .client import digest, utcnow, write_json
from .cohort_mapping import verify_mapping
from .crc_pilot import new_output, sha
from .evaluation import engine_fingerprint
from .graph import verify_snapshot

ARTICLE_ID = 27993248
ARTICLE_URL = 'https://api.figshare.com/v2/articles/27993248/versions/1'
FILES = {'README.txt', 'Model.csv', 'Gene.csv', 'CRISPRGeneEffect.csv', 'ModelCondition.csv',
         'CRISPRInferredModelEfficacy.csv', 'AchillesScreenQCReport.csv', 'CRISPRScreenMap.csv', 'ScreenSequenceMap.csv'}
POLICY = 'depmap-crc-coverage-and-leakage.v1'
MISSING = {'', 'NA', 'NaN', 'nan'}


def checksums(path):
    md5 = hashlib.md5(); sha256 = hashlib.sha256(); size = 0
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            size += len(block); md5.update(block); sha256.update(block)
    return size, md5.hexdigest(), sha256.hexdigest()


def freeze_depmap(downloads, output):
    """Verify supplied public archive downloads against the pinned publisher record."""
    downloads = Path(downloads)
    raw = (downloads / 'article_27993248_v1.json').read_bytes(); article = json.loads(raw)
    if (article.get('id') != ARTICLE_ID or article.get('version') != 1 or article.get('title') != 'DepMap 24Q4 Public' or
            article.get('doi') != '10.25452/figshare.plus.27993248.v1'):
        raise ValueError('Expected the explicitly pinned 24Q4 v1 archive, not an inferred latest release.')
    selected = {name: [f for f in article['files'] if f['name'] == name] for name in FILES}
    if any(len(v) != 1 for v in selected.values()):
        raise ValueError('Missing or duplicate publisher file metadata.')
    out = new_output(output, downloads); records = []
    for name in sorted(FILES):
        info = selected[name][0]; path = downloads / 'downloads' / name
        if path.is_symlink() or info['is_link_only'] or info['download_url'] != 'https://ndownloader.figshare.com/files/' + str(info['id']):
            raise ValueError('Unsupported archive file identity.')
        size, md5, sha256 = checksums(path)
        if size != info['size'] or md5 != info['computed_md5'] or (info.get('supplied_md5') and info['supplied_md5'] != md5):
            raise ValueError('DepMap bytes do not match the publisher checksum/size.')
        shutil.copyfile(path, out / name)
        records.append({'file': name, 'file_id': info['id'], 'bytes': size, 'publisher_md5': md5,
                        'sha256': sha256, 'url': info['download_url']})
    (out / 'article.json').write_bytes(raw)
    manifest = {'format': 'biograph-steward.depmap-archive.v1', 'created_at': utcnow(),
                'release': article['title'], 'article_id': ARTICLE_ID, 'version': 1, 'doi': article['doi'],
                'publisher_record_url': ARTICLE_URL, 'publisher_record_sha256': sha(out / 'article.json'),
                'publisher_date': article['published_date'], 'license': article['license'],
                'ingest': 'Provided archive downloads; exact publisher sizes and MD5s verified locally.',
                'release_scope': 'Pinned historical feasibility audit. No claim of current-release coverage or independent assay reprocessing.',
                'files': records}
    manifest['source_sha256'] = digest(manifest); write_json(out / 'manifest.json', manifest)
    return manifest


def load_depmap(path):
    path = Path(path); manifest = json.loads((path / 'manifest.json').read_text())
    if (manifest['source_sha256'] != digest({k: v for k, v in manifest.items() if k != 'source_sha256'}) or
            {r['file'] for r in manifest['files']} != FILES or len(manifest['files']) != len(FILES) or
            (path / 'article.json').is_symlink() or sha(path / 'article.json') != manifest['publisher_record_sha256']):
        raise ValueError('Frozen DepMap manifest changed.')
    for row in manifest['files']:
        name = row['file']
        if (path / name).is_symlink() or checksums(path / name) != (row['bytes'], row['publisher_md5'], row['sha256']):
            raise ValueError('Frozen DepMap source changed.')
    return manifest


def read_table(path, required, key):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not set(required) <= set(reader.fieldnames):
            raise ValueError('Missing or duplicate source columns: ' + Path(path).name)
        rows = list(reader)
    if not rows or any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError('Empty or malformed source table.')
    if key and (any(not r[key] for r in rows) or len({r[key] for r in rows}) != len(rows)):
        raise ValueError('Missing or duplicate source row identity.')
    return rows


def ncbi_id(value):
    # Gene.csv stores integer identifiers as strings such as '3845.0'. No rounding.
    return value.split('.')[0] if re.fullmatch(r'[1-9][0-9]*(?:\.0+)?', value) else None


def gene_crosswalk(header, mappings, release_genes):
    if len(header) < 2 or header[0] not in {'', 'ModelID'} or len(set(header)) != len(header):
        raise ValueError('Expected a model-indexed gene-effect matrix with unique labels.')
    release_by_ncbi = defaultdict(set)
    for gene in release_genes:
        ident = ncbi_id(gene['entrez_id'])
        if gene['status'] == 'Approved' and ident:
            release_by_ncbi[ident].add(gene['hgnc_id'])
    columns = []; by_gene = defaultdict(list)
    for index, label in enumerate(header[1:], 1):
        match = re.fullmatch(r'(.+) \(([1-9][0-9]*)\)', label)
        if not match:
            raise ValueError('Gene-effect column lacks its explicit NCBI Gene ID.')
        column = {'matrix_column': index, 'label': label, 'symbol': match[1], 'ncbi_gene_id': match[2],
                  'release_hgnc_ids': sorted(release_by_ncbi[match[2]])}
        columns.append(column)
        for gid in column['release_hgnc_ids']:
            by_gene[gid].append(column)
    crosswalk = []
    for row in mappings:
        candidates = by_gene.get(row['hgnc_id'], []) if row['identifier_eligible'] else []
        if not row['identifier_eligible']:
            status = 'input_gene_identity_unresolved'
        elif not candidates:
            status = 'absent_from_gene_effect_matrix'
        elif len(candidates) != 1 or len(candidates[0]['release_hgnc_ids']) != 1:
            status = 'ambiguous_release_gene_identity'
        elif candidates[0]['ncbi_gene_id'] != row['ncbi_gene_id']:
            status = 'ncbi_gene_id_disagreement'
        else:
            status = 'unique_stable_id_match'
        matched = candidates[0] if status == 'unique_stable_id_match' else None
        crosswalk.append({'reported_symbol': row['reported_symbol'], 'approved_symbol': row['approved_symbol'],
                          'hgnc_id': row['hgnc_id'], 'ncbi_gene_id': row['ncbi_gene_id'],
                          'cptac_matrix_row': row['matrix_row'], 'protein_context_eligible': row['protein_context_eligible'],
                          'status': status, 'matrix_column': matched['matrix_column'] if matched else None,
                          'release_label': matched['label'] if matched else None,
                          'release_symbol_differs': bool(matched and matched['symbol'] != row['approved_symbol']),
                          'candidate_columns': candidates})
    return columns, crosswalk


def model_coverage(source, mappings):
    source = Path(source)
    required = ['ModelID', 'PatientID', 'CellLineName', 'OncotreeLineage', 'OncotreePrimaryDisease',
                'OncotreeSubtype', 'ModelType', 'EngineeredModel', 'CulturedResistanceDrug']
    models = {r['ModelID']: r for r in read_table(source / 'Model.csv', required, 'ModelID')}
    genes = read_table(source / 'Gene.csv', ['hgnc_id', 'symbol', 'entrez_id', 'status'], 'hgnc_id')
    screen_map = read_table(source / 'CRISPRScreenMap.csv', ['ScreenID', 'ModelID'], 'ScreenID')
    qc = {r['ScreenID']: r for r in read_table(source / 'AchillesScreenQCReport.csv',
          ['ScreenID', 'ModelID', 'ModelConditionID', 'PassesQC', 'CanInclude', 'Library', 'ScreenType'], 'ScreenID')}
    conditions = {r['ModelConditionID']: r for r in read_table(source / 'ModelCondition.csv', ['ModelConditionID', 'ModelID', 'CellFormat'], 'ModelConditionID')}
    screens_by_model = defaultdict(list)
    for row in screen_map:
        screens_by_model[row['ModelID']].append(row['ScreenID'])
    crc = {mid for mid, r in models.items() if r['OncotreeLineage'] == 'Bowel' and
           r['OncotreePrimaryDisease'] == 'Colorectal Adenocarcinoma' and r['ModelType'] == 'Cell Line' and
           not r['EngineeredModel'] and not r['CulturedResistanceDrug']}
    inventory = []; seen = set(); total_missing = total_observed = 0
    with (source / 'CRISPRGeneEffect.csv').open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f); header = next(reader, [])
        columns, crosswalk = gene_crosswalk(header, mappings, genes)
        selected = {r['matrix_column']: r for r in crosswalk if r['status'] == 'unique_stable_id_match'}
        if len(selected) != sum(r['status'] == 'unique_stable_id_match' for r in crosswalk):
            raise ValueError('Two candidate rows would reuse one gene-effect column.')
        for row in selected.values():
            row.update(crc_observed_models=0, crc_missing_models=0, other_observed_models=0, other_missing_models=0)
        for number, values in enumerate(reader, 2):
            if len(values) != len(header) or values[0] in seen or values[0] not in models:
                raise ValueError('Malformed, duplicate or unannotated model row.')
            mid = values[0]; seen.add(mid); model = models[mid]; is_crc = mid in crc
            relevant = []
            for screen_id in screens_by_model[mid]:
                screen = qc.get(screen_id)
                if screen and screen['ModelID'] != mid:
                    raise ValueError('Screen/model identity disagreement.')
                condition = conditions.get(screen['ModelConditionID']) if screen else None
                if condition and condition['ModelID'] != mid:
                    raise ValueError('Condition/model identity disagreement.')
                relevant.append({'screen_id': screen_id, 'passes_qc': screen['PassesQC'] if screen else None,
                                 'can_include': screen['CanInclude'] if screen else None,
                                 'library': screen['Library'] if screen else None, 'screen_type': screen['ScreenType'] if screen else None,
                                 'condition_id': screen['ModelConditionID'] if screen else None,
                                 'cell_format': condition['CellFormat'] if condition else None,
                                 'condition_treatments': {k: condition.get(k) for k in ['PrescreenTreatmentDrug', 'AnchorDrug'] if condition and condition.get(k)}})
            eligible_screens = bool(relevant) and all(r['passes_qc'] == 'True' and r['can_include'] == 'True' and
                                                    r['screen_type'] == '2DS' and r['condition_id'] in conditions and not r['condition_treatments'] for r in relevant)
            inventory.append({'model_id': mid, 'cell_line_name': model['CellLineName'], 'patient_sample_group': model['PatientID'] or None,
                              'lineage': model['OncotreeLineage'], 'primary_disease': model['OncotreePrimaryDisease'],
                              'subtype': model['OncotreeSubtype'], 'model_type': model['ModelType'], 'matrix_row': number,
                              'selected_crc_model': is_crc, 'included_screens': relevant,
                              'screen_provenance_eligible_2d': eligible_screens,
                              'eligible_other_cell_line_context': (not is_crc and model['OncotreeLineage'] != 'Bowel' and
                                  model['ModelType'] == 'Cell Line' and not model['EngineeredModel'] and not model['CulturedResistanceDrug'] and eligible_screens)})
            # Numeric values are discarded immediately. Only validity and missingness are retained.
            for index, value in enumerate(values[1:], 1):
                missing = value in MISSING
                if not missing and not math.isfinite(float(value)):
                    raise ValueError('Non-finite gene effect; missingness must be explicit.')
                total_missing += missing; total_observed += not missing
                if index in selected:
                    key = ('crc_' if is_crc else 'other_') + ('missing_models' if missing else 'observed_models')
                    selected[index][key] += 1
    crc_rows = [r for r in inventory if r['selected_crc_model']]
    patient_groups = defaultdict(list)
    for row in crc_rows:
        if row['patient_sample_group']:
            patient_groups[row['patient_sample_group']].append(row['model_id'])
    matched = list(selected.values())
    stats = {'metadata_models': len(models), 'matrix_models': len(inventory), 'matrix_gene_columns': len(columns),
             'observed_matrix_values': total_observed, 'missing_matrix_values': total_missing,
             'crc_cell_lines_in_metadata': len(crc), 'screened_crc_cell_lines': len(crc_rows),
             'crc_metadata_cell_lines_without_matrix_row': len(crc - seen),
             'crc_models_with_documented_included_2d_screens': sum(r['screen_provenance_eligible_2d'] for r in crc_rows),
             'crc_included_screens': sum(len(r['included_screens']) for r in crc_rows),
             'crc_patient_sample_groups': len(patient_groups), 'crc_models_without_patient_group': sum(not r['patient_sample_group'] for r in crc_rows),
             'related_crc_model_groups': [v for _, v in sorted(patient_groups.items()) if len(v) > 1],
             'other_screened_models': len(inventory) - len(crc_rows),
             'other_cell_line_models_with_documented_2d_context': sum(r['eligible_other_cell_line_context'] for r in inventory),
             'candidate_input_rows': len(mappings), 'candidate_gene_status_counts': dict(sorted(Counter(r['status'] for r in crosswalk).items())),
             'candidate_genes_with_matrix_column': len(matched),
             'protein_context_genes_with_matrix_column': sum(r['protein_context_eligible'] for r in matched),
             'matched_gene_labels_changed_since_release': sum(r['release_symbol_differs'] for r in matched),
             'candidate_genes_observed_in_any_crc_model': sum(r['crc_observed_models'] > 0 for r in matched),
             'candidate_genes_observed_in_every_crc_model': sum(r['crc_observed_models'] == len(crc_rows) and len(crc_rows) > 0 for r in matched),
             'minimum_crc_observations_per_matched_gene': min((r['crc_observed_models'] for r in matched), default=None)}
    return stats, crosswalk, inventory, columns


PROGRAM = re.compile(r'depmap|achilles|chronos|ceres|demeter|project[ -]score', re.I)
ADJACENT = re.compile(r'harmonizome|\bccle\b|\bctd2\b', re.I)
PERTURBATION = re.compile(r'crispr|\brnai\b|\bshrna\b|gene essentiality|gene dependency', re.I)


def source_hits(value, prefix):
    hits = []
    def walk(node, pointer):
        if isinstance(node, dict):
            for key, child in node.items():
                child_pointer = pointer + '/' + str(key).replace('~', '~0').replace('/', '~1')
                if PROGRAM.search(str(key)) or re.search(r'gene[_ -]?(effect|dependency|fitness)|harmonizome|\bccle\b', str(key), re.I):
                    hits.append({'locator': child_pointer, 'category': 'source_or_dependency_field_name',
                                 'value': child if isinstance(child, (str, int, float, bool)) or child is None else 'Structured source field; inspect its frozen locator.',
                                 'value_sha256': digest(child)})
                walk(child, child_pointer)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, pointer + '/' + str(index))
        elif isinstance(node, str):
            category = 'dependency_program_reference' if PROGRAM.search(node) else ('related_aggregator_or_cell_model_reference' if ADJACENT.search(node) else ('perturbation_or_essentiality_reference' if PERTURBATION.search(node) else None))
            if category:
                hits.append({'locator': pointer, 'category': category, 'value': node, 'value_sha256': digest(node)})
    walk(value, prefix)
    return hits


def leakage_inventory(snapshot, civic=None, probe=None):
    hits = source_hits(snapshot['targets'], 'snapshot.json#/targets')
    requests = source_hits([r['response'] for r in snapshot.get('requests', [])], 'raw_response_inventory#')
    if civic:
        hits += source_hits([r['record'] for r in civic['items']], 'civic_records#')
    probe_hits = source_hits(probe['response'], 'historical_probe#/response') if probe else []
    return {'materialized_record_hits': hits, 'raw_response_hits': requests, 'historical_probe_hits': probe_hits,
            'summary': {'materialized_hits_by_category': dict(sorted(Counter(r['category'] for r in hits).items())),
                        'raw_response_reference_hits': len(requests), 'historical_probe_hits_by_category': dict(sorted(Counter(r['category'] for r in probe_hits).items())),
                        'targets_with_harmonizome_flag': sum('Harmonizome' in t.get('pharos_context', {}).get('metadata', {}).get('dataSources', []) for t in snapshot['targets']),
                        'targets_with_ccle_flag': sum('CCLE' in t.get('pharos_context', {}).get('metadata', {}).get('dataSources', []) for t in snapshot['targets'])},
            'interpretation': ['Reference hits are source-overlap candidates, not counts of independent experiments or proof of leaked outcome values.',
                               'The historical probe is discovery context outside the scoped baseline inputs; preserve its retrieval date and assay description.',
                               'Legacy shRNA/RNAi knockdown and CRISPR knockout in this pinned release are distinct modalities. A related program name alone does not establish identical measurements.',
                               'No hit in this bounded extract does not establish independence from upstream integrated resources or the entire Pharos database.']}


def run_audit(source, mapping, pharos_run, output, *, enriched_run=None, probe_file=None):
    source = Path(source); mapping = Path(mapping); pharos_run = Path(pharos_run)
    manifest = load_depmap(source); mapped = verify_mapping(mapping)
    snapshot = json.loads((pharos_run / 'snapshot.json').read_text()); verify_snapshot(snapshot)
    if snapshot['content_sha256'] != mapped['pharos_snapshot_sha256']:
        raise ValueError('Pharos and measured-cohort controls differ.')
    civic = None; civic_sha = None
    if enriched_run:
        enriched = json.loads((Path(enriched_run) / 'snapshot.json').read_text()); verify_snapshot(enriched)
        if enriched['content_sha256'] != snapshot['content_sha256']:
            raise ValueError('The compared source arms have different Pharos inputs.')
        from .civic import verify_civic
        civic = json.loads((Path(enriched_run) / 'civic_snapshot.json').read_text()); verify_civic(civic)
        civic_sha = civic['content_sha256']
    probe = json.loads(Path(probe_file).read_text()) if probe_file else None
    if probe and digest(probe['response']) != probe['response_sha256']:
        raise ValueError('Historical source probe changed.')
    rows = json.loads((mapping / 'mappings.json').read_text())
    stats, crosswalk, models, columns = model_coverage(source, rows)
    matched_rows = {r['cptac_matrix_row'] for r in crosswalk if r['status'] == 'unique_stable_id_match' and r['crc_observed_models'] > 0}
    pharos = json.loads((mapping / 'pharos_crosswalk.json').read_text())
    linked = [r for r in pharos if any(n in matched_rows for n in r['matrix_rows'])]
    stats.update(pharos_proteins_in_frozen_baseline=len(pharos), pharos_proteins_with_matched_crc_measurement=len(linked),
                 pharos_measured_gene_rows_with_matched_crc_measurement=len({n for r in linked for n in r['matrix_rows'] if n in matched_rows}))
    leakage = leakage_inventory(snapshot, civic, probe)
    policy = {'format': 'biograph-steward.proposed-dependency-feature-policy.v1', 'status': 'proposal_not_applied_to_graphs',
              'exclude_from_every_predictor_arm': ['DepMap/Achilles/Chronos/CERES/DEMETER/SCORE gene-effect, dependency, fitness and co-dependency scores or derived labels.',
                                                  'Harmonizome attributes/aggregate counts and CCLE/CTD2-derived summaries until their source/assay provenance is resolved.',
                                                  'Raw discovery text, publication counts, source-presence flags, patient outcomes and endpoint/QC-derived statistics.',
                                                  'Precomputed common-essential or dependency labels derived from the evaluation screens.'],
              'review_before_use': ['Source channels and releases for integrated STRING/PPI, GO and pathway evidence; a database name alone does not prove independence.',
                                    'CIViC biological scope and publications; therapy response does not become a gene-knockout growth label.',
                                    'CPTAC tumor measurements versus cell-model context; abundance is not gene essentiality.'],
              'required_controls': ['Retrieve matched baseline features for a label-independent population; do not compare disease-selected 99 proteins with all measured genes as though coverage were equal.',
                                    'Freeze candidate genes, endpoint, scoring rule and missing-data policy before examining effect sizes.',
                                    'Keep models sharing PatientID/tissue-sample group in one partition; screens are not additional independent models.',
                                    'Use compatible model/condition and assay contexts; do not mix missing measurements with non-dependencies.',
                                    'The published Chronos matrix uses joint screen/library processing; a model split does not establish independent preprocessing or held-library validation.',
                                    'Keep held-out screen outcomes and their derivatives out of fitting, feature selection, prompts and graph inputs.']}
    out = new_output(output, source, mapping, pharos_run, *([enriched_run] if enriched_run else []))
    write_json(out / 'gene_coverage.json', crosswalk); write_json(out / 'model_inventory.json', models)
    write_json(out / 'matrix_columns.json', columns); write_json(out / 'leakage_inventory.json', leakage)
    write_json(out / 'feature_policy.json', policy); write_json(out / 'source_manifest.json', manifest)
    shutil.copyfile(source / 'README.txt', out / 'depmap_README.txt')
    if probe:
        write_json(out / 'historical_probe.json', probe)
    with (out / 'gene_coverage.tsv').open('w', newline='') as f:
        writer = csv.writer(f, delimiter='\t'); writer.writerow(['hgnc_id', 'reported_symbol', 'approved_symbol', 'status', 'release_label', 'crc_observed_models', 'crc_missing_models'])
        for r in crosswalk:
            writer.writerow([r['hgnc_id'] or '', r['reported_symbol'], r['approved_symbol'] or '', r['status'], r['release_label'] or '', r.get('crc_observed_models', ''), r.get('crc_missing_models', '')])
    result = {'format': 'biograph-steward.depmap-feasibility.v1', 'created_at': utcnow(), 'policy': POLICY,
              'source_sha256': manifest['source_sha256'], 'release': manifest['release'], 'doi': manifest['doi'],
              'release_scope': manifest['release_scope'], 'cohort_mapping_result_sha256': mapped['result_sha256'],
              'pharos_snapshot_sha256': snapshot['content_sha256'], 'civic_snapshot_sha256': civic_sha,
              'historical_probe_sha256': sha(probe_file) if probe_file else None,
              'engine_files': engine_fingerprint(), 'coverage': stats, 'leakage': leakage['summary'],
              'coverage_feasible': bool(stats['screened_crc_cell_lines'] and stats['candidate_genes_observed_in_any_crc_model']),
              'ready_for_prediction_comparison': False,
              'remaining_requirements': policy['required_controls'],
              'outcome_access': 'Numeric validity and observed/missing counts only. No effect statistics, thresholds, labels, rankings, training or agent inference.',
              'model_requests': 0, 'graph_assertions_changed': 0, 'scientific_accuracy': None, 'scientific_improvement_established': False,
              'files': {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    result['result_sha256'] = digest(result); write_json(out / 'metrics.json', result)
    (out / 'report.html').write_text(render_audit(result, crosswalk, models, leakage, policy), encoding='utf-8')
    return result


def verify_audit(path):
    path = Path(path); result = json.loads((path / 'metrics.json').read_text())
    expected = {'gene_coverage.json', 'model_inventory.json', 'matrix_columns.json', 'leakage_inventory.json',
                'feature_policy.json', 'source_manifest.json', 'depmap_README.txt', 'gene_coverage.tsv'}
    if result['historical_probe_sha256']:
        expected.add('historical_probe.json')
    if result['result_sha256'] != digest({k: v for k, v in result.items() if k != 'result_sha256'}) or set(result['files']) != expected:
        raise ValueError('DepMap audit manifest changed.')
    for name, value in result['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('DepMap audit artifact changed.')
    rows = json.loads((path / 'gene_coverage.json').read_text()); models = json.loads((path / 'model_inventory.json').read_text())
    if (len(rows) != result['coverage']['candidate_input_rows'] or len(models) != result['coverage']['matrix_models'] or
            sum(r['status'] == 'unique_stable_id_match' for r in rows) != result['coverage']['candidate_genes_with_matrix_column'] or
            sum(r['selected_crc_model'] for r in models) != result['coverage']['screened_crc_cell_lines']):
        raise ValueError('DepMap audit inventory changed.')
    return result


def render_audit(result, crosswalk, models, leakage, policy):
    esc = lambda x: escape(str(x), quote=True)
    crc = [r for r in models if r['selected_crc_model']]
    model_rows = ''.join('<tr><td>' + esc(r['cell_line_name']) + '</td><td>' + esc(r['model_id']) + '</td><td>' + esc(r['patient_sample_group']) + '</td><td>' + esc(r['subtype']) + '</td></tr>' for r in crc)
    unmatched = [r for r in crosswalk if r['status'] != 'unique_stable_id_match']
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>DepMap coverage and leakage audit</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{border:1px solid #ccd;padding:12px;margin:12px 0}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}</style>'
            '<h1>DepMap coverage and leakage audit</h1><p><strong>Historical 24Q4 v1 feasibility audit. No prediction comparison or biological improvement score.</strong></p>'
            '<p>Gene-effect values were parsed only for validity and missingness. Current-release portal coverage was not established. <a href="https://doi.org/10.25452/figshare.plus.27993248.v1">Broad public archive and license</a>.</p>'
            '<h2>Measured coverage</h2><pre>' + esc(json.dumps(result['coverage'], indent=2)) + '</pre>'
            '<h2>Decision</h2><p>The data can support a scoped experiment. Prediction comparison remains gated on matched baseline features, resolved source provenance and a frozen evaluation policy. The 99-protein disease-selected baseline is not the full comparison population.</p>'
            '<h2>Leakage and feature restrictions</h2><pre>' + esc(json.dumps(policy, indent=2)) + '</pre>'
            '<details><summary>Exact overlap references and source locators</summary><pre>' + esc(json.dumps(leakage, indent=2)) + '</pre></details>'
            '<details><summary>Screened colorectal models and tissue-sample groups</summary><table><tr><th>Model</th><th>ID</th><th>Group, keep together in splits</th><th>Subtype</th></tr>' + model_rows + '</table></details>'
            '<details><summary>Unmatched or unresolved genes</summary><pre>' + esc(json.dumps(unmatched, indent=2)) + '</pre></details>'
            '<details><summary>Provenance and checksums</summary><pre>' + esc(json.dumps(result, indent=2)) + '</pre></details></html>')
