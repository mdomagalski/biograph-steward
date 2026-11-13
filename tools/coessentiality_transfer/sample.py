"""Freeze a metadata-only SRSWOR of new native Entrez genes before source queries.

The estimand is not whole-proteome accuracy: eligibility is an explicit reviewed,
uniquely mapped human subset of one published experimental gene universe.
"""
from collections import Counter, defaultdict
import argparse
import itertools
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.file_utils import new_output, sha
from biograph_steward.human_gene_relation import gene_relationship
from tools.reference_accuracy.design import need, read_rows, write_jsonl
from tools.coessentiality_feasibility.identifiers import native_order
from tools.coessentiality_feasibility.chromosome import canonical_chromosome

FORMAT = 'biograph-steward.prospective-native-gene-sample.v1'
N = 128
SEED = 2026111302
CANON = re.compile(r'[A-Z0-9]{6}(?:[A-Z0-9]{4})?\Z')
NATIVE_PINS = {'genes': 'ecf1b3ec888689d2d19ff8de4ba58904dbdf457438c7d30c6a6f0446f5639f22',
               'header': '13e5685912ab4901c497cacaa1a4604cb80d2cc0a849f12dfabdc464418b3612'}
IMPLEMENTATIONS = ['tools/coessentiality_transfer/sample.py',
    'tools/coessentiality_feasibility/identifiers.py', 'tools/coessentiality_feasibility/chromosome.py',
    'biograph_steward/human_gene_relation.py', 'biograph_steward/cohort_mapping.py',
    'biograph_steward/gold_packet.py', 'biograph_steward/file_utils.py', 'biograph_steward/client.py']


def sealed(path):
    value = gold_packet._read(Path(path)); need(gold_packet._sealed(value), 'gene-sample content seal differs')
    return value


def exclusions(snapshot, registry):
    old = {'gene_ids': set(), 'hgnc_ids': set(), 'products': set()}
    for target in snapshot['targets']:
        subject = 'UniProtKB:' + target['uniprot']; relation = gene_relationship(subject, registry)
        need(relation['qualified'], 'original cohort no longer has exact reviewed gene-product relationships')
        old['gene_ids'].add(relation['ncbi_gene_id']); old['hgnc_ids'].add(relation['hgnc_id']); old['products'].add(subject)
    return {k: sorted(v) for k, v in old.items()}


def eligible_frame(order, registry, old):
    native = defaultdict(list); genes = defaultdict(list); products = defaultdict(set)
    for row in order:
        native[row['native_ncbi_gene_id']].append(row)
    for hid, gene in registry.genes.items():
        if gene['status'] == 'Approved' and re.fullmatch(r'[1-9][0-9]*', gene['entrez_id'] or ''):
            genes[gene['entrez_id']].append(hid)
            for accession in gene['uniprot_ids'].split('|'):
                if accession in registry.proteins and CANON.fullmatch(accession):
                    products[gene['entrez_id']].add(accession)
    # Include conflicting current reviewed candidates, not just the convenient
    # qualified one. This prevents choosing among contradictory product records.
    for accession, protein in registry.proteins.items():
        if not CANON.fullmatch(accession):
            continue
        for gid in protein['ncbi_gene_ids']:
            products[gid].add(accession)
        for hid in protein['hgnc_ids']:
            gene = registry.genes.get(hid)
            if gene is not None and gene['status'] == 'Approved':
                products[gene['entrez_id']].add(accession)
    frame = []; ledger = []
    for gid in sorted(native, key=int):
        candidates = sorted(products[gid]); hids = sorted(genes[gid]); rows = native[gid]
        record = {'ncbi_gene_id': gid, 'native_matrix_row_count': len(rows), 'native_matrix_indices': [r['matrix_index'] for r in rows],
            'approved_hgnc_candidates': hids, 'reviewed_canonical_product_candidates': candidates}
        status = None; relation = None; chromosome = None
        if gid in old['gene_ids'] or any(h in old['hgnc_ids'] for h in hids) or any('UniProtKB:' + a in old['products'] for a in candidates):
            status = 'excluded_original_gene_HGNC_or_product'
        elif len(rows) != 1:
            status = 'UNKNOWN_nonunique_native_Entrez_matrix_index'
        elif len(hids) != 1:
            status = 'UNKNOWN_missing_or_nonunique_approved_HGNC_gene'
        elif len(candidates) != 1:
            status = 'UNKNOWN_missing_or_nonunique_reviewed_canonical_product'
        else:
            relation = gene_relationship('UniProtKB:' + candidates[0], registry)
            if not relation['qualified'] or relation['ncbi_gene_id'] != gid or relation['hgnc_id'] != hids[0]:
                status = 'UNKNOWN_gene_product_cross_reference_conflict'
            else:
                gene = registry.genes[hids[0]]; chromosome = canonical_chromosome(gene.get('location'))
                if chromosome is None:
                    status = 'UNKNOWN_missing_or_ambiguous_canonical_chromosome'
        if status is None:
            gene = registry.genes[hids[0]]; n = rows[0]
            frame.append({'ncbi_gene_id': gid, 'hgnc_id': hids[0], 'accession': candidates[0],
                'subject': 'UniProtKB:' + candidates[0], 'approved_symbol': gene['symbol'],
                'canonical_chromosome': chromosome, 'current_HGNC_location_literal': gene['location'],
                'native_matrix_index': n['matrix_index'], 'native_matrix_symbol': n['native_symbol'],
                'native_header_field': n['native_header_field'], 'gene_product_relation': relation,
                'gene_product_mapping_claims_identity': False})
            status = 'eligible_reviewed_unique_human_gene_product_and_chromosome'
        ledger.append({**record, 'status': status})
    need(len(frame) == len({r['ncbi_gene_id'] for r in frame}) == len({r['hgnc_id'] for r in frame})
         == len({r['subject'] for r in frame}), 'eligible identities are not one-to-one')
    return frame, ledger


