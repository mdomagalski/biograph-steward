"""Frozen human identifiers for every measured CPTAC gene, without protein labels."""
from collections import Counter, defaultdict
import csv
from html import escape
from io import StringIO
import json
from pathlib import Path
import re
import statistics
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .client import digest, utcnow, write_json
from .cptac import inspect_matrix, load_cptac
from .file_utils import new_output, sha
from .reviews import read_run

HGNC_URL = 'https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt'
UNIPROT_URL = 'https://rest.uniprot.org/uniprotkb/stream?' + urlencode({
    'query': '(organism_id:9606) AND (reviewed:true)', 'format': 'tsv',
    'fields': 'accession,id,gene_primary,gene_synonym,xref_hgnc,xref_geneid,organism_id,protein_name'})
SOURCES = {'hgnc_complete_set.txt': HGNC_URL, 'uniprot_reviewed_human_symbols.tsv': UNIPROT_URL}
POLICY = 'human-measured-gene-crosswalk.v1'


def collect_registry(output, *, downloads=None, transport=None):
    """Download fixed public registries, or freeze hash-checked existing receipts."""
    out = new_output(output, *([downloads] if downloads else []))
    receipts = []
    previous = json.loads((Path(downloads) / 'retrieval.json').read_text()) if downloads else []
    for name, url in SOURCES.items():
        if downloads:
            matches = [r for r in previous if r['file'] == name and r['url'] == url]
            if len(matches) != 1:
                raise ValueError('Missing or conflicting official registry receipt.')
            receipt = dict(matches[0]); source = Path(downloads) / name
            if source.is_symlink() or sha(source) != receipt['sha256']:
                raise ValueError('Registry download bytes changed.')
            raw = source.read_bytes()
        else:
            if transport:
                raw, headers = transport(url)
            else:
                with urlopen(Request(url, headers={'User-Agent': 'BioGraph-Steward identifier audit'}), timeout=120) as response:
                    raw = response.read(60_000_001)
                    headers = {k.lower(): v for k, v in response.headers.items()
                               if k.lower() in {'last-modified', 'etag', 'x-uniprot-release', 'x-uniprot-release-date'}}
            receipt = {'file': name, 'url': url, 'retrieved_at': utcnow(), 'headers': headers}
        if not isinstance(raw, bytes) or not 0 < len(raw) <= 60_000_000:
            raise ValueError('Invalid or over-budget registry file.')
        (out / name).write_bytes(raw)
        receipt.update(sha256=sha(out / name), bytes=len(raw)); receipts.append(receipt)
    registry = Registry((out / 'hgnc_complete_set.txt').read_bytes(), (out / 'uniprot_reviewed_human_symbols.tsv').read_bytes())
    manifest = {'format': 'biograph-steward.human-registry.v1', 'created_at': utcnow(), 'taxon_id': 9606,
                'ingest_mode': 'provided_downloads_and_receipts' if downloads else 'official_live_download',
                'identity_note': 'Receipts and bytes are frozen; provided receipt metadata is caller-supplied, not an independent attestation.' if downloads else 'Fixed official HGNC and reviewed human UniProt query.',
                'hgnc_records': len(registry.genes), 'uniprot_records': len(registry.proteins),
                'sources': receipts, 'files': {name: sha(out / name) for name in SOURCES}}
    manifest['registry_sha256'] = digest(manifest); write_json(out / 'manifest.json', manifest)
    return manifest


