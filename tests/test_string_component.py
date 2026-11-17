"""Invented identifiers/scores only; no assay outcomes or new source calls."""
from copy import deepcopy
import unittest

from biograph_steward import string_component as component


def tsv(columns, rows, *, final_blank=False):
    text = '\t'.join(columns) + '\n'
    text += ''.join('\t'.join(str(row[key]) for key in columns) + '\n' for row in rows)
    return (text + ('\n' if final_blank else '')).encode()


def mapping_row(query, index, string_id):
    return dict(zip(component.MAPPING_COLUMNS,
        (str(index), query, string_id, '9606', 'Homo sapiens', 'invented', 'invented annotation')))


def network_rows(a='9606.A', b='9606.B', functional='0.8', physical='0.2'):
    values = {key: '0' for key in component.FUNCTIONAL_COLUMNS}
    values.update({key: '-' for key in component.PHYSICAL_COLUMNS + component.REGULATORY_COLUMNS})
    values.update(stringId_A=a, stringId_B=b, preferredName_A=a[5:], preferredName_B=b[5:],
        ncbiTaxonId='9606', sign='n/a', functional_combined_score=functional,
        physical_combined_score=physical)
    reciprocal = {**values, 'stringId_A': b, 'stringId_B': a,
                  'preferredName_A': b[5:], 'preferredName_B': a[5:]}
    return [values, reciprocal]


def parsed_network(rows=None, ids=None):
    return component.parse_network(tsv(component.NETWORK_COLUMNS, rows or []),
                                   ids or ['9606.A', '9606.B'])


def parsed_mappings(requested=None, ids=None):
    requested = requested or ['P00001', 'P00002']
    ids = ids or ['9606.A', '9606.B']
    rows = [mapping_row(query, index, value) for index, (query, value)
            in enumerate(zip(requested, ids)) if value is not None]
    return component.parse_mapping(tsv(component.MAPPING_COLUMNS, rows), requested)