def draw(frame):
    need(len(frame) >= N and [int(r['ncbi_gene_id']) for r in frame] == sorted(int(r['ncbi_gene_id']) for r in frame),
         'eligible frame must have at least128 genes in increasing integer-Entrez order')
    return sorted(random.Random(SEED).sample(frame, N), key=lambda r: int(r['ncbi_gene_id']))


def pairs_for(sample):
    lookup = {r['ncbi_gene_id']: r for r in sample}
    return [{'gene_pair': [a, b], 'scope': 'syntenic' if lookup[a]['canonical_chromosome'] == lookup[b]['canonical_chromosome'] else 'nonsyntenic',
             'native_matrix_indices': [lookup[a]['native_matrix_index'], lookup[b]['native_matrix_index']]}
            for a, b in itertools.combinations(sorted(lookup), 2)]


def conflict_details(ledger, registry):
    details = []
    for row in ledger:
        if row['status'] != 'UNKNOWN_missing_or_nonunique_reviewed_canonical_product' or len(row['approved_hgnc_candidates']) != 1:
            continue
        hid = row['approved_hgnc_candidates'][0]; gene = registry.genes[hid]
        products = []
        for accession in row['reviewed_canonical_product_candidates']:
            relation = gene_relationship('UniProtKB:' + accession, registry)
            products.append({'accession': accession, 'native_UniProt_record': registry.proteins[accession],
                             'relation_check': relation})
        qualified = [p for p in products if p['relation_check']['qualified'] and
                     p['relation_check']['ncbi_gene_id'] == row['ncbi_gene_id'] and p['relation_check']['hgnc_id'] == hid]
        if len(qualified) == 1 and canonical_chromosome(gene.get('location')) is not None:
            details.append({**row, 'approved_HGNC_record': gene, 'all_candidate_products': products,
                'reason': 'Excluded before SRS: one qualified product plus another current reviewed candidate asserted by a source but conflicting/unqualified; no product chosen.'})
    return details


def protocol_record(frame, ledger, old, old_columns, registry_sha, frame_sha, conflicts_sha, *, created_at, python_version):
    return {'format': FORMAT, 'created_at': created_at, 'unit': 'distinct_native_Entrez_gene',
        'population': 'reviewed uniquely mapped human subset of published native gene universe; not whole proteome',
        'eligibility_rule': 'one consistent approved HGNC/Entrez/canonical reviewed UniProt product; no conflicting secondary reviewed candidate; one known canonical chromosome',
        'population_size': len(frame), 'sample_size': N, 'seed': SEED,
        'method': 'Simple random sampling without replacement via Python random.Random(seed).sample',
        'frame_order': 'increasing integer native Entrez ID', 'python_version': python_version,
        'eligibility_status_counts': dict(Counter(r['status'] for r in ledger)),
        'exclusions': old, 'registry_sha256': registry_sha, 'native_reference_file_sha256': NATIVE_PINS,
        'eligible_frame_file_sha256': frame_sha, 'conservative_product_conflicts_file_sha256': conflicts_sha,
        'Pharos_Wiki_TDL_fitness_or_outcome_based_selection': False,
        'source_queries_or_new_reference_values_opened': False,
        'source_failure_policy': 'Any required Pharos identity/pathway failure,notfound,truncation,versiondrift => wholecomparison UNKNOWN/no-go; completezeroWiki valid0',
        'no_replacements_or_outcome_driven_reframing': True,
        'reference_exposure': {'old_raw_column_indices': old_columns, 'old_new_raw_pair_bytes_previously_persisted': True,
            'new_new_pair_block_previously_captured': False, 'prior_paper_methods_and_illustrative_examples_seen': True,
            'prior_Broad_and_RA_results_consumed': True, 'independent_study_or_complete_knowledge_blinding_claimed': False},
        'purpose': 'prospective unseen-gene transfer within the same published reference, not independent experimental confirmation or biological truth'}


