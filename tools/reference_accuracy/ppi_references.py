"""Prepare source-pinned public PPI references without fitting or score access.

SNOOPPI labels are used as released. Exact canonical sequence admission and
manual Negatome assay-pair concordance remain distinct reference profiles.
Optional readers are Biopython and pyarrow; no upstream curation/model code is
vendored or executed. Preparation never changes a graph or author gold label.
"""
from collections import Counter, defaultdict
import argparse
import csv
import json
from pathlib import Path
import re

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .ppi_gold import pair_key


FORMAT = 'biograph-steward.public-ppi-reference-preparation.v1'
SOURCE_PROFILE = 'SNOOPPI_HF45e4f022_IntAct251_202509'
ACCESSION = re.compile(r'(?<![A-Za-z0-9])([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?![A-Za-z0-9])')


def need(condition, message):
    if not condition:
        raise ValueError('PPI reference preparation: ' + message)


def text_sha(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def checked(spec, root):
    path = Path(spec['file'])
    path = path.resolve() if path.is_absolute() else (root / path).resolve()
    need(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
         'ordinary workspace input required.')
    need(sha(path) == spec['sha256'], 'source byte pin differs: ' + path.name)
    return path


def human_canonical_sequences(path):
    """Use the published FASTA parser; descriptions may contain inline '>'."""
    from Bio.SeqIO.FastaIO import SimpleFastaParser
    result = {}
    with Path(path).open() as handle:
        for header, sequence in SimpleFastaParser(handle):
            need(header.startswith('sp|') and ' OX=9606 ' in header,
                 'reviewed human canonical FASTA required.')
            accession = header.split('|')[1]
            pair_key((accession, accession))
            need(accession not in result and sequence, 'duplicate or empty FASTA entry.')
            result[accession] = sequence
    need(result, 'empty canonical sequence source.')
    return result


def native_snooppi(path, label):
    need(label in ('positive', 'negative'), 'unknown split is not binary gold.')
    import pyarrow.parquet as pq
    rows = pq.read_table(path).to_pylist()
    for ordinal, row in enumerate(rows, 1):
        need(row['SNOOPPI_final_label'] == label, 'declared split differs from author label.')
        row['_source_split'] = label
        row['_source_row_1based'] = ordinal
    return rows


def canonical_frame(native, frame, canonical):
    """Require exact assayed chains; retain rejected states with their reasons."""
    candidates, eligible, sensitivity = [], [], []
    exclusions = Counter()
    for row in native:
        need(row['SNOOPPI_final_label'] in ('positive', 'negative'),
             'unknown author records cannot enter binary gold.')
        if not all(re.search(r'(?<!\d)9606(?!\d)', row['partner_' + side + '_species'] or '')
                   for side in ('A', 'B')):
            continue
        ids = [set(ACCESSION.findall(row['partner_' + side + '_uniprot_ids'] or ''))
               for side in ('A', 'B')]
        if not all(found & frame for found in ids):
            continue
        reasons = []
        if any(len(found) != 1 for found in ids):
            reasons.append('ambiguous_base_accession')
        bases = [sorted(found)[0] if len(found) == 1 else None for found in ids]
        exact = []
        for side, accession in zip(('A', 'B'), bases):
            sequence = row['partner_' + side + '_sequence'] or ''
            if accession not in canonical:
                reasons.append(side + '_missing_canonical_FASTA')
                exact.append(False)
            else:
                ok = sequence == canonical[accession]
                exact.append(ok)
                if not ok:
                    reasons.append(side + '_assayed_sequence_not_exact_full_canonical')
            if row['partner_' + side + '_mol_type'] != 'protein':
                reasons.append(side + '_not_protein')
        origin = {part.strip() for part in (row['seq_sort_origin_categories'] or '').split('|') if part.strip()}
        inferred = any('binding' in token for token in origin)
        if inferred:
            reasons.append('binding_region_designed_sequence_not_exact_experiment')
        obj = {'reference_pair_id': row['SNOOPPI_Pair_ID'],
               'reference_labeled_pair_id': row['SNOOPPI_Labeled_Pair_ID'],
               'reference_split': row['_source_split'],
               'source_row_1based': row['_source_row_1based'],
               'reference_label': row['SNOOPPI_final_label'],
               'MI0915_final_label': row['MI0915_final_label'],
               'raw_UniProt_ids': [row['partner_' + s + '_uniprot_ids'] for s in ('A', 'B')],
               'base_accessions': bases,
               'sequence_SHA256': [text_sha(row['partner_' + s + '_sequence'] or '') for s in ('A', 'B')],
               'sequence_lengths': [len(row['partner_' + s + '_sequence'] or '') for s in ('A', 'B')],
               'exact_full_canonical_sequence_match': exact,
               'eligible_canonical_gold': not reasons,
               'exclusion_reasons': sorted(set(reasons)),
               'experimental_state_sensitivity_not_canonical_gold': bool(reasons) and not inferred,
               'inferred_binding_region_sequence': inferred,
               'origin_categories': sorted(origin),
               'unique_interaction_mi_terms': row['unique_interaction_mi_terms'],
               'feature_relationship_types': row['feature_relationship_types'],
               'feature_relationship_summary': row['feature_relationship_summary'],
               'wildtype_SNOOPPI_final_label': row['wildtype_SNOOPPI_final_label'],
               'intact_interaction_ids': row['intact_interaction_ids'],
               'pubmed_ids': sorted(set(re.findall(r'\b\d+\b', row['pubmed_ids'] or ''))),
               'publication_year_min': row['publication_year_min'],
               'publication_year_max': row['publication_year_max'],
               'host_context': [row['partner_' + s + '_host_context'] for s in ('A', 'B')],
               'assays_unique': row['assays_unique'],
               'independent_experiment_claimed': False,
               'source_lineage': 'IntAct_release251_September2025;STRING/Pharosstudyreuse_unresolved',
               'comparison_scope': 'direct_binary_sequence_specific_physical_interaction'}
        candidates.append(obj)
        if reasons:
            exclusions.update(set(reasons))
            if not inferred:
                sensitivity.append(obj)
        else:
            eligible.append(obj)
    return {'all_base_pair_candidates': candidates, 'canonical_gold': eligible,
            'experimental_state_sensitivity': sensitivity,
            'exclusion_reason_counts_nonexclusive': dict(exclusions)}


def manual_negative_rows(path, source_status, *, root):
    """Retain the native publication and assay, including a legacy PMCID row."""
    need(source_status in ('unfiltered_manual_expert_curated_primary',
                          'manual_expert_curated_filtered_against_IntAct_distinct_stratum'),
         'declare native manual-negative source ascertainment.')
    result = []
    with Path(path).open() as handle:
        for ordinal, row in enumerate(csv.reader(handle, delimiter='\t'), 1):
            if not row or row[0].startswith('#'):
                continue
            need(len(row) == 4 and row[0] and row[1], 'manual reference columns differ.')
            publication = row[2]
            need(publication.isdigit() or (publication.startswith('PMC') and publication[3:].isdigit()),
                 'native manual publication identifier differs.')
            # A native isoform identifier is preserved literally. It cannot
            # match a base-accession frame and is never collapsed into one.
            need(all(re.fullmatch(ACCESSION.pattern + r'(?:-\d+)?', uid) for uid in row[:2]),
                 'native manual protein identifier differs.')
            key = tuple(sorted(row[:2]))
            result.append({'pair': key, 'reference_label': 'negative',
                           'source_file': str(Path(path).resolve().relative_to(root)),
                           'source_row_1based': ordinal, 'native_UniProt_ids': row[:2],
                           'publication_id_raw': publication,
                           'publication_namespace': 'PMID' if publication.isdigit() else 'PMCID',
                           'PMID': publication if publication.isdigit() else None,
                           'assay_MI_raw': row[3], 'source_filter_status': source_status,
                           'assayed_sequence_and_proteoform_verified': False,
                           'tissue_cell_context_available_in_native_reference_row': False,
                           'label_scope': 'manual_expert_reported_noninteraction_under_source_assay',
                           'not_a_functional_association_false_label': True})
    return result


def manual_frame(positives, negatives, frame, human):
    positive_by_pair, negative_by_pair = defaultdict(list), defaultdict(list)
    exclusions = Counter()
    for row in positives:
        if row['reference_label'] != 'positive':
            continue
        pair = pair_key(row['base_accessions'])
        need(set(pair) <= frame, 'positive source belongs to another scope.')
        if pair[0] != pair[1]:
            positive_by_pair[pair].append(row)
    for row in negatives:
        pair = row['pair']
        if not set(pair) <= frame:
            continue
        if pair[0] == pair[1]:
            exclusions['self_pair_excluded'] += 1
        elif not set(pair) <= human:
            exclusions['native_accession_not_in_reviewed_human_canonical_FASTA'] += 1
        else:
            negative_by_pair[pair].append(row)
    panel = []
    for pair in sorted(set(positive_by_pair) | set(negative_by_pair)):
        pp, nn = positive_by_pair.get(pair, []), negative_by_pair.get(pair, [])
        label = 'unknown' if pp and nn else ('positive' if pp else 'negative')
        panel.append({'base_accession_pair': list(pair), 'reference_label': label,
                      'positive_reference_rows': pp, 'negative_reference_rows': nn,
                      'positive_PMIDs': sorted({p for row in pp for p in row['pubmed_ids']}),
                      'negative_PMIDs': sorted({row['PMID'] for row in nn if row['PMID'] is not None}),
                      'conflict_rule_applied': bool(pp and nn),
                      'negative_unfiltered_manual_available': any('unfiltered' in r['source_filter_status'] for r in nn),
                      'negative_only_IntAct_filtered_manual': bool(nn) and all('filtered_against' in r['source_filter_status'] for r in nn),
                      'independent_experiment_claimed': False,
                      'canonical_assayed_sequence_claimed_for_Negatome': False,
                      'generic_functional_association_truth_label': False,
                      'source_exposure': 'Published expert-curated reference; shared IntAct/STRING benchmarking/Pharos exposure possible, not ruled out.'})
    return panel, dict(exclusions)


def run(configuration, configuration_sha256, output, *, root):
    root = Path(root).resolve()
    configuration = Path(configuration).resolve()
    need(sha(configuration) == configuration_sha256, 'configuration hash differs.')
    config = json.loads(configuration.read_text())
    need(config['format'] == FORMAT, 'preparation format differs.')
    need(config['source_profile'] == SOURCE_PROFILE, 'this reader is qualified for the declared published source release only.')
    producer = checked(config['producer_source'], root)
    need(producer == Path(__file__).resolve(), 'another preparation implementation.')
    source_specs = [config['canonical_fasta'], *config['snooppi'].values(),
                    *config['frames'].values(), *config['manual_negative_sources']]
    expected_source_pins = {str(checked(spec, root)): spec['sha256'] for spec in source_specs}
    files = [checked(config['canonical_fasta'], root)]
    canonical = human_canonical_sequences(files[0])
    need(len(canonical) == config['canonical_fasta']['expected_records'], 'canonical source count differs.')
    native = []
    for label in ('positive', 'negative'):
        path = checked(config['snooppi'][label], root)
        files.append(path)
        rr = native_snooppi(path, label)
        need(len(rr) == config['snooppi'][label]['expected_rows'], 'author split count differs.')
        native.extend(rr)
    frames = {}
    for name, spec in config['frames'].items():
        path = checked(spec, root)
        files.append(path)
        value = json.loads(path.read_text())
        for key in spec['key_path']:
            value = value[key]
        need(isinstance(value, list) and len(value) == len(set(value)) == spec['expected_proteins'],
             'cohort membership count/uniqueness differs.')
        frames[name] = {pair_key((accession, accession))[0] for accession in value}
    negatives = []
    for spec in config['manual_negative_sources']:
        path = checked(spec, root)
        files.append(path)
        rr = manual_negative_rows(path, spec['status'], root=root)
        need(len(rr) == spec['expected_rows'], 'manual source row count differs.')
        negatives.extend(rr)
    folder = new_output(output, configuration.parent, *files)
    summaries, outputs = {}, {}
    for name, frame in frames.items():
        need(name and '/' not in name and '\\' not in name and name not in ('.', '..'), 'scope name is not a safe locator.')
        prepared = canonical_frame(native, frame, canonical)
        manual, excluded = manual_frame(prepared['canonical_gold'], negatives, frame, set(canonical))
        scope = folder / name
        scope.mkdir()
        for role, rows in (*[(role, prepared[role]) for role in (
                'all_base_pair_candidates', 'canonical_gold', 'experimental_state_sensitivity')],
                ('manual_assay_reference', manual)):
            path = scope / (role + '.private.jsonl')
            path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
            outputs[str(path.relative_to(folder))] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
        summaries[name] = {'proteins': len(frame), 'canonical_FASTA_present': len(frame & set(canonical)),
                           'canonical_labels': dict(Counter(r['reference_label'] for r in prepared['canonical_gold'])),
                           'manual_assay_labels': dict(Counter(r['reference_label'] for r in manual)),
                           'canonical_exclusion_reason_counts_nonexclusive': prepared['exclusion_reason_counts_nonexclusive'],
                           'manual_source_exclusions': excluded}
    receipt = {'format': FORMAT, 'created_at': utcnow(), 'configuration_sha256': configuration_sha256,
               'producer_sha256': sha(producer), 'canonical_sequences': len(canonical),
               'source_files': {str(p.relative_to(root)): expected_source_pins[str(p)] for p in files},
               'scopes': summaries, 'files': outputs, 'graph_changed': False, 'model_calls': 0,
               'unknown_as_negative': False, 'independent_experiment_claimed': False,
               'interpretation': 'Source-pinned published curator labels; exactcanonicalphysical gold and incompletelycontextualized manual-assaypairgold remain separate. No functionalassociation falselabels or wholegraphaccuracy implied.'}
    need(sha(configuration) == configuration_sha256 and sha(producer) == config['producer_source']['sha256'],
         'preparation source changed.')
    for path in files:
        need(sha(path) == receipt['source_files'][str(path.relative_to(root))], 'reference source changed.')
    write_json(folder / 'preparation_receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--configuration-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = run(args.configuration, args.configuration_sha256, args.out, root=args.root)
    print(json.dumps({'format': result['format'], 'scopes': result['scopes']}))


if __name__ == '__main__':
    main()
