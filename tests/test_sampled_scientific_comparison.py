"""Claim/source admission controls for the offline scientific comparison."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from tools.sampled_audit.scientific_comparison import (
    SEMANTICS, admit_judgments, compatible_inspector, population_and_memberships,
)


def graph_fixture():
    assertions = [
        {'id': 'old1', 'subject': 'invented:p1', 'predicate': 'biograph:has_go_annotation',
         'object': 'invented:go1', 'kind': 'go_annotation', 'qualifiers': {'go_aspect': 'P'},
         'evidence_edge_ids': ['edge1']},
        {'id': 'old2', 'subject': 'invented:p2', 'predicate': 'biograph:has_go_annotation',
         'object': 'invented:go2', 'kind': 'go_annotation', 'qualifiers': {'go_aspect': 'P'},
         'evidence_edge_ids': ['edge2']},
        {'id': 'added', 'subject': 'invented:p1', 'predicate': 'biograph:has_assay_observation_with',
         'object': 'invented:p2', 'kind': 'tissue_proximity_observation', 'qualifiers': {},
         'evidence_edge_ids': ['edge3']},
    ]
    ee = [{'id': 'edge' + str(i), 'aggregator': 'Pharos' if i < 3 else 'Invented external',
           'data_kind': 'live_pharos' if i < 3 else 'invented_external'} for i in (1, 2, 3)]
    union = {'assertions': assertions, 'edges': ee, 'targets': [{'id': 'invented:p1'}, {'id': 'invented:p2'}],
             'snapshot_sha256': '1' * 64}
    pure = {**deepcopy(union), 'assertions': deepcopy(assertions[:2]), 'edges': deepcopy(ee[:2])}
    final = {**deepcopy(union), 'assertions': deepcopy([assertions[0], assertions[2]]),
             'edges': deepcopy([ee[0], ee[2]])}
    return union, pure, final


class ScientificComparisonTests(unittest.TestCase):
    def test_unqualified_renderer_is_rejected_before_its_code_executes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'unqualified.py'
            path.write_text("raise RuntimeError('This source must never execute.')\n")
            with self.assertRaisesRegex(ValueError, 'hash is not qualified'):
                compatible_inspector(path)

    def test_source_memberships_keep_original_units_and_explicit_semantics(self):
        universe, pure, final = graph_fixture()
        population, membership = population_and_memberships(universe, pure, final)
        self.assertEqual(set(membership['pharos_only']), {'old1', 'old2'})
        self.assertEqual(set(membership['retained']), {'old1', 'added'})
        p = next(r for r in population if r['assertion_id'] == 'old1')
        self.assertEqual(p['assertion_content_sha256'], digest(universe['assertions'][0]))
        self.assertEqual(p['claim_semantics'], SEMANTICS['go_annotation'])

    def test_changed_qualifier_or_target_cannot_keep_same_comparison_identity(self):
        for change in ('qualifier', 'cohort', 'snapshot'):
            u, p, f = graph_fixture()
            if change == 'qualifier': f['assertions'][0]['qualifiers']['go_aspect'] = 'F'
            if change == 'cohort': p['targets'].pop()
            if change == 'snapshot': f['snapshot_sha256'] = '2' * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                population_and_memberships(u, p, f)

    def test_native_Gold_retained_profile_inherits_source_cohort_and_preserves_target_nodes(self):
        u, p, f = graph_fixture()
        f.pop('targets')
        f.update(graph_format='biograph-steward.retained-evidence-graph.v1',
                 retention_policy='remove_explicit_prune_keep_abstain_preserve_all_nodes.v1',
                 nodes=[{'id': 'invented:p1'}, {'id': 'invented:p2'}])
        _, memberships = population_and_memberships(u, p, f)
        self.assertEqual(set(memberships['retained']), {'old1', 'added'})
        f['nodes'].pop()
        with self.assertRaisesRegex(ValueError, 'preserves the original primary targets'):
            population_and_memberships(u, p, f)

    def test_pharos_origin_markers_payloads_and_complete_captured_frame_are_checked(self):
        for change in ('marker', 'origin', 'payload', 'subset'):
            u, p, f = graph_fixture()
            if change == 'marker': p['civic_snapshot_sha256'] = '2' * 64
            if change == 'origin': p['edges'][0]['aggregator'] = 'Invented external'
            if change == 'payload': p['edges'][0]['extra'] = 'changed source'
            if change == 'subset': p['assertions'].pop(); p['edges'].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                population_and_memberships(u, p, f)

    def fixture_admission(self, root, label='unknown'):
        u, p, f = graph_fixture()
        population, _ = population_and_memberships(u, p, f)
        pop = next(r for r in population if r['assertion_id'] == 'old1')
        case = {'case_id': 'case1', 'sample_id': 'invented:sample',
                'dossier_content_sha256': '4' * 64, 'assertion_id': 'old1'}
        reference = root / 'invented_reference.tsv'
        reference.write_text('Invented test reference; no biological labels.\n')
        row = {**pop, **case, 'scientific_label': label,
            'reference_kind': 'none' if label == 'unknown' else 'expert_curation',
            'reference_independence': 'unresolved' if label == 'unknown' else 'independent',
            'exact_claim_match': label != 'unknown', 'context_complete': label != 'unknown',
            'qualifier_scope_complete': label != 'unknown', 'reason': 'Invented software control.',
            'reference_files': [] if label == 'unknown' else [{'file': str(reference), 'sha256': sha(reference)}]}
        path = root / 'judgments.jsonl'
        path.write_text(json.dumps(row) + '\n')
        return population, case, row, path, reference

    def test_unknown_is_explicit_and_shared_reference_cannot_be_independent_truth(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            population, case, row, path, _ = self.fixture_admission(root)
            rr, _, refs = admit_judgments([path], population, [case], root)
            self.assertEqual(rr[0]['scientific_label'], 'unknown')
            self.assertEqual(refs, {})
            row.update(scientific_label='true', reference_independence='shared')
            path.write_text(json.dumps(row) + '\n')
            with self.assertRaisesRegex(ValueError, 'shared/unresolved'):
                admit_judgments([path], population, [case], root)

    def test_reference_bytes_and_dossier_hash_are_bound_before_statistics(self):
        for change in ('reference', 'dossier', 'assertion', 'missing'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                population, case, row, path, ref = self.fixture_admission(root, 'true')
                if change == 'reference': ref.write_text('Different invented source bytes.\n')
                if change == 'dossier': row['dossier_content_sha256'] = '5' * 64
                if change == 'assertion': row['assertion_content_sha256'] = '6' * 64
                path.write_text('' if change == 'missing' else json.dumps(row) + '\n')
                with self.assertRaises(ValueError):
                    admit_judgments([path], population, [case], root)

    def test_duplicate_sampled_identity_is_one_truth_with_two_allowed_case_bindings(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            population, case, row, path, _ = self.fixture_admission(root)
            extra = {**case, 'sample_id': 'invented:other_sample', 'case_id': 'other_case',
                     'dossier_content_sha256': '8' * 64}
            rr, _, _ = admit_judgments([path], population, [case, extra], root)
            self.assertEqual(len(rr), 1)


if __name__ == '__main__':
    unittest.main()
