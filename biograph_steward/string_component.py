"""Pure adapters for the fixed STRING 12.5 typed-network comparison.

This adapts official identifier and network responses; it does not retrieve
sources, infer sequence equivalence, fit scores or inspect assay outcomes.
Missing mappings and absent provider rows are operational coverage states.
"""
from __future__ import annotations

import csv
import io
import math
import re


MAPPING_COLUMNS = (
    'queryIndex', 'queryItem', 'stringId', 'ncbiTaxonId', 'taxonName',
    'preferredName', 'annotation',
)
NETWORK_COLUMNS = (
    'stringId_A', 'stringId_B', 'preferredName_A', 'preferredName_B',
    'ncbiTaxonId', 'functional_neighborhood_on_chromosome_score',
    'functional_gene_fusion_score', 'functional_phylogenetic_cooccurrence_score',
    'functional_homology_score', 'functional_coexpression_score',
    'functional_experimental_score', 'functional_database_score',
    'functional_textmining_score', 'functional_combined_score',
    'physical_homology_score', 'physical_experimental_score',
    'physical_database_score', 'physical_textmining_score',
    'physical_combined_score', 'regulatory_experimental_score',
    'regulatory_database_score', 'regulatory_textmining_score',
    'regulatory_combined_score', 'sign',
)
FUNCTIONAL_COLUMNS = tuple(key for key in NETWORK_COLUMNS if key.startswith('functional_'))
PHYSICAL_COLUMNS = tuple(key for key in NETWORK_COLUMNS if key.startswith('physical_'))
REGULATORY_COLUMNS = tuple(key for key in NETWORK_COLUMNS if key.startswith('regulatory_'))
MAPPING_STATES = {'resolved', 'unmapped', 'ambiguous', 'mapping_limit_reached'}
RANKING_FLOOR = -1.0


def _identifiers(values, label):
    if (not isinstance(values, list) or not values
            or any(not isinstance(value, str) or not value or re.search(r'\s', value)
                   for value in values)
            or len(set(values)) != len(values)):
        raise ValueError(f'{label} must contain unique exact nonempty identifiers.')
    return values


