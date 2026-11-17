"""Pure adapters for the archived STRING 12.0 native network interface.

The archive exposes separate functional and physical networks, each with the
same 13-column schema. Their returned pair sets are independent. Identifier
correspondence and strict TSV/numeric handling reuse the established adapter;
no outcomes, retrieval, sequence-equivalence inference or score fitting occurs.
"""
from __future__ import annotations

from copy import deepcopy

from .string_component import (
    MAPPING_COLUMNS, MAPPING_STATES, RANKING_FLOOR, _identifiers, _mapping_for,
    _score, _source_id, _tsv, _view, parse_mapping,
)


ARMS = ('functional', 'physical')
NETWORK_COLUMNS = (
    'stringId_A', 'stringId_B', 'preferredName_A', 'preferredName_B',
    'ncbiTaxonId', 'score', 'nscore', 'fscore', 'pscore', 'ascore',
    'escore', 'dscore', 'tscore',
)
SCORE_COLUMNS = NETWORK_COLUMNS[5:]
CANDIDATE_BATCH_SIZE = 25


def parse_network(raw: bytes, requested_string_ids: list[str]) -> dict:
    """Validate native rows, accepting one row or identical reciprocal rows.

    Native absence requires a valid header-only or other complete response; an
    error, truncated schema, missing score or added endpoint is a hard failure.
    All score channels and endpoint labels must agree for reciprocal rows.
    """
    _identifiers(requested_string_ids, 'Network query')
    if len(requested_string_ids) < 2:
        raise ValueError('The native network query needs at least two distinct representatives.')
    requested = set(map(_source_id, requested_string_ids))
    result, orientations = {}, {}
    for line, row in _tsv(raw, NETWORK_COLUMNS, ordered=True):
        a, b = _source_id(row['stringId_A']), _source_id(row['stringId_B'])
        if row['ncbiTaxonId'] != '9606' or a not in requested or b not in requested or a == b:
            raise ValueError('Native network has a foreign, added or self endpoint.')
        pair = tuple(sorted((a, b)))
        direction = (a, b)
        if direction in orientations.setdefault(pair, set()):
            raise ValueError('Native network duplicates the same row orientation.')
        orientations[pair].add(direction)
        normalized = dict(row)
        normalized['ncbiTaxonId'] = 9606
        for field in SCORE_COLUMNS:
            normalized[field] = _score(row[field], missing_allowed=False)
        if a > b:
            normalized['stringId_A'], normalized['stringId_B'] = b, a
            normalized['preferredName_A'], normalized['preferredName_B'] = (
                row['preferredName_B'], row['preferredName_A'])
        normalized['source_row_numbers'] = [line]
        if pair in result:
            if any(result[pair][field] != normalized[field] for field in NETWORK_COLUMNS):
                raise ValueError('Native reciprocal network labels or scores disagree.')
            result[pair]['source_row_numbers'].append(line)
        else:
            result[pair] = normalized
    return result


def _validate_candidates(candidates, mappings):
    if not isinstance(candidates, list) or not candidates or not isinstance(mappings, dict):
        raise ValueError('A nonempty fixed candidate list and complete mapping dictionary are required.')
    pairs, source_rows = set(), set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError('Candidate must be an object.')
        products, source_row = candidate.get('products'), candidate.get('source_row')
        if (not isinstance(products, list) or len(products) != 2
                or any(not isinstance(item, str) or not item or any(c.isspace() for c in item)
                       for item in products)
                or products != sorted(set(products))
                or type(source_row) is not int or source_row < 1):
            raise ValueError('Exact sorted accession pair and positive source-row identity are required.')
        if tuple(products) in pairs or source_row in source_rows:
            raise ValueError('Duplicate candidate pair or source-row identity.')
        pairs.add(tuple(products)); source_rows.add(source_row)
        for accession in products:
            _mapping_for(accession, mappings)


def _validate_parsed_network(network, endpoints):
    if not isinstance(network, dict):
        raise ValueError('A complete parsed native network dictionary is required.')
    for pair, row in network.items():
        if (not isinstance(pair, tuple) or len(pair) != 2 or tuple(sorted(set(pair))) != pair
                or not set(pair) <= endpoints or not isinstance(row, dict)
                or set(row) != {*NETWORK_COLUMNS, 'source_row_numbers'}
                or (row['stringId_A'], row['stringId_B']) != pair
                or type(row['ncbiTaxonId']) is not int or row['ncbiTaxonId'] != 9606
                or any(not isinstance(row[field], str) for field in ('preferredName_A', 'preferredName_B'))):
            raise ValueError('Parsed native row does not belong to the declared human query.')
        for value in pair:
            _source_id(value)
        for field in SCORE_COLUMNS:
            if type(row[field]) not in (int, float) or _score(row[field], missing_allowed=False) != row[field]:
                raise ValueError('Parsed native channel must retain a numeric score.')
        lines = row['source_row_numbers']
        if (not isinstance(lines, list) or not 1 <= len(lines) <= 2
                or any(type(line) is not int or line < 2 for line in lines)
                or lines != sorted(set(lines))):
            raise ValueError('Parsed native source-row proof differs.')


