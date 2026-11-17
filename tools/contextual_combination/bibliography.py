"""Post-seal descriptive publication-year inventory for every support PMID.

This does not redefine references, recover unpublished claims, score models or
select favorable cases. Official Europe PMC lite metadata is identity checked.
Provider-normalized dates may be imputed; only publication YEAR bins are used.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode

ENDPOINT = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'
PMID = re.compile(r'[1-9][0-9]{0,9}')
YEAR_BINS = ('pubYear_through_2025', 'pubYear_cutoff_year_2026', 'pubYear_after_2026',
             'pubYear_missing_or_invalid', 'metadata_missing_duplicate_or_error')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def require(condition, message):
    if not condition:
        raise ValueError('Bibliographic metadata audit: ' + message)


def reference_inventory(report_path, expected_sha256, forecast_seal_sha256):
    require(sha(report_path) == expected_sha256, 'completed provenance report changed.')
    report = json.loads(Path(report_path).read_text())
    require(report['forecast_seal_sha256'] == forecast_seal_sha256
            and report['scores_labels_models_choices_or_thresholds_changed'] is False,
            'expected post-seal descriptive provenance required.')
    views, files = {}, {str(report_path): expected_sha256}
    for view in ('native', 'fixed_T0'):
        source = report['views'][view]
        path = Path(source['complete_label_support_file'])
        require(sha(path) == source['sha256'], 'complete all-positive support file changed.')
        files[str(path)] = source['sha256']
        references, seen = set(), set()
        with path.open() as stream:
            for line in stream:
                row = json.loads(line)
                key = (row['accession'], row['GO_ID'])
                require(key not in seen, 'duplicate residual-positive pair in support inventory.')
                seen.add(key)
                # Scores, prediction success and thresholds are never read.
                for match in row['positive_support']:
                    references.update(match['references'])
        literal_pmids = {ref for ref in references if ref.startswith('PMID:')}
        require(len(seen) == source['aggregate']['labels']
                and len(literal_pmids) == source['aggregate']['distinct_literal_PMID_identifiers'],
                'all residual labels/support PMIDs must remain in the inventory.')
        valid = sorted({ref[5:] for ref in literal_pmids if PMID.fullmatch(ref[5:])}, key=int)
        views[view] = {'labels_in_complete_private_support': len(seen), 'pmids': valid,
            'literal_PMID_references': len(literal_pmids),
            'invalid_PMID_literals': sorted(ref for ref in literal_pmids if not PMID.fullmatch(ref[5:])),
            'non_PMID_reference_count': len(references - literal_pmids)}
    return views, files


def batch_url(pmids):
    require(0 < len(pmids) <= 50 and len(pmids) == len(set(pmids))
            and all(PMID.fullmatch(p) for p in pmids), 'one to50 distinct literal PMIDs required.')
    query = '(' + ' OR '.join('EXT_ID:' + p for p in pmids) + ') AND SRC:MED'
    return ENDPOINT + '?' + urlencode({'query': query, 'format': 'json', 'resultType': 'lite',
                                       'pageSize': 1000, 'synonym': 'false'})


def contains_forbidden_text(value):
    if isinstance(value, dict):
        return bool(set(value) & {'abstractText', 'abstractList', 'fullTextXML', 'body'}) or any(
            contains_forbidden_text(v) for v in value.values())
    return isinstance(value, list) and any(contains_forbidden_text(v) for v in value)


def parse_batch(payload, requested):
    """Exact source/identity matching; duplicate records remain unresolved."""
    require(not contains_forbidden_text(payload), 'lite metadata only; unexpected text payload.')
    require(payload.get('request', {}).get('resultType', 'lite') == 'lite', 'lite response required.')
    rows = payload.get('resultList', {}).get('result', [])
    require(isinstance(rows, list), 'result list required.')
    grouped = defaultdict(list)
    unexpected, wrong_source = [], []
    for row in rows:
        identifier = str(row.get('id', ''))
        if row.get('source') != 'MED':
            wrong_source.append({'id': identifier, 'source': row.get('source')})
        elif identifier not in requested:
            unexpected.append(identifier)
        else:
            grouped[identifier].append(row)
    records = {}
    for identifier in requested:
        found = grouped[identifier]
        if len(found) != 1:
            records[identifier] = {'status': 'not_returned' if not found else 'duplicate_provider_records',
                                   'returned_matching_records': len(found)}
            continue
        row = found[0]
        records[identifier] = {'status': 'matched_exact_MED_ID', 'id': identifier, 'source': 'MED',
            'provider_pubYear_literal': row.get('pubYear'),
            'provider_normalized_firstPublicationDate_literal': row.get('firstPublicationDate'),
            'provider_firstIndexDate_literal_not_publication': row.get('firstIndexDate'),
            'firstPublicationDate_precision_or_imputation_known': False}
    audit = {'requested': len(requested), 'provider_hit_count': payload.get('hitCount'),
             'returned_rows': len(rows), 'wrong_source_rows': wrong_source,
             'unexpected_MED_IDs': unexpected,
             'status_counts': dict(Counter(row['status'] for row in records.values()))}
    return records, audit


def retrieve(pmids, cache, *, transport=None):
    """Reuse bounded app transport; cache every attempt and exact query scope."""
    if transport is None:
        from biograph_steward.literature import fetch
        transport = fetch
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=False)
    records, batches = {}, []
    for number, offset in enumerate(range(0, len(pmids), 50), 1):
        requested = list(pmids[offset:offset + 50])
        url = batch_url(requested)
        attempts, raw = [], None
        for attempt in range(3):
            try:
                raw = transport(url)
                payload = json.loads(raw)
                batch_records, audit = parse_batch(payload, requested)
                attempts.append({'attempt': attempt + 1, 'status': 'received_lite_metadata'})
                break
            except Exception as error:
                attempts.append({'attempt': attempt + 1, 'status': 'failed',
                                 'error_type': type(error).__name__, 'error': str(error)[:500]})
                raw = None
                if attempt < 2:
                    time.sleep(2 ** attempt)
        if raw is None:
            batch_records = {p: {'status': 'request_error'} for p in requested}
            audit = {'requested': len(requested), 'returned_rows': 0,
                     'status_counts': {'request_error': len(requested)}}
        else:
            response = cache / f'batch_{number:03d}_lite_response.json'
            with response.open('xb') as stream:
                stream.write(raw)
            audit.update(response_file=str(response), response_sha256=sha(response))
        record = {'url': url, 'requested_pmids': requested, 'attempts': attempts,
                  'audit': audit, 'records': batch_records}
        path = cache / f'batch_{number:03d}_identity_checked.json'
        write(path, record)
        batches.append({'file': str(path), 'sha256': sha(path), 'status_counts': audit['status_counts'],
            'wrong_source_rows': len(audit.get('wrong_source_rows', [])),
            'unexpected_MED_rows': len(audit.get('unexpected_MED_IDs', []))})
        require(not (set(records) & set(batch_records)), 'batch request identities overlap.')
        records.update(batch_records)
    require(set(records) == set(pmids), 'complete exact PMID denominator required.')
    return records, batches


def year_bin(record):
    if record.get('status') != 'matched_exact_MED_ID':
        return YEAR_BINS[4]
    literal = record.get('provider_pubYear_literal')
    value = str(literal) if type(literal) in (str, int) else ''
    if not re.fullmatch(r'[1-9][0-9]{3}', value):
        return YEAR_BINS[3]
    year = int(value)
    return YEAR_BINS[0] if year <= 2025 else YEAR_BINS[1] if year == 2026 else YEAR_BINS[2]


def public_year_inventory(views, records):
    """Aggregate proportions retain missing metadata in every denominator."""
    result = {}
    for view, source in views.items():
        pmids = source['pmids']
        bins = Counter(year_bin(records[p]) for p in pmids)
        statuses = Counter(records[p]['status'] for p in pmids)
        result[view] = {'distinct_requested_PMID_identifiers': len(pmids),
            'literal_PMID_reference_count': source['literal_PMID_references'],
            'invalid_PMID_literal_count_not_queried': len(source['invalid_PMID_literals']),
            'distinct_non_PMID_reference_identifiers_not_queried': source['non_PMID_reference_count'],
            'complete_private_residual_positive_labels': source['labels_in_complete_private_support'],
            'identity_metadata_status_counts': dict(statuses),
            'year_bins': {key: {'count': bins[key], 'fraction_of_all_requested_PMIDs':
                bins[key] / len(pmids) if pmids else None} for key in YEAR_BINS},
            'year2026_split_around_April10': False,
            'publication_years_are_independent_experiment_counts': False}
    return result


def run(config, output, *, transport=None):
    require(config.get('format') == 'biograph-steward.postseal-bibliographic-inventory.v1'
            and config.get('parent_authorized_descriptive_metadata_only') is True,
            'explicit post-seal metadata-only authorization required.')
    if transport is None:
        require(config.get('user_authorized_sending_selected_PMIDs_to_EuropePMC') is True,
                'explicit user approval is required before exporting the selected PMID set to Europe PMC; descriptive research authorization alone is insufficient.')
    views, inputs = reference_inventory(config['provenance_report'], config['provenance_report_sha256'],
                                        config['forecast_seal_sha256'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    pmids = sorted(set().union(*(set(v['pmids']) for v in views.values())), key=int)
    # Freeze complete reference-ID universe before the first public API call.
    write(output / 'private_reference_inventory.json', {'views': views, 'union_pmids': pmids,
        'source_file_pins': inputs, 'model_score_or_threshold_selection': False})
    records, batches = retrieve(pmids, output / 'private_lite_metadata_cache', transport=transport)
    write(output / 'private_exact_MED_metadata.json', records)
    report = {'format': 'biograph-steward.aggregate-publication-year-inventory.v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'forecast_seal_sha256': config['forecast_seal_sha256'],
        'provenance_report_sha256': config['provenance_report_sha256'],
        'distinct_PMID_union_requested': len(pmids), 'views': public_year_inventory(views, records),
        'API_batches': len(batches), 'API_status_counts': dict(Counter(r['status'] for r in records.values())),
        'API_wrong_source_rows_not_used': sum(b['wrong_source_rows'] for b in batches),
        'API_unrequested_MED_rows_not_used': sum(b['unexpected_MED_rows'] for b in batches),
        'source_input_pins': inputs, 'private_cache_receipt_pins': batches,
        'metadata_only_no_abstract_or_fulltext_requests': True,
        'new_accuracy_endpoint_threshold_choice_or_model_fit': False,
        'publication_scope': 'Aggregate year/status proportions only; per-ID metadata and case mappings stay private.',
        'chronology': 'Descriptive metadata inventory after complete forecasts, fixed evaluation and raw-source provenance; no model-dependent PMID selection.',
        'limitations': ['pubYear is provider publication-year metadata; it does not date an experiment.',
            'firstPublicationDate is retained privately as provider-normalized and may be algorithmically imputed for partial dates; no precise day-level lag is inferred.',
            'firstIndexDate is indexing, not publication; it is not used for bins.',
            'All2026 publication years remain cutoff-year ambiguous; no before/after-April10 claim is inferred.',
            'A distinct PMID is not a count of independent studies or biological experiments; multiple source rows/labels can share one paper.',
            'Invalid/missing/duplicate/error metadata and non-PMID references remain explicit coverage limits.',
            'This inventory is not the official author-publishedaftert0 benchmark and does not alter or rescore reference labels.'],
        'sources': ['https://dev.europepmc.org/RestfulWebService',
            'https://dev.europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf',
            'https://www.biorxiv.org/content/10.64898/2026.04.27.716980v2']}
    write(output / 'aggregate_report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_text()), args.output)


if __name__ == '__main__':
    main()
