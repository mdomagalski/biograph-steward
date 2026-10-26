#!/usr/bin/env python3
"""Reconcile a focused Pharos PPI retrieval against the sealed identity audit.

Reads identity-only audit outputs, never author assay tables. Provider bundles
and property names remain separate; numeric properties are not calibrated or
combined into an interaction confidence. Exact accession matches are reported
without silently accepting an identity redirect as the assayed construct.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_lambourne_reference import COMMIT, PANEL, pair
from audit_pharos_inventory import verified_chunk, source_rows, retained_rows
from retrieve_pharos_inventory import accession_inventory, read_json, verify_sealed
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.retrieval import metadata_query, page_query, reported_count

GROUP = 'published_af_rf_nominations'
IDENTITY_FIELDS = {'source_row', 'uniprot_a', 'uniprot_b', 'ad_orf_id', 'db_orf_id',
                   'source_dataset_column_5', 'source_dataset_column_6',
                   'in_biorxiv_version', 'in_published_version'}
REFERENCE_NAME = re.compile(r'pmid|pubmed|reference|publication', re.I)


def ordinary(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Audit inputs must be ordinary saved files.')
    return path


def prior_identity_audit(folder, expected_report_sha):
    folder = Path(folder)
    report_path = ordinary(folder / 'report.json')
    if sha(report_path) != expected_report_sha:
        raise ValueError('Prior identity report differs from its declared hash.')
    report = read_json(report_path)
    if (report.get('format') != 'biograph-steward.lambourne-identity-audit.v1'
            or report.get('author_commit') != COMMIT
            or report.get('outcome_fields_decoded') is not False):
        raise ValueError('Expected the reviewed outcome-blind identity audit.')
    for name in ('identity_rows.json', 'pair_exposure.json'):
        if sha(ordinary(folder / name)) != report['output_sha256'][name]:
            raise ValueError('Prior identity output differs from its report hash.')
    rows = read_json(folder / 'identity_rows.json')
    if any(set(row) != IDENTITY_FIELDS for row in rows):
        raise ValueError('Identity-only row schema changed; no assay fields accepted.')
    selected = [r for r in rows if r['source_dataset_column_5'] ==
                r['source_dataset_column_6'] == 'Zhang_et_al' and r['in_published_version'] == 'True']
    pairs = [pair(r['uniprot_a'], r['uniprot_b']) for r in selected
             if r['uniprot_a'] and r['uniprot_b']]
    expected = report['groups'][GROUP]
    if (len(selected) != expected['source_rows'] or len(pairs) != len(selected)
            or len(set(pairs)) != len(pairs)
            or len(pairs) != expected['distinct_unordered_product_pairs']):
        raise ValueError('Published identity denominator differs from the prior audit.')
    previous = read_json(folder / 'pair_exposure.json')
    by_pair = {tuple(r['products']): r for r in previous}
    if len(by_pair) != len(previous) or any(p not in by_pair for p in pairs):
        raise ValueError('Prior pair exposure lacks a unique record for every published pair.')
    baseline = [by_pair[p] for p in pairs]
    check = {
        'pharos_status_pairs': dict(Counter(r['pharos_status'] for r in baseline)),
        'pharos_retained_match_pairs': sum(r['pharos_retained_match'] for r in baseline),
        'huri_either_mapping_match_pairs': sum(r['huri_registry_projected_match'] or
                                              r['huri_author_crosswalk_match'] for r in baseline),
        'inmc_either_mapping_match_pairs': sum(r['inmc_registry_projected_match'] or
                                              r['inmc_author_crosswalk_match'] for r in baseline),
    }
    if any(expected[k] != v for k, v in check.items()):
        raise ValueError('Prior pair flags do not reproduce their aggregate report.')
    return report, selected, {p: by_pair[p] for p in pairs}, check


def lookup_header(folder, prior, rows):
    folder = Path(folder)
    for name in ('plan.json', 'source.json', 'summary.json', 'context_targets.json'):
        ordinary(folder / name)
    plan, source, saved = [verify_sealed(read_json(folder / name))
                           for name in ('plan.json', 'source.json', 'summary.json')]
    inventory, ids = accession_inventory(folder / 'context_targets.json')
    products = sorted({r[k] for r in rows for k in ('uniprot_a', 'uniprot_b')})
    if (inventory.get('format') != 'biograph-steward.lambourne-ppi-lookup-candidate-inventory.v1'
            or inventory.get('author_commit') != prior['author_commit']
            or inventory.get('author_panel_sha256') != prior['author_files_sha256'][PANEL]
            or ids != products or sha(folder / 'context_targets.json') != plan['inventory_sha256']):
        raise ValueError('Lookup inventory is not the complete audited published identity population.')
    if (plan.get('profile') != 'ppi' or plan.get('ppi_confidence') != 400
            or plan['limits'].get('ppis') != 5000
            or any(value for key, value in plan['limits'].items() if key != 'ppis')):
        raise ValueError('Expected the declared PPI-only retrieval profile.')
    if (source.get('plan_sha256') != plan['content_sha256']
            or saved.get('plan_sha256') != plan['content_sha256']
            or source.get('endpoint') != plan['endpoint'] or plan.get('ppi_cohort') != ids):
        raise ValueError('Retrieval source, plan, population, and summary bindings differ.')
    if type(plan['chunk_size']) is not int or plan['chunk_size'] < 1 or not saved.get('retrieval_finished'):
        raise ValueError('A completed retrieval is required before auditing absence of matches.')
    names = [f'chunks/{offset:05d}.json' for offset in range(0, len(ids), plan['chunk_size'])]
    actual = {str(p.relative_to(folder)) for p in (folder / 'chunks').glob('*.json')}
    if actual != set(names) or set(saved['files']) != set(names):
        raise ValueError('Chunk files differ from the completed manifest.')
    for record in source['requests']:
        if record['endpoint'] != plan['endpoint']:
            raise ValueError('Source receipt endpoint differs from the plan.')
    versions = [r['response']['data']['dbVersion'] for r in source['requests']
                if 'dbVersion' in r['response']['data']]
    catalogs = [r['response']['data']['dataSourceCounts'] for r in source['requests']
                if 'dataSourceCounts' in r['response']['data']]
    if versions != [source['db_version']] or catalogs != [source['source_catalog']]:
        raise ValueError('Source version or catalog does not reproduce its response receipt.')
    return plan, source, saved, inventory, ids, names


def check_resolution(chunk):
    for row in chunk['target_resolution']:
        receipt = chunk['requests'][row['request_index']]
        pointer = row['response_pointer']
        if not re.fullmatch(r'/data/t[0-9]+', pointer):
            raise ValueError('Invalid identity response locator.')
        alias = pointer.split('/')[-1]
        data = receipt['response']['data']
        if ('ExplicitInventoryTargets' not in receipt['request']['query'] or alias not in data
                or receipt['request']['variables'].get('id' + alias[1:]) != row['requested_uniprot']
                or data[alias] != row['returned']):
            raise ValueError('Identity resolution does not reproduce its request/response receipt.')
        returned = row['returned']
        status = ('not_found' if returned is None else 'resolved'
                  if returned.get('uniprot') == row['requested_uniprot'] else 'identity_mismatch')
        if status != row['status']:
            raise ValueError('Identity status disagrees with the raw returned accession.')


def check_ppi_coverage(chunk, resolved):
    """Replay complete-count claims from the existing adapter's raw receipts.

    A zero-neighbor target has no PPI page, so its metadata receipt is required
    too. Reusing the query builders binds both count and row requests to the
    declared confidence filter instead of trusting an operation-name label.
    """
    metadata, pages = {}, defaultdict(list)
    for request_index, receipt in enumerate(chunk['requests']):
        request = receipt['request']
        is_metadata = bool(re.search(r'\bquery\s+ScopedMetadata\b', request['query']))
        is_page = bool(re.search(r'\bquery\s+Scoped_ppis\b', request['query']))
        if not is_metadata and not is_page:
            continue
        data, variables = receipt['response']['data'], request['variables']
        if not data or set(data) != {f't{i}' for i in range(len(data))}:
            raise ValueError('PPI coverage receipt has malformed response aliases.')
        ids = [variables.get(f'id{i}') for i in range(len(data))]
        if len(set(ids)) != len(ids) or any(uid not in resolved for uid in ids):
            raise ValueError('PPI coverage receipt includes an unexpected subject.')
        if is_metadata:
            expected_query, expected_variables = metadata_query(ids)
        else:
            tasks = [(uid, variables.get(f'skip{i}'), variables.get(f'top{i}'))
                     for i, uid in enumerate(ids)]
            if any(type(skip) is not int or skip < 0 or type(top) is not int or not 0 < top <= 5000
                   for _, skip, top in tasks):
                raise ValueError('PPI page request has invalid pagination bounds.')
            expected_query, expected_variables = page_query('ppis', tasks, '')
        if request['query'] != expected_query or variables != expected_variables:
            raise ValueError('PPI coverage request differs from the declared adapter query and filter.')
        for i, uid in enumerate(ids):
            response = data[f't{i}']
            if not isinstance(response, dict) or response.get('uniprot') != uid:
                raise ValueError('PPI coverage response identity differs from its request.')
            if is_metadata:
                if uid in metadata:
                    raise ValueError('Duplicate PPI metadata receipt for a resolved subject.')
                metadata[uid] = response
            else:
                rows = response.get('rows')
                if not isinstance(rows, list) or len(rows) > variables[f'top{i}']:
                    raise ValueError('PPI page receipt has invalid row count.')
                pages[uid].append(({
                    'skip': variables[f'skip{i}'], 'requested': variables[f'top{i}'],
                    'returned': len(rows), 'request_index': request_index,
                    'response_pointer': f'/data/t{i}/rows',
                }, reported_count(response.get('reported'), 'ppis')))
    if set(metadata) != resolved:
        raise ValueError('Every resolved subject needs a raw PPI metadata receipt.')
    target_metadata = {t['uniprot']: t.get('pharos_context', {}).get('metadata')
                       for t in chunk['targets']}
    if target_metadata != metadata:
        raise ValueError('Retained target metadata differs from its raw response receipt.')
    coverage = [r for r in (chunk['retrieval_coverage'] or {}).get('targets', [])
                if r['family'] == 'ppis']
    if {r['uniprot'] for r in coverage} != resolved or len(coverage) != len(resolved):
        raise ValueError('PPI coverage does not account for every resolved accession.')
    for row in coverage:
        uid = row['uniprot']
        total = reported_count(metadata[uid].get('ppiCounts'), 'ppis')
        raw_pages = pages.get(uid, [])
        if (total is None or row['available'] != total or row['available_before_scope'] != total
                or row['observed_counts'] != [total] or row['retrieved'] != total):
            raise ValueError('Per-product PPI counts do not reproduce the raw metadata receipt.')
        if any(page_total != total for _, page_total in raw_pages):
            raise ValueError('PPI page reported count differs from the raw metadata receipt.')
        if row['pages'] != [page for page, _ in raw_pages]:
            raise ValueError('PPI page locators do not reproduce the raw request/response receipts.')
        offset = 0
        for page, _ in raw_pages:
            if page['skip'] != offset:
                raise ValueError('PPI page offsets do not cover a contiguous source population.')
            offset += page['returned']
        if row['status'] != 'complete' or row.get('issues') or offset != total:
            raise ValueError('PPI source coverage is not complete for every resolved accession.')
    return coverage


def summarize_properties(groups):
    result = []
    for (bundle, name), values in sorted(groups.items()):
        numeric, nonnumeric = [], Counter()
        for encoded, count in values.items():
            value = json.loads(encoded)
            try:
                number = float(value) if not isinstance(value, bool) else math.nan
            except (TypeError, ValueError):
                number = math.nan
            if math.isfinite(number):
                numeric.extend([number] * count)
            else:
                nonnumeric[encoded] += count
        result.append({'source_bundle': bundle, 'property_name': name,
            'observations': sum(values.values()), 'numeric_observations': len(numeric),
            'numeric_min': min(numeric) if numeric else None,
            'numeric_median': statistics.median(numeric) if numeric else None,
            'numeric_max': max(numeric) if numeric else None,
            'value_counts': [{'value': json.loads(value), 'observations': count}
                             for value, count in sorted(values.items())],
            'nonnumeric_observations': sum(nonnumeric.values())})
    return result


def audit(args):
    prior, identities, previous, prior_counts = prior_identity_audit(args.identity_audit, args.identity_report_sha256)
    folder = Path(args.pharos)
    plan, source, saved, inventory, ids, names = lookup_header(folder, prior, identities)
    candidates, resolved, resolution_rows = set(previous), set(), []
    matches = {'raw': defaultdict(list), 'retained': defaultdict(list)}
    totals, statuses, families = Counter(), Counter(), {}
    provider_counts = {'raw': Counter(), 'retained': Counter()}
    properties = {'all_raw': defaultdict(Counter), 'candidate_raw': defaultdict(Counter)}
    property_names, reference_properties = Counter(), Counter()
    responses = cached = 0
    for index, name in enumerate(names):
        chunk = verified_chunk(folder, name, plan, source, saved,
                               ids[index * plan['chunk_size']:(index + 1) * plan['chunk_size']])
        check_resolution(chunk)
        resolution_rows.extend({**r, 'chunk': name} for r in chunk['target_resolution'])
        statuses.update(r['status'] for r in chunk['target_resolution'])
        chunk_resolved = {r['requested_uniprot'] for r in chunk['target_resolution'] if r['status'] == 'resolved'}
        resolved.update(chunk_resolved)
        responses += len(chunk['requests'])
        cached += sum(bool(r.get('loaded_from_cache')) for r in chunk['requests'])
        coverage = chunk['retrieval_coverage'] or {}
        for family, row in coverage.get('summary', {}).items():
            aggregate = families.setdefault(family, {'retrieved': 0, 'retained': 0,
                'excluded_by_scope': 0, 'available': 0, 'target_statuses': Counter()})
            for key in ('retrieved', 'retained', 'excluded_by_scope'):
                aggregate[key] += row[key]
            aggregate['available'] = (None if row['available'] is None or aggregate['available'] is None
                                      else aggregate['available'] + row['available'])
            aggregate['target_statuses'].update(row['target_statuses'])
        target_coverage = check_ppi_coverage(chunk, chunk_resolved)
        raw_inventory, expected_retained = Counter(), Counter()
        endpoint_counts = {'raw': Counter(), 'retained': Counter()}
        for view, iterator in (('raw', source_rows), ('retained', retained_rows)):
            for uid, row, locator in iterator(chunk, name, 'ppis'):
                partner = row.get('target', {}).get('uniprot')
                if uid not in chunk_resolved or not isinstance(partner, str) or not partner:
                    raise ValueError('PPI record endpoint is missing or outside resolved subject identities.')
                fingerprint = digest(row)
                key = (uid, fingerprint)
                if view == 'raw':
                    raw_inventory[key] += 1
                    if partner in ids:
                        expected_retained[key] += 1
                elif raw_inventory[key] < 1:
                    raise ValueError('Retained PPI record has no identical raw source view.')
                else:
                    raw_inventory[key] -= 1
                    expected_retained[key] -= 1
                if view == 'retained' and partner not in ids:
                    raise ValueError('Retained PPI partner is outside the declared inventory.')
                totals[view] += 1
                endpoint_counts[view][uid] += 1
                bundle = row.get('type')
                if not isinstance(bundle, str):
                    raise ValueError('PPI provider bundle must remain a source string.')
                provider_counts[view][bundle] += 1
                product_pair = pair(uid, partner)
                if view == 'raw':
                    if not isinstance(row.get('props'), list):
                        raise ValueError('PPI properties must retain their source list.')
                    for prop in row['props']:
                        if not isinstance(prop, dict) or not isinstance(prop.get('name'), str):
                            raise ValueError('PPI property lacks a source name.')
                        property_names[prop['name']] += 1
                        if REFERENCE_NAME.search(prop['name']):
                            reference_properties[prop['name']] += 1
                        encoded = json.dumps(prop.get('value'), sort_keys=True, allow_nan=False)
                        properties['all_raw'][(bundle, prop['name'])][encoded] += 1
                        if product_pair in candidates:
                            properties['candidate_raw'][(bundle, prop['name'])][encoded] += 1
                if product_pair in candidates:
                    matches[view][product_pair].append({'subject': uid, 'partner': partner,
                        'locator': locator, 'record_sha256': fingerprint, 'record': row})
        if any(expected_retained.values()):
            raise ValueError('Retained PPI rows do not exactly reproduce the declared cohort filter.')
        for row in target_coverage:
            if (endpoint_counts['raw'][row['uniprot']] != row['retrieved']
                    or endpoint_counts['retained'][row['uniprot']] != row['retained']
                    or row['excluded_by_scope'] != row['retrieved'] - row['retained']):
                raise ValueError('Per-product PPI row counts do not reproduce coverage.')
    reconciled = bool(resolved) and families.get('ppis', {}).get('target_statuses') == {'complete': len(resolved)}
    if (dict(statuses) != saved['resolution_statuses'] or families != saved['families']
            or saved['requested_accessions'] != len(ids) or saved['completed_chunks'] != len(names)
            or saved['db_versions'] != [source['db_version']]
            or saved['successful_source_envelopes'] != responses
            or saved['cached_source_envelopes'] != cached
            or saved['all_requested_families_count_reconciled'] != reconciled
            or totals['raw'] != families.get('ppis', {}).get('retrieved', 0)
            or totals['retained'] != families.get('ppis', {}).get('retained', 0)):
        raise ValueError('Saved retrieval manifest does not reproduce from source chunks.')
    details = []
    resolution_by_id = {r['requested_uniprot']: r for r in resolution_rows}
    for row in identities:
        p = pair(row['uniprot_a'], row['uniprot_b'])
        n_resolved = sum(uid in resolved for uid in p)
        present = bool(matches['raw'].get(p))
        status = ('present_in_raw_ppi' if present else 'no_match_both_endpoints_resolved'
                  if n_resolved == 2 else 'no_match_one_endpoint_resolved'
                  if n_resolved == 1 else 'unassessed_both_requested_endpoints_unresolved')
        old = previous[p]
        directions = {r['subject'] for r in matches['raw'].get(p, [])}
        bundles_by_direction = {uid: sorted({r['record']['type'] for r in matches['raw'].get(p, [])
                                            if r['subject'] == uid}) for uid in p}
        details.append({'source_row': row['source_row'], 'products': list(p), 'identity': row,
            'pharos_status': status, 'resolved_endpoint_count': n_resolved,
            'endpoint_resolution': {uid: resolution_by_id[uid] for uid in p},
            'observed_subject_directions': sorted(directions),
            'asymmetric_with_both_endpoints_resolved': present and n_resolved == 2 and len(directions) == 1,
            'provider_bundles_by_direction': bundles_by_direction,
            'provider_bundle_asymmetry_with_both_endpoints_resolved': present and n_resolved == 2
                and bundles_by_direction[p[0]] != bundles_by_direction[p[1]],
            'pharos_matches': {view: matches[view].get(p, []) for view in matches},
            'previous_pharos_status': old['pharos_status'],
            'previous_pharos_retained_match': old['pharos_retained_match'],
            **{key: old[key] for key in ('huri_registry_projected_match', 'huri_author_crosswalk_match',
                                        'inmc_registry_projected_match', 'inmc_author_crosswalk_match')}})
    huri = lambda row: row['huri_registry_projected_match'] or row['huri_author_crosswalk_match']
    inmc = lambda row: row['inmc_registry_projected_match'] or row['inmc_author_crosswalk_match']
    old_present = lambda row: row['previous_pharos_status'] == 'present_in_saved_raw_ppi'
    new_present = lambda row: row['pharos_status'] == 'present_in_raw_ppi'
    counts = {'published_pairs': len(details), 'requested_products': len(ids), 'resolved_products': len(resolved),
        'resolution_statuses': dict(statuses), 'pair_lookup_statuses': dict(Counter(r['pharos_status'] for r in details)),
        'raw_matching_pairs': len(matches['raw']), 'retained_matching_pairs': len(matches['retained']),
        'raw_matching_source_views': sum(map(len, matches['raw'].values())),
        'retained_matching_source_views': sum(map(len, matches['retained'].values())),
        'raw_source_views': totals['raw'], 'retained_source_views': totals['retained'],
        'both_direction_matching_pairs': sum(len(r['observed_subject_directions']) == 2 for r in details),
        'asymmetric_matching_pairs_both_resolved': sum(r['asymmetric_with_both_endpoints_resolved'] for r in details),
        'provider_bundle_asymmetric_pairs_both_resolved': sum(
            r['provider_bundle_asymmetry_with_both_endpoints_resolved'] for r in details),
        'newly_observed_pharos_pairs': sum(new_present(r) and not old_present(r) for r in details),
        'previous_pharos_pairs_not_returned_now': sum(old_present(r) and not new_present(r) for r in details),
        'huri_either_mapping_pairs': sum(huri(r) for r in details),
        'inmc_either_mapping_pairs': sum(inmc(r) for r in details),
        'no_observed_overlap_current_or_prior_any_route_pairs': sum(not new_present(r) and not old_present(r)
            and not huri(r) and not inmc(r) for r in details),
        'fully_resolved_no_observed_overlap_current_or_prior_any_route_pairs': sum(
            r['resolved_endpoint_count'] == 2 and not new_present(r) and not old_present(r)
            and not huri(r) and not inmc(r) for r in details)}
    report = {'format': 'biograph-steward.lambourne-pharos-lookup-audit.v1', 'created_at': utcnow(),
        'script_sha256': sha(__file__), 'prior_identity_report_sha256': args.identity_report_sha256,
        'prior_identity_outputs_sha256': prior['output_sha256'], 'author_commit': prior['author_commit'],
        'author_panel_sha256': prior['author_files_sha256'][PANEL], 'prior_published_counts': prior_counts,
        'retrieval_plan_sha256': plan['content_sha256'], 'retrieval_summary_sha256': saved['content_sha256'],
        'retrieval_source_sha256': sha(folder / 'source.json'), 'inventory_sha256': plan['inventory_sha256'],
        'db_version': source['db_version'], 'endpoint': plan['endpoint'], 'ppi_confidence_filter': plan['ppi_confidence'],
        'counts': counts, 'source_views_by_provider_bundle': provider_counts,
        'matching_source_views_by_provider_bundle': {view: dict(Counter(
            record['record']['type'] for records in matches[view].values() for record in records)) for view in matches},
        'matching_pairs_by_provider_bundle': {view: dict(Counter(bundle for records in matches[view].values()
            for bundle in {record['record']['type'] for record in records})) for view in matches},
        'property_name_counts': property_names, 'reference_named_property_counts': reference_properties,
        'properties_by_provider_bundle': {key: summarize_properties(value) for key, value in properties.items()},
        'unresolved_accessions': [r for r in resolution_rows if r['status'] != 'resolved'],
        'outcome_fields_decoded': False, 'assay_eligibility_determined': False,
        'independence_established': False, 'performance_evaluated': False,
        'limitations': ['A no-match applies only to the declared Pharos endpoint, accession identity and confidence filter.',
            'Provider labels and scores are source properties, not independent studies or calibrated truth probabilities.',
            'Properties remain grouped by exact provider bundle and property name; scores are never pooled across providers.',
            'A returned identity mismatch is retained for investigation and never substituted for an author accession.',
            'Exact product overlap and prior gene-crosswalk overlap do not resolve assayed isoform or construct identity.',
            'All published identity pairs remain in the denominator, including unresolved targets and assay eligibility unknown.',
            'No observed overlap does not establish source or temporal independence; pair-level source studies remain to audit.']}
    return report, details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pharos', required=True, type=Path)
    parser.add_argument('--identity-audit', required=True, type=Path)
    parser.add_argument('--identity-report-sha256', required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Choose a new output directory.')
    report, details = audit(args)
    out = new_output(args.output_dir, args.pharos, args.identity_audit)
    write_json(out / 'pair_lookup.json', details)
    report['output_sha256'] = {'pair_lookup.json': sha(out / 'pair_lookup.json')}
    write_json(out / 'report.json', report)
    print(json.dumps({'report': str(out / 'report.json'), 'counts': report['counts'],
                      'outcome_fields_decoded': False}, indent=2))


if __name__ == '__main__':
    main()
