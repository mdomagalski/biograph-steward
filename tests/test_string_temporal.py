"""Synthetic archive-contract tests: no assay outcomes or provider access."""
from copy import deepcopy
import unittest

from biograph_steward import string_temporal as temporal


def tsv(columns, rows, final_blank=False):
    text = '\t'.join(columns) + '\n'
    text += ''.join('\t'.join(str(row[column]) for column in columns) + '\n' for row in rows)
    return (text + ('\n' if final_blank else '')).encode()


def network_row(a='9606.A', b='9606.B', score='0.8'):
    return dict(zip(temporal.NETWORK_COLUMNS,
                    (a, b, a[5:], b[5:], '9606', score, '0', '0.1', '0.2', '0.3', '0.4', '0.5', '0.6')))


def reciprocal(row):
    return {**row, 'stringId_A': row['stringId_B'], 'stringId_B': row['stringId_A'],
            'preferredName_A': row['preferredName_B'], 'preferredName_B': row['preferredName_A']}


def parsed(rows=(), ids=('9606.A', '9606.B')):
    return temporal.parse_network(tsv(temporal.NETWORK_COLUMNS, rows), list(ids))


def mappings(queries=('P00001', 'P00002'), ids=('9606.A', '9606.B')):
    rows = [dict(zip(temporal.MAPPING_COLUMNS,
                     (str(index), query, value, '9606', 'Homo sapiens', value[5:], 'invented')))
            for index, (query, value) in enumerate(zip(queries, ids)) if value is not None]
    return temporal.parse_mapping(tsv(temporal.MAPPING_COLUMNS, rows), list(queries))


def plan(candidates, mapping):
    result = []
    for offset in range(0, len(candidates), 25):
        indices = list(range(offset, min(offset + 25, len(candidates))))
        ids = set()
        for index in indices:
            values = [mapping[accession] for accession in candidates[index]['products']]
            if all(value['status'] == 'resolved' for value in values) and values[0]['string_id'] != values[1]['string_id']:
                ids.update(value['string_id'] for value in values)
        result.append({'batch_id': 'network_%04d' % (len(result) + 1),
                       'candidate_indices': indices, 'string_ids': sorted(ids)})
    return result


def candidates(count=1):
    return [{'products': ['P%05dA' % index, 'P%05dB' % index], 'source_row': index + 1,
             'detected': 'must not propagate'} for index in range(count)]


def projected_setup(count=1):
    nominated = candidates(count)
    queries = [accession for candidate in nominated for accession in candidate['products']]
    mapping = mappings(queries, ['9606.A', '9606.B'] * count)
    batchplan = plan(nominated, mapping)
    networks = {arm: {batch['batch_id']: parsed([network_row()]) for batch in batchplan}
                for arm in temporal.ARMS}
    return nominated, mapping, networks, batchplan


class NativeParserTests(unittest.TestCase):
    def test_single_and_identical_reciprocal_rows_are_same_prediction(self):
        row = network_row()
        single = parsed([row])[('9606.A', '9606.B')]
        dual = parsed([row, reciprocal(row)])[('9606.A', '9606.B')]
        self.assertEqual(single['source_row_numbers'], [2])
        self.assertEqual(dual['source_row_numbers'], [2, 3])
        self.assertEqual({key: single[key] for key in temporal.NETWORK_COLUMNS},
                         {key: dual[key] for key in temporal.NETWORK_COLUMNS})
        reverse_only = parsed([reciprocal(row)])[('9606.A', '9606.B')]
        self.assertEqual(single, reverse_only)

    def test_explicit_numeric_zero_remains_zero_for_all_channels(self):
        row = network_row()
        row.update({key: '0' for key in temporal.SCORE_COLUMNS})
        value = parsed([row])[('9606.A', '9606.B')]
        self.assertTrue(all(value[key] == 0.0 for key in temporal.SCORE_COLUMNS))

    def test_header_only_and_terminal_blank_are_valid(self):
        self.assertEqual(parsed(), {})
        self.assertEqual(temporal.parse_network(tsv(temporal.NETWORK_COLUMNS, [], True), ['9606.A', '9606.B']), {})
        self.assertEqual(len(temporal.parse_network(tsv(temporal.NETWORK_COLUMNS, [network_row()], True),
                                                   ['9606.A', '9606.B'])), 1)

    def test_empty_error_wrong_schema_interior_blank_and_nonbytes_fail(self):
        row = network_row()
        valid = tsv(temporal.NETWORK_COLUMNS, [row])
        for raw in [b'', b'<html>HTTP500</html>', b'ERROR\tnot found\n', b'\xff', b'\x00',
                    valid.decode(), tsv(temporal.NETWORK_COLUMNS[:-1], []),
                    tsv(tuple(reversed(temporal.NETWORK_COLUMNS)), []),
                    tsv(temporal.NETWORK_COLUMNS, []) + b'\n' + valid.split(b'\n', 1)[1],
                    valid + b'wrong\tcolumn\tcount\n']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                temporal.parse_network(raw, ['9606.A', '9606.B'])

    def test_missing_nonfinite_and_out_of_range_channel_rejected(self):
        for field in temporal.SCORE_COLUMNS:
            for bad in ['-', '', 'nan', 'inf', '-0.1', '1.1', 'unavailable']:
                row = network_row(); row[field] = bad
                with self.subTest(field=field, value=bad), self.assertRaises(ValueError):
                    parsed([row])

    def test_wrong_species_added_self_or_namespace_fail(self):
        for row in [network_row('9606.A', '9606.C'), network_row('9606.A', '9606.A'),
                    network_row('10090.A', '9606.B'), network_row('UniProtKB:P00001', '9606.B'),
                    {**network_row(), 'ncbiTaxonId': '10090'}]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                parsed([row])
        for ids in [[], ['9606.A'], ['9606.A', '9606.A'], ['9606.A', '10090.B']]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                temporal.parse_network(tsv(temporal.NETWORK_COLUMNS, []), ids)

    def test_duplicate_orientation_rejected_even_if_identical(self):
        row = network_row()
        for rows in [[row, row], [row, reciprocal(row), row]]:
            with self.assertRaises(ValueError):
                parsed(rows)

    def test_every_reciprocal_channel_and_canonical_label_must_agree(self):
        row = network_row()
        for field in temporal.SCORE_COLUMNS + ('preferredName_A', 'preferredName_B'):
            other = reciprocal(row); other[field] = 'different' if field.startswith('preferred') else '0.7'
            with self.subTest(field=field), self.assertRaises(ValueError):
                parsed([row, other])