class MappingTests(unittest.TestCase):
    def test_exact_input_isoform_and_provider_bestmatch_qualification_preserved(self):
        queries = ['P00001', 'P00001-2', 'P00002']
        columns = ('queryItem', 'queryIndex', *component.MAPPING_COLUMNS[2:])
        rows = [mapping_row(query, index, value) for index, (query, value)
                in enumerate(zip(queries, ['9606.A', '9606.A', '9606.B']))]
        result = component.parse_mapping(tsv(columns, rows, final_blank=True), queries)
        self.assertEqual(list(result), queries)
        self.assertEqual(result[queries[1]]['query_item'], 'P00001-2')
        self.assertEqual(result[queries[1]]['status'], 'resolved')
        self.assertEqual(result[queries[1]]['source_row_numbers'], [3])
        self.assertEqual(result[queries[1]]['resolution_basis'], 'provider_best_match')
        self.assertIs(result[queries[1]]['candidate_search_exhaustive'], False)
        self.assertEqual(result[queries[1]]['hits'], [rows[1]])

    def test_header_only_maps_all_queries_to_unmapped(self):
        result = component.parse_mapping(tsv(component.MAPPING_COLUMNS, []), ['P00001'])
        self.assertEqual(result['P00001']['status'], 'unmapped')
        self.assertIsNone(result['P00001']['string_id'])
        self.assertEqual(result['P00001']['hits'], [])

    def test_multiple_reported_ids_are_ambiguous_without_besthit_selection(self):
        rows = [mapping_row('P00001', 0, value) for value in ['9606.A', '9606.B']]
        result = component.parse_mapping(tsv(component.MAPPING_COLUMNS, rows), ['P00001'])
        self.assertEqual(result['P00001']['status'], 'ambiguous')
        self.assertIsNone(result['P00001']['string_id'])
        self.assertEqual(len(result['P00001']['hits']), 2)

    def test_optional_local_hitguard_does_not_silently_resolve_atlimit(self):
        rows = [mapping_row('P00001', 0, value) for value in ['9606.A', '9606.B']]
        result = component.parse_mapping(tsv(component.MAPPING_COLUMNS, rows), ['P00001'], limit=2)
        self.assertEqual(result['P00001']['status'], 'mapping_limit_reached')
        with self.assertRaises(ValueError):
            component.parse_mapping(tsv(component.MAPPING_COLUMNS, rows * 2), ['P00001'], limit=2)

    def test_wrong_echo_index_species_or_source_namespace_rejected(self):
        for key, value in [('queryItem', 'P00001-2'), ('queryIndex', '1'),
                           ('queryIndex', '-1'), ('queryIndex', '0.0'),
                           ('ncbiTaxonId', '10090'), ('stringId', '10090.A'),
                           ('stringId', 'UniProtKB:P00001')]:
            row = mapping_row('P00001', 0, '9606.A'); row[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                component.parse_mapping(tsv(component.MAPPING_COLUMNS, [row]), ['P00001'])

    def test_invalid_request_or_schema_is_not_missing_evidence(self):
        for raw in [b'', b'ERROR\nnot found', b'\xff', b'\x00',
                    tsv(component.MAPPING_COLUMNS[:-1], []),
                    tsv(component.MAPPING_COLUMNS, [mapping_row('P00001', 0, '9606.A')]) + b'\n' +
                    '\t'.join(component.MAPPING_COLUMNS).encode()]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                component.parse_mapping(raw, ['P00001'])
        for queries in [[], ['P00001', 'P00001'], ['P00001\nP00002'], ['']]:
            with self.assertRaises(ValueError):
                component.parse_mapping(tsv(component.MAPPING_COLUMNS, []), queries)


class NetworkTests(unittest.TestCase):
    def test_native_zero_missing_overlay_and_reciprocal_rows_distinct(self):
        result = parsed_network(network_rows(functional='0', physical='-'))
        row = result[('9606.A', '9606.B')]
        self.assertEqual(row['functional_combined_score'], 0.0)
        self.assertIsNone(row['physical_combined_score'])
        self.assertEqual(row['source_row_numbers'], [2, 3])
        self.assertEqual(row['preferredName_A'], 'A')

    def test_header_only_is_valid_but_empty_error_or_wrong_schema_fails(self):
        self.assertEqual(parsed_network(), {})
        for raw in [b'', b'<html>gateway error</html>', tsv(component.NETWORK_COLUMNS[:-1], []),
                    tsv(tuple(reversed(component.NETWORK_COLUMNS)), [])]:
            with self.assertRaises(ValueError):
                component.parse_network(raw, ['9606.A', '9606.B'])

    def test_numeric_range_finiteness_and_functional_missing_are_checked(self):
        for key, value in [('functional_combined_score', '-'),
                           ('functional_database_score', 'nan'),
                           ('physical_combined_score', 'inf'),
                           ('physical_experimental_score', '-0.1'),
                           ('physical_combined_score', '1.1')]:
            rows = network_rows()
            for row in rows:
                row[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                parsed_network(rows)

    def test_no_added_foreign_self_or_wrong_taxon_endpoints(self):
        for a, b in [('9606.A', '9606.C'), ('10090.A', '9606.B'), ('9606.A', '9606.A')]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                parsed_network(network_rows(a, b))
        rows = network_rows()
        rows[0]['ncbiTaxonId'] = '10090'
        with self.assertRaises(ValueError):
            parsed_network(rows)

    def test_reciprocal_all_channels_must_agree_and_both_orientations_required(self):
        for key in component.FUNCTIONAL_COLUMNS + component.PHYSICAL_COLUMNS:
            rows = network_rows()
            rows[1][key] = '0.4'
            with self.subTest(key=key), self.assertRaises(ValueError):
                parsed_network(rows)
        rows = network_rows()
        for invalid in [rows[:1], [rows[0], rows[0]], rows + [rows[1]]]:
            with self.assertRaises(ValueError):
                parsed_network(invalid)

    def test_regulatory_overlay_profile_mismatch_rejected(self):
        for key, value in [('regulatory_combined_score', '0'), ('sign', 'pos')]:
            rows = network_rows()
            for row in rows:
                row[key] = value
            with self.assertRaises(ValueError):
                parsed_network(rows)


class ProjectionTests(unittest.TestCase):
    def test_preserves_original_nomination_and_outputs_only_declared_predictor_fields(self):
        candidates = [{'products': ['P00001', 'P00002'], 'source_row': 77,
                       'assay_eligible': True, 'detected': 'must not propagate'}]
        original = deepcopy(candidates)
        plan = [{'batch_id': 'batch_0001', 'candidate_indices': [0],
                 'string_ids': ['9606.A', '9606.B']}]
        result = component.project_predictions(candidates, parsed_mappings(),
            {'batch_0001': parsed_network(network_rows(functional='0', physical='0'))}, plan)
        self.assertEqual(candidates, original)
        self.assertEqual(set(result[0]), {'products', 'source_row', 'mapping_states',
            'mapping_proof', 'query_batch', 'views'})
        self.assertEqual(result[0]['source_row'], 77)
        self.assertEqual(result[0]['views']['functional'],
            {'state': 'numeric', 'native_score': 0.0, 'ranking_score': 0.0})
        self.assertEqual(result[0]['views']['physical']['state'], 'numeric')
        self.assertEqual(result[0]['mapping_proof'][0]['accession'], 'P00001')

    def test_full_population_mapping_collapsed_absent_and_overlay_states_kept(self):
        queries = ['P00001', 'P00002', 'P00003', 'P00004', 'P00005', 'P00006-2']
        mappings = parsed_mappings(queries, ['9606.A', '9606.B', None, '9606.C', '9606.A', '9606.B'])
        ambiguous = mapping_row('P00004', 3, '9606.D')
        mappings = component.parse_mapping(tsv(component.MAPPING_COLUMNS,
            [row for item in mappings.values() for row in item['hits']] + [ambiguous]), queries)
        products = [['P00001', 'P00002'], ['P00001', 'P00003'],
                    ['P00001', 'P00004'], ['P00001', 'P00005'],
                    ['P00002', 'P00006-2']]
        candidates = [{'products': pair, 'source_row': index} for index, pair in enumerate(products)]
        plan = [{'batch_id': 'one', 'candidate_indices': list(range(5)),
                 'string_ids': ['9606.A', '9606.B']}]
        result = component.project_predictions(candidates, mappings,
            {'one': parsed_network(network_rows(physical='-'))}, plan)
        self.assertEqual(len(result), len(candidates))
        self.assertEqual([row['views']['functional']['state'] for row in result],
                         ['numeric', 'unmapped', 'ambiguous', 'collapsed_representative', 'collapsed_representative'])
        self.assertEqual(result[0]['views']['physical']['state'], 'physical_not_returned_under_profile')
        self.assertEqual(result[0]['views']['physical']['ranking_score'], -1)
        self.assertEqual(result[1]['query_batch'], None)
        absent = component.project_predictions(candidates[:1], mappings, {'one': {}},
            [{'batch_id': 'one', 'candidate_indices': [0], 'string_ids': ['9606.A', '9606.B']}])
        self.assertEqual(absent[0]['views']['functional']['state'], 'no_returned_functional_row')
        self.assertEqual(absent[0]['views']['physical']['state'], 'no_returned_functional_row')

    def test_all_unqueryable_batch_is_explicit_skipped_response(self):
        candidates = [{'products': ['P00001', 'P00002'], 'source_row': 1}]
        mappings = parsed_mappings(ids=[None, '9606.B'])
        plan = [{'batch_id': 'skip', 'candidate_indices': [0], 'string_ids': []}]
        result = component.project_predictions(candidates, mappings, {}, plan)
        self.assertEqual(result[0]['views']['functional']['state'], 'unmapped')
        with self.assertRaises(ValueError):
            component.project_predictions(candidates, mappings, {'skip': {}}, plan)

    def test_missing_or_added_batch_endpoints_or_candidates_fail_instead_of_floor(self):
        candidates = [{'products': ['P00001', 'P00002'], 'source_row': 1}]
        mappings = parsed_mappings()
        plan = [{'batch_id': 'one', 'candidate_indices': [0], 'string_ids': ['9606.A', '9606.B']}]
        for network, altered in [({}, plan), ({'other': {}}, plan), ({'one': {}}, []),
                                  ({'one': {}}, [{**plan[0], 'candidate_indices': [0, 0]}]),
                                  ({'one': {}}, [{**plan[0], 'string_ids': ['9606.A', '9606.B', '9606.C']}])]:
            with self.subTest(network=network, plan=altered), self.assertRaises(ValueError):
                component.project_predictions(candidates, mappings, network, altered)
        with self.assertRaises(ValueError):
            component.project_predictions(candidates, {}, {'one': {}}, plan)

    def test_crossbatch_returned_and_absent_or_score_conflicts_fail(self):
        candidates = [{'products': ['P00001', 'P00002'], 'source_row': index} for index in range(2)]
        mappings = parsed_mappings()
        plan = [{'batch_id': 'one', 'candidate_indices': [0], 'string_ids': ['9606.A', '9606.B']},
                {'batch_id': 'two', 'candidate_indices': [1], 'string_ids': ['9606.A', '9606.B']}]
        known = parsed_network(network_rows())
        for second in [{}, parsed_network(network_rows(physical='0.9')),
                       parsed_network(network_rows(functional='0.9'))]:
            with self.assertRaises(ValueError):
                component.project_predictions(candidates, mappings, {'one': known, 'two': second}, plan)
        result = component.project_predictions(candidates, mappings, {'one': known, 'two': known}, plan)
        self.assertEqual(len(result), 2)


if __name__ == '__main__':
    unittest.main()