def source_inputs(genes, header, registry, old_gold, old_capture):
    paths = {k: Path(v).absolute() for k, v in dict(genes=genes, header=header, registry=registry,
                                                  old_gold=old_gold, old_capture=old_capture).items()}
    need(all(paths[k].is_file() and not paths[k].is_symlink() and sha(paths[k]) == pin for k, pin in NATIVE_PINS.items()),
         'published native gene order/header pins differ')
    initial_registry = gold_packet._read(paths['registry'] / 'manifest.json')
    initial_gold = gold_packet._read(paths['old_gold'] / 'packet_manifest.json')
    capture = sealed(paths['old_capture'] / 'report.json')
    pins = {str(paths['genes']): NATIVE_PINS['genes'], str(paths['header']): NATIVE_PINS['header'],
        str(paths['registry'] / 'manifest.json'): sha(paths['registry'] / 'manifest.json'),
        **{str(paths['registry'] / name): pin for name, pin in initial_registry['files'].items()},
        str(paths['old_gold'] / 'packet_manifest.json'): sha(paths['old_gold'] / 'packet_manifest.json'),
        **{str(paths['old_gold'] / name): pin for name, pin in initial_gold['files'].items()},
        str(paths['old_capture'] / 'report.json'): sha(paths['old_capture'] / 'report.json'),
        **{str(paths['old_capture'] / name): pin for name, pin in capture['files'].items()}}
    need(all(sha(p) == pin for p, pin in pins.items()), 'metadata source differs before eligibility parsing')
    reg_manifest, reg = load_registry(paths['registry'])
    manifest, graph = gold_packet.load_packet(paths['old_gold'])
    need(reg_manifest == initial_registry and manifest == initial_gold, 'source manifest changed during metadata parsing')
    snapshot = gold_packet._read(paths['old_gold'] / 'source/snapshot.json')
    old = exclusions(snapshot, reg)
    need(len(old['gene_ids']) == 98, 'expected original98-gene exclusion cohort differs')
    need(capture['format'] == 'biograph-steward.coessentiality-native-column-capture.v1', 'old capture metadata format differs')
    need(not any(p.is_symlink() for p in [paths['old_capture'], *paths['old_capture'].rglob('*')]), 'symlink in old capture')
    actual = {p.relative_to(paths['old_capture']).as_posix(): sha(p) for p in paths['old_capture'].rglob('*')
              if p.is_file() and p != paths['old_capture'] / 'report.json'}
    need(actual == capture['files'], 'old persisted-column inventory differs')
    order = native_order(paths['genes'].read_text(), paths['header'].read_text())
    old_columns = sorted({r['column'] for r in capture['columns']})
    need(len(old_columns) == 92 and all(order[i]['native_ncbi_gene_id'] in old['gene_ids'] for i in old_columns),
         'old92-column exposure does not match excluded original genes')
    need(all(sha(p) == pin for p, pin in pins.items()), 'metadata source changed during eligibility input loading')
    return paths, order, reg_manifest, reg, old, old_columns, pins