class NativeProjectionTests(unittest.TestCase):
    def test_physical_only_and_functional_only_pairs_are_independent(self):
        nominated, mapping, networks, batchplan = projected_setup()
        networks['functional']['network_0001'] = {}
        networks['physical']['network_0001'] = parsed([network_row(score='0')])
        result = temporal.project_predictions(nominated, mapping, networks, batchplan)[0]
        self.assertEqual(result['views']['functional'],
                         {'state': 'no_returned_native_row', 'native_score': None, 'ranking_score': -1.0})
        self.assertEqual(result['views']['physical'], {'state': 'numeric', 'native_score': 0.0, 'ranking_score': 0.0})
        self.assertEqual(result['query_batch'], {'functional': 'functional_network_0001',
                                               'physical': 'physical_network_0001'})
        networks['functional']['network_0001'], networks['physical']['network_0001'] = (
            networks['physical']['network_0001'], networks['functional']['network_0001'])
        reversed_views = temporal.project_predictions(nominated, mapping, networks, batchplan)[0]['views']
        self.assertEqual(reversed_views['functional']['state'], 'numeric')
        self.assertEqual(reversed_views['physical']['state'], 'no_returned_native_row')

    def test_no_subset_or_score_equality_constraint_across_views(self):
        nominated, mapping, networks, batchplan = projected_setup()
        networks['physical']['network_0001'] = parsed([network_row(score='0.99')])
        result = temporal.project_predictions(nominated, mapping, networks, batchplan)[0]
        self.assertEqual(result['views']['functional']['native_score'], 0.8)
        self.assertEqual(result['views']['physical']['native_score'], 0.99)

    def test_source_absence_in_both_is_distinct_from_unmapped(self):
        nominated, mapping, networks, batchplan = projected_setup()
        for arm in temporal.ARMS:
            networks[arm]['network_0001'] = {}
        result = temporal.project_predictions(nominated, mapping, networks, batchplan)[0]
        self.assertEqual(result['mapping_states'], ['resolved', 'resolved'])
        self.assertTrue(all(view['state'] == 'no_returned_native_row' for view in result['views'].values()))
        self.assertTrue(all(result['query_batch'].values()))

    def test_predictor_output_excludes_outcome_and_does_not_mutate_input(self):
        inputs = projected_setup()
        original = deepcopy(inputs)
        result = temporal.project_predictions(*inputs)
        self.assertEqual(inputs, original)
        self.assertEqual(set(result[0]), {'products', 'source_row', 'mapping_states', 'mapping_proof', 'query_batch', 'views'})
        self.assertEqual(result[0]['products'], inputs[0][0]['products'])
        self.assertEqual(result[0]['source_row'], 1)
        proof = result[0]['mapping_proof'][0]
        self.assertEqual(proof['correspondence'], 'STRING_locus_representative_not_sequence_identity')
        self.assertEqual(proof['resolution_basis'], 'provider_best_match')
        self.assertIs(proof['candidate_search_exhaustive'], False)
        proof['hits'][0]['annotation'] = 'copy is independent'
        self.assertEqual(inputs, original)

    def test_unmapped_ambiguous_hitlimit_and_collapsed_have_no_queries(self):
        nominated = [{'products': ['P00001', 'P00002-2'], 'source_row': 1}]
        for ids, status in [((None, '9606.B'), 'unmapped'),
                            (('9606.A', '9606.A'), 'collapsed_representative')]:
            mapping = mappings(nominated[0]['products'], ids)
            result = temporal.project_predictions(nominated, mapping, {'functional': {}, 'physical': {}},
                                                    plan(nominated, mapping))[0]
            self.assertEqual(result['query_batch'], {'functional': None, 'physical': None})
            self.assertTrue(all(value['state'] == status for value in result['views'].values()))
            self.assertEqual(result['mapping_proof'][1]['accession'], 'P00002-2')
        mapping = mappings(nominated[0]['products'])
        for status in ['ambiguous', 'mapping_limit_reached']:
            mapping['P00001'].update(status=status, string_id=None)
            result = temporal.project_predictions(nominated, mapping, {'functional': {}, 'physical': {}},
                                                    plan(nominated, mapping))[0]
            self.assertEqual(result['mapping_states'][0], status)
            self.assertTrue(all(value['state'] == 'ambiguous' for value in result['views'].values()))

    def test_missing_mapping_is_failure_not_unmapped(self):
        nominated, mapping, networks, batchplan = projected_setup()
        del mapping[nominated[0]['products'][0]]
        with self.assertRaises(ValueError):
            temporal.project_predictions(nominated, mapping, networks, batchplan)

    def test_missing_extra_or_missing_view_batch_response_fails(self):
        for arm in temporal.ARMS:
            nominated, mapping, networks, batchplan = projected_setup()
            for changed in [{}, {'other': {}}, {'network_0001': {}, 'network_0002': {}}]:
                altered = deepcopy(networks); altered[arm] = changed
                with self.subTest(arm=arm, changed=changed), self.assertRaises(ValueError):
                    temporal.project_predictions(nominated, mapping, altered, batchplan)
        nominated, mapping, networks, batchplan = projected_setup()
        del networks['physical']
        with self.assertRaises(ValueError):
            temporal.project_predictions(nominated, mapping, networks, batchplan)

    def test_unqueryable_batch_cannot_supply_even_empty_response(self):
        nominated = [{'products': ['P00001', 'P00002'], 'source_row': 1}]
        mapping = mappings(ids=(None, '9606.B'))
        for arm in temporal.ARMS:
            networks = {'functional': {}, 'physical': {}}
            networks[arm]['network_0001'] = {}
            with self.assertRaises(ValueError):
                temporal.project_predictions(nominated, mapping, networks, plan(nominated, mapping))

    def test_candidate_coverage_and_fixed_batch_plan_are_enforced(self):
        nominated, mapping, networks, batchplan = projected_setup(26)
        self.assertEqual([len(batch['candidate_indices']) for batch in batchplan], [25, 1])
        self.assertEqual(len(temporal.project_predictions(nominated, mapping, networks, batchplan)), 26)
        for mutation in ['missing', 'duplicate', 'reordered', 'added_id', 'renamed', 'split']:
            altered = deepcopy(batchplan)
            if mutation == 'missing':
                altered[0]['candidate_indices'].pop()
            elif mutation == 'duplicate':
                altered[0]['candidate_indices'].append(25)
            elif mutation == 'reordered':
                altered.reverse()
            elif mutation == 'added_id':
                altered[0]['string_ids'].append('9606.C')
            elif mutation == 'renamed':
                altered[0]['batch_id'] = 'arbitrary'
            elif mutation == 'split':
                altered[1]['candidate_indices'].insert(0, altered[0]['candidate_indices'].pop())
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                temporal.project_predictions(nominated, mapping, networks, altered)

    def test_crossbatch_presence_conflict_rejected_in_either_native_view(self):
        for arm in temporal.ARMS:
            nominated, mapping, networks, batchplan = projected_setup(26)
            networks[arm]['network_0002'] = {}
            with self.subTest(arm=arm), self.assertRaises(ValueError):
                temporal.project_predictions(nominated, mapping, networks, batchplan)

    def test_crossbatch_all_channel_and_label_conflicts_rejected_in_either_view(self):
        for arm in temporal.ARMS:
            for field in temporal.SCORE_COLUMNS + ('preferredName_A', 'preferredName_B'):
                nominated, mapping, networks, batchplan = projected_setup(26)
                row = network_row(); row[field] = 'different' if field.startswith('preferred') else '0.7'
                networks[arm]['network_0002'] = parsed([row])
                with self.subTest(arm=arm, field=field), self.assertRaises(ValueError):
                    temporal.project_predictions(nominated, mapping, networks, batchplan)

    def test_projector_rejects_unvalidated_native_rows(self):
        for field, bad in [('score', '-'), ('score', True), ('ncbiTaxonId', '9606'),
                           ('source_row_numbers', []), ('preferredName_A', None)]:
            nominated, mapping, networks, batchplan = projected_setup()
            networks['physical']['network_0001'][('9606.A', '9606.B')][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                temporal.project_predictions(nominated, mapping, networks, batchplan)

    def test_empty_duplicate_unsorted_and_invalid_candidate_identity_fails(self):
        nominated, mapping, networks, batchplan = projected_setup()
        for changed in [[], nominated * 2,
                        [{**nominated[0], 'products': list(reversed(nominated[0]['products']))}],
                        [{**nominated[0], 'products': ['P00001', 'P00001']}],
                        [{**nominated[0], 'source_row': True}], [{**nominated[0], 'source_row': 0}]]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                temporal.project_predictions(changed, mapping, networks, batchplan)


if __name__ == '__main__':
    unittest.main()
