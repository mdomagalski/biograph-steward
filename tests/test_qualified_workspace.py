"""Invented-source app consumer tests; these are not biological labels."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.graph import save_run
from biograph_steward.qualified_workspace import publish_workspace, load_workspace
from biograph_steward.questions import answer_question, save_answer, verify_answer, graph_basis
from biograph_steward.reviews import read_run, review_run
from biograph_steward.webapp import verify_qualified_question_source
from biograph_steward.workspaces import saved_workspaces
from test_normalization import fixture, resign
from test_wiki_version_projection import pathway


class QualifiedWorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        source = fixture()
        source['targets'][0]['pathways'] = [pathway(11), pathway(12), pathway(13, 'WP1_r11'), pathway(14, 'WP2_r20')]
        source['targets'][1]['pathways'] = [pathway(21), pathway(22, 'WP1_r11'), pathway(23, 'WP2_r20')]
        self.baseline = save_run(resign(source), self.root/'baseline')
        packet = self.root/'packet'
        manifest = gold_packet.export_packet(self.root/'baseline', packet)
        value = json.loads((packet/'decisions.template.json').read_text())
        value['method'] = 'Invented qualification policy'
        value['actor'] = 'Invented software-test actor'
        removed = next(e['id'] for e in self.baseline['edges'] if e.get('evidence_record', {}).get('pwid') == 23)
        for decision in value['decisions']:
            decision['decision'] = 'prune' if decision['edge_id'] == removed else 'abstain'
            decision['reason'] = 'Invented test decision, not a biological negative'
        write_json(self.root/'decisions.json', value)
        self.retained = self.root/'retained'
        gold_packet.save_decisions(packet, self.root/'decisions.json', self.retained)
        self.out = self.root/'qualified'
        publish_workspace(self.retained, self.out)
        self.graph = read_run(self.out)[2]
        self.protein = self.graph['targets'][0]['id']

    def question(self, **kwargs):
        return answer_question(self.graph, self.protein, template='qualified_pathway_source_context.v1',
            relations=['shared_pathways'], view='candidates', source_run='qualified', **kwargs)

    def test_retained_graph_in_actual_consumer_keeps_unknown_and_source_states(self):
        self.assertEqual(len(self.graph['edges']), len(self.baseline['edges']) - 1)
        self.assertEqual(self.graph['question_basis_sha256'], graph_basis(self.graph))
        self.assertNotEqual(graph_basis(self.graph), graph_basis(self.baseline))
        self.assertTrue(self.graph['qualified_view']['read_only'])
        self.assertEqual(read_run(self.root/'baseline')[2], self.baseline)
        self.assertEqual(saved_workspaces(self.root)['runs'][0]['qualified_view'], True)
        original = {e['id']: e for e in self.baseline['edges']}
        self.assertTrue(all(e == original[e['id']] for e in self.graph['edges']))

    def test_query_groups_repeats_keeps_revisions_and_applies_prune(self):
        answer = self.question(max_paths=5)
        self.assertEqual(answer['returned_proteins'], 1)
        self.assertEqual(answer['results'][0]['eligible_path_count'], 2)
        self.assertEqual(len(answer['results'][0]['paths']), 2)
        self.assertEqual({c['source_model_id'] for c in answer['citations']}, {'WP1_r10', 'WP1_r11'})
        repeat = next(c for c in answer['citations'] if c['subject'] == self.protein and c['source_model_id'] == 'WP1_r10')
        self.assertEqual(len(repeat['evidence_records']), 2)
        self.assertEqual(len(repeat['source_assertion_ids']), 2)
        self.assertEqual(answer['availability']['accepted_proteins'], 0)
        self.assertFalse(answer['llm_used'])
        verify_answer(answer)

    def test_unfiltered_source_cannot_claim_qualified_template(self):
        with self.assertRaisesRegex(ValueError, 'verified retained'):
            answer_question(self.baseline, self.protein, template='qualified_pathway_source_context.v1')

    def test_candidate_evidence_is_not_implicitly_accepted(self):
        answer = answer_question(self.graph, self.protein, template='qualified_pathway_source_context.v1', view='accepted')
        self.assertEqual(answer['returned_proteins'], 0)
        self.assertEqual(answer['availability']['inspectable_proteins'], 1)

    def test_saved_answer_exports_original_groups_and_source_replays(self):
        answer = self.question()
        save_answer(answer, self.root/'answer')
        self.assertTrue((self.root/'answer/source_context_groups.json').is_file())
        verify_qualified_question_source(answer, self.root)
        altered = deepcopy(answer)
        altered['projection_counts']['projected_edges'] += 1
        altered['answer_sha256'] = digest({k: v for k, v in altered.items() if k != 'answer_sha256'})
        with self.assertRaisesRegex(ValueError, 'differs'):
            verify_qualified_question_source(altered, self.root)

    def test_resealed_wrong_citation_revision_fails_group_binding(self):
        answer = self.question()
        answer['citations'][0]['object'] = 'http://www.wikipathways.org/instance/WP1_r999'
        answer['answer_sha256'] = digest({k: v for k, v in answer.items() if k != 'answer_sha256'})
        with self.assertRaisesRegex(ValueError, 'source group'):
            verify_answer(answer)

    def test_changed_materialized_graph_fails_retained_replay(self):
        graph = json.loads((self.out/'graph.json').read_text())
        graph['edges'].pop()
        write_json(self.out/'graph.json', graph)
        with self.assertRaisesRegex(ValueError, 'does not replay'):
            load_workspace(self.out)

    def test_missing_marker_cannot_rebuild_unfiltered_snapshot(self):
        (self.out/'qualified_workspace.json').unlink()
        with self.assertRaises((ValueError, OSError)):
            read_run(self.out)

    def test_missing_all_top_level_markers_and_graph_cannot_drop_retained_source(self):
        for name in ('qualified_workspace.json', 'run_manifest.json', 'graph.json'):
            (self.out/name).unlink()
        with self.assertRaises((ValueError, OSError)):
            read_run(self.out)

    def test_qualified_view_cannot_be_reviewed_into_unfiltered_graph(self):
        with self.assertRaisesRegex(ValueError, 'read-only'):
            review_run(self.out, self.root/'reviewed', self.graph['assertions'][0]['id'],
                'accepted', 'Invented reviewer', 'Invented reason')


if __name__ == '__main__':
    unittest.main()
