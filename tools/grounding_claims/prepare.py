"""Prepare a label-blind, source-bound human-gene grounding frame."""
from collections import Counter
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from .native import project_evidence

FORMAT = 'biograph-steward.grounding-claim-frame.v1'
SPLIT_SEED = '20261113-grounding-v1'


def need(ok, message):
    if not ok:
        raise ValueError('Grounding frame: ' + message)


def ordinary(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), 'ordinary source file required.')
    return path


def signed_id(value):
    need(type(value) in (str, int), 'source IDs must be signed-decimal integers or strings.')
    text = str(value)
    need(re.fullmatch(r'0|-?[1-9][0-9]*', text) is not None, 'source ID is not canonical signed decimal.')
    return text


def case_id(pa, source):
    return 'indra:' + signed_id(pa) + ':' + signed_id(source)


def split_for_group(group_id, *, exposed=False):
    need(isinstance(group_id, str) and re.fullmatch('[0-9a-f]{64}', group_id), 'invalid exposure-group identity.')
    if exposed:
        return 'development'
    value = hashlib.sha256((SPLIT_SEED + ':' + group_id).encode()).digest()
    return 'test' if int.from_bytes(value[:8], 'big') % 4 == 0 else 'development'


def inventory_publication_consensus(evidence):
    """Replay the *original* conservative blind-audit metadata commitment."""
    refs = evidence.get('text_refs')
    refs = refs if isinstance(refs, dict) else {}
    supplied = [x for x in (evidence.get('pmid'), refs.get('PMID')) if x not in (None, '')]
    values = set()
    for value in supplied:
        if type(value) not in (str, int) or not re.fullmatch(r'[0-9]+', str(value).strip()):
            return None
        number = int(str(value).strip())
        if number < 1:
            return None
        values.add(str(number))
    return next(iter(values)) if len(values) == 1 else None


def publication_consensus(evidence):
    """Use validated native citation identity, preserving stale reader metadata.

    INDRA's documented Sparser setter can update Evidence.pmid while retaining
    an internal TEXT identifier in text_refs.PMID. DisambManager prioritizes
    the legacy PMID. Invalid strings are not competing PubMed identifiers;
    different valid numeric identifiers remain an unresolved conflict.
    """
    from .native import _pmid
    return _pmid(evidence, [])


def _source_encoded(value):
    # The native streaming audit uses published simplejson to preserve Decimal
    # values. This is parsed-value canonicalization, not literal byte slicing.
    import simplejson
    return simplejson.dumps(value, sort_keys=True, separators=(',', ':'),
                            ensure_ascii=False, use_decimal=True, allow_nan=False).encode()


