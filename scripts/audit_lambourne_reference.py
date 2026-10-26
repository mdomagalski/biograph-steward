#!/usr/bin/env python3
"""Audit public human PPI identities and input exposure; never decode assay results.

The author export has duplicate source_dataset column names. Read by position,
preserving both, and leave column 6 as opaque bytes. This is an inventory audit,
not an outcome adapter, cohort eligibility decision, or performance evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_inmc_inputs import ARCHIVE_SHA256, PANEL_MEMBER, TRAIN_MEMBER, identifier_pairs, map_identifiers
from audit_pharos_inventory import verified_header, verified_chunk, source_rows, retained_rows
from biograph_steward.client import utcnow, write_json
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.file_utils import new_output, sha

COMMIT = 'fb05ab3ca2cc0fcaf402bb0df568e95a5158178b'
PANEL = 'supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv'
ORF_MAP = 'data/internal/uniprot_ac_to_orf_id_used_for_Zhang_et_al_experiment.tsv'
GENE_MAP = 'data/internal/ensembl_to_uniprot_mapping.tsv'
HEADER = b'uniprot_ac_a\tuniprot_ac_b\tAD_CCSB_ORF_ID\tDB_CCSB_ORF_ID\tsource_dataset\tsource_dataset\tresult\tin_biorxiv_version\tin_published_version'
ACCESSION = re.compile(r'[A-Z0-9]{6}(?:[A-Z0-9]{4})?(?:-[1-9][0-9]*)?\Z')


def pair(a, b):
    return tuple(sorted((a, b)))


def panel_identities(raw):
    """Decode identities and nomination metadata only, never result bytes."""
    lines = raw.splitlines()
    if not lines or lines[0] != HEADER:
        raise ValueError('Unexpected author panel schema (including duplicate headers).')
    rows = []
    for number, line in enumerate(lines[1:], 2):
        fields = line.split(b'\t')
        if len(fields) != 9:
            raise ValueError(f'Unexpected panel width at row {number}.')
        # Deliberately do not decode, inspect, count, or expose fields[6].
        a, b, ad, db, source1, source2, preprint, published = (
            fields[i].decode('ascii') for i in (0, 1, 2, 3, 4, 5, 7, 8))
        if not all(v in {'None', 'NULL', ''} or ACCESSION.fullmatch(v) for v in (a, b)) or not ad.isdigit() or not db.isdigit():
            raise ValueError(f'Invalid identity at row {number}.')
        if preprint not in {'True', 'False', 'NULL'} or published not in {'True', 'False', 'NULL'}:
            raise ValueError(f'Unrecognized nomination metadata at row {number}.')
        rows.append({'source_row': number, 'uniprot_a': a if ACCESSION.fullmatch(a) else None,
                     'uniprot_b': b if ACCESSION.fullmatch(b) else None,
                     'ad_orf_id': ad, 'db_orf_id': db,
                     'source_dataset_column_5': source1, 'source_dataset_column_6': source2,
                     'in_biorxiv_version': preprint, 'in_published_version': published})
    if not rows:
        raise ValueError('Empty author panel.')
    return rows


def mapping(raw, header):
    lines = raw.splitlines()
    if not lines or lines[0] != header:
        raise ValueError('Unexpected author mapping header.')
    result = defaultdict(set)
    for line in lines[1:]:
        cells = line.split(b'\t')
        if len(cells) != 2:
            raise ValueError('Unexpected mapping width.')
        key, value = [c.decode('ascii') for c in cells]
        if not ACCESSION.fullmatch(key) or not value:
            raise ValueError('Missing or invalid mapping identity.')
        result[key].add(value)
    return result


def verified_author_files(source_dir, receipts_path):
    receipt = json.loads(Path(receipts_path).read_text())
    if receipt['commit'] != COMMIT:
        raise ValueError('Author source commit differs from the reviewed version.')
    result, hashes = {}, {}
    for name in (PANEL, ORF_MAP, GENE_MAP):
        records = [r for r in receipt['files'] if r['path'] == name]
        if len(records) != 1:
            raise ValueError('Missing or duplicate author source receipt.')
        record = records[0]
        p = Path(source_dir) / name
        if p.is_symlink():
            raise ValueError('Author inputs must be ordinary files.')
        raw = p.read_bytes()
        blob = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        expected_url = f'https://raw.githubusercontent.com/CCSB-DFCI/ai-interactome-experimental-assessment/{COMMIT}/{name}'
        if (hashlib.sha256(raw).hexdigest() != record['sha256'] or len(raw) != record['bytes']
                or blob != record['git_blob_sha1'] or record['url'] != expected_url):
            raise ValueError('Author file does not match its pinned retrieval receipt.')
        result[name], hashes[name] = raw, record['sha256']
    return result, hashes


def projected_pairs(gene_pairs, gene_products):
    return {pair(a, b) for x, y in gene_pairs
            for a in gene_products.get(x, ()) for b in gene_products.get(y, ())}


def gene_pair_match(protein_pair, protein_genes, gene_pairs):
    return any(pair(a, b) in gene_pairs for a, b in product(
        protein_genes.get(protein_pair[0], ()), protein_genes.get(protein_pair[1], ())))


def orf_pair_matches(row, orfs):
    """Author UniProt columns are sorted; they are not AD/DB assignments."""
    a, b = row['uniprot_a'], row['uniprot_b']
    if not a or not b:
        return None
    ad, db = row['ad_orf_id'], row['db_orf_id']
    return ((ad in orfs.get(a, ()) and db in orfs.get(b, ())) or
            (db in orfs.get(a, ()) and ad in orfs.get(b, ())))


def pharos_status(protein_pair, raw_matches, resolved, requested=None):
    if protein_pair in raw_matches:
        return 'present_in_saved_raw_ppi'
    n = sum(p in resolved for p in protein_pair)
    if n:
        return 'not_found_both_endpoints_queried' if n == 2 else 'not_found_one_endpoint_queried'
    if requested and any(p in requested for p in protein_pair):
        return 'unassessed_requested_endpoint_unresolved'
    return 'unassessed_neither_endpoint_queried'


def audit(args):
    author, author_hashes = verified_author_files(args.sources, args.receipts)
    rows = panel_identities(author[PANEL])
    orfs = mapping(author[ORF_MAP], b'uniprot_ac\torf_id')
    author_genes = mapping(author[GENE_MAP], b'uniprot_ac\tensembl_gene_id')
    if any(not re.fullmatch(r'ENSG[0-9]{11}', g) for gs in author_genes.values() for g in gs):
        raise ValueError('Author Ensembl crosswalk contains an unexpected gene identity.')
    candidate_pairs = {pair(r['uniprot_a'], r['uniprot_b']) for r in rows if r['uniprot_a'] and r['uniprot_b']}

    if sha(args.archive) != ARCHIVE_SHA256:
        raise ValueError('INMC archive differs from the pinned source.')
    with zipfile.ZipFile(args.archive) as z:
        huri = {pair(*p) for p in identifier_pairs(z.read(TRAIN_MEMBER), panel=False)}
        inmc = {pair(*p) for p in identifier_pairs(z.read(PANEL_MEMBER), panel=True)}
    registry_manifest, registry = load_registry(args.registry)
    gene_maps = map_identifiers({g for p in huri | inmc for g in p}, registry)
    gene_products = {r['ensembl_gene_id']: {x.removeprefix('UniProtKB:') for x in r['confirmed_reviewed_products']}
                     for r in gene_maps}
    huri_products = projected_pairs(huri, gene_products)
    inmc_products = projected_pairs(inmc, gene_products)

    folder = Path(args.pharos)
    plan, source, saved, inventory, ids, names = verified_header(folder)
    if registry_manifest['registry_sha256'] != inventory['registry_sha256']:
        raise ValueError('Registry differs from the Pharos inventory mapping source.')
    resolved, counts, matches = set(), Counter(), {'raw': defaultdict(list), 'retained': defaultdict(list)}
    reference_fields = Counter()
    for offset, name in enumerate(names):
        chunk = verified_chunk(folder, name, plan, source, saved,
                               ids[offset * plan['chunk_size']:(offset + 1) * plan['chunk_size']])
        chunk_resolved = {r['requested_uniprot'] for r in chunk['target_resolution'] if r['status'] == 'resolved'}
        coverage = [r for r in (chunk['retrieval_coverage'] or {}).get('targets', []) if r['family'] == 'ppis']
        if ({r['uniprot'] for r in coverage} != chunk_resolved or len(coverage) != len(chunk_resolved)
                or any(r['status'] != 'complete' or r['available'] != r['retrieved'] for r in coverage)):
            raise ValueError('PPI retrieval is not complete for every resolved accession.')
        resolved.update(chunk_resolved)
        raw_inventory = Counter()
        endpoint_counts = {'raw': Counter(), 'retained': Counter()}
        for view, iterator in (('raw', source_rows), ('retained', retained_rows)):
            for uid, row, locator in iterator(chunk, name, 'ppis'):
                if uid not in chunk_resolved:
                    raise ValueError('PPI record subject is outside resolved chunk identities.')
                partner = row.get('target', {}).get('uniprot')
                if not partner:
                    raise ValueError('PPI row lacks a partner.')
                fingerprint = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
                row_key = (uid, fingerprint)
                if view == 'raw':
                    raw_inventory[row_key] += 1
                elif raw_inventory[row_key] < 1:
                    raise ValueError('Retained PPI record has no identical raw source view.')
                else:
                    raw_inventory[row_key] -= 1
                counts[view] += 1
                endpoint_counts[view][uid] += 1
                if view == 'raw':
                    names_seen = {str(p.get('name', '')).lower() for p in row.get('props', [])}
                    reference_fields.update(names_seen & {'pmid', 'pmids', 'reference', 'references', 'pubmed'})
                key = pair(uid, partner)
                if key in candidate_pairs:
                    matches[view][key].append({'locator': locator, 'subject': uid, 'partner': partner,
                        'record_sha256': fingerprint,
                        'providers': sorted({s.strip() for s in str(row.get('type', '')).split(',') if s.strip()})})
        if any(endpoint_counts['raw'][r['uniprot']] != r['retrieved'] or
               endpoint_counts['retained'][r['uniprot']] != r['retained'] or
               r['excluded_by_scope'] != r['retrieved'] - r['retained'] for r in coverage):
            raise ValueError('Per-target PPI source counts do not reconcile to coverage.')
    if counts != {'raw': saved['families']['ppis']['retrieved'],
                  'retained': saved['families']['ppis']['retained']}:
        raise ValueError('PPI counts do not reconcile to saved manifest.')

    details = {}
    for p in sorted(candidate_pairs):
        details[p] = {'products': list(p), 'self_pair': p[0] == p[1],
                     'pharos_status': pharos_status(p, matches['raw'], resolved, set(ids)),
                     'queried_endpoints': sum(x in resolved for x in p),
                     'requested_endpoints': sum(x in ids for x in p),
                     'pharos_retained_match': p in matches['retained'],
                     'huri_registry_projected_match': p in huri_products,
                     'inmc_registry_projected_match': p in inmc_products,
                     'huri_author_crosswalk_match': gene_pair_match(p, author_genes, huri),
                     'inmc_author_crosswalk_match': gene_pair_match(p, author_genes, inmc),
                     'author_gene_mapping_sizes': [len(author_genes[x]) for x in p],
                     'pharos_matches': {v: matches[v].get(p, []) for v in matches}}
    groups = {'entire_author_export': rows,
              'published_af_rf_nominations': [r for r in rows
                  if r['source_dataset_column_5'] == r['source_dataset_column_6'] == 'Zhang_et_al'
                  and r['in_published_version'] == 'True']}
    summaries = {}
    for name, selected in groups.items():
        mapped = [r for r in selected if r['uniprot_a'] and r['uniprot_b']]
        pairs = {pair(r['uniprot_a'], r['uniprot_b']) for r in mapped}
        ds = [details[p] for p in sorted(pairs)]
        huri_seen = lambda d: d['huri_registry_projected_match'] or d['huri_author_crosswalk_match']
        inmc_seen = lambda d: d['inmc_registry_projected_match'] or d['inmc_author_crosswalk_match']
        summaries[name] = {'source_rows': len(selected), 'distinct_unordered_product_pairs': len(pairs),
            'rows_missing_product_identity': len(selected) - len(mapped),
            'duplicate_or_reciprocal_mapped_rows': len(mapped) - len(pairs),
            'distinct_products': len({x for p in pairs for x in p}),
            'self_pairs': sum(d['self_pair'] for d in ds),
            'pharos_status_pairs': dict(Counter(d['pharos_status'] for d in ds)),
            'pharos_queried_endpoints_pairs': dict(Counter(d['queried_endpoints'] for d in ds)),
            'pharos_requested_endpoints_pairs': dict(Counter(d['requested_endpoints'] for d in ds)),
            'pharos_retained_match_pairs': sum(d['pharos_retained_match'] for d in ds),
            'huri_registry_match_pairs': sum(d['huri_registry_projected_match'] for d in ds),
            'huri_author_crosswalk_match_pairs': sum(d['huri_author_crosswalk_match'] for d in ds),
            'huri_either_mapping_match_pairs': sum(huri_seen(d) for d in ds),
            'inmc_registry_match_pairs': sum(d['inmc_registry_projected_match'] for d in ds),
            'inmc_author_crosswalk_match_pairs': sum(d['inmc_author_crosswalk_match'] for d in ds),
            'inmc_either_mapping_match_pairs': sum(inmc_seen(d) for d in ds),
            'author_crosswalk_both_single_gene_pairs': sum(d['author_gene_mapping_sizes'] == [1, 1] for d in ds),
            'author_crosswalk_missing_endpoint_pairs': sum(0 in d['author_gene_mapping_sizes'] for d in ds),
            'author_crosswalk_ambiguous_endpoint_pairs': sum(any(n > 1 for n in d['author_gene_mapping_sizes']) for d in ds),
            'author_orf_crosswalk_mismatch_rows': sum(orf_pair_matches(r, orfs) is False for r in selected),
            'no_observed_pair_overlap_any_route_pairs': sum(not huri_seen(d) and not inmc_seen(d)
                and d['pharos_status'] != 'present_in_saved_raw_ppi' for d in ds),
            'both_endpoints_queried_and_no_observed_overlap_pairs': sum(not huri_seen(d) and not inmc_seen(d)
                and d['pharos_status'] == 'not_found_both_endpoints_queried' for d in ds)}
    metadata_counts = Counter((r['source_dataset_column_5'], r['source_dataset_column_6'],
                               r['in_biorxiv_version'], r['in_published_version']) for r in rows)
    report = {'format': 'biograph-steward.lambourne-identity-audit.v1', 'created_at': utcnow(),
        'script_sha256': sha(__file__), 'author_commit': COMMIT, 'author_files_sha256': author_hashes,
        'source_receipts_sha256': sha(args.receipts), 'registry_sha256': registry_manifest['registry_sha256'],
        'inmc_archive_sha256': ARCHIVE_SHA256, 'pharos_plan_sha256': plan['content_sha256'],
        'pharos_summary_sha256': saved['content_sha256'], 'pharos_version': source['db_version'],
        'pharos_raw_records_scanned': counts['raw'], 'pharos_retained_records_scanned': counts['retained'],
        'pharos_resolved_queried_products': len(resolved), 'pharos_reference_property_counts': dict(reference_fields),
        'groups': summaries, 'nomination_metadata_counts': [{'metadata': list(k), 'rows': v} for k, v in sorted(metadata_counts.items())],
        'author_orf_crosswalk_mismatch_rows': [r['source_row'] for r in rows if orf_pair_matches(r, orfs) is False],
        'outcome_fields_decoded': False, 'assay_eligibility_determined': False,
        'performance_evaluated': False, 'independence_established': False,
        'limitations': ['Nomination metadata is not assay eligibility; result column stays opaque.',
            'No match in scoped/thresholded saved Pharos responses is not global absence.',
            'Gene crosswalk matches flag possible overlap, not assayed isoform/construct identity.',
            'Unmatched pairs may have shared studies or derivative evidence; no temporal independence certified.',
            'Current Pharos source rows lack study-level provenance; provider labels are not independent evidence.',
            'Duplicate or reciprocal rows retained; no outcome aggregation rule inferred.']}
    return report, rows, list(details.values())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('sources', 'receipts', 'pharos', 'archive', 'registry', 'output-dir'):
        p.add_argument('--' + name, required=True, type=Path)
    args = p.parse_args()
    # Reject a reused output before opening any files; inputs stay immutable.
    if args.output_dir.exists():
        p.error('Choose a new output directory.')
    report, rows, pairs = audit(args)
    out = new_output(args.output_dir, args.sources, args.pharos, args.archive, args.registry)
    write_json(out / 'identity_rows.json', rows)
    write_json(out / 'pair_exposure.json', pairs)
    report['output_sha256'] = {n: sha(out / n) for n in ('identity_rows.json', 'pair_exposure.json')}
    write_json(out / 'report.json', report)
    print(json.dumps({'report': str(out / 'report.json'), 'groups': report['groups'],
                      'orf_mismatch_rows': len(report['author_orf_crosswalk_mismatch_rows']),
                      'outcome_fields_decoded': False}, indent=2))


if __name__ == '__main__':
    main()
