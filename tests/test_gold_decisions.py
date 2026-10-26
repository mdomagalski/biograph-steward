"""Retained graph integrity on invented data; no biological pruning labels."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.assertions import new_review_event
from biograph_steward.client import digest, write_json
from biograph_steward.demo import demo_snapshot
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import export_packet, load_decisions, save_decisions
from biograph_steward.graph import build_graph, save_run
from test_normalization import fixture, resign


def read(path):
    return json.loads(Path(path).read_text())


class RetainedGraphTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.packet, self.out = (self.root / name for name in ('run', 'packet', 'decisions'))
        self.path = self.root / 'input.json'

    def prepare(self, snapshot=None, events=None):
        self.graph = save_run(snapshot or demo_snapshot(), self.run, review_events=events)
        export_packet(self.run, self.packet)
        self.value = read(self.packet / 'decisions.template.json')
        self.value.update(actor='Invented test reviewer', method='Invented structural fixture')

    def save(self):
        write_json(self.path, self.value)
        self.report = save_decisions(self.packet, self.path, self.out)
        return load_decisions(self.out)[1]

    def mark(self, edge_id, decision):
        next(row for row in self.value['decisions'] if row['edge_id'] == edge_id).update(
            decision=decision, reason='Invented fixture decision; no biological adjudication')

    def reseal(self, *names):
        report = read(self.out / 'report.json')
        for name in names:
            report['files'][name] = sha(self.out / name)
        report.pop('content_sha256')
        report['content_sha256'] = digest(report)
        write_json(self.out / 'report.json', report)

    def test_abstain_retains_exact_evidence_nodes_qualifiers_and_review_state(self):
        snapshot = demo_snapshot()
        graph = build_graph(snapshot)
        assertion = next(row for row in graph['assertions'] if row['kind'] == 'disease_association'
                         and row['structurally_usable_evidence_ids'])
        event = new_review_event(graph, assertion['id'], 'accepted', 'Invented reviewer', 'Fixture review')
        self.prepare(snapshot, [event])
        retained = self.save()
        self.assertEqual(retained['nodes'], self.graph['nodes'])
        self.assertEqual(retained['edges'], self.graph['edges'])
        self.assertEqual(retained['assertions'], self.graph['assertions'])
        self.assertEqual(retained['quarantine'], self.graph['quarantine'])
        self.assertEqual(retained['assertion_summary']['lifecycle_counts']['accepted'], 1)
        self.assertTrue(all(row['status'] == 'unchanged' for row in retained['assertion_changes']))
        self.assertEqual(self.report['counts']['abstain'], len(self.graph['edges']))
        # Package is complete without the original run/packet directories.
        shutil.rmtree(self.run)
        shutil.rmtree(self.packet)
        self.assertEqual(load_decisions(self.out)[1], retained)

    def test_mixed_support_rebuilds_aggregates_and_does_not_carry_stale_acceptance(self):
        snapshot = demo_snapshot()
        graph = build_graph(snapshot)
        assertion = next(row for row in graph['assertions']
                         if len(row['evidence_edge_ids']) > 1 and row['structurally_usable_evidence_ids'])
        event = new_review_event(graph, assertion['id'], 'accepted', 'Invented reviewer', 'Fixture review')
        self.prepare(snapshot, [event])
        pruned = assertion['evidence_edge_ids'][0]
        kept = assertion['evidence_edge_ids'][1]
        self.mark(pruned, 'prune')
        self.mark(kept, 'keep')
        retained = self.save()
        current = next(row for row in retained['assertions'] if row['id'] == assertion['id'])
        edge = next(row for row in retained['edges'] if row['id'] == kept)
        self.assertEqual(current['evidence_edge_ids'], [kept])
        self.assertEqual(current['structurally_usable_evidence_ids'],
                         [kept] if edge['status'] == 'passed_structural_checks' else [])
        self.assertEqual(current['publications'], sorted(set(edge['publications'])))
        self.assertEqual(current['source_names'], [edge['primary_source_raw']])
        self.assertEqual(current['source_record_count'], edge.get('source_record_count', len(edge['record_locators'])))
        self.assertEqual(current['lifecycle_state'], 'candidate')
        self.assertEqual(current['review_history'], [])
        self.assertNotEqual(current['revision'], assertion['revision'])
        change = next(row for row in retained['assertion_changes'] if row['assertion_id'] == assertion['id'])
        self.assertEqual(change['status'], 'evidence_changed')
        self.assertFalse(change['review_history_carried'])
        self.assertEqual(change['baseline_review_event_count'], 1)
        self.assertEqual(read(self.out / 'baseline_packet/source/review_events.json'), [event])
        self.assertEqual(retained['nodes'], graph['nodes'])
        self.assertEqual(len(retained['edges']), len(graph['edges']) - 1)

    def test_all_pruned_keeps_every_node_and_context_without_dangling_links(self):
        self.prepare(fixture())
        for edge in self.graph['edges']:
            self.mark(edge['id'], 'prune')
        retained = self.save()
        self.assertEqual(retained['nodes'], self.graph['nodes'])
        self.assertEqual(retained['edges'], [])
        self.assertEqual(retained['assertions'], [])
        self.assertEqual(retained['summary']['isolated_nodes'], len(self.graph['nodes']))
        self.assertEqual(len(retained['context_records']), len(self.graph['context_records']))
        self.assertTrue(all(not row['assertion_ids'] and not row['normalized_evidence_edge_ids']
                            for row in retained['context_records']))
        self.assertTrue(all(row['status'] == 'removed' and row['retained_revision'] is None
                            for row in retained['assertion_changes']))
        for original, current in zip(self.graph['context_records'], retained['context_records']):
            self.assertEqual(current['record'], original['record'])
            self.assertEqual(current['normalization_status'], original['normalization_status'])
            self.assertEqual(current['retention']['baseline_evidence_edge_ids'], original['normalized_evidence_edge_ids'])
        self.assertEqual((self.out / 'retained_edges.jsonl').read_bytes(), b'')

    def test_context_links_only_retain_remaining_support_in_same_assertion(self):
        snapshot = fixture()
        first = snapshot['targets'][0]['pharos_context']['go'][0]
        snapshot['targets'][0]['pharos_context']['go'].append({**first, 'assigned_by': 'SECOND', 'evidence': 'IDA'})
        self.prepare(resign(snapshot))
        assertion = next(row for row in self.graph['assertions']
                         if row['kind'] == 'go_annotation' and len(row['evidence_edge_ids']) == 2)
        self.mark(assertion['evidence_edge_ids'][0], 'prune')
        retained = self.save()
        retained_ids = {row['id'] for row in retained['edges']}
        for context in retained['context_records']:
            self.assertTrue(set(context['normalized_evidence_edge_ids']) <= retained_ids)
            self.assertEqual(bool(context['assertion_ids']), bool(context['normalized_evidence_edge_ids']))
        current = next(row for row in retained['assertions'] if row['id'] == assertion['id'])
        self.assertEqual(current['evidence_edge_ids'], assertion['evidence_edge_ids'][1:])

    def test_tampered_and_resealed_graph_or_projection_rejected(self):
        self.prepare()
        retained = self.save()
        path = self.out / 'retained_graph.json'
        original = path.read_bytes()
        changed = deepcopy(retained)
        changed['edges'][0]['qualifiers']['disease'] = 'invented:other-context'
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, 'saved bytes'):
            load_decisions(self.out)
        self.reseal('retained_graph.json')
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            load_decisions(self.out)
        path.write_bytes(original)
        self.reseal('retained_graph.json')
        # Keep a valid hash manifest but stale assertion support in the JSONL view.
        row = deepcopy(retained['assertions'][0])
        row['evidence_edge_ids'] = []
        path = self.out / 'retained_assertions.jsonl'
        lines = path.read_text().splitlines()
        lines[0] = json.dumps(row)
        path.write_text('\n'.join(lines) + '\n')
        self.reseal('retained_assertions.jsonl')
        with self.assertRaisesRegex(ValueError, 'JSONL inventory'):
            load_decisions(self.out)

    def test_resealed_ledger_disagreement_and_extra_file_rejected(self):
        self.prepare()
        self.save()
        path = self.out / 'decisions.json'
        value = read(path)
        value['decisions'][0].update(decision='prune', reason='Changed after export')
        write_json(path, value)
        self.reseal('decisions.json')
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            load_decisions(self.out)
        write_json(path, self.value)
        self.reseal('decisions.json')
        (self.out / 'extra.txt').write_text('not part of handoff')
        self.reseal('extra.txt')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            load_decisions(self.out)

    def test_baseline_stale_support_is_rejected_before_output_created(self):
        self.prepare()
        from biograph_steward import gold_packet
        manifest, graph = gold_packet.load_packet(self.packet)
        graph['assertions'][0]['source_record_count'] += 1
        write_json(self.path, self.value)
        with patch.object(gold_packet, 'load_packet', return_value=(manifest, graph)):
            with self.assertRaisesRegex(ValueError, 'support mapping'):
                save_decisions(self.packet, self.path, self.out)
        self.assertFalse(self.out.exists())

    def test_mutating_decision_input_during_export_leaves_no_sealed_report(self):
        self.prepare()
        write_json(self.path, self.value)
        from biograph_steward import gold_packet
        original = gold_packet._retained_graph

        def change(*args):
            result = original(*args)
            self.path.write_text('{}')
            return result

        with patch.object(gold_packet, '_retained_graph', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'changed while saving'):
                save_decisions(self.packet, self.path, self.out)
        self.assertFalse((self.out / 'report.json').exists())


if __name__ == '__main__':
    unittest.main()
