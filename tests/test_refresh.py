"""Controlled invented refreshes test maintenance, never biological truth."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.assertions import new_review_event
from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.civic import CivicClient
from biograph_steward.graph import build_graph, save_run
from biograph_steward.reviews import read_run
from test_starter import MockAPI
from test_retrieval import ContextAPI
from test_civic import CivicAPI


WHEN = '2031-01-02T03:04:05+00:00'


def resign(value):
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    return value


def mock_snapshot(*, change=None, version='TEST-ONLY', incomplete=False,
                  pathway=False, pathway_top=0):
    api = MockAPI(4)
    if pathway:
        api.rows[0]['pathways'] = [{'pwid': 101, 'name': 'Invented pathway',
                                  'type': 'Reactome', 'sourceID': 'R-HSA-101'}]
    if change:
        change(api)

    def transport(payload):
        result = api(payload)
        if 'DatabaseVersion' in payload['query']:
            result['data']['dbVersion'] = version
        if incomplete and 'DiseaseTargets' in payload['query']:
            result['data']['targets']['targets'] = result['data']['targets']['targets'][:1]
        return result

    return PharosClient(transport=transport).build_snapshot(
        'Test disease', max_targets=4, page_size=2, pathway_top=pathway_top)


def claim(graph, protein='UniProtKB:P04637', kind='disease_association'):
    return next(a for a in graph['assertions'] if a['subject'] == protein and a['kind'] == kind)


def source_bytes(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob('*') if path.is_file()}


class RefreshTests(unittest.TestCase):
    def setUp(self):
        from biograph_steward import refresh
        self.refresh = refresh
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def save(self, name, snapshot, *, civic=None, decisions=()):
        graph = build_graph(snapshot, civic_snapshot=civic)
        events = []
        for selector, state in decisions:
            assertion = selector(graph)
            events.append(new_review_event(graph, assertion['id'], state,
                                           'Invented human reviewer', 'Invented source assessment.'))
            graph = build_graph(snapshot, events, civic)
        directory = self.root / name
        save_run(snapshot, directory, review_events=events, civic_snapshot=civic)
        return directory, graph

    def migration(self, before, after, comparison):
        return self.refresh.migrate_reviews(before, after, comparison,
            reviewer='Refresh reconciliation tool', reason='Preserve exact reviewed evidence.', created_at=WHEN)

    @staticmethod
    def row(comparison, assertion_id):
        return next(row for row in comparison['assertions'] if row['assertion_id'] == assertion_id)

    def test_timestamp_refresh_preserves_full_eligible_lifecycle_with_new_binding(self):
        snapshot = mock_snapshot()
        first = lambda g: claim(g)
        second = lambda g: claim(g, 'UniProtKB:P00533')
        before, original = self.save('before', snapshot, decisions=[
            (first, 'accepted'), (first, 'provisional'), (first, 'accepted'),
            (first, 'obsolete'), (second, 'accepted')])
        after, target = self.save('after', mock_snapshot())
        inputs = source_bytes(before), source_bytes(after)
        comparison = self.refresh.compare_runs(before, after)
        self.refresh.verify_comparison(comparison, before, after)
        self.assertEqual(comparison['summary']['eligible_review_assertions'], 2)
        self.assertTrue(all(row['observed_change'] == 'unchanged' for row in comparison['assertions']))
        migrated = self.migration(before, after, comparison)
        self.assertEqual(len(migrated), len(original['review_events']))
        rebuilt = build_graph(json.loads((after / 'snapshot.json').read_text()), migrated)
        self.assertEqual(first(rebuilt)['lifecycle_state'], 'obsolete')
        self.assertEqual(second(rebuilt)['lifecycle_state'], 'accepted')
        self.assertNotEqual(original['snapshot_sha256'], rebuilt['snapshot_sha256'])
        self.assertTrue(all(event['snapshot_sha256'] == target['snapshot_sha256'] for event in migrated))
        self.assertTrue(all(event['reviewer'] == 'Refresh reconciliation tool' for event in migrated))
        self.assertTrue(all(event['created_at'] == WHEN for event in migrated))
        for event, prior in zip(migrated, original['review_events']):
            ancestry = event['migration']
            self.assertEqual(ancestry['kind'], 'inherited_review_decision')
            self.assertIs(ancestry['fresh_human_adjudication'], False)
            self.assertEqual(ancestry['original_event'], prior)
            self.assertEqual(ancestry['original_event_sha256'], digest(prior))
            self.assertEqual(ancestry['comparison_sha256'], comparison['comparison_sha256'])
            self.assertEqual(ancestry['source_parent'], comparison['parents']['before'])
            self.assertEqual(ancestry['target_parent'], comparison['parents']['after'])
        self.assertTrue(all(not a['biologically_validated'] for a in rebuilt['assertions']))
        self.assertEqual(inputs, (source_bytes(before), source_bytes(after)))

    def test_changed_source_evidence_requeues_only_affected_assertion(self):
        decisions = [(lambda g: claim(g), 'accepted'),
                     (lambda g: claim(g, 'UniProtKB:P00533'), 'accepted')]
        before, old = self.save('before', mock_snapshot(), decisions=decisions)
        def changed(api):
            api.rows[0]['diseaseAssociationDetails'][0]['evidence'] = 'Changed invented source evidence.'
        after, new = self.save('after', mock_snapshot(change=changed))
        comparison = self.refresh.compare_runs(before, after)
        affected = self.row(comparison, claim(old)['id'])
        untouched = self.row(comparison, claim(old, 'UniProtKB:P00533')['id'])
        self.assertEqual(affected['observed_change'], 'changed')
        self.assertFalse(affected['review_eligible'])
        self.assertTrue(untouched['review_eligible'])
        migrated = self.migration(before, after, comparison)
        rebuilt = build_graph(json.loads((after / 'snapshot.json').read_text()), migrated)
        self.assertEqual(claim(rebuilt)['lifecycle_state'], 'candidate')
        self.assertEqual(claim(rebuilt, 'UniProtKB:P00533')['lifecycle_state'], 'accepted')
        self.assertEqual(claim(old)['id'], claim(new)['id'])
        self.assertNotEqual(claim(old)['revision'], claim(new)['revision'])

    def test_changed_disease_context_does_not_move_a_review_to_the_new_claim(self):
        before, old = self.save('before', mock_snapshot(), decisions=[(lambda g: claim(g), 'accepted')])
        def changed(api):
            api.rows[0]['diseaseAssociationDetails'][0]['name'] = 'Other invented disease'
        after, new = self.save('after', mock_snapshot(change=changed))
        comparison = self.refresh.compare_runs(before, after)
        self.assertNotEqual(claim(old)['id'], claim(new)['id'])
        self.assertEqual(self.row(comparison, claim(old)['id'])['observed_change'], 'removed')
        self.assertEqual(self.row(comparison, claim(new)['id'])['observed_change'], 'added')
        self.assertFalse(self.row(comparison, claim(old)['id'])['review_eligible'])
        self.assertEqual(self.migration(before, after, comparison), [])

    def test_same_evidence_id_cannot_preserve_acceptance_after_validation_changes(self):
        before, old = self.save('before', mock_snapshot(), decisions=[
            (lambda g: claim(g), 'accepted'),
            (lambda g: claim(g, 'UniProtKB:P00533'), 'accepted')])
        def changed(api):
            api.rows[0]['tdl'] = 'Unknown-development-level'
        after, new = self.save('after', mock_snapshot(change=changed))
        self.assertEqual(claim(old)['id'], claim(new)['id'])
        self.assertEqual(claim(old)['revision'], claim(new)['revision'])
        self.assertNotEqual(claim(old)['validation_status'], claim(new)['validation_status'])
        comparison = self.refresh.compare_runs(before, after)
        self.assertFalse(self.row(comparison, claim(old)['id'])['review_eligible'])
        self.assertTrue(self.row(comparison, claim(old, 'UniProtKB:P00533')['id'])['review_eligible'])

    def test_incomplete_targets_and_changed_scope_never_establish_removal(self):
        before, old = self.save('before', mock_snapshot(), decisions=[(lambda g: claim(g), 'accepted')])
        for name, snapshot in (('incomplete', mock_snapshot(incomplete=True)),
                               ('scope', mock_snapshot())):
            if name == 'scope':
                snapshot['query_settings']['max_targets'] = 99
                resign(snapshot)
            after, _ = self.save(name, snapshot)
            comparison = self.refresh.compare_runs(before, after)
            with self.subTest(case=name):
                self.assertEqual(comparison['summary']['eligible_review_assertions'], 0)
                self.assertTrue(all(row['status'] == 'not_comparable'
                                    for row in comparison['assertions']))
                self.assertEqual(self.migration(before, after, comparison), [])

    def test_preview_pathway_cap_and_failed_scoped_family_do_not_prove_withdrawal(self):
        before, old = self.save('preview_before', mock_snapshot(pathway=True, pathway_top=1))
        after, _ = self.save('preview_after', mock_snapshot(pathway=False, pathway_top=1))
        comparison = self.refresh.compare_runs(before, after)
        pathway = claim(old, kind='pathway_membership')
        removed = self.row(comparison, pathway['id'])
        self.assertEqual(removed['observed_change'], 'removed')
        self.assertEqual(removed['status'], 'not_comparable')
        api = ContextAPI()
        old_snapshot = PharosClient(transport=api).build_snapshot(
            'Test disease', profile='scoped', tissue_term='colon rectum')
        before, old = self.save('scoped_before', old_snapshot)
        api = ContextAPI()
        api.modify = lambda family, uid, skip, result: ({**result, 'rows': []}
            if family == 'ppis' and uid == 'P04637' else result)
        incomplete = PharosClient(transport=api).build_snapshot(
            'Test disease', profile='scoped', tissue_term='colon rectum')
        after, _ = self.save('scoped_after', incomplete)
        interaction = next(a for a in old['assertions'] if a['kind'] == 'protein_interaction')
        removed = self.row(self.refresh.compare_runs(before, after), interaction['id'])
        self.assertEqual(removed['observed_change'], 'removed')
        self.assertEqual(removed['status'], 'not_comparable')
        self.assertFalse(removed['review_eligible'])

    def test_release_and_normalization_policy_changes_never_carry_reviews(self):
        before, _ = self.save('before', mock_snapshot(), decisions=[(lambda g: claim(g), 'accepted')])
        after, _ = self.save('release_after', mock_snapshot(version='DIFFERENT-TEST-RELEASE'))
        comparison = self.refresh.compare_runs(before, after)
        self.assertEqual(comparison['summary']['eligible_review_assertions'], 0)
        self.assertEqual(self.migration(before, after, comparison), [])
        after, _ = self.save('unknown_release', mock_snapshot(version=None))
        self.assertEqual(self.refresh.compare_runs(before, after)['summary']['eligible_review_assertions'], 0)
        after, _ = self.save('policy_after', mock_snapshot())
        manifest = json.loads((after / 'run_manifest.json').read_text())
        manifest['normalization_policy'] = 'different-invented-policy'
        write_json(after / 'run_manifest.json', manifest)
        comparison = self.refresh.compare_runs(before, after)
        self.assertEqual(comparison['summary']['eligible_review_assertions'], 0)

    def test_target_review_is_preserved_instead_of_overwritten_by_source_review(self):
        decisions = [(lambda g: claim(g), 'accepted'),
                     (lambda g: claim(g, 'UniProtKB:P00533'), 'accepted')]
        before, _ = self.save('before', mock_snapshot(), decisions=decisions)
        after, target = self.save('after', mock_snapshot(),
                                  decisions=[(lambda g: claim(g), 'rejected')])
        comparison = self.refresh.compare_runs(before, after)
        self.assertFalse(self.row(comparison, claim(target)['id'])['review_eligible'])
        migrated = self.migration(before, after, comparison)
        self.assertEqual(migrated[:len(target['review_events'])], target['review_events'])
        rebuilt = build_graph(json.loads((after / 'snapshot.json').read_text()), migrated)
        self.assertEqual(claim(rebuilt)['lifecycle_state'], 'rejected')
        self.assertEqual(claim(rebuilt, 'UniProtKB:P00533')['lifecycle_state'], 'accepted')

    def test_tampered_sources_review_histories_and_recomputed_comparisons_are_rejected(self):
        before, _ = self.save('before', mock_snapshot(), decisions=[(lambda g: claim(g), 'accepted')])
        after, _ = self.save('after', mock_snapshot())
        original_snapshot = (after / 'snapshot.json').read_bytes()
        snapshot = json.loads(original_snapshot)
        snapshot['created_at'] = WHEN
        write_json(after / 'snapshot.json', snapshot)
        with self.assertRaises(ValueError):
            self.refresh.compare_runs(before, after)
        (after / 'snapshot.json').write_bytes(original_snapshot)
        history_path = before / 'review_events.json'
        original_history = history_path.read_bytes()
        history = json.loads(original_history)
        history[0]['revision'] = 'invented-stale-revision'
        write_json(history_path, history)
        with self.assertRaises(ValueError):
            self.refresh.compare_runs(before, after)
        history_path.write_bytes(original_history)
        comparison = self.refresh.compare_runs(before, after)
        comparison['assertions'][0]['review_eligible'] = not comparison['assertions'][0]['review_eligible']
        comparison.pop('comparison_sha256')
        comparison['comparison_sha256'] = digest(comparison)
        with self.assertRaises(ValueError):
            self.refresh.migrate_reviews(before, after, comparison, created_at=WHEN)

    def test_civic_requires_exact_sidecar_but_new_civic_does_not_invalidate_pharos(self):
        civic = CivicClient(transport=CivicAPI()).retrieve()
        select_civic = lambda g: next(a for a in g['assertions'] if a['kind'] == 'variant_therapy_response')
        before, old = self.save('before', mock_snapshot(), civic=civic, decisions=[
            (lambda g: claim(g), 'accepted'), (select_civic, 'accepted')])
        after, _ = self.save('exact_after', mock_snapshot(), civic=deepcopy(civic))
        comparison = self.refresh.compare_runs(before, after)
        self.assertTrue(self.row(comparison, select_civic(old)['id'])['review_eligible'])
        migrated = self.migration(before, after, comparison)
        rebuilt = build_graph(json.loads((after / 'snapshot.json').read_text()), migrated, civic)
        self.assertEqual(select_civic(rebuilt)['lifecycle_state'], 'accepted')
        self.assertTrue(all(event.get('civic_snapshot_sha256') == civic['content_sha256']
                            for event in migrated if event['assertion_id'] == select_civic(old)['id']))
        changed_civic = deepcopy(civic)
        changed_civic['created_at'] = WHEN
        resign(changed_civic)
        after, _ = self.save('changed_sidecar', mock_snapshot(), civic=changed_civic)
        comparison = self.refresh.compare_runs(before, after)
        self.assertFalse(self.row(comparison, select_civic(old)['id'])['review_eligible'])
        self.assertTrue(self.row(comparison, claim(old)['id'])['review_eligible'])
        after, _ = self.save('missing_sidecar', mock_snapshot())
        missing = self.row(self.refresh.compare_runs(before, after), select_civic(old)['id'])
        self.assertEqual(missing['observed_change'], 'removed')
        self.assertEqual(missing['status'], 'not_comparable')

    def test_refresh_workflow_is_immutable_replays_and_escapes_inherited_review_text(self):
        from biograph_steward.refresh_workflow import run_refresh, verify_refresh
        snapshot = mock_snapshot()
        source_graph = build_graph(snapshot)
        script = '<script>alert("invented review text")</script>'
        event = new_review_event(source_graph, claim(source_graph)['id'], 'accepted',
                                 'Invented reviewer', script)
        before = self.root / 'before'
        save_run(snapshot, before, review_events=[event])
        after, target = self.save('after', mock_snapshot())
        inputs = source_bytes(before), source_bytes(after)
        comparison_only = run_refresh(before, after, self.root / 'comparison_only')
        self.assertEqual(comparison_only['graph']['review_events'], [])
        self.assertEqual(claim(comparison_only['graph'])['lifecycle_state'], 'candidate')
        output = self.root / 'carried'
        result = run_refresh(before, after, output, carry_reviews=True)
        self.assertEqual(claim(result['graph'])['lifecycle_state'], 'accepted')
        self.assertEqual(verify_refresh(output), result['receipt'])
        self.assertEqual(inputs, (source_bytes(before), source_bytes(after)))
        self.assertEqual((output / 'refresh_inputs/before/snapshot.json').read_bytes(),
                         (before / 'snapshot.json').read_bytes())
        self.assertEqual(result['receipt']['network_requests'], 0)
        self.assertEqual(result['receipt']['llm_calls'], 0)
        self.assertIs(result['receipt']['review_carryover_is_new_human_judgment'], False)
        report = (output / 'refresh_report.html').read_text()
        self.assertNotIn('<script>', report)
        self.assertIn('&lt;script&gt;', report)
        for invalid_output in (output, before / 'nested_result', after):
            with self.subTest(output=invalid_output), self.assertRaises(ValueError):
                run_refresh(before, after, invalid_output, carry_reviews=True)

    def test_refresh_rejects_forged_ancestry_even_with_resigned_output_receipt(self):
        from biograph_steward.refresh_workflow import run_refresh, verify_refresh
        before, _ = self.save('before', mock_snapshot(), decisions=[(lambda g: claim(g), 'accepted')])
        after, _ = self.save('after', mock_snapshot())
        output = self.root / 'result'
        run_refresh(before, after, output, carry_reviews=True)
        events = json.loads((output / 'review_events.json').read_text())
        ancestry = events[0]['migration']
        ancestry['original_event']['reviewer'] = 'Forged inherited reviewer'
        ancestry['original_event_sha256'] = digest(ancestry['original_event'])
        write_json(output / 'review_events.json', events)
        receipt = json.loads((output / 'refresh_receipt.json').read_text())
        receipt['files']['review_events.json'] = hashlib.sha256((output / 'review_events.json').read_bytes()).hexdigest()
        receipt.pop('receipt_sha256')
        receipt['receipt_sha256'] = digest(receipt)
        write_json(output / 'refresh_receipt.json', receipt)
        with self.assertRaises(ValueError):
            verify_refresh(output)


if __name__ == '__main__':
    unittest.main()
