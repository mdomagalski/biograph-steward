"""Offline native physical-network supplement, with exact sequence admission.

Reuses the qualified STRING 12.5 bulk readers, without fitting or selecting a
score cutoff. Complete pinned source files permit portable reader replay. The
functional graph, review states and earlier typed-overlay profile are preserved.
"""
from collections import Counter, OrderedDict
from copy import deepcopy
import gzip
from html import escape
from itertools import combinations
import io
import json
from pathlib import Path
import re
import threading

from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import digest, utcnow, write_json
from .file_utils import new_output, sha
from .string_native import (ACCESSION, crosswalk, mapped_pair, read_aliases,
                            read_links, sequence_records, need)
from .string_source_update import SOURCE_LICENSE

FORMAT = 'biograph-steward.native-STRING-physical-publication.v1'
PROJECTION_FORMAT = 'biograph-steward.native-STRING-physical-projection.v1'
POLICY = 'STRING12.5-native-physical-exact-reciprocal-sequence.v1'
EVIDENCE_TYPE = 'STRING12.5native_physical_association'
NAMES = {'canonical': 'canonical.fasta', 'aliases': '9606.protein.aliases.v12.5.txt.gz',
         'sequences': '9606.protein.sequences.v12.5.fa.gz',
         'physical': '9606.protein.physical.links.v12.5.txt.gz'}
LIMITATIONS = [
    'Native STRING physical associations describe predicted physical proximity or co-complex membership, not proof of direct binding.',
    'This separately named source profile preserves all original Pharos functional associations and does not automatically accept or prune assertions.',
    'STRING already contributes to Pharos; a separately versioned row is not an independent experiment or independent supporting study.',
    'Admission requires unique reciprocal literal UniProt_AC aliases and identical full canonical/source sequences; isoforms and unresolved identities are unavailable.',
    'Sequence equality binds these two pinned references, not historical Pharos sequences, assay constructs, tissue state or disease relevance.',
    'The complete pinned human physical file is scanned within the declared cohort. A pair not listed or an identity not admitted is unknown, never biological absence.',
    'Native bulk scores remain integers on the provider 0–1000 scale; physical_score_0_to_1 is exactly that integer divided by 1000. Source-file inclusion floors remain explicit, without a fitted threshold or biological accuracy claim.',
    'A source-file hash and replay prove local consistency, not independent remote authenticity or study-level evidence independence.',
]


def _seal(value):
    return {**value, 'content_sha256': digest(value)}


def _fasta(stream):
    """Strict literal FASTA framing; source letters and headers are not rewritten.

    Uses the existing forecast adapter's line-join rule, allowing the complete
    descriptive UniProt header required by the shared sequence identity reader.
    """
    header, parts = None, []
    for line in stream:
        row = line.rstrip('\r\n')
        if row.startswith('>'):
            if header is not None:
                yield header, ''.join(parts)
            header, parts = row[1:], []
            need(bool(header), 'empty FASTA header.')
        else:
            need(header is not None and re.fullmatch('[A-Z]+', row), 'invalid literal FASTA sequence row.')
            parts.append(row)
    if header is not None:
        yield header, ''.join(parts)


def _text(raw, compressed=False):
    return io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)) if compressed else io.BytesIO(raw),
                            encoding='utf-8', newline='')


