"""Read a pinned used-term GO snapshot-content index, never a truth verdict.

This standard-library consumer does not run an ontology reasoner, resolve an
alias, modify a graph, or update a historical prediction's meaning.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re

from .client import digest

FORMAT = 'biograph-steward.go-used-term-content-currency.v1'
TERM = re.compile(r'GO:[0-9]{7}')
MAX_INDEX_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 160 * 1024 * 1024
FLAGS = ('name_changed', 'definition_text_changed', 'namespace_changed',
         'synonym_scope_or_text_records_changed', 'explicit_is_a_part_of_records_changed')
LIMITATIONS = [
    'This is literal source-content qualification between two pinned snapshots, not biological accuracy or full ontology equivalence.',
    'Historical predictions retain their historical term meaning. The comparison snapshot has its own explicit date and is not asserted to be the latest release.',
    'An explicit parent, synonym, label or definition change requests source-scope inspection; it does not establish a false annotation or authorize pruning.',
    'Graph Pharos GO vintage remains unknown. Its recorded labels are preserved, not assigned the predictor historical ontology date.',
    'Missing literal identifiers and declared alternative identifiers or replacements remain source-qualified; no mapping or replacement is applied.'
]


def need(value, message):
    if not value:
        raise ValueError('GO term-content currency: ' + message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_term(row):
    need(isinstance(row, dict) and isinstance(row.get('term_id'), str)
         and TERM.fullmatch(row['term_id']) and isinstance(row.get('scopes'), list)
         and all(isinstance(x, str) for x in row['scopes'])
         and row['scopes'] == sorted(set(row['scopes'])) and bool(row['scopes']), 'term identity/scope differs.')
    need(row.get('semantic_equivalence_inferred') is False and row.get('biological_falsehood_inferred') is False
         and row.get('automatic_action') == 'none', 'source-content flags cannot become biological decisions.')
    for key in ('historical', 'comparison'):
        value = row.get(key)
        need(isinstance(value, dict) and type(value.get('present')) is bool
             and value.get('state') in ('active', 'obsolete', 'not_found'), 'invalid literal snapshot state.')
        need(value.get('name') is None or isinstance(value['name'], str), 'invalid source name.')
        need(value.get('definition') is None or isinstance(value['definition'], str), 'invalid source definition.')
    flags = row.get('flags')
    need(isinstance(flags, dict) and set(flags) == set(FLAGS)
         and all(v is None or type(v) is bool for v in flags.values()), 'literal flag scope differs.')
    need(isinstance(row.get('graph_labels'), list) and all(isinstance(x, str) for x in row['graph_labels']),
         'graph label records differ.')
    need(flags == literal_flags(row['historical'], row['comparison']), 'literal flags do not reproduce from saved fields.')
    return row


def literal_flags(old, new):
    """Compare recorded fields only; missing text remains unassessed."""
    result = {key: None for key in FLAGS}
    if old['present'] and new['present']:
        for key, field in (('name_changed', 'name'), ('definition_text_changed', 'definition'),
                           ('namespace_changed', 'namespace')):
            if old.get(field) is not None and new.get(field) is not None:
                result[key] = old[field] != new[field]
        result['synonym_scope_or_text_records_changed'] = {
            (x['scope'], x['value']) for x in old['synonyms']} != {
            (x['scope'], x['value']) for x in new['synonyms']}
        result['explicit_is_a_part_of_records_changed'] = {
            (x['predicate'], x['object']) for x in old['parents']} != {
            (x['predicate'], x['object']) for x in new['parents']}
    return result


def load_index(folder, expected_sha256):
    """Verify the compact saved index without loading scientific source data."""
    folder = Path(folder)
    need(folder.is_dir() and not folder.is_symlink() and isinstance(expected_sha256, str)
         and re.fullmatch('[a-f0-9]{64}', expected_sha256), 'supply an ordinary index directory and manifest FILE SHA.')
    manifest_path = folder / 'publication.json'
    need(manifest_path.is_file() and not manifest_path.is_symlink()
         and manifest_path.stat().st_size <= 1024 * 1024 and sha(manifest_path) == expected_sha256,
         'publication FILE differs.')
    m = json.loads(manifest_path.read_text())
    need(m.get('format') == FORMAT and m.get('content_sha256') == digest(
        {k: v for k, v in m.items() if k != 'content_sha256'}), 'publication seal/format differs.')
    need(m.get('semantic_equivalence_claimed') is False and m.get('biological_accuracy_measured') is False
         and m.get('automatic_graph_or_prediction_changes') is False, 'publication interpretation differs.')
    versions = m.get('source_versions', {})
    need(isinstance(versions, dict) and all(isinstance(versions.get(k), str)
         and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', versions[k])
         for k in ('historical_predictor', 'comparison_snapshot'))
         and versions.get('graph_Pharos_GO_vintage') == 'UNKNOWN'
         and versions.get('latest_release_claimed') is False, 'explicit snapshot/vintage qualification required.')
    need(set(m['files']) == {'terms.jsonl.gz'}, 'only the declared term index is consumed.')
    spec = m['files']['terms.jsonl.gz']; path = folder / 'terms.jsonl.gz'
    need(path.is_file() and not path.is_symlink() and path.stat().st_size == spec['bytes'] <= MAX_INDEX_BYTES
         and sha(path) == spec['sha256'], 'term-index source bytes differ.')
    rows = {}; total = 0
    with gzip.open(path, 'rb') as stream:
        while line := stream.readline(512 * 1024 + 1):
            total += len(line)
            need(len(line) <= 512 * 1024 and total <= MAX_EXPANDED_BYTES, 'expanded term index exceeds its bound.')
            row = validate_term(json.loads(line))
            need(row['term_id'] not in rows, 'term identity repeats.')
            rows[row['term_id']] = row
            need(len(rows) <= 50_000, 'used-term inventory exceeds its bound.')
    need(len(rows) == m['term_count'] and digest(sorted(rows)) == m['term_frame_sha256'],
         'complete term frame differs.')
    return m, rows


def get_term(manifest, rows, term_id):
    need(isinstance(term_id, str) and TERM.fullmatch(term_id), 'supply an exact GO CURIE.')
    need(term_id in rows, 'term is outside this declared used-term frame.')
    return {'format': FORMAT + '.lookup', 'source_versions': deepcopy(manifest['source_versions']),
            'source_publication_sha256': manifest['content_sha256'],
            'term': deepcopy(validate_term(rows[term_id])), 'limitations': list(LIMITATIONS),
            'graph_or_prediction_modified': False}


def project_terms(manifest, rows, term_ids):
    """Offline, exact-ID projection; raw ontology bodies stay in the full index.

    This deliberately accepts an explicit ID frame rather than discovering new
    model candidates or modifying a saved ranking. The caller supplies the full
    source-index FILE pin in its separate publication receipt.
    """
    need(isinstance(term_ids, (list, tuple)) and 0 < len(term_ids) <= 500
         and all(isinstance(uid, str) and TERM.fullmatch(uid) for uid in term_ids)
         and len(set(term_ids)) == len(term_ids), 'bounded unique exact projection IDs required.')
    projected = []
    for uid in sorted(term_ids):
        row = get_term(manifest, rows, uid)['term']
        for name in ('historical', 'comparison'):
            row[name].pop('raw_stanza', None)
            row[name].pop('native_node', None)
        projected.append(row)
    return projected
