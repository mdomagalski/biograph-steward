"""Invented source/assay fixtures for fixed pruning; never read real labels."""
from copy import deepcopy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import load_decisions
from test_pharos_inventory import InventoryAPI, retrieval
from test_ppi_pruning_preparation import preparation

SPEC = importlib.util.spec_from_file_location('assess_ppi_pruning',
    Path(__file__).resolve().parents[1] / 'scripts/assess_ppi_pruning.py')
pruning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pruning)


def invented_source(root):
    """Use existing offline retrieval, normalization and packet export."""
    api = InventoryAPI()
    products = ['P%05d' % i for i in range(1, 7)]
    for i, uid in enumerate(products):
        api.identities[uid] = {'uniprot': uid, 'sym': 'INVENTED%d' % i,
            'name': 'Invented fixture protein', 'tdl': 'Tbio', 'fam': None}
        api.context[uid] = {key: [] for key in retrieval.PPI_LIMITS}
    missing = 'P00007'; api.identities[missing] = None
    pairs = [(products[0], products[i], 'STRINGDB', i / 10) for i in range(1, 6)]
    pairs += [(products[1], products[2], 'BioPlex,STRINGDB', 0.8),
              (products[3], products[4], 'BioPlex', None)]
    for index, (a, b, bundle, weight) in enumerate(pairs):
        props = [] if weight is None else [{'name': 'Score', 'value': str(weight)}]
        if 'BioPlex' in bundle:
            props.append({'name': 'p_int', 'value': '0.9999'})
        for left, right in ((a, b), (b, a)):
            api.context[left]['ppis'].append({'nid': index + 1, 'type': bundle,
                'props': deepcopy(props), 'target': {'uniprot': right, 'sym': 'INVENTED'}})
    inventory = root / 'inventory.json'
    write_json(inventory, {'format': retrieval.ACCESSION_FORMAT, 'author_commit': 'a' * 40,
        'author_panel_sha256': 'b' * 64, 'published_uniprot_accessions': products + [missing],
        'outcome_fields_decoded': False})
    folder = root / 'retrieval'
    retrieval.retrieve_inventory(inventory, folder, chunk_size=2, profile='ppi', progress=None,
        client_factory=lambda: PharosClient(transport=api))
    plan, source, summary = [preparation.read_json(folder / name)
        for name in ('plan.json', 'source.json', 'summary.json')]
    audit = root / 'audit.json'
    write_json(audit, {'format': 'biograph-steward.lambourne-pharos-lookup-audit.v1',
        'outcome_fields_decoded': False, 'retrieval_plan_sha256': plan['content_sha256'],
        'retrieval_summary_sha256': summary['content_sha256'],
        'retrieval_source_sha256': sha(folder / 'source.json'),
        'inventory_sha256': sha(folder / 'context_targets.json'), 'db_version': source['db_version'],
        'endpoint': plan['endpoint'], 'counts': {'raw_source_views': 14,
            'retained_source_views': 14, 'resolved_products': 6, 'requested_products': 7}})
    prepared = root / 'prepared'
    preparation.prepare(folder, audit, prepared)
    return prepared