def _replay_projection(files):
    config = _decode(files['capture.json'])
    need(_sealed(config) and config.get('policy') == POLICY and config.get('release') == '12.5',
         'native physical source policy differs.')
    accessions = config.get('accessions')
    need(isinstance(accessions, list) and 2 <= len(accessions) <= 250
         and accessions == sorted(set(accessions))
         and all(isinstance(a, str) and ACCESSION.fullmatch(a) for a in accessions),
         'bounded literal canonical accession cohort required.')
    need(isinstance(config.get('canonical_release'), str) and bool(config['canonical_release'])
         and isinstance(config.get('snapshot_sha256'), str)
         and re.fullmatch('[0-9a-f]{64}', config['snapshot_sha256']), 'source release/snapshot binding missing.')
    specs = config.get('source_files')
    need(isinstance(specs, dict) and set(specs) == set(NAMES), 'complete native bulk source inventory required.')
    for role, name in NAMES.items():
        spec, raw = specs[role], files['source/' + name]
        need(isinstance(spec, dict) and set(spec) == {'file', 'sha256', 'bytes', 'url'} and spec['file'] == 'source/' + name
             and isinstance(spec['url'], str) and spec['url'].startswith('https://')
             and len(raw) == spec['bytes'] and digest_bytes(raw) == spec['sha256'],
             'preserved complete source bytes or provenance changed.')
    with _text(files['source/canonical.fasta']) as stream:
        canonical = sequence_records(_fasta(stream), canonical=True)
    with _text(files['source/' + NAMES['sequences']], True) as stream:
        source = sequence_records(_fasta(stream), canonical=False)
    with _text(files['source/' + NAMES['aliases']], True) as stream:
        aliases, alias_meta = read_aliases(stream, canonical)
    all_mapping = crosswalk(canonical, source, aliases)
    mapping = {a: all_mapping.get(a, {'canonical_accession': a,
        'direct_STRING_alias_candidates': [], 'selected_STRING_ID': None,
        'admission': 'accession_outside_reviewed_canonical_reference',
        'canonical_sequence_sha256': None, 'source_sequence_sha256': None,
        'biological_truth_inferred': False}) for a in accessions}
    pairs = list(combinations(accessions, 2))
    wanted = {key for pair in pairs for key, reason in [mapped_pair(pair, mapping)] if key is not None}
    with _text(files['source/' + NAMES['physical']], True) as stream:
        scores, scan = read_links(stream, wanted, set(source))
    ledger = []
    for pair in pairs:
        key, reason = mapped_pair(pair, mapping)
        value = scores.get(key)
        state = ('identity_unavailable' if reason else 'native_physical_pair_not_listed' if value is None
                 else 'native_physical_association')
        ledger.append({'id': 'native-physical-observation:' + digest([POLICY, pair])[:24],
            'source_kind': 'string_physical',
            'source_locators': [{'role': 'complete_pair_and_identity_ledger',
                'locator': 'extension_sources/string_physical/projection.json#/pair_ledger/' + str(len(ledger))}],
            'products': ['UniProtKB:' + a for a in pair], 'state': state,
            'identity_unavailable_reason': reason, 'STRING_pair': list(key) if key else None,
            'native_physical_score': int(round(value * 1000)) if value is not None else None,
            'physical_score_0_to_1': value, 'mapping_proof': [deepcopy(mapping[a]) for a in pair]})
    return _seal({'format': PROJECTION_FORMAT, 'policy': POLICY, 'source_kind': 'string_native_physical',
        'source_release': '12.5', 'canonical_release': config['canonical_release'],
        'snapshot_sha256': config['snapshot_sha256'],
        'scope': {'kind': 'complete_declared_cohort_native_physical_network', 'accessions': accessions,
                  'possible_unordered_pairs': len(pairs), 'add_nodes': 0},
        'source_files': deepcopy(specs), 'mappings': mapping, 'pair_ledger': ledger,
        'summary': {'requested_accessions': len(accessions), 'possible_unordered_pairs': len(pairs),
            'mapping_admission_counts': dict(sorted(Counter(r['admission'] for r in mapping.values()).items())),
            'pair_states': dict(sorted(Counter(r['state'] for r in ledger).items())),
            'complete_human_source_scan': scan,
            'all_reference_identity_counts': dict(sorted(Counter(r['admission'] for r in all_mapping.values()).items())),
            'canonical_reference_proteins': len(canonical), 'STRING_sequence_proteins': len(source),
            'alias_scan': alias_meta, 'selection_threshold': None,
            'score_scales': {'native_physical_score': 'integer_0_to_1000',
                'physical_score_0_to_1': 'native_physical_score / 1000; provider score rescaling only'},
            'biological_accuracy_established': False, 'independent_evidence_count': None},
        'limitations': list(LIMITATIONS)})


# Full native files are hashed on every publication load. Reader replay can be
# reused only for identical complete source bytes, not mutable paths or mtimes.
# Two bounded entries keep repeated HTTP source checks practical on the CPU.
_PROJECTIONS = OrderedDict()
_PROJECTION_LOCK = threading.RLock()