def _tsv(raw, expected, *, ordered):
    if not isinstance(raw, bytes):
        raise ValueError('Provider response must be preserved bytes.')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('Provider response is not UTF-8 TSV.') from exc
    if '\x00' in text:
        raise ValueError('Provider response contains NUL.')
    rows = list(csv.reader(io.StringIO(text, newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
    if not rows:
        raise ValueError('Provider TSV has no header; an empty/error body is not a valid missing row.')
    header = rows[0]
    if (len(header) != len(expected) or len(set(header)) != len(header)
            or (tuple(header) != expected if ordered else set(header) != set(expected))):
        raise ValueError('Provider TSV schema differs from the supported STRING response.')
    # The native provider emits a final blank line. Only this terminal framing
    # is ignored; an empty row within the data is a schema error.
    while len(rows) > 1 and rows[-1] == []:
        rows.pop()
    output = []
    for line, values in enumerate(rows[1:], 2):
        if len(values) != len(header):
            raise ValueError(f'Provider TSV row {line} has the wrong column count.')
        output.append((line, dict(zip(header, values))))
    return output


def _source_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'9606\.[^\s.]+', value):
        raise ValueError('Expected a human STRING identifier, not an added or foreign endpoint.')
    return value


def parse_mapping(raw: bytes, requested: list[str], limit: int | None = None) -> dict:
    """Validate echoed mappings, retaining exact input isoforms and all hits.

    The documented API returns its best match, not an exhaustive candidate
    search. A unique returned human representative is provider correspondence,
    not sequence identity or proof that alternative correspondences do not
    exist. ``limit`` is an optional local guard for separately documented
    captures; it is not sent as an undocumented provider parameter.
    """
    _identifiers(requested, 'Mapping query')
    if limit is not None and (type(limit) is not int or limit < 2):
        raise ValueError('Mapping hit limit must be an integer of at least two.')
    groups = {value: [] for value in requested}
    lines = {value: [] for value in requested}
    for line, row in _tsv(raw, MAPPING_COLUMNS, ordered=False):
        if not re.fullmatch(r'0|[1-9][0-9]*', row['queryIndex']):
            raise ValueError('Mapping queryIndex is not a zero-based integer.')
        index = int(row['queryIndex'])
        if index >= len(requested) or row['queryItem'] != requested[index]:
            raise ValueError('Mapping query index/echo differs from the exact request.')
        if row['ncbiTaxonId'] != '9606':
            raise ValueError('Mapping response contains an unexpected species.')
        _source_id(row['stringId'])
        groups[requested[index]].append(row)
        lines[requested[index]].append(line)
    result = {}
    for index, accession in enumerate(requested):
        hits = groups[accession]
        identities = {hit['stringId'] for hit in hits}
        if limit is not None and len(hits) > limit:
            raise ValueError('Mapping response exceeds the declared per-query hit limit.')
        if limit is not None and len(hits) == limit:
            status = 'mapping_limit_reached'
        elif not hits:
            status = 'unmapped'
        elif len(identities) > 1:
            status = 'ambiguous'
        else:
            status = 'resolved'
        result[accession] = {
            'status': status,
            'string_id': next(iter(identities)) if status == 'resolved' else None,
            'query_index': index,
            'query_item': accession,
            'hits': hits,
            'source_row_numbers': lines[accession],
            'correspondence': 'STRING_locus_representative_not_sequence_identity',
            'resolution_basis': 'provider_best_match',
            'candidate_search_exhaustive': False,
        }
    return result


def _score(value, *, missing_allowed):
    if value == '-' and missing_allowed:
        return None
    if isinstance(value, bool):
        raise ValueError('A boolean is not a native STRING score.')
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError('STRING score is not an explicit supported numeric value.') from exc
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError('STRING score must be finite and within [0, 1].')
    return result


def parse_network(raw: bytes, requested_string_ids: list[str]) -> dict:
    """Parse the observed 24-column typed functional response without expansion.

    Reciprocal rows are one prediction. Every functional and physical channel
    must agree; directed regulatory channels are excluded by this profile.
    Header-only responses are legitimate, while technical/error bodies fail.
    """
    _identifiers(requested_string_ids, 'Network query')
    if len(requested_string_ids) < 2:
        raise ValueError('The fixed network query needs at least two distinct representatives.')
    requested = set(map(_source_id, requested_string_ids))
    output = {}
    orientations = {}
    for line, row in _tsv(raw, NETWORK_COLUMNS, ordered=True):
        a, b = _source_id(row['stringId_A']), _source_id(row['stringId_B'])
        if row['ncbiTaxonId'] != '9606' or a not in requested or b not in requested or a == b:
            raise ValueError('Network response has a foreign, added or self endpoint.')
        normalized = dict(row)
        normalized['ncbiTaxonId'] = 9606
        for field in FUNCTIONAL_COLUMNS:
            normalized[field] = _score(row[field], missing_allowed=False)
        for field in PHYSICAL_COLUMNS + REGULATORY_COLUMNS:
            normalized[field] = _score(row[field], missing_allowed=True)
        if any(normalized[field] is not None for field in REGULATORY_COLUMNS) or row['sign'] != 'n/a':
            raise ValueError('The fixed typed profile disables regulatory overlays.')
        key = tuple(sorted((a, b)))
        direction = (a, b)
        if direction in orientations.setdefault(key, set()):
            raise ValueError('Typed network duplicates the same row orientation.')
        orientations[key].add(direction)
        if a > b:
            normalized['stringId_A'], normalized['stringId_B'] = b, a
            normalized['preferredName_A'], normalized['preferredName_B'] = row['preferredName_B'], row['preferredName_A']
        normalized['source_row_numbers'] = [line]
        if key in output:
            previous = output[key]
            if any(previous[field] != normalized[field]
                   for field in NETWORK_COLUMNS):
                raise ValueError('Duplicate/reciprocal network predictions disagree.')
            previous['source_row_numbers'].append(line)
        else:
            output[key] = normalized
    if any(directions != {pair, (pair[1], pair[0])}
           for pair, directions in orientations.items()):
        raise ValueError('Typed network is missing a documented reciprocal row.')
    return output


def _view(state, score=None):
    if state == 'numeric':
        score = _score(score, missing_allowed=False)
        return {'state': state, 'native_score': score, 'ranking_score': score}
    return {'state': state, 'native_score': None, 'ranking_score': RANKING_FLOOR}


def _mapping_for(accession, mappings):
    if accession not in mappings:
        raise ValueError('Candidate mapping is missing; retrieval failure is not an unmapped state.')
    value = mappings[accession]
    if (not isinstance(value, dict) or value.get('query_item') != accession
            or value.get('status') not in MAPPING_STATES):
        raise ValueError('Candidate mapping schema/echo differs.')
    if value['status'] == 'resolved':
        _source_id(value.get('string_id'))
    elif value.get('string_id') is not None:
        raise ValueError('An unresolved mapping cannot select a representative.')
    return value


def project_predictions(candidates: list[dict], mappings: dict,
                        network_by_batch: dict, batchplan: list[dict]) -> list[dict]:
    """Project every original nomination using validated complete query batches.

    ``batchplan`` rows contain ``batch_id``, ``string_ids`` and
    ``candidate_indices``. Every resolved noncollapsed candidate must have one
    assigned query containing its two representatives. Other source rows may
    be returned in the induced subgraph; they do not create new candidates.
    """
    if not isinstance(candidates, list) or not isinstance(mappings, dict):
        raise ValueError('Candidate/mapping collection schema differs.')
    if not isinstance(batchplan, list) or not isinstance(network_by_batch, dict):
        raise ValueError('Network batch collection schema differs.')
    assignments = {}
    batch_ids = set()
    queried_ids = set()
    for batch in batchplan:
        if not isinstance(batch, dict) or not isinstance(batch.get('batch_id'), str) or not batch['batch_id']:
            raise ValueError('Network batch identifier schema differs.')
        batch_id = batch['batch_id']
        if batch_id in batch_ids:
            raise ValueError('Duplicate network batch identifier.')
        batch_ids.add(batch_id)
        string_ids = batch.get('string_ids')
        if not isinstance(string_ids, list):
            raise ValueError('Batch representative schema differs.')
        if string_ids:
            _identifiers(string_ids, 'Batch representatives')
        if len(string_ids) == 1:
            raise ValueError('A query batch must have at least two representatives.')
        endpoints = set(map(_source_id, string_ids))
        indices = batch.get('candidate_indices')
        if not isinstance(indices, list) or not indices or any(type(index) is not int for index in indices):
            raise ValueError('Batch candidate indices differ.')
        if string_ids and batch_id not in network_by_batch:
            raise ValueError('A planned network response is missing.')
        if not string_ids and batch_id in network_by_batch:
            raise ValueError('An unqueryable batch cannot supply a network response.')
        if string_ids:
            queried_ids.add(batch_id)
        network = network_by_batch[batch_id] if string_ids else {}
        if not isinstance(network, dict):
            raise ValueError('Network batch must be a parsed network mapping.')
        for pair, row in network.items():
            if (not isinstance(pair, tuple) or len(pair) != 2 or tuple(sorted(pair)) != pair
                    or not set(pair) <= endpoints or not isinstance(row, dict)
                    or (row.get('stringId_A'), row.get('stringId_B')) != pair):
                raise ValueError('Parsed network row does not belong to the declared query.')
        for index in indices:
            if not 0 <= index < len(candidates) or index in assignments:
                raise ValueError('Candidate has a duplicate/out-of-range query assignment.')
            assignments[index] = (batch_id, endpoints)
    if set(network_by_batch) != queried_ids:
        raise ValueError('Unplanned network batch response is not allowed.')
    if set(assignments) != set(range(len(candidates))):
        raise ValueError('Every original candidate must have exactly one deterministic batch assignment.')
    # The provider promises the induced functional network for each query.
    # Whenever two queries contain a pair, its returned/absent state and all
    # symmetric native scores must agree. Alias collapse may repeat pairs.
    all_returned = set().union(*(set(rows) for rows in network_by_batch.values())) if network_by_batch else set()
    for pair in all_returned:
        relevant = [network_by_batch[batch['batch_id']].get(pair)
                    for batch in batchplan if set(pair) <= set(batch['string_ids'])]
        expected = next(row for row in relevant if row is not None)
        if any(row is None or any(row[field] != expected[field]
                                 for field in FUNCTIONAL_COLUMNS + PHYSICAL_COLUMNS)
               for row in relevant):
            raise ValueError('Repeated cross-batch pair predictions or return states disagree.')
    for batch in batchplan:
        expected = set()
        for index in batch['candidate_indices']:
            candidate = candidates[index]
            if (not isinstance(candidate, dict) or not isinstance(candidate.get('products'), list)
                    or len(candidate['products']) != 2):
                raise ValueError('Candidate exact products schema differs.')
            endpoints = [_mapping_for(accession, mappings) for accession in candidate['products']]
            if all(item['status'] == 'resolved' for item in endpoints):
                values = {item['string_id'] for item in endpoints}
                if len(values) == 2:
                    expected.update(values)
        if expected != set(batch['string_ids']):
            raise ValueError('Batch query endpoints differ from its mapped candidate union.')
    result = []
    for index, candidate in enumerate(candidates):
        if (not isinstance(candidate, dict) or not isinstance(candidate.get('products'), list)
                or len(candidate['products']) != 2
                or any(not isinstance(item, str) or not item for item in candidate['products'])
                or type(candidate.get('source_row')) is not int):
            raise ValueError('Candidate exact products/source-row schema differs.')
        mapping = [_mapping_for(accession, mappings) for accession in candidate['products']]
        row = {'products': list(candidate['products']), 'source_row': candidate['source_row']}
        row['mapping_states'] = [item['status'] for item in mapping]
        row['mapping_proof'] = [
            {'accession': item['query_item'], 'query_index': item.get('query_index'),
             'source_row_numbers': list(item.get('source_row_numbers', [])),
             'string_id': item['string_id'], 'status': item['status'],
             'hits': item.get('hits', []),
             'correspondence': 'STRING_locus_representative_not_sequence_identity',
             'resolution_basis': 'provider_best_match',
             'candidate_search_exhaustive': False}
            for item in mapping]
        row['query_batch'] = None
        views = {}
        if any(item['status'] != 'resolved' for item in mapping):
            # Preserve both per-endpoint states. A hit-limit result is unresolved
            # ambiguity at the ranking level, never a convenient selected hit.
            state = 'unmapped' if any(item['status'] == 'unmapped' for item in mapping) else 'ambiguous'
            views = {'functional': _view(state), 'physical': _view(state)}
        elif mapping[0]['string_id'] == mapping[1]['string_id']:
            views = {'functional': _view('collapsed_representative'), 'physical': _view('collapsed_representative')}
        else:
            batch_id, endpoints = assignments[index]
            pair = tuple(sorted(item['string_id'] for item in mapping))
            if not set(pair) <= endpoints:
                raise ValueError('Candidate representatives are not both in the assigned query.')
            source_row = network_by_batch[batch_id].get(pair)
            row['query_batch'] = batch_id
            if source_row is None:
                views = {'functional': _view('no_returned_functional_row'),
                         'physical': _view('no_returned_functional_row')}
            else:
                views['functional'] = _view('numeric', source_row['functional_combined_score'])
                score = source_row['physical_combined_score']
                views['physical'] = (_view('physical_not_returned_under_profile') if score is None
                                     else _view('numeric', score))
        row['views'] = views
        result.append(row)
    return result
