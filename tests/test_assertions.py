"""Scientific context boundaries, review integrity and immutable persistence."""
from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.assertions import assertion_identity, new_review_event
from biograph_steward.client import digest
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import build_graph, save_run
from biograph_steward.reviews import review_run
from biograph_steward.__main__ import main


def resign(snapshot):
    snapshot.pop('content_sha256', None)
    snapshot['content_sha256'] = digest(snapshot)
    return snapshot


def reviewable(graph):
    return next(a for a in graph['assertions'] if a['kind'] == 'disease_association'
                and a['structurally_usable_evidence_ids'])


class AssertionTests(unittest.TestCase):
    def test_other_disease_has_its_own_unmapped_node_and_no_selected_disease_link(self):
        graph = build_graph(demo_snapshot())
        edge = next(e for e in graph['edges'] if e['evidence_record'].get('name') == 'Demo rectal cancer')
        self.assertNotEqual(edge['object'], graph['disease_node_id'])
        node = next(n for n in graph['nodes'] if n['id'] == edge['object'])
        self.assertEqual(node['name'], 'Demo rectal cancer')
        self.assertFalse(node['identifier_mapped'])
        self.assertEqual(edge['qualifiers']['disease'], edge['object'])
        self.assertEqual(graph['benchmark_readiness']['counts']['proteins_without_selected_disease_evidence'], 1)

    def test_missing_context_preserves_record_without_creating_an_association(self):
        s = demo_snapshot(); s['targets'][1]['diseaseAssociationDetails'][0]['name'] = None
        graph = build_graph(resign(s)); pid = 'demo:protein:DEMO_PROTEIN_002'
        self.assertFalse(any(e['subject'] == pid and e['predicate'] == 'biolink:associated_with' for e in graph['edges']))
        self.assertTrue(any(q.get('subject') == pid and q['reason'] == 'explicit_disease_context_missing' for q in graph['quarantine']))

    def test_two_sources_are_one_claim_with_both_records_not_two_votes(self):
        g = build_graph(demo_snapshot())
        a = next(a for a in g['assertions'] if a['subject'] == 'demo:protein:DEMO_PROTEIN_001' and a['kind'] == 'disease_association')
        self.assertEqual(len(a['evidence_edge_ids']), 2)
        self.assertEqual(len(a['source_names']), 2)
        self.assertIsNone(a['independent_evidence_count'])

    def test_qualifiers_and_relation_kind_change_identity(self):
        base = assertion_identity('protein:1', 'biolink:associated_with', 'disease:1', 'disease_association', {})
        variant = assertion_identity('protein:1', 'biolink:associated_with', 'disease:1', 'disease_association', {'variant': 'HGVS:test'})
        membership = assertion_identity('protein:1', 'biolink:associated_with', 'disease:1', 'disease_filtered_membership', {})
        self.assertNotEqual(digest(base), digest(variant))
        self.assertNotEqual(digest(base), digest(membership))
        with self.assertRaises(ValueError): assertion_identity('p', 'r', 'o', 'kind', {'therapy': []})
        with self.assertRaises(ValueError): assertion_identity('p', 'r', 'o', 'kind', {'made_up': 'x'})

    def test_claim_identity_survives_record_changes_but_revision_changes(self):
        s = demo_snapshot(); g = build_graph(s)
        before = next(a for a in g['assertions'] if a['subject'] == 'demo:protein:DEMO_PROTEIN_002' and a['kind'] == 'disease_association')
        s['targets'][1]['diseaseAssociationDetails'][0]['evidence'] = 'Changed synthetic evidence'
        after = next(a for a in build_graph(resign(s))['assertions'] if a['id'] == before['id'])
        self.assertNotEqual(before['revision'], after['revision'])

    def test_structural_pass_does_not_accept_any_assertion(self):
        g = build_graph(demo_snapshot())
        self.assertGreater(g['summary']['passed_structural_checks'], 0)
        self.assertTrue(all(a['lifecycle_state'] == 'candidate' for a in g['assertions']))
        self.assertTrue(all(not a['biologically_validated'] for a in g['assertions']))

    def test_human_acceptance_is_not_a_benchmark_label(self):
        s = demo_snapshot(); g = build_graph(s); a = reviewable(g)
        event = new_review_event(g, a['id'], 'accepted', 'Test reviewer', 'Checked this synthetic example.')
        reviewed = build_graph(s, [event])
        self.assertEqual(reviewed['assertion_summary']['lifecycle_counts']['accepted'], 1)
        self.assertEqual(reviewed['benchmark_readiness']['counts']['reviewed_positive_labels'], 0)
        self.assertTrue(all(not a['biologically_validated'] for a in reviewed['assertions']))
        self.assertEqual(g['assertion_summary']['lifecycle_counts']['accepted'], 0)

    def test_unresolved_context_and_membership_cannot_be_accepted(self):
        g = build_graph(demo_snapshot())
        blocked = [a for a in g['assertions'] if not a['structurally_usable_evidence_ids'] or a['kind'] == 'disease_filtered_membership']
        self.assertTrue(blocked)
        for a in blocked:
            with self.assertRaises(ValueError): new_review_event(g, a['id'], 'accepted', 'Tester', 'Reason')
            self.assertNotIn('accepted', a['allowed_transitions'])

    def test_review_requires_actor_reason_and_valid_transition(self):
        g = build_graph(demo_snapshot()); a = reviewable(g)
        for state, actor, reason in [('accepted', '', 'reason'), ('accepted', 'Tester', ''), ('obsolete', 'Tester', 'reason'), ('bogus', 'Tester', 'reason')]:
            with self.assertRaises(ValueError): new_review_event(g, a['id'], state, actor, reason)

    def test_old_snapshot_decisions_are_not_automatically_reapplied(self):
        s = demo_snapshot(); g = build_graph(s); a = reviewable(g)
        event = new_review_event(g, a['id'], 'accepted', 'Tester', 'Reason')
        s['created_at'] = '2030-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(ValueError, 'another snapshot'): build_graph(resign(s), [event])

    def test_review_history_rejects_unknown_revision_sequence_and_state(self):
        s = demo_snapshot(); g = build_graph(s); a = reviewable(g)
        original = new_review_event(g, a['id'], 'accepted', 'Tester', 'Reason')
        for key, value in [('assertion_id', 'missing'), ('revision', 'stale'), ('sequence', 2), ('from_state', 'accepted'), ('created_at', '2026-01-01')]:
            event = {**original, key: value}
            with self.assertRaises(ValueError): build_graph(s, [event])

    def test_review_lifecycle_and_history_are_replayed_without_mutation(self):
        s = demo_snapshot(); original = deepcopy(s); g = build_graph(s); a = reviewable(g); events = []
        for state in ('accepted', 'provisional', 'quarantined', 'candidate', 'rejected', 'candidate', 'accepted', 'obsolete'):
            events.append(new_review_event(g, a['id'], state, 'Tester', 'Synthetic lifecycle test'))
            g = build_graph(s, events)
        self.assertEqual(next(x for x in g['assertions'] if x['id'] == a['id'])['lifecycle_state'], 'obsolete')
        self.assertEqual(s, original)
        self.assertEqual(len(g['review_events']), 8)

    def test_review_run_preserves_original_and_exports_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); g = save_run(demo_snapshot(), p/'source'); a = reviewable(g)
            before = {str(f.relative_to(p/'source')): f.read_bytes() for f in (p/'source').rglob('*') if f.is_file()}
            review_run(p/'source', p/'reviewed', a['id'], 'accepted', 'Tester', 'Reason')
            after = {str(f.relative_to(p/'source')): f.read_bytes() for f in (p/'source').rglob('*') if f.is_file()}
            self.assertEqual(before, after)
            self.assertEqual((p/'source/snapshot.json').read_bytes(), (p/'reviewed/snapshot.json').read_bytes())
            self.assertEqual(len(json.loads((p/'reviewed/review_events.json').read_text())), 1)
            for name in ['assertions.json', 'assertions.tsv', 'question_scope.json', 'review_parent.json']:
                self.assertTrue((p/'reviewed'/name).exists())
            with self.assertRaises(ValueError): review_run(p/'source', p/'source/nested', a['id'], 'accepted', 'Tester', 'Reason')
            with self.assertRaises(ValueError): review_run(p/'source', p/'reviewed', a['id'], 'accepted', 'Tester', 'Reason')

    def test_cli_review_and_replay_keep_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); g = save_run(demo_snapshot(), p/'source'); a = reviewable(g)
            with redirect_stdout(StringIO()):
                self.assertEqual(main(['review', '--run', str(p/'source'), '--out', str(p/'reviewed'), '--assertion', a['id'], '--state', 'accepted', '--reviewer', 'Tester', '--reason', 'Reason']), 0)
                self.assertEqual(main(['replay', '--snapshot', str(p/'reviewed/snapshot.json'), '--reviews', str(p/'reviewed/review_events.json'), '--out', str(p/'replayed')]), 0)
            self.assertEqual((p/'reviewed/graph.json').read_bytes(), (p/'replayed/graph.json').read_bytes())