def invented_ne(source, root):
    """Adapter-shaped scores only; no algorithm/accuracy claim for fixture."""
    output = root / 'invented_ne'; output.mkdir()
    weighted = pruning.tsv(source / 'weighted_pairs.tsv', ('subject', 'object', 'weight', 'pair_id'), extra=True)
    with (output / 'scores.tsv').open('w', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(('pair_id', 'score'))
        writer.writerows((row['pair_id'], 2 - float(row['weight'])) for row in weighted)
    nodes = pruning.tsv(source / 'network_nodes.tsv', pruning.NODE_COLUMNS)
    write_json(output / 'manifest.json', pruning.seal({'format': pruning.NE_FORMAT,
        'status': 'completed', 'runtime_execution_verified': True,
        'author': {'revision': pruning.AUTHOR_REVISION, 'compatibility_patches': [],
                   'source_files_sha256': pruning.AUTHOR_HASHES},
        'adapter_sha256': sha(pruning.ROOT / 'scripts/run_network_enhancement.py'),
        'runtime_image': pruning.OCTAVE_IMAGE, 'runtime': {'octave_version': '11.3.0'},
        'method': {'order': 2, 'alpha': 0.9, 'K': 1,
            'parameter_selection': 'author_defaults_no_tuning',
            'pruning_or_labels_applied': False, 'output_scope': 'original_input_edges_only'},
        'node_count': len(nodes), 'original_edge_count': len(weighted), 'score_count': len(weighted),
        'inputs_sha256': {name: sha(source / name) for name in ('network_nodes.tsv', 'weighted_pairs.tsv')},
        'outputs_sha256': {'scores.tsv': sha(output / 'scores.tsv')}}))
    return output


class PPIPruningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def prepared(self):
        source = invented_source(self.root)
        ne = invented_ne(source, self.root)
        return source, ne

    def test_actual_materialization_preserves_protected_source_and_changes_edges(self):
        source, ne = self.prepared()
        # Deliberately invalid JSON proves freeze fingerprints, never parses labels.
        refs = [self.root / (name + '.json') for name in ('candidates', 'labels', 'predictions')]
        for path in refs:
            path.write_text('NOT OUTCOME JSON')
        before = pruning.inventory(source)
        out = self.root / 'frozen'
        protocol = pruning.freeze(source, ne, *refs, out)
        self.assertFalse(protocol['outcomes_loaded'])
        self.assertTrue(pruning.sealed(protocol))
        self.assertEqual(pruning.inventory(source), before)
        proofs = protocol['arms']
        self.assertEqual(proofs['native_top80']['eligible_pairs_removed'], 1)
        self.assertEqual(proofs['ne_top80']['eligible_pairs_removed'], 1)
        self.assertNotEqual(proofs['native_top80']['retained_edge_ids_sha256'], proofs['ne_top80']['retained_edge_ids_sha256'])
        _, _, graph, groups = pruning.verify_source(source, ne)
        protected = {eid for group in groups.values() if not group['eligible'] for eid in group['edge_ids']}
        for arm in pruning.ARMS:
            report, retained = load_decisions(out / arm)
            ids = {edge['id'] for edge in retained['edges']}
            self.assertTrue(protected <= ids)
            self.assertEqual(retained['nodes'], graph['nodes'])
            self.assertTrue(proofs[arm]['all_protected_source_edges_retained'])
            self.assertEqual(proofs[arm]['utility']['preserved_node_count'], 6)
            ledger = pruning.read(out / (arm + '.decisions.json'))
            self.assertTrue(all(row['confidence'] is None for row in ledger['decisions']))
            self.assertTrue(all('biological falsity' in row['reason'] for row in ledger['decisions']))
        pruning.verify_frozen(out, protocol['content_sha256'])
        # A changed frozen reference blocks before JSON decoding or outcome access.
        refs[1].write_text('CHANGED NOT OUTCOME JSON')
        with patch.object(pruning, 'joined_observations', side_effect=AssertionError('must not join')):
            with self.assertRaisesRegex(ValueError, 'reference bytes'):
                pruning.score_frozen(out, protocol['content_sha256'], self.root / 'results')
        self.assertFalse((self.root / 'results').exists())

    def test_native_field_mixed_source_and_author_binding_are_checked(self):
        source, ne = self.prepared()
        _, _, graph, groups = pruning.verify_source(source, ne)
        mixed = next(group for group in groups.values() if len(group['providers']) > 1)
        self.assertFalse(mixed['eligible'])
        self.assertEqual(mixed['native_score'], 0.8)
        self.assertNotEqual(mixed['native_score'], 0.9999)
        rows = pruning.tsv(source / 'graph_pairs.tsv', pruning.PAIR_COLUMNS)
        bad = deepcopy(rows)
        next(row for row in bad if row['pair_id'] == mixed['pair_id'])['pruning_eligible'] = 'true'
        with self.assertRaisesRegex(ValueError, 'eligibility'):
            pruning.prepare_groups(graph, bad, pruning.tsv(source / 'network_nodes.tsv', pruning.NODE_COLUMNS),
                pruning.tsv(ne / 'scores.tsv', ('pair_id', 'score')))
        manifest = pruning.read(ne / 'manifest.json')
        manifest['method']['alpha'] = 0.8
        write_json(ne / 'manifest.json', pruning.seal({k: v for k, v in manifest.items() if k != 'content_sha256'}))
        with self.assertRaisesRegex(ValueError, 'fixed method'):
            pruning.verify_source(source, ne)

    def test_pair_ties_have_exact_budget_without_modifying_raw_scores(self):
        groups = {str(i): {'eligible': True, 'native_score': 0.5,
                          'ne_score': (2 if i == 4 else 1)} for i in range(5)}
        selections, info = pruning.select_arms(groups)
        self.assertEqual(selections['native_top80'], {'0', '1', '2', '3'})
        self.assertEqual(len(selections['ne_top80']), 4)
        self.assertTrue(info['native_top80']['cutoff_tie_split'])
        self.assertEqual(info['native_top80']['cutoff_tied_pairs'], 5)
        self.assertEqual({group['native_score'] for group in groups.values()}, {0.5})
        self.assertTrue(info['native_ne_selected_pairs_differ'])

    def test_no_actual_selection_contrast_stops_before_materialization_or_outcomes(self):
        source, ne = self.prepared()
        weighted = pruning.tsv(source / 'weighted_pairs.tsv', ('subject', 'object', 'weight', 'pair_id'), extra=True)
        with (ne / 'scores.tsv').open('w', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
            writer.writerow(('pair_id', 'score'))
            writer.writerows((row['pair_id'], row['weight']) for row in weighted)
        manifest = pruning.read(ne / 'manifest.json')
        manifest['outputs_sha256']['scores.tsv'] = sha(ne / 'scores.tsv')
        write_json(ne / 'manifest.json', pruning.seal({k: v for k, v in manifest.items() if k != 'content_sha256'}))
        refs = [self.root / (name + '.json') for name in ('candidates', 'labels', 'predictions')]
        for path in refs:
            path.write_text('NOT OUTCOME JSON')
        with patch.object(pruning, '_isolated_view_proof', side_effect=AssertionError('must not materialize')):
            with self.assertRaisesRegex(ValueError, 'identical pair sets'):
                pruning.freeze(source, ne, *refs, self.root / 'no_op')
        self.assertFalse((self.root / 'no_op/protocol.json').exists())
        self.assertFalse(pruning.read(self.root / 'no_op/no_op.json')['scoring_permitted'])

    def test_secondary_ap_preserves_raw_ties_and_explicit_missing_scores(self):
        calls = []
        def capture(labels, scores):
            calls.append((labels, scores))
            return 0.5
        rows = []
        for detected, score in ((True, 0.5), (False, 0.5), (True, None)):
            rows.append({'assay_evaluable': True, 'detected': detected, 'graph_present': score is not None,
                'pruning_eligible': score is not None, 'assay_status': 'detected' if detected else 'not_detected',
                'exposure': {'huri_overlap': False, 'inmc_overlap': False},
                'scores': {'native': score, 'ne': score},
                'arms': {arm: {'retained': score is not None} for arm in pruning.ARMS}})
        with patch.dict('sys.modules', {'sklearn': SimpleNamespace(__version__='1.9.1'),
                                       'sklearn.metrics': SimpleNamespace(average_precision_score=capture)}):
            metrics = pruning.metrics_for_rows(rows, with_ap=True)
        self.assertEqual(calls, [([1, 0, 1], [0.5, 0.5, -1])] * 2)
        self.assertEqual(metrics['average_precision']['native']['missing_tied_below_numeric'], 1)
        self.assertIn('not AP of the pruned graph', metrics['average_precision_policy'])

    def test_reciprocal_evidence_ids_share_decisions_and_protected_group_abstains(self):
        groups = {'pair': {'eligible': True, 'edge_ids': ['forward', 'reverse']},
                  'mixed': {'eligible': False, 'edge_ids': ['mixed1', 'mixed2']}}
        graph = {'edges': [{'id': uid} for uid in ('forward', 'reverse', 'mixed1', 'mixed2', 'other')]}
        ledger = pruning.decision_ledger({'packet_id': 'invented'}, graph, groups, set(), 'ne_top80')
        values = {row['edge_id']: row['decision'] for row in ledger['decisions']}
        self.assertEqual(values, {'forward': 'prune', 'reverse': 'prune', 'mixed1': 'abstain', 'mixed2': 'abstain', 'other': 'abstain'})

    def test_all_denominators_missingness_and_failures_remain_explicit(self):
        def row(detected, present, native, enhanced, *, evaluable=True, protected=False):
            return {'assay_evaluable': evaluable, 'detected': detected, 'graph_present': present,
                'pruning_eligible': present and not protected, 'assay_status': 'test_failed' if not evaluable else ('detected' if detected else 'not_detected'),
                'exposure': {'huri_overlap': False, 'inmc_overlap': False},
                'scores': {'native': 0.5 if present else None, 'ne': 1.5 if present else None},
                'arms': {arm: {'retained': keep if present else None} for arm, keep in
                         (('unpruned', True), ('native_top80', native), ('ne_top80', enhanced))}}
        rows = [row(True, True, False, True), row(False, True, True, False),
                row(True, True, True, True, protected=True), row(True, False, False, False),
                row(False, False, False, False), row(None, True, True, True, evaluable=False)]
        metrics = pruning.metrics_for_rows(rows)
        native, enhanced = (metrics['arms'][arm] for arm in pruning.ARMS[1:])
        self.assertEqual(metrics['population']['all_nominations'], 6)
        self.assertEqual(metrics['population']['assay_eligible'], 5)
        self.assertEqual(metrics['population']['assay_exclusion_states'], {'test_failed': 1})
        self.assertEqual(native['source_absent_pairs'], 2)
        self.assertEqual(native['pruned_pairs'], 1)
        self.assertEqual(native['detection_retention_relative_to_unpruned_present'], 0.5)
        self.assertEqual(enhanced['detection_retention_relative_to_unpruned_present'], 1)
        self.assertEqual(enhanced['full_panel_detection_coverage'], 2 / 3)
        self.assertEqual(enhanced['nondetection_removal_relative_to_unpruned_present'], 1)
        self.assertEqual(metrics['pruning_eligible_measured_subset']['arms']['native_top80']['retained_detected'], 0)
        self.assertIsNone(metrics['average_precision'])
        self.assertFalse(metrics['independent_validation'])

    def test_connectivity_accounts_for_preserved_isolates(self):
        graph = {'nodes': [{'id': str(i)} for i in range(6)], 'edges': [
            {'subject': '0', 'object': '1'}, {'subject': '1', 'object': '2'}, {'subject': '3', 'object': '4'}]}
        utility = pruning.graph_utility(graph)
        self.assertEqual(utility['preserved_node_count'], 6)
        self.assertEqual(utility['isolated_nodes'], 1)
        self.assertEqual(utility['undirected_component_count'], 3)
        self.assertEqual(utility['largest_undirected_component_nodes'], 3)


if __name__ == '__main__':
    unittest.main()