def prepare(join_dir, exposure_file, output, *, projector=project_evidence):
    join_dir = Path(join_dir).absolute()
    files = {n: ordinary(join_dir / n) for n in (
        'join_report.json', 'pair_join_inventory.json', 'selected_statements.jsonl', 'exposure_groups.json')}
    exposure_file = ordinary(exposure_file)
    pins = {str(p): sha(p) for p in (*files.values(), exposure_file)}
    report = json.loads(files['join_report.json'].read_text())
    need(report.get('curation_tag_comment_or_correctness_fields_used') is False
         and report.get('grounder_or_model_predictions_run') is False
         and report.get('all_original_pair_IDs_joined') is True,
         'the source join is not a complete label-blind inventory.')
    need(report.get('content_sha256') == digest({k: v for k, v in report.items() if k != 'content_sha256'}),
         'blind join content seal differs.')
    for name in ('pair_join_inventory.json', 'selected_statements.jsonl', 'exposure_groups.json'):
        need(report['outputs'][name]['SHA256'] == sha(files[name]), 'blind joined file differs: ' + name)
    inventory = json.loads(files['pair_join_inventory.json'].read_text())
    groups = json.loads(files['exposure_groups.json'].read_text())
    exposure = json.loads(exposure_file.read_text())
    need(exposure.get('labels_inspected') is False and isinstance(exposure.get('tokens'), list),
         'use a source-only prior-exposure inventory.')
    exposed_tokens = set(exposure['tokens'])
    pair_group, group_splits = {}, {}
    token_owner = {}
    for group in groups['groups']:
        tokens = set(group['candidate_tokens'])
        gid = group['group_id']
        group_splits[gid] = split_for_group(gid, exposed=bool(tokens & exposed_tokens))
        for token in tokens:
            need(token not in token_owner, 'an exposure token crosses groups.')
            token_owner[token] = gid
        for pair in group['pair_ids']:
            need(pair not in pair_group, 'a source pair crosses exposure groups.')
            pair_group[pair] = gid
    need(len(pair_group) == len(inventory['pairs']), 'group inventory differs from the reference pairs.')
    import simplejson
    statements = {}
    with files['selected_statements.jsonl'].open() as stream:
        for line in stream:
            source = simplejson.loads(line, use_decimal=True)
            need(hashlib.sha256(_source_encoded(source['statement'])).hexdigest()
                 == source['canonical_statement_sha256'], 'selected source Statement differs.')
            ordinal = source['corpus_ordinal']
            need(type(ordinal) is int and ordinal not in statements, 'duplicate source Statement ordinal.')
            # Native INDRA's normal JSON API uses Python floats for non-ID
            # decimal values. IDs remain exact ints/strings; original lossless
            # source bytes and canonical commitments remain separately bound.
            statements[ordinal] = {
                'native': json.loads(_source_encoded(source['statement'])),
                'canonical_sha256': source['canonical_statement_sha256'],
                'evidence_sha256': [hashlib.sha256(_source_encoded(ev)).hexdigest()
                                   for ev in source['statement'].get('evidence', [])]}
    out = new_output(output, join_dir, exposure_file)
    reasons, scope_counts, cases, all_pmids = Counter(), Counter(), [], set()
    coverage = []
    for pair in inventory['pairs']:
        pa, src = signed_id(pair['pa_hash']), signed_id(pair['source_hash'])
        key, identifier = pa + ':' + src, case_id(pa, src)
        gid = pair_group[key]
        need(type(pair.get('matched')) is bool
             and type(pair.get('all_occurrences_have_explicit_all_HGNC_origins')) is bool,
             'native pair status fields must be booleans.')
        for field in ('evidence_payload_variant_count', 'statement_payload_variant_count'):
            need(type(pair.get(field)) is int and pair[field] >= 0, 'native variant count must be an integer.')
        reason = None
        if not pair.get('matched'):
            reason = 'source_pair_unjoined'
        elif pair['evidence_payload_variant_count'] != 1 or pair['statement_payload_variant_count'] != 1:
            reason = 'multiple_source_payloads_for_curated_hash_pair'
        elif not pair['all_occurrences_have_explicit_all_HGNC_origins']:
            reason = 'outside_explicit_human_gene_origin_frame'
        occurrence = pair['evidence_occurrences'][0] if reason is None else None
        projection = None
        if occurrence:
            ordinal, evidence_ordinal = occurrence['corpus_ordinal'], occurrence['evidence_ordinal']
            need(type(ordinal) is int and type(evidence_ordinal) is int
                 and ordinal in statements and evidence_ordinal >= 0, 'invalid native source ordinal.')
            source = statements[ordinal]
            statement = source['native']
            need(evidence_ordinal < len(statement['evidence'])
                 and occurrence['canonical_statement_sha256'] == source['canonical_sha256']
                 and occurrence['canonical_evidence_sha256'] == source['evidence_sha256'][evidence_ordinal],
                 'source occurrence payload commitment differs.')
            evidence = statement['evidence'][evidence_ordinal]
            need(signed_id(statement['matches_hash']) == pa and signed_id(evidence['source_hash']) == src,
                 'source Statement/Evidence identity differs from the joined inventory.')
            pmid = publication_consensus(evidence)
            need(occurrence['publication']['single_PMID_consensus'] == inventory_publication_consensus(evidence),
                 'source publication context differs from native Evidence.')
            need(pmid is None or token_owner.get('PMID:' + pmid) == gid,
                 'native source PMID is outside its publication-disjoint exposure group.')
            # A native source object is selected only when *all* source payloads
            # for this hash pair are identical. This is not an arbitrary
            # selection among different papers, contexts or agent origins.
            projection = projector(statement, evidence)
            actual = [a for a in projection['agents'] if a['status'] != 'neutral']
            if projection['status'] != 'ready':
                reason = 'native_projection_unresolved'
            elif not actual or any(a['assigned']['namespace'] != 'HGNC' for a in actual):
                reason = 'outside_native_preferred_HGNC_frame'
        if reason:
            reasons[reason] += 1
            coverage.append({'case_id': identifier, 'pa_hash': pa, 'source_hash': src,
                             'status': 'outside_primary_frame', 'reason': reason,
                             'group_id': gid, 'split': group_splits[gid]})
            continue
        pmid = publication_consensus(evidence)
        if pmid:
            all_pmids.add(pmid)
        row = {'case_id': identifier, 'pa_hash': pa, 'source_hash': src,
               'group_id': gid, 'split': group_splits[gid], 'pmid': pmid,
               'publication_resolution': {
                   'native_inventory_strict_consensus': occurrence['publication']['single_PMID_consensus'],
                   'validated_native_PMID': pmid,
                   'malformed_native_fields_preserved': occurrence['publication']['malformed_nonempty_PMID_fields'],
                   'policy': 'Unique valid native PMID; invalid secondary reader IDs do not veto it, conflicting valid IDs remain unknown.'},
               'source_api': projection['source_api'], 'input': projection,
               'source_origin': {'corpus_ordinal': occurrence['corpus_ordinal'],
                   'evidence_ordinal': occurrence['evidence_ordinal'],
                   'canonical_statement_sha256': occurrence['canonical_statement_sha256'],
                   'canonical_evidence_sha256': occurrence['canonical_evidence_sha256']}}
        cases.append(row)
        scope_counts[row['split']] += 1
        coverage.append({k: v for k, v in row.items() if k not in ('input', 'source_origin')})
    with gzip.open(out / 'cases.jsonl.gz', 'wt', encoding='utf-8') as stream:
        for row in cases:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n')
    write_json(out / 'frame_coverage.json', coverage)
    write_json(out / 'requested_pmids.json', sorted(all_pmids, key=int))
    write_json(out / 'group_splits.json', group_splits)
    need(all(sha(path) == pin for path, pin in pins.items()), 'source changed during frame preparation.')
    result = {'format': FORMAT, 'created_at': utcnow(),
        'task': 'Curator-relative human-gene grounding-conflict detection; not protein-form or biological truth.',
        'primary_frame': 'Unique complete source payload, explicit evidence-specific agent text and native preferred HGNC identity for every actual agent.',
        'reference_source_pairs': len(inventory['pairs']), 'primary_cases': len(cases),
        'outside_primary_counts': dict(reasons), 'primary_split_counts': dict(scope_counts),
        'groups': len(group_splits), 'requested_PMIDs': len(all_pmids),
        'restored_valid_citation_cases': sum(r['pmid'] is not None
            and r['publication_resolution']['native_inventory_strict_consensus'] is None for r in cases),
        'label_categories_inspected': False, 'predictions_run': False,
        'source_IDs_rewritten': False, 'graph_or_review_changed': False,
        'split_policy': 'Publication/source-hash/Statement-family components; fixed SHA256 quarter test; known reviewed-source tokens forced to development before labels.',
        'split_seed': SPLIT_SEED, 'prior_exposure_audit_not_exhaustive': True,
        'pretrained_grounder_paper_training_independence_established': False,
        'input_files_sha256': pins, 'implementation_sha256': sha(__file__),
        'native_adapter_sha256': sha(Path(__file__).with_name('native.py')),
        'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    result['content_sha256'] = digest(result)
    write_json(out / 'report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--join', required=True, type=Path)
    parser.add_argument('--exposure', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(prepare(args.join, args.exposure, args.out)['content_sha256'])


if __name__ == '__main__':
    main()