def project_predictions(candidates: list[dict], mappings: dict,
                        networks_by_view: dict, batchplan: list[dict]) -> list[dict]:
    """Project both separately queried native networks onto every nomination.

    ``networks_by_view`` contains ``functional`` and ``physical`` dictionaries,
    each keyed by the shared base batch identifier. Query receipt identities in
    the output prepend the view, e.g. ``physical_network_0001``. The plan must
    retain contiguous groups of 25 original candidates and their exact sorted
    representative union; an unqueryable group has no response in either view.
    """
    _validate_candidates(candidates, mappings)
    if (not isinstance(batchplan, list) or not isinstance(networks_by_view, dict)
            or set(networks_by_view) != set(ARMS)
            or any(not isinstance(networks_by_view[arm], dict) for arm in ARMS)):
        raise ValueError('Both separate native network views and the fixed plan are required.')
    expected_plan = []
    assignments = {}
    for offset in range(0, len(candidates), CANDIDATE_BATCH_SIZE):
        indices = list(range(offset, min(offset + CANDIDATE_BATCH_SIZE, len(candidates))))
        ids = set()
        for index in indices:
            pair = [_mapping_for(accession, mappings) for accession in candidates[index]['products']]
            if all(item['status'] == 'resolved' for item in pair) and pair[0]['string_id'] != pair[1]['string_id']:
                ids.update(item['string_id'] for item in pair)
        batch_id = 'network_%04d' % (len(expected_plan) + 1)
        expected_plan.append({'batch_id': batch_id, 'candidate_indices': indices, 'string_ids': sorted(ids)})
        for index in indices:
            assignments[index] = batch_id
    if batchplan != expected_plan:
        raise ValueError('Network plan differs from the fixed 25-candidate representative union.')
    queryable = {batch['batch_id'] for batch in batchplan if batch['string_ids']}
    for arm in ARMS:
        networks = networks_by_view[arm]
        if set(networks) != queryable:
            raise ValueError('Every queryable batch requires its separate native response, with no extras.')
        for batch in batchplan:
            if batch['string_ids']:
                _validate_parsed_network(networks[batch['batch_id']], set(batch['string_ids']))
        # A pair in an induced query must have the same presence, labels and
        # native channels in every overlapping query of this same view. There
        # is intentionally no equality or subset constraint across views.
        returned = set().union(*(set(network) for network in networks.values())) if networks else set()
        for pair in returned:
            relevant = [networks[batch['batch_id']].get(pair)
                        for batch in batchplan if set(pair) <= set(batch['string_ids'])]
            expected = next(row for row in relevant if row is not None)
            if any(row is None or any(row[field] != expected[field] for field in NETWORK_COLUMNS)
                   for row in relevant):
                raise ValueError('Cross-batch native pair presence, labels or scores disagree within a view.')
    result = []
    for index, candidate in enumerate(candidates):
        mapping = [_mapping_for(accession, mappings) for accession in candidate['products']]
        output = {'products': list(candidate['products']), 'source_row': candidate['source_row'],
                  'mapping_states': [item['status'] for item in mapping],
                  'mapping_proof': [
                      {'accession': item['query_item'], 'query_index': item.get('query_index'),
                       'source_row_numbers': list(item.get('source_row_numbers', [])),
                       'string_id': item['string_id'], 'status': item['status'],
                       'hits': deepcopy(item.get('hits', [])),
                       'correspondence': 'STRING_locus_representative_not_sequence_identity',
                       'resolution_basis': 'provider_best_match', 'candidate_search_exhaustive': False}
                      for item in mapping],
                  'query_batch': {arm: None for arm in ARMS}, 'views': {}}
        if any(item['status'] != 'resolved' for item in mapping):
            state = 'unmapped' if any(item['status'] == 'unmapped' for item in mapping) else 'ambiguous'
            output['views'] = {arm: _view(state) for arm in ARMS}
        elif mapping[0]['string_id'] == mapping[1]['string_id']:
            output['views'] = {arm: _view('collapsed_representative') for arm in ARMS}
        else:
            batch_id = assignments[index]
            pair = tuple(sorted(item['string_id'] for item in mapping))
            for arm in ARMS:
                output['query_batch'][arm] = arm + '_' + batch_id
                row = networks_by_view[arm][batch_id].get(pair)
                output['views'][arm] = (_view('no_returned_native_row') if row is None
                                        else _view('numeric', row['score']))
        result.append(output)
    return result
