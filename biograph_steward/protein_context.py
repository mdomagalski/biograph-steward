"""Offline, exact-protein sequence context; never new graph evidence.

Registration order is explicit. Native match records, including neural methods,
versions, missing values, fragments and sites, are retained without merging.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from .client import PharosClient, PharosError, digest
from .file_utils import sha
from .graph import UNIPROT
from .inspection import _selection
from .questions import graph_basis

FORMAT = 'biograph-steward.protein-context.v1'
INDEX = 'protein_context_index.json'
INDEX_FORMAT = 'biograph-steward.protein-context-index.v1'
MANIFEST = 'protein_context.json'
SHA = re.compile(r'[a-f0-9]{64}')
IPR = re.compile(r'IPR[0-9]{6}')
FAMILIES = ('interpro', 'pfam', 'prosite', 'smart', 'panther')
LIMITATIONS = [
    'This is current retrieved reference-sequence context, not the historical workspace sequence or an experimental construct/proteoform.',
    'Matching entry identifiers do not establish identical annotation versions, independent experiments or new biological knowledge.',
    'Integrated InterPro entries and their member signatures are related records, not independent supporting votes. Neural and conventional methods remain distinct.',
    'Coordinates, fragments and sites retain native provider semantics; no clinical, disease-specific, catalytic or physical-interaction claim is inferred.',
    'Missing sequence, absent database match and a found record with no matches are distinct; none establishes biological absence.',
    'Native GO lineage concerns its own preserved annotation; no historical Pharos record identity, mapping-version equivalence or independent corroboration is established.',
    'Optional entry lifecycle and editorial metadata are a separately dated current API lookup; they do not remap historical identifiers or establish equality with the saved Matches release.',
]


def _need(value, message):
    if not value:
        raise ValueError('Protein context: ' + message)


def _protein(value):
    return isinstance(value, str) and value.startswith('UniProtKB:') and bool(UNIPROT.fullmatch(value[10:]))


def _sha(value):
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def _read(path, limit=25_000_000):
    path = Path(path)
    _need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit,
          'bounded ordinary source file required.')
    def invalid_constant(value):
        raise ValueError('Nonfinite JSON source value: ' + value)
    try:
        return json.loads(path.read_bytes(), parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError('Protein context: malformed JSON source.') from error


def _sealed(value):
    return isinstance(value, dict) and value.get('content_sha256') == digest(
        {key: item for key, item in value.items() if key != 'content_sha256'})


def _relative(value):
    _need(isinstance(value, str) and value and '\\' not in value,
          'canonical relative source path required.')
    path = PurePosixPath(value)
    _need(not path.is_absolute() and path.as_posix() == value
          and all(part not in ('', '.', '..') for part in path.parts), 'unsafe source path.')
    return value


def load_publication(folder, expected_manifest_sha256):
    """Verify one bounded immutable source packet; perform no source calls."""
    from .protein_context_source import normalize_sequence, parse_match_rpc
    folder = Path(folder).absolute()
    _need(folder.is_dir() and not folder.is_symlink() and _sha(expected_manifest_sha256),
          'ordinary publication folder and exact manifest FILE pin required.')
    manifest_path = folder / MANIFEST
    _need(manifest_path.is_file() and not manifest_path.is_symlink()
          and manifest_path.stat().st_size <= 2_000_000
          and sha(manifest_path) == expected_manifest_sha256, 'manifest FILE differs.')
    manifest = _read(manifest_path, 2_000_000)
    _need(_sealed(manifest) and manifest.get('format') == FORMAT
          and manifest.get('source_scope') == 'current_retrieved_sequence_context'
          and manifest.get('tool_name') == 'matchSequences' and manifest.get('model_calls') == 0,
          'source manifest format/scope differs.')
    for key in ('app_or_graph_changed', 'scientific_accuracy_assessed',
                'historical_pharos_record_identity_established'):
        _need(manifest.get(key) is False, 'source-only publication boundary differs.')
    _need(isinstance(manifest.get('created_at'), str)
          and datetime.fromisoformat(manifest['created_at']).tzinfo is not None, 'dated source context required.')
    files = manifest.get('files')
    _need(isinstance(files, dict) and 1 <= len(files) <= 1000, 'bounded source inventory required.')
    paths = list(folder.rglob('*'))
    _need(not any(path.is_symlink() for path in paths)
          and all(path.is_file() or path.is_dir() for path in paths)
          and {p.relative_to(folder).as_posix() for p in paths if p.is_file()}
              == set(files) | {MANIFEST}, 'source inventory contains undeclared files or links.')
    contents = {}; total = 0
    for name, pin in files.items():
        _relative(name)
        _need(name != MANIFEST and isinstance(pin, dict)
              and set(pin) == {'sha256', 'bytes'} and _sha(pin['sha256'])
              and type(pin['bytes']) is int and 0 <= pin['bytes'] <= 25_000_000,
              'source file pin/size differs.')
        path = folder / name
        _need(path.is_file() and not path.is_symlink() and path.stat().st_size == pin['bytes']
              and sha(path) == pin['sha256'], 'source bytes differ: ' + name)
        total += pin['bytes']
    _need(total <= 200_000_000, 'source packet exceeds its bound.')

    def source(name):
        _relative(name); _need(name in files, 'source file is not inventoried.')
        if name not in contents:
            contents[name] = _read(folder / name)
        return contents[name]

    before = source(manifest['info_before_file']); after = source(manifest['info_after_file'])
    _need(isinstance(before, dict) and isinstance(after, dict)
          and all(key in before and key in after and before[key] == after[key]
                  for key in ('api', 'release', 'release_date', 'analyses')), 'mixed or missing Matches release metadata.')
    tools = source(manifest['tools_file'])
    _need(isinstance(tools, dict) and not tools.get('error') and isinstance(tools.get('result'), dict)
          and isinstance(tools['result'].get('tools'), list)
          and all(isinstance(tool, dict) for tool in tools['result']['tools']),
          'native tools/list response required.')
    selected = [tool for tool in tools['result'].get('tools', []) if tool.get('name') == 'matchSequences']
    _need(len(selected) == 1 and digest(selected[0]) == manifest.get('tool_schema_sha256'),
          'native full tool schema differs.')
    requests = source(manifest['requests_file'])
    _need(isinstance(requests, dict) and isinstance(requests.get('requests'), list),
          'recorded source request inventory required.')
    entries = manifest.get('entry_files', {})
    _need(isinstance(entries, dict) and len(entries) <= 100,
          'bounded explicit entry metadata required.')
    entry_metadata = {}
    for identifier, name in entries.items():
        _need(isinstance(identifier, str) and IPR.fullmatch(identifier),
              'exact requested InterPro entry identifier required.')
        body = source(name)
        receipts = [row for row in requests['requests']
                    if isinstance(row, dict) and row.get('response_file') == name]
        _need(len(receipts) == 1, 'unique native entry request receipt required.')
        receipt = receipts[0]; status = receipt.get('http_status')
        _need(type(status) is int and status in (200, 410)
              and receipt.get('method') == 'GET'
              and receipt.get('url') == 'https://www.ebi.ac.uk/interpro/api/entry/interpro/' + identifier + '/?format=json'
              and receipt.get('file_sha256') == files[name]['sha256'],
              'native entry source/status binding differs.')
        _need(isinstance(body, dict), 'native entry object required.')
        if status == 200:
            _need(isinstance(body.get('metadata'), dict)
                  and isinstance(body['metadata'].get('accession'), str)
                  and body['metadata']['accession'].upper() == identifier,
                  'current native entry identifier differs.')
            _need(all(key not in body['metadata'] or type(body['metadata'][key]) is bool
                      for key in ('is_llm', 'is_reviewed_llm', 'is_updated_llm')),
                  'native entry editorial flags must retain boolean values when supplied.')
        else:
            _need(isinstance(body.get('accession'), str)
                  and body['accession'].upper() == identifier
                  and body.get('source_database') == 'interpro'
                  and isinstance(body.get('deletion_date'), str) and body['deletion_date'],
                  'deleted native entry identifier/date differs.')
        entry_metadata[identifier] = {'interpro_id': identifier, 'http_status': status,
            'native_record': deepcopy(body), 'source_pointer': name + '#',
            'source_url': receipt['url'], 'retrieved_at': receipt.get('completed_at'),
            'automatic_remapping_performed': False, 'independent_evidence': False}
    rows = manifest.get('proteins')
    _need(isinstance(rows, list) and 1 <= len(rows) <= 100
          and all(isinstance(row, dict) and _protein(row.get('protein')) for row in rows)
          and len({row['protein'] for row in rows}) == len(rows), 'exact bounded primary proteins required.')
    match_files = {row['matches_file'] for row in rows if row.get('matches_file') is not None}
    results = {}; file_results = {}
    for name in sorted(match_files):
        parsed = parse_match_rpc(source(name))
        _need(not set(results) & set(parsed), 'duplicate MD5 results across native responses.')
        results.update(parsed); file_results[name] = parsed
    proteins = {}; expected = set()
    for row in rows:
        envelope = source(row['pharos_file'])
        _need(isinstance(envelope, dict) and isinstance(envelope.get('response'), dict)
              and envelope.get('response_sha256') == digest(envelope['response']), 'Pharos envelope hash differs.')
        try:
            PharosClient._validate_response(envelope['response'])
        except PharosError as error:
            raise ValueError('Protein context: invalid native Pharos response.') from error
        data = envelope['response']['data']; target = data.get('target')
        _need(isinstance(target, dict) and target.get('uniprot') == row['protein'][10:],
              'Pharos returned a different exact protein/product identifier.')
        for family in FAMILIES:
            aliases = target.get(family)
            _need(aliases is None or (isinstance(aliases, list)
                  and all(isinstance(alias, dict) and isinstance(alias.get('name'), str)
                          for alias in aliases)), 'native Pharos alias list differs.')
        sequence = normalize_sequence(target.get('seq'))
        if sequence is None:
            _need(row.get('status') == 'sequence_unavailable' and all(row.get(key) is None
                  for key in ('query_md5', 'sequence_sha256', 'sequence_length', 'matches_file')),
                  'missing sequence cannot become a no-match observation.')
            result = None
        else:
            raw = sequence.encode('ascii'); md5 = hashlib.md5(raw).hexdigest().upper()
            _need(row.get('status') == 'sequence_available' and row.get('query_md5') == md5
                  and row.get('sequence_sha256') == hashlib.sha256(raw).hexdigest()
                  and type(row.get('sequence_length')) is int and row['sequence_length'] == len(sequence)
                  and row.get('matches_file') in file_results
                  and md5 in file_results[row['matches_file']], 'sequence/MD5/native result binding differs.')
            result = file_results[row['matches_file']][md5]; expected.add(md5)
            for match in result.get('matches') or []:
                for location in match['locations']:
                    _need(location['end'] <= len(sequence), 'native match exceeds the exact source sequence.')
                    for fragment in location['location-fragments']:
                        _need(location['start'] <= fragment['start'] <= fragment['end'] <= location['end'],
                              'native fragment is outside its recorded location.')
                    for site in location.get('sites') or []:
                        _need(all(position['end'] <= len(sequence) for position in site['siteLocations']),
                              'native site exceeds the exact source sequence.')
        result_index = (list(file_results[row['matches_file']]).index(row['query_md5']) if result is not None else None)
        proteins[row['protein']] = {'manifest': deepcopy(row), 'pharos': deepcopy(envelope),
                                    'result': deepcopy(result), 'result_index': result_index}
    _need(set(results) == expected, 'missing or unrequested native MD5 response.')
    return {'manifest': manifest, 'manifest_sha256': expected_manifest_sha256,
            'proteins': proteins, 'info_before': before, 'info_after': after,
            'entry_metadata': entry_metadata}


def registered_contexts(runs_dir):
    """Load explicit registrations in their original order; no directory scan."""
    root = Path(runs_dir).absolute()
    _need(root.is_dir() and not root.is_symlink(), 'ordinary runs directory required.')
    path = root / INDEX
    if not path.exists():
        return []
    index = _read(path, 1_000_000)
    _need(isinstance(index, dict) and index.get('format') == INDEX_FORMAT
          and isinstance(index.get('contexts'), list) and len(index['contexts']) <= 100,
          'explicit bounded context index required.')
    if 'content_sha256' in index:
        _need(_sealed(index), 'context index content seal differs.')
    registrations = []; seen = set()
    for row in index['contexts']:
        _need(isinstance(row, dict) and set(row) == {'id', 'manifest_sha256'}
              and isinstance(row['id'], str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', row['id'])
              and row['id'] not in seen and _sha(row['manifest_sha256']), 'invalid or duplicate registration.')
        seen.add(row['id'])
        registrations.append({**row, 'publication': load_publication(root / row['id'], row['manifest_sha256'])})
    return registrations


def _endpoints(graph, selection_id):
    _need(isinstance(selection_id, str) and 1 <= len(selection_id) <= 300, 'existing selection required.')
    _, selected, assertion, edges, observations = _selection(graph, selection_id)
    supplied = set()
    for row in [selected, assertion, *edges, *observations]:
        if isinstance(row, dict):
            supplied.update(row.get(key) for key in ('subject', 'object') if _protein(row.get(key)))
    nodes = {node['id']: node for node in graph.get('nodes', []) if node.get('category') == 'biolink:Protein'}
    return {protein: nodes[protein] for protein in sorted(supplied) if protein in nodes}


def selection_contexts(runs_dir, graph, selection_id):
    endpoints = _endpoints(graph, selection_id); registrations = registered_contexts(runs_dir)
    chosen = {}
    for registration in registrations:
        publication = registration['publication']
        for protein in endpoints:
            if protein not in chosen and protein in publication['proteins']:
                row = publication['proteins'][protein]['manifest']
                chosen[protein] = {'protein': protein, 'label': endpoints[protein].get('sym') or
                    endpoints[protein].get('name') or protein, 'context_id': registration['id'],
                    'manifest_sha256': registration['manifest_sha256'],
                    'created_at': publication['manifest']['created_at'], 'status': row['status']}
    return {'configured': bool(registrations), 'eligible': bool(chosen),
            'selection_id': selection_id, 'proteins': list(chosen.values())}


def _lineage(native_go, graph, selection_id, protein, source_run, present):
    result = {'status': 'not_configured', 'records': [], 'reference_independence_established': False,
              'historical_record_identity_established': False}
    if native_go is None:
        return result
    _need(_sealed(native_go) and native_go.get('format') == 'biograph-steward.native-go-selection.v1'
          and native_go.get('read_only') is True and native_go.get('source_run') == source_run
          and native_go.get('selection_id') == selection_id
          and native_go.get('snapshot_sha256') == graph['snapshot_sha256']
          and native_go.get('query', {}).get('protein') == protein
          and native_go.get('source_bytes_and_native_scope_verified') is True
          and isinstance(native_go.get('records'), list)
          and native_go.get('record_count') == len(native_go['records']), 'verified native GO context binding differs.')
    _, _, _, edges, _ = _selection(graph, selection_id)
    _need(edges and all(edge.get('record_kind') == 'go_annotation' for edge in edges)
          and {(edge.get('subject'), edge.get('object')) for edge in edges}
              == {(protein, native_go['query'].get('go_id'))}, 'native GO query differs from selected graph evidence.')
    records = []
    for row in native_go['records']:
        _need(row.get('subject') == protein and row.get('go_id') == native_go['query'].get('go_id'),
              'native GO subject/term differs from the selected scope.')
        groups = []
        for members in row['with_from_or_groups_raw']:
            _need(isinstance(members, list) and all(isinstance(token, str) for token in members),
                  'native With/From logical groups required.')
            matched = sorted({token[9:] for token in members
                if token.startswith('InterPro:') and IPR.fullmatch(token[9:]) and token[9:] in present})
            covered = {'InterPro:' + identifier for identifier in matched}
            groups.append({'members': deepcopy(members), 'matched_interpro_ids': matched,
                'additional_required_members': [token for token in members if token not in covered],
                'status': ('complete_group' if members and all(token in covered for token in members)
                           else 'partial_group' if matched else 'unmatched_group'),
                'record_identity_or_independence_established': False})
        matched = sorted({identifier for group in groups for identifier in group['matched_interpro_ids']})
        form = row.get('gene_product_form_id')
        chain = row.get('evidence_code') == 'IEA' and 'GO_REF:0000002' in row.get('reference_identifiers', [])
        records.append({'native_record': deepcopy(row), 'matched_interpro_ids': matched,
            'with_from_groups': groups, 'interpro2go_reference_chain': chain,
            'derivation_status': ('shared_interpro_identifier_in_IEA_chain' if chain and matched else
                                  'shared_interpro_identifier_only' if matched else 'no_shared_interpro_identifier'),
            'sequence_form_compatibility': ('coordinate_context_not_verified_for_product_form'
                if form not in (None, '', protein) else 'exact_subject_identifier_only_sequence_version_unverified'),
            'single_human_taxon': row.get('taxon_ids') == ['taxon:9606'],
            'positive_annotation_inferred': False, 'historical_record_identity_established': False})
    result.update(status='native_source_lineage_available', records=records,
                  context_report_content_sha256=native_go.get('context_report_content_sha256'))
    return result


def inspect_selection(runs_dir, graph, selection_id, protein, source_run, native_go=None):
    _need(_protein(protein) and isinstance(source_run, str)
          and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', source_run), 'exact protein and saved run required.')
    _need(protein in _endpoints(graph, selection_id), 'protein is not an exact selected evidence endpoint.')
    chosen = None
    for registration in registered_contexts(runs_dir):
        if protein in registration['publication']['proteins']:
            chosen = registration; break
    _need(chosen is not None, 'no explicitly registered context for this exact protein.')
    publication = chosen['publication']; item = publication['proteins'][protein]
    meta = item['manifest']; envelope = item['pharos']; target = envelope['response']['data']['target']
    native = item['result']; matches = []; grouped = defaultdict(list)
    for index, row in enumerate((native.get('matches') or []) if native is not None else []):
        signature = row['signature']; entry = signature.get('entry') or {}
        identifier = entry.get('accession') if isinstance(entry, dict) else None
        mid = 'protein-context-match:' + digest({'context': chosen['manifest_sha256'],
            'protein': protein, 'index': index, 'native': row})[:24]
        matches.append({'id': mid, 'source': row.get('source'), 'model_ac': row.get('model-ac'),
            'signature': deepcopy(signature), 'locations': deepcopy(row.get('locations')),
            'native_match': deepcopy(row), 'source_pointer': meta['matches_file'] + '#/result/content/0/text',
            'decoded_text_pointer': '/results/' + str(item['result_index']) + '/matches/' + str(index)})
        # This index groups presentation only. Every native method/version row remains.
        release = signature['signatureLibraryRelease']
        grouped[(row.get('source'), identifier, release['library'], release['version'])].append(mid)
    present = {row['signature']['entry']['accession'] for row in matches
        if isinstance(row['signature'].get('entry'), dict)
        and isinstance(row['signature']['entry'].get('accession'), str)
        and IPR.fullmatch(row['signature']['entry']['accession'])}
    old_ipr = {row.get('name') for row in (target.get('interpro') or []) if isinstance(row, dict)}
    aliases = {'Pfam': 'pfam', 'SMART': 'smart', 'PANTHER': 'panther',
               'PROSITE patterns': 'prosite', 'PROSITE profiles': 'prosite'}
    member_overlap = []
    for row in matches:
        signature = row['signature']; library = signature.get('signatureLibraryRelease') or {}
        family = aliases.get(library.get('library'))
        if family and any(x.get('name') == signature.get('accession') for x in (target.get(family) or [])):
            member_overlap.append({'match_id': row['id'], 'source': row['source'],
                'signature': signature.get('accession'), 'library': deepcopy(library),
                'pharos_family': family, 'record_version_equivalence_established': False})
    status = ('sequence_unavailable' if native is None else 'not_found' if native['found'] is False
              else 'found_with_matches' if matches else 'found_without_matches')
    result = {'format': 'biograph-steward.protein-context-selection.v1',
        'source_run': source_run, 'selection_id': selection_id, 'snapshot_sha256': graph['snapshot_sha256'],
        'graph_basis_sha256': graph_basis(graph), 'protein': protein, 'context_id': chosen['id'],
        'manifest_sha256': chosen['manifest_sha256'], 'context_manifest_sha256': chosen['manifest_sha256'],
        'read_only': True, 'source_fetches': 0, 'precomputed_found': native['found'] if native is not None else None,
        'model_calls': 0, 'source_graph_changed': False,
        'sequence': {'status': meta['status'], 'match_status': status, 'length': meta['sequence_length'], 'md5': meta['query_md5'],
            'sha256': meta['sequence_sha256'], 'source': 'Pharos API', 'retrieved_at': envelope.get('retrieved_at'),
            'normalization': 'Whitespace removed and uppercased only; no residue substitutions.',
            'isoform_scope': 'exact_requested_identifier', 'historical_identity_established': False,
            'historical_sequence_identity_established': False, 'taxon': None, 'taxon_status': 'not_supplied_by_this_payload'},
        'releases': {'pharos_database': envelope['response']['data'].get('dbVersion'),
            'interpro_before': deepcopy(publication['info_before']), 'interpro_after': deepcopy(publication['info_after']),
            'context_created_at': publication['manifest']['created_at'], 'scope': 'current_retrieved_sequence_context'},
        'matches': matches, 'groups': [{'source': source, 'interpro_accession': identifier,
            'library': library, 'library_version': version, 'match_ids': ids}
            for (source, identifier, library, version), ids in grouped.items()],
        'pharos_context': {'db_version': envelope['response']['data'].get('dbVersion'),
            'description': target.get('description'), 'family': target.get('fam'),
            'sequence_annotations': deepcopy(target.get('sequence_annotations')),
            **{name: deepcopy(target.get(name)) for name in FAMILIES}},
        'entry_metadata': [deepcopy(row) for identifier, row in publication['entry_metadata'].items()
                           if identifier in present or identifier in old_ipr],
        'identifier_overlap': {'shared_interpro_ids': sorted(present & old_ipr),
            'interpro_ids_not_in_captured_pharos_xrefs': sorted(present - old_ipr),
            'pharos_interpro_ids': sorted(x for x in old_ipr if isinstance(x, str)),
            'shared_member_ids': member_overlap, 'independent_evidence': False,
            'historical_record_identity_established': False},
        'goa_lineage': _lineage(native_go, graph, selection_id, protein, source_run, present),
        'attribution': deepcopy(publication['manifest'].get('attribution', {})), 'limitations': LIMITATIONS[:]}
    result['content_sha256'] = digest(result)
    return result
