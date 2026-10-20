"""Processed CPTAC measurements as a provenance-bearing sidecar, not response labels."""
from collections import defaultdict
import csv
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import statistics

from .client import digest, utcnow, write_json
from .literature import fetch
from .reviews import read_run

MATRIX = 'https://linkedomics.org/cptac-colon/Human__CPTAC_COAD__PNNL__Proteome__TMT__03_01_2017__BCM__Gene__Tumor_Normal_log2FC.cct'
STUDY = {'pdc_study_id': 'PDC000116', 'url': 'https://pdc.cancer.gov/pdc/study/PDC000116',
         'download_catalogue': 'https://www.linkedomics.org/data_download/CPTAC-COAD/',
         'publication_doi': '10.1016/j.cell.2019.03.030', 'assay': 'PNNL TMT gene-level proteome',
         'measurement': 'Source-reported tumor/normal log2 fold change', 'row_identity': 'reported gene symbol',
         'mapping_note': 'The publication links this study to LinkedOmics final matrices. Related proteome/phosphoproteome accessions are not independent cohorts.'}


def inspect_matrix(raw, graph):
    rows = csv.reader(StringIO(raw.decode('utf-8-sig')), delimiter='\t')
    header = next(rows, [])
    if len(header) < 3 or header[0] != 'attrib_name' or len(set(header)) != len(header) or any(not x.strip() for x in header):
        raise ValueError('Expected a unique sample header in a LinkedOmics CCT matrix.')
    by_symbol = defaultdict(list)
    for n in graph['nodes']:
        if n['id'].startswith('UniProtKB:') and n.get('sym'):
            by_symbol[n['sym']].append(n['id'])
    seen = set(); matched = []; missing = observed = 0
    for number, row in enumerate(rows, 2):
        if len(row) != len(header) or not row[0] or row[0] in seen:
            raise ValueError(f'Duplicate gene or inconsistent matrix row {number}.')
        seen.add(row[0]); values = []
        for value in row[1:]:
            if value in {'NA', '', 'NaN'}:
                missing += 1; continue
            v = float(value)
            if not math.isfinite(v):
                raise ValueError('Non-finite measurement; missing values must be explicit.')
            observed += 1; values.append(v)
        if row[0] in by_symbol:
            matched.append({'gene_symbol': row[0], 'pharos_ids': sorted(by_symbol[row[0]]),
                            'mapping_status': 'exact_unique_cohort_symbol' if len(by_symbol[row[0]]) == 1 else 'ambiguous_cohort_symbol',
                            'nonmissing_samples': len(values), 'missing_samples': len(row) - 1 - len(values),
                            'median_reported_log2_ratio': statistics.median(values) if values else None,
                            'matrix_row': number, 'measurement_sha256': digest(row), 'experimental_independence': 'not_established'})
    if not seen:
        raise ValueError('The matrix has no measurements.')
    return {'gene_rows': len(seen), 'sample_columns': len(header) - 1, 'sample_ids': header[1:],
            'observed_values': observed, 'missing_values': missing,
            'cohort_gene_rows_matching_pharos': len(matched), 'pharos_proteins': sum(map(len, by_symbol.values())),
            'matched_measurements': matched, 'other_reported_genes': len(seen) - len(matched),
            'unmatched_pharos_symbols': sorted(set(by_symbol) - seen),
            'population_policy': 'All source matrix genes retained; cohort not selected by Pharos disease-association labels.',
            'mapping_policy': 'Exact reported gene symbol within frozen Pharos cohort only; no fuzzy aliases or whole-proteome UniProt mapping claimed.',
            'labels_created': 0, 'graph_assertions_created': 0}


def prepare_cptac(pharos_run, output, *, matrix=None, transport=None):
    source = Path(pharos_run).resolve(); output = Path(output).resolve()
    if output == source or source in output.parents or output in source.parents or output.exists():
        raise ValueError('Choose a new output outside the frozen source.')
    snapshot, _, graph = read_run(source)
    raw = Path(matrix).read_bytes() if matrix is not None else (transport or fetch)(MATRIX)
    if len(raw) > 20_000_000:
        raise ValueError('Matrix exceeds 20 MB.')
    analysis = inspect_matrix(raw, graph)
    output.mkdir(parents=True); (output / 'measurements.cct').write_bytes(raw)
    # Pharos can already point to this underlying CPTAC study via LinkedOmicsKB.
    context = snapshot.get('targets', [])
    links = []
    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, str) and any(t in v.casefold() for t in ['linkedomics', 'cptac', STUDY['publication_doi']]):
                    links.append({'field': k, 'value': v})
                else: walk(v)
        elif isinstance(value, list):
            for v in value: walk(v)
    walk(context)
    result = {'format': 'biograph-steward.cptac-measurement-sidecar.v1', 'created_at': utcnow(),
              'study': STUDY, 'matrix_url': MATRIX, 'matrix_sha256': hashlib.sha256(raw).hexdigest(),
              'ingest_mode': 'provided_file' if matrix is not None else 'live_download',
              'source_identity_verification': 'Caller-declared source; only provided bytes verified.' if matrix is not None else 'Retrieved from the fixed source matrix URL.',
              'pharos_snapshot_sha256': graph['snapshot_sha256'], 'analysis': analysis,
              'pharos_cptac_or_linkedomics_mentions': links,
              'overlap_classification': 'Additional quantitative detail; independence and release-level overlap unresolved.',
              'rights': 'Retain source attribution and study-specific data terms; no new blanket license assigned.',
              'scientific_improvement_established': False,
              'limitations': ['Gene-level abundance is not causal disease evidence or a drug-response label.',
                             'Matching a Pharos symbol is a bounded cohort crosswalk, not a verified whole-proteome identifier map.',
                             'PDC and LinkedOmics representations of the same study must not be counted as independent experiments.']}
    result['sidecar_sha256'] = digest(result); write_json(output / 'sidecar.json', result)
    return result


def load_cptac(path):
    path = Path(path); r = json.loads((path / 'sidecar.json').read_text())
    if (r['sidecar_sha256'] != digest({k: v for k, v in r.items() if k != 'sidecar_sha256'}) or
            hashlib.sha256((path / 'measurements.cct').read_bytes()).hexdigest() != r['matrix_sha256']):
        raise ValueError('Frozen CPTAC sidecar changed.')
    return r