def prepare(genes, header, registry, old_gold, old_capture, output):
    code = {str(ROOT / p): sha(ROOT / p) for p in IMPLEMENTATIONS}
    paths, order, reg_manifest, reg, old, old_columns, pins = source_inputs(genes, header, registry, old_gold, old_capture)
    frame, ledger = eligible_frame(order, reg, old)
    out = new_output(output, *paths.values())
    write_jsonl(out / 'eligible_frame.jsonl', frame); write_jsonl(out / 'eligibility_ledger.jsonl', ledger)
    write_jsonl(out / 'conservative_product_conflicts.jsonl', conflict_details(ledger, reg))
    protocol = protocol_record(frame, ledger, old, old_columns, reg_manifest['registry_sha256'],
        sha(out / 'eligible_frame.jsonl'), sha(out / 'conservative_product_conflicts.jsonl'), created_at=utcnow(), python_version=sys.version)
    protocol['content_sha256'] = digest(protocol); write_json(out / 'protocol.json', protocol)
    # The sealed protocol and entire eligible population precede the only draw.
    sample = draw(frame)
    need(not ({r['native_matrix_index'] for r in sample} & set(old_columns)), 'sample overlaps old persisted columns')
    sample_id = 'gene-transfer:' + digest({'protocol': protocol['content_sha256'], 'genes': [r['ncbi_gene_id'] for r in sample]})
    selected = [{**row, 'sample_id': sample_id, 'sample_number': i,
                 'inclusion_probability': {'numerator': N, 'denominator': len(frame)}} for i, row in enumerate(sample, 1)]
    write_jsonl(out / 'sample.jsonl', selected); write_jsonl(out / 'pairs.jsonl', pairs_for(sample))
    need(all(sha(p) == h for p, h in {**pins, **code}.items()), 'metadata/code changed during sampling')
    report = {'format': FORMAT, 'created_at': utcnow(), 'protocol_content_sha256': protocol['content_sha256'],
        'sample_id': sample_id, 'sample_size': N, 'population_size': len(frame),
        'source_paths': {k: str(v) for k, v in paths.items()}, 'input_files_sha256': pins,
        'implementation_sha256': code, 'source_queries_or_new_reference_values_opened': False,
        'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    report['content_sha256'] = digest(report); write_json(out / 'report.json', report)
    return report


def verify(directory, expected_content_sha256=None):
    directory = Path(directory); report = sealed(directory / 'report.json')
    need(report['format'] == FORMAT and (expected_content_sha256 is None or report['content_sha256'] == expected_content_sha256),
         'fixed gene sample format/seal differs')
    need(not any(p.is_symlink() for p in [directory, *directory.rglob('*')]), 'symlink in gene sample')
    need({p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob('*') if p.is_file() and p != directory / 'report.json'}
         == report['files'], 'gene sample byte inventory differs')
    need(all(sha(p) == h for p, h in {**report['input_files_sha256'], **report['implementation_sha256']}.items()),
         'gene sample metadata or implementation pin differs')
    paths, order, rm, reg, old, columns, pins = source_inputs(**report['source_paths'])
    need(pins == report['input_files_sha256'], 'gene sample input inventory replay differs')
    frame, ledger = eligible_frame(order, reg, old); protocol = sealed(directory / 'protocol.json')
    need(frame == read_rows(directory / 'eligible_frame.jsonl') and ledger == read_rows(directory / 'eligibility_ledger.jsonl'),
         'metadata eligibility replay differs')
    conflicts = conflict_details(ledger, reg)
    need(conflicts == read_rows(directory / 'conservative_product_conflicts.jsonl'), 'conservative product-conflict proof replay differs')
    expected_protocol = protocol_record(frame, ledger, old, columns, rm['registry_sha256'],
        sha(directory / 'eligible_frame.jsonl'), sha(directory / 'conservative_product_conflicts.jsonl'),
        created_at=protocol['created_at'], python_version=protocol['python_version'])
    expected_protocol['content_sha256'] = digest(expected_protocol)
    need(protocol == expected_protocol and protocol['content_sha256'] == report['protocol_content_sha256']
         and report['population_size'] == len(frame) and report['source_queries_or_new_reference_values_opened'] is False,
         'fixed sampling/scientific exposure protocol differs')
    sample = draw(frame); sample_id = 'gene-transfer:' + digest({'protocol': protocol['content_sha256'],
                                                               'genes': [r['ncbi_gene_id'] for r in sample]})
    expected = [{**row, 'sample_id': sample_id, 'sample_number': i,
                 'inclusion_probability': {'numerator': N, 'denominator': len(frame)}} for i, row in enumerate(sample, 1)]
    selected = read_rows(directory / 'sample.jsonl')
    need(expected == selected and sample_id == report['sample_id'] and report['sample_size'] == N
         and pairs_for(sample) == read_rows(directory / 'pairs.jsonl'), 'fixed SRS draw/weights/pairs replay differs')
    need(not ({r['native_matrix_index'] for r in selected} & set(columns)), 'new sample overlaps old matrix columns')
    return report, protocol, selected


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['genes', 'header', 'registry', 'old-gold', 'old-capture', 'out']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); print(prepare(a.genes, a.header, a.registry, a.old_gold, a.old_capture, a.out)['content_sha256'])


if __name__ == '__main__':
    main()