def load_registry(path):
    path = Path(path); manifest = json.loads((path / 'manifest.json').read_text())
    if (manifest['registry_sha256'] != digest({k: v for k, v in manifest.items() if k != 'registry_sha256'}) or
            set(manifest['files']) != set(SOURCES) or manifest['taxon_id'] != 9606):
        raise ValueError('Registry manifest changed.')
    for name, value in manifest['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('Registry bytes changed.')
    return manifest, Registry((path / 'hgnc_complete_set.txt').read_bytes(), (path / 'uniprot_reviewed_human_symbols.tsv').read_bytes())


def table(raw, required):
    reader = csv.DictReader(StringIO(raw.decode('utf-8-sig')), delimiter='\t')
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not set(required) <= set(reader.fieldnames):
        raise ValueError('Missing or duplicate registry columns.')
    rows = list(reader)
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('Empty or malformed registry.')
    return rows


def split(value, delimiter='|'):
    return [v.strip() for v in value.split(delimiter) if v.strip()]


class Registry:
    def __init__(self, hgnc, uniprot):
        self.genes = {}; self.proteins = {}; self.primary = defaultdict(set)
        self.relations = defaultdict(list); self.by_gene = defaultdict(set)
        for number, row in enumerate(table(hgnc, ['hgnc_id', 'symbol', 'status', 'prev_symbol', 'alias_symbol', 'uniprot_ids', 'entrez_id', 'ensembl_gene_id', 'locus_type']), 2):
            gid = row['hgnc_id']
            if not re.fullmatch(r'HGNC:[1-9][0-9]*', gid) or gid in self.genes or not row['symbol']:
                raise ValueError('Invalid or duplicate HGNC identity.')
            self.genes[gid] = {**row, 'source_row': number}
            if row['status'] != 'Approved':
                continue
            self.primary[row['symbol']].add(gid)
            for field in ['prev_symbol', 'alias_symbol']:
                for symbol in split(row[field]):
                    self.relations[symbol].append({'hgnc_id': gid, 'source': 'HGNC', 'field': field, 'source_row': number})
        columns = ['Entry', 'Gene Names (primary)', 'Gene Names (synonym)', 'HGNC', 'GeneID', 'Organism (ID)', 'Protein names']
        for number, row in enumerate(table(uniprot, columns), 2):
            accession = row['Entry']
            if not re.fullmatch(r'[A-Z0-9]{6}(?:[A-Z0-9]{4})?', accession) or accession in self.proteins or row['Organism (ID)'] != '9606':
                raise ValueError('Invalid, duplicate or non-human UniProt identity.')
            gids = split(row['HGNC'], ';')
            protein = {**row, 'source_row': number, 'hgnc_ids': gids, 'ncbi_gene_ids': split(row['GeneID'], ';')}
            self.proteins[accession] = protein
            for gid in gids:
                if gid not in self.genes or self.genes[gid]['status'] != 'Approved':
                    continue
                self.by_gene[gid].add(accession)
                for field in ['Gene Names (primary)', 'Gene Names (synonym)']:
                    for symbol in row[field].split():
                        self.relations[symbol].append({'hgnc_id': gid, 'source': 'UniProt', 'field': field, 'accession': accession, 'source_row': number})

    def resolve(self, symbol):
        relations = self.relations.get(symbol, [])
        primary = self.primary.get(symbol, set())
        candidates = sorted(primary or {r['hgnc_id'] for r in relations})
        status = ('approved_symbol' if primary else 'unique_registry_relation') if len(candidates) == 1 else ('ambiguous_registry_relation' if candidates else 'unresolved_symbol')
        return {'status': status, 'hgnc_id': candidates[0] if len(candidates) == 1 else None,
                'candidate_hgnc_ids': candidates, 'matched_relations': relations,
                'candidate_genes': [{'hgnc_id': gid, 'approved_symbol': self.genes[gid]['symbol']} for gid in candidates],
                'shadowed_relation_candidates': sorted({r['hgnc_id'] for r in relations} - set(primary)) if primary else []}

    def products(self, gid):
        gene = self.genes[gid]; declared = set(split(gene['uniprot_ids']))
        products = []
        for accession in sorted(declared | self.by_gene[gid]):
            protein = self.proteins.get(accession)
            mismatch = bool(protein and (gid not in protein['hgnc_ids'] or
                            (gene['entrez_id'] and protein['ncbi_gene_ids'] and gene['entrez_id'] not in protein['ncbi_gene_ids'])))
            status = 'registry_conflict' if mismatch else ('reviewed_human_hgnc_match' if protein else 'hgnc_link_not_confirmed_in_reviewed_human')
            products.append({'uniprot_id': 'UniProtKB:' + accession, 'status': status,
                             'hgnc_declares_accession': accession in declared,
                             'uniprot_hgnc_ids': protein['hgnc_ids'] if protein else [],
                             'shared_across_genes': len(protein['hgnc_ids']) > 1 if protein else None,
                             'protein_name': protein['Protein names'] if protein else None,
                             'uniprot_source_row': protein['source_row'] if protein else None})
        return products


def map_matrix(raw, graph, registry):
    original = inspect_matrix(raw, graph)  # Same strict finite/missing-value contract as the first pilot.
    matrix = list(csv.reader(StringIO(raw.decode('utf-8-sig')), delimiter='\t'))
    mappings = []; gene_rows = defaultdict(list)
    for number, row in enumerate(matrix[1:], 2):
        resolution = registry.resolve(row[0]); gid = resolution['hgnc_id']
        gene = registry.genes.get(gid, {})
        values = [float(x) for x in row[1:] if x not in {'NA', '', 'NaN'}]
        products = registry.products(gid) if gid else []
        entry = {'reported_symbol': row[0], 'matrix_row': number, 'measurement_sha256': digest(row),
                 **resolution, 'approved_symbol': gene.get('symbol'), 'ncbi_gene_id': gene.get('entrez_id'),
                 'ensembl_gene_id': gene.get('ensembl_gene_id'), 'locus_type': gene.get('locus_type'),
                 'hgnc_source_row': gene.get('source_row'), 'protein_candidates': products,
                 'measurement_granularity': 'gene', 'protein_specific_assignment': False,
                 'observed_samples': len(values), 'missing_samples': len(row) - 1 - len(values),
                 'median_reported_log2_ratio': statistics.median(values) if values else None}
        if gid:
            gene_rows[gid].append(number)
        mappings.append(entry)
    # Distinct reported rows resolving to one gene remain separate; never average or duplicate them.
    for row in mappings:
        row['rows_for_resolved_gene'] = gene_rows.get(row['hgnc_id'], [])
        row['identifier_eligible'] = bool(row['hgnc_id'] and row['observed_samples'] and len(row['rows_for_resolved_gene']) == 1)
        row['protein_context_eligible'] = bool(row['identifier_eligible'] and row['locus_type'] in {'gene with protein product', 'complex locus constituent'} and
                                               any(p['status'] == 'reviewed_human_hgnc_match' for p in row['protein_candidates']))
    by_gene = dict(gene_rows)
    pharos = []
    for node in graph['nodes']:
        if not node['id'].startswith('UniProtKB:'):
            continue
        accession = node['id'].split(':', 1)[1]; protein = registry.proteins.get(accession)
        gids = protein['hgnc_ids'] if protein else []
        valid = [g for g in gids if g in registry.genes and registry.genes[g]['status'] == 'Approved']
        matched = sorted({n for g in valid for n in by_gene.get(g, [])})
        state = ('mapped_measured_gene' if matched else 'no_unambiguous_measured_gene') if len(valid) == 1 else ('ambiguous_protein_gene' if valid else 'protein_not_resolved_in_reviewed_human_registry')
        pharos.append({'pharos_id': node['id'], 'reported_symbol': node.get('sym'), 'hgnc_ids': valid,
                       'matrix_rows': matched, 'status': state, 'protein_specific_assignment': False})
    counts = Counter(r['status'] for r in mappings)
    stats = {'measured_gene_rows': len(mappings), 'sample_columns': original['sample_columns'],
             'observed_values': original['observed_values'], 'missing_values': original['missing_values'],
             'mapping_status_counts': dict(sorted(counts.items())),
             'resolved_gene_rows': sum(bool(r['hgnc_id']) for r in mappings),
             'unresolved_or_ambiguous_rows': sum(not r['hgnc_id'] for r in mappings),
             'identifier_eligible_gene_rows': sum(r['identifier_eligible'] for r in mappings),
             'protein_context_eligible_gene_rows': sum(r['protein_context_eligible'] for r in mappings),
             'resolved_rows_with_multiple_protein_candidates': sum(len(r['protein_candidates']) > 1 for r in mappings if r['hgnc_id']),
             'resolved_rows_without_confirmed_reviewed_product': sum(not any(p['status'] == 'reviewed_human_hgnc_match' for p in r['protein_candidates']) for r in mappings if r['hgnc_id']),
             'duplicate_resolved_gene_groups': sum(len(rows) > 1 for rows in gene_rows.values()),
             'pharos_proteins': len(pharos), 'pharos_proteins_linked_to_measured_gene': sum(r['status'] == 'mapped_measured_gene' for r in pharos),
             'measured_rows_linked_to_pharos': len({n for r in pharos if r['status'] == 'mapped_measured_gene' for n in r['matrix_rows']}),
             'original_exact_symbol_rows': original['cohort_gene_rows_matching_pharos'],
             'labels_created': 0, 'graph_assertions_created': 0, 'protein_specific_measurements_created': 0}
    return mappings, pharos, stats


def map_cohort(cptac, pharos_run, registry_path, output):
    sidecar = load_cptac(cptac); manifest, registry = load_registry(registry_path)
    _, _, graph = read_run(pharos_run)
    if sidecar['pharos_snapshot_sha256'] != graph['snapshot_sha256']:
        raise ValueError('CPTAC and Pharos controls differ.')
    raw = (Path(cptac) / 'measurements.cct').read_bytes()
    rows, pharos, stats = map_matrix(raw, graph, registry)
    out = new_output(output, cptac, pharos_run, registry_path)
    # Keep the mapping inputs in the export; no full Pharos evidence graph is needed for an identifier join.
    inputs = ['measurements.cct', 'source_pharos_identifiers.json', 'registry/manifest.json']
    (out / 'measurements.cct').write_bytes(raw)
    write_json(out / 'source_pharos_identifiers.json', {
        'snapshot_sha256': graph['snapshot_sha256'],
        'nodes': [{'id': n['id'], 'sym': n.get('sym')} for n in graph['nodes'] if n['id'].startswith('UniProtKB:')]})
    (out / 'registry').mkdir()
    for name in ['manifest.json', *SOURCES]:
        (out / 'registry' / name).write_bytes((Path(registry_path) / name).read_bytes())
        if name != 'manifest.json':
            inputs.append('registry/' + name)
    write_json(out / 'mappings.json', rows); write_json(out / 'pharos_crosswalk.json', pharos)
    # Small TSVs are review/export conveniences; JSON preserves every registry relation and candidate.
    with (out / 'mapping_review.tsv').open('w', newline='') as f:
        writer = csv.writer(f, delimiter='\t'); writer.writerow(['matrix_row', 'reported_symbol', 'status', 'hgnc_id', 'approved_symbol', 'candidate_hgnc_ids', 'protein_candidates', 'identifier_eligible', 'protein_context_eligible'])
        for row in rows:
            writer.writerow([row['matrix_row'], row['reported_symbol'], row['status'], row['hgnc_id'] or '', row['approved_symbol'] or '', '|'.join(row['candidate_hgnc_ids']), '|'.join(p['uniprot_id'] for p in row['protein_candidates']), row['identifier_eligible'], row['protein_context_eligible']])
    cohort = {'format': 'biograph-steward.measured-gene-cohort.v1', 'taxon_id': 9606,
              'selection': 'Every unambiguously resolved measured gene with an observed value and no duplicate gene rows; no disease-label selection. Identifier eligibility is not scientific validation or benchmark readiness.',
              'members': [{'hgnc_id': r['hgnc_id'], 'matrix_row': r['matrix_row'], 'measurement_sha256': r['measurement_sha256'], 'protein_context_eligible': r['protein_context_eligible']} for r in rows if r['identifier_eligible']],
              'labels': None, 'matrix_sha256': sidecar['matrix_sha256'], 'registry_sha256': manifest['registry_sha256']}
    cohort['cohort_sha256'] = digest(cohort); write_json(out / 'cohort.json', cohort)
    report = {'format': 'biograph-steward.cptac-mapping.v1', 'created_at': utcnow(), 'policy': POLICY,
              'cptac_sidecar_sha256': sidecar['sidecar_sha256'], 'matrix_sha256': sidecar['matrix_sha256'],
              'pharos_snapshot_sha256': graph['snapshot_sha256'], 'registry_sha256': manifest['registry_sha256'],
              'cohort_sha256': cohort['cohort_sha256'], 'registry_sources': manifest['sources'], 'summary': stats,
              'unresolved': [r for r in rows if not r['hgnc_id']],
              'policy_details': ['Exact approved HGNC symbols take precedence; other exact previous/alias/UniProt gene names must identify one approved human HGNC gene across both registries.',
                                 'No fuzzy matching, case conversion, best-candidate ranking or arbitrary protein selection.',
                                 'Reviewed human protein candidates require an agreeing HGNC cross-reference and, where supplied, NCBI Gene ID; unconfirmed/conflicting links stay visible.',
                                 'Multiple protein products share one gene measurement; shared products and duplicate gene rows do not create independent observations.',
                                 'Protein context eligibility requires an agreeing reviewed human product and a protein-coding or complex-locus-constituent HGNC record; it does not establish protein-specific abundance or benchmark readiness.',
                                 'All input rows are accounted for. Ambiguities need assay-level IDs or peptides; absence from this matrix is not a negative label.'],
              'scientific_improvement_established': False, 'scientific_accuracy': None, 'human_scientific_labels': 0,
              'files': {name: sha(out / name) for name in ['mappings.json', 'pharos_crosswalk.json', 'mapping_review.tsv', 'cohort.json', *inputs]}}
    report['result_sha256'] = digest(report); write_json(out / 'metrics.json', report)
    (out / 'report.html').write_text(render_mapping(report, rows, pharos), encoding='utf-8')
    return report


def verify_mapping(path):
    path = Path(path); report = json.loads((path / 'metrics.json').read_text())
    expected = {'mappings.json', 'pharos_crosswalk.json', 'mapping_review.tsv', 'cohort.json',
                'measurements.cct', 'source_pharos_identifiers.json', 'registry/manifest.json',
                *('registry/' + name for name in SOURCES)}
    if report['result_sha256'] != digest({k: v for k, v in report.items() if k != 'result_sha256'}) or set(report['files']) != expected:
        raise ValueError('Mapping manifest changed.')
    for name, value in report['files'].items():
        if (path / name).is_symlink() or sha(path / name) != value:
            raise ValueError('Mapping artifact changed.')
    rows = json.loads((path / 'mappings.json').read_text()); cohort = json.loads((path / 'cohort.json').read_text())
    if (cohort['cohort_sha256'] != digest({k: v for k, v in cohort.items() if k != 'cohort_sha256'}) or
            cohort['cohort_sha256'] != report['cohort_sha256'] or len(rows) != report['summary']['measured_gene_rows'] or
            len({r['matrix_row'] for r in rows}) != len(rows) or len(cohort['members']) != report['summary']['identifier_eligible_gene_rows']):
        raise ValueError('Mapping cohort inventory changed.')
    manifest, registry = load_registry(path / 'registry')
    graph = json.loads((path / 'source_pharos_identifiers.json').read_text())
    reproduced, crosswalk, stats = map_matrix((path / 'measurements.cct').read_bytes(), graph, registry)
    if (reproduced != rows or stats != report['summary'] or crosswalk != json.loads((path / 'pharos_crosswalk.json').read_text()) or
            manifest['registry_sha256'] != report['registry_sha256'] or graph['snapshot_sha256'] != report['pharos_snapshot_sha256'] or
            sha(path / 'measurements.cct') != report['matrix_sha256'] or cohort['members'] != [
                {'hgnc_id': r['hgnc_id'], 'matrix_row': r['matrix_row'], 'measurement_sha256': r['measurement_sha256'], 'protein_context_eligible': r['protein_context_eligible']} for r in rows if r['identifier_eligible']]):
        raise ValueError('Mapping does not reproduce from its frozen inputs.')
    return report


def render_mapping(report, rows, pharos):
    esc = lambda x: escape(str(x), quote=True)
    def table_rows(entries):
        return ''.join('<tr><td>' + esc(r['reported_symbol']) + '</td><td>' + esc(r['status']) + '</td><td>' + esc(r['approved_symbol'] or r['candidate_genes']) + '</td><td>' + esc([p['uniprot_id'] + ' (' + p['status'] + ')' for p in r['protein_candidates']]) + '</td></tr>' for r in entries)
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>CPTAC measured cohort mapping</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.6 system-ui}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{padding:12px;border:1px solid #ccd;margin:12px 0}</style>'
            '<h1>CPTAC measured cohort mapping</h1><p>Every matrix row is accounted for. Gene-level ratios remain gene-level measurements. Identifier resolution supplies no biological gold labels or evidence of graph improvement.</p>'
            '<pre>' + esc(json.dumps(report['summary'], indent=2)) + '</pre><h2>Unresolved identities</h2>'
            '<p>All candidates remain visible. Original assay identifiers or peptides are needed to distinguish them.</p><table><tr><th>Source symbol</th><th>Status</th><th>Gene candidates</th><th>Protein candidates</th></tr>' + table_rows(report['unresolved']) + '</table>'
            '<h2>Multiple products from one gene</h2><table><tr><th>Source symbol</th><th>Status</th><th>Approved gene</th><th>Candidate products, no separate measurements</th></tr>' + table_rows([r for r in rows if len(r['protein_candidates']) > 1]) + '</table>'
            '<details><summary>Full gene crosswalk</summary><table><tr><th>Source symbol</th><th>Status</th><th>Approved gene / candidates</th><th>Protein candidates</th></tr>' + table_rows(rows) + '</table></details>'
            '<details><summary>Pharos cohort crosswalk</summary><pre>' + esc(json.dumps(pharos, indent=2)) + '</pre></details>'
            '<details><summary>Sources, checksums and policy</summary><pre>' + esc(json.dumps(report, indent=2)) + '</pre></details></html>')