def _projection(files):
    names = ['capture.json', *('source/' + name for name in NAMES.values())]
    need(isinstance(files, dict) and set(names) <= set(files), 'complete native bulk files and capture are required.')
    key = digest({name: digest_bytes(files[name]) for name in names})
    with _PROJECTION_LOCK:
        if key not in _PROJECTIONS:
            _PROJECTIONS[key] = _replay_projection(files)
            if len(_PROJECTIONS) > 2:
                _PROJECTIONS.popitem(last=False)
        _PROJECTIONS.move_to_end(key)
        return deepcopy(_PROJECTIONS[key])


def digest_bytes(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def publish_sources(snapshot, sources, output):
    """Publish pinned generic bulk files; never retrieve or load reference labels.

    sources contains release, canonical_release and four named files, each with
    path, expected sha256 and original URL. Entire preserved sources replay.
    """
    need(_sealed(snapshot) and snapshot.get('data_kind') == 'live_pharos', 'bound live Pharos snapshot required.')
    need(isinstance(sources, dict) and sources.get('release') == '12.5'
         and isinstance(sources.get('canonical_release'), str) and bool(sources['canonical_release'])
         and isinstance(sources.get('files'), dict) and set(sources['files']) == set(NAMES),
         'exact native source manifest required.')
    files, specs = {}, {}
    input_paths = []
    for role, name in NAMES.items():
        spec = sources['files'][role]
        need(isinstance(spec, dict) and set(spec) == {'path', 'sha256', 'url'}
             and isinstance(spec['path'], str) and isinstance(spec['sha256'], str)
             and re.fullmatch('[0-9a-f]{64}', spec['sha256'])
             and isinstance(spec['url'], str) and spec['url'].startswith('https://'),
             'source manifest requires literal path, SHA-256 and original HTTPS URL.')
        path = Path(spec['path']).absolute(); raw = _ordinary(path)
        need(sha(path) == spec['sha256'], 'declared bulk source byte pin differs.')
        files['source/' + name] = raw; input_paths.append(path)
        specs[role] = {'file': 'source/' + name, 'sha256': spec['sha256'], 'bytes': len(raw), 'url': spec['url']}
    accessions = [r['uniprot'] for r in snapshot['targets']]
    need(len(accessions) == len(set(accessions)), 'duplicate cohort accession.')
    config = _seal({'policy': POLICY, 'release': '12.5', 'canonical_release': sources['canonical_release'],
        'snapshot_sha256': snapshot['content_sha256'], 'accessions': sorted(accessions), 'source_files': specs})
    files['capture.json'] = json.dumps(config, sort_keys=True).encode() + b'\n'
    projection = _projection(files)
    folder = new_output(output, *(p.parent for p in input_paths))
    for name, raw in files.items():
        path = folder / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    write_json(folder / 'projection.json', projection)
    (folder / 'LICENSE.txt').write_text('STRING 12.5 and UniProt data: CC BY 4.0. Attribute both original providers.\n'
        'https://creativecommons.org/licenses/by/4.0/\nhttps://string-db.org/\nhttps://www.uniprot.org/\n')
    (folder / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>Native STRING physical source</title><h1>Native STRING 12.5 physical source</h1>'
        '<p>Separately sourced physical proximity/co-complex associations. Original functional evidence stays in the workspace.</p>'
        '<pre>' + escape(json.dumps(projection['summary'], indent=2)) + '</pre>'
        '<p>No automatic acceptance, pruning or direct-binding inference.</p><a href="projection.json">Complete pair and identity ledger</a></html>')
    manifest = _seal({'format': FORMAT, 'created_at': utcnow(), 'policy': POLICY,
        'source_kind': 'string_native_physical', 'source_release': '12.5',
        'source_license': deepcopy(SOURCE_LICENSE), 'summary': deepcopy(projection['summary']),
        'snapshot_sha256': snapshot['content_sha256'], 'projection_sha256': projection['content_sha256'],
        'model_calls': 0, 'baseline_modified': False, 'automatic_pruning': False,
        'independent_validation_performed': False,
        'files': {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}})
    write_json(folder / 'publication.json', manifest)
    return load_publication(folder)[0]


def load_publication(path):
    manifest, files = _capture(path, 'publication.json')
    need(manifest.get('format') == FORMAT and manifest.get('policy') == POLICY
         and manifest.get('model_calls') == 0 and manifest.get('source_release') == '12.5'
         and manifest.get('source_license') == SOURCE_LICENSE
         and all(manifest.get(k) is False for k in ('baseline_modified', 'automatic_pruning', 'independent_validation_performed')),
         'native physical publication contract differs.')
    projection = _projection(files)
    need(projection == _decode(files['projection.json'])
         and manifest.get('summary') == projection['summary']
         and manifest.get('projection_sha256') == projection['content_sha256']
         and manifest.get('snapshot_sha256') == projection['snapshot_sha256'],
         'physical projection differs from complete source replay.')
    return manifest, projection, files


def prepare(snapshot, baseline_graph, manifest, projection):
    need(_sealed(manifest) and _sealed(projection) and manifest.get('format') == FORMAT
         and manifest.get('projection_sha256') == projection['content_sha256']
         and projection.get('policy') == POLICY, 'native physical publication/projection binding differs.')
    need(_sealed(snapshot) and snapshot.get('data_kind') == 'live_pharos'
         and baseline_graph.get('snapshot_sha256') == snapshot['content_sha256'] == projection['snapshot_sha256']
         and {r['uniprot'] for r in snapshot['targets']} == set(projection['scope']['accessions']),
         'physical source does not cover exactly this Pharos snapshot cohort.')
    nodes = {n['id'] for n in baseline_graph['nodes'] if n.get('category') == 'biolink:Protein'}
    old_pairs = {tuple(sorted((e['subject'], e['object']))) for e in baseline_graph['edges']
                 if e.get('record_kind') == 'protein_interaction'}
    edges, observations = [], []
    for row in projection['pair_ledger']:
        pair = tuple(row['products']); observation = deepcopy(row)
        observation['baseline_pair_present'] = pair in old_pairs
        observation['graph_edge_id'] = None
        if not set(pair) <= nodes:
            observation['integration_state'] = 'endpoint_outside_resolved_cohort'
        elif row['state'] != 'native_physical_association':
            observation['integration_state'] = row['state']
        else:
            eid = 'native-string-physical:' + digest([POLICY, pair, manifest['content_sha256']])[:24]
            observation.update(graph_edge_id=eid, integration_state='additional_versioned_source_record' if pair in old_pairs else 'new_workspace_pair')
            locator = 'extension_sources/string_physical/projection.json#/pair_ledger/' + str(len(observations))
            edges.append({'id': eid, 'subject': pair[0], 'object': pair[1],
                'predicate': 'biograph:has_interaction_annotation', 'record_kind': 'protein_interaction',
                'primary_source_raw': 'STRING', 'evidence_sources': ['STRING'], 'publications': [],
                'reference_raw': None, 'status': 'passed_structural_checks', 'review_reasons': [],
                'record_locators': [locator], 'source_record_count': 1, 'duplicate_count': 0, 'symmetric': True,
                'qualifiers': {'evidence_type': EVIDENCE_TYPE, 'species': 'NCBITaxon:9606'},
                'source_scores_raw': {'physical_combined_score': row['native_physical_score']},
                'evidence_record': {'source_release': '12.5', 'network_type': 'physical',
                    'mapping_proof': deepcopy(row['mapping_proof']), 'STRING_pair': deepcopy(row['STRING_pair']),
                    'native_bulk_combined_score': row['native_physical_score'],
                    'physical_score_0_to_1': row['physical_score_0_to_1'],
                    'display_score_rule': 'native_bulk_combined_score / 1000',
                    'source_files': deepcopy(projection['source_files'])},
                'snapshot_sha256': snapshot['content_sha256'], 'data_kind': 'published_database_annotations',
                'biologically_validated': False, 'extension_source_kind': 'string_physical',
                'extension_publication_sha256': manifest['content_sha256'],
                'retrieval_provenance': {'aggregator': 'STRING', 'database_version': '12.5',
                    'source_responses': ['extension_sources/string_physical/' + s['file'] for s in projection['source_files'].values()]},
                'normalization_notes': list(LIMITATIONS)})
        observations.append(observation)
    return {'nodes': [], 'edges': edges, 'observations': observations, 'summary': {
        **deepcopy(projection['summary']), 'source_release': '12.5', 'policy': POLICY,
        'publication_sha256': manifest['content_sha256'], 'additional_source_records': len(edges),
        'integration_state_counts': dict(sorted(Counter(r['integration_state'] for r in observations).items())),
        'automatic_acceptance_performed': False, 'automatic_pruning_performed': False,
        'biological_validation_performed': False, 'source_license': deepcopy(SOURCE_LICENSE),
        'limitations': list(LIMITATIONS)}}
