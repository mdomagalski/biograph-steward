"""Model-selected construction provenance survives the source-preserving handoff.

All source and model responses below are invented, not live evaluations.
"""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.__main__ import main
from biograph_steward.assay_attachment import attach_assay
from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.construction import construct_snapshot, publish_construction
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.graph import save_run
from biograph_steward.reviews import read_run, review_run, preserve_construction_plan
from test_assay_attachment import make_publication
from test_construction_planning import planner, proposal, scope
from test_pharos_inventory import InventoryAPI


def read(path):
    return json.loads(Path(path).read_text())


class GoldConstructionTraceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.ids = ['P04637', 'P00533', 'P01111']
        self.trace = planner(proposal(accessions=self.ids)).plan(scope(accessions=self.ids))
        api = InventoryAPI()
        api.identities['P01111'] = {**deepcopy(api.identities['P00533']), 'uniprot': 'P01111',
                                    'name': 'Invented fixture protein P01111'}
        api.context['P01111'] = deepcopy(api.context['P00533'])
        self.snapshot = construct_snapshot(PharosClient(transport=api),
                                          self.trace['construction_request'], data_kind='live_pharos')
        self.source = self.root / 'planned'
        publish_construction(self.snapshot, self.source, planning_trace=self.trace)

    def test_planner_trace_is_preserved_in_publication_and_offline_packet(self):
        raw = (self.source / 'construction_planner_trace.json').read_bytes()
        packet = self.source / 'gold_packet'
        manifest, graph = load_packet(packet)
        self.assertIn('construction_planner_trace.json', manifest['input_files'])
        self.assertEqual((packet / 'source/construction_planner_trace.json').read_bytes(), raw)
        self.assertEqual(graph['construction']['request'], self.trace['construction_request'])

    def test_attached_reviewed_and_replayed_runs_preserve_trace_bytes(self):
        publication, attached, reviewed, replay = [self.root / name for name in
            ('publication', 'attached', 'reviewed', 'replay')]
        make_publication(publication)
        graph = attach_assay(self.source, publication, attached)
        assertion = next(a for a in graph['assertions'] if a['kind'] == 'assay_observation')
        reviewed_graph = review_run(attached, reviewed, assertion['id'], 'provisional', 'Fixture reviewer', 'Inspect context')
        # Mirrors the reusable propagation hook invoked by CLI replay after save_run.
        from biograph_steward.reviews import read_assay
        save_run(self.snapshot, replay, review_events=reviewed_graph['review_events'],
                 assay_attachment=read_assay(reviewed), assay_source=reviewed / 'assay_source')
        preserve_construction_plan(reviewed, replay)
        original = (self.source / 'construction_planner_trace.json').read_bytes()
        for index, folder in enumerate((attached, reviewed, replay)):
            with self.subTest(folder=folder.name):
                self.assertEqual((folder / 'construction_planner_trace.json').read_bytes(), original)
                self.assertEqual(read(folder / 'run_manifest.json')['construction_planner_trace_sha256'], digest(self.trace))
                self.assertEqual(read_run(folder)[2]['construction']['request'], self.trace['construction_request'])
                packet = self.root / ('packet_' + str(index))
                export_packet(folder, packet)
                self.assertEqual((packet / 'source/construction_planner_trace.json').read_bytes(), original)

    def test_missing_marked_trace_and_valid_but_mismatched_plan_rejected(self):
        replay = self.root / 'replay'
        save_run(self.snapshot, replay)
        preserve_construction_plan(self.source, replay)
        path = replay / 'construction_planner_trace.json'
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            read_run(replay)
        with self.assertRaisesRegex(ValueError, 'missing'):
            export_packet(replay, self.root / 'missing_packet')
        other = planner(proposal(accessions=['P04637'])).plan(scope(accessions=self.ids))
        write_json(path, other)
        manifest = read(replay / 'run_manifest.json')
        manifest['construction_planner_trace_sha256'] = digest(other)
        write_json(replay / 'run_manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'source request'):
            read_run(replay)
        with self.assertRaisesRegex(ValueError, 'source request'):
            export_packet(replay, self.root / 'mismatched_packet')

    def test_cli_replay_rejects_missing_or_corrupt_trace_before_publishing(self):
        path = self.source / 'construction_planner_trace.json'
        original = path.read_bytes()
        for index, content in enumerate((None, b'{}')):
            with self.subTest(content=content):
                if content is None:
                    path.unlink()
                else:
                    path.write_bytes(content)
                output = self.root / ('invalid_replay_' + str(index))
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    code = main(['replay', '--snapshot', str(self.source / 'snapshot.json'), '--out', str(output)])
                self.assertEqual(code, 1)
                self.assertFalse(output.exists())
                path.write_bytes(original)

    def test_cli_staged_failure_never_leaves_unmarked_replay(self):
        output = self.root / 'failed_replay'
        with patch('biograph_steward.reviews.preserve_construction_plan', side_effect=ValueError('Fixture source race')):
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = main(['replay', '--snapshot', str(self.source / 'snapshot.json'), '--out', str(output)])
        self.assertEqual(code, 1)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob('.planned-replay-*')), [])

    def test_planned_review_failure_never_leaves_unmarked_output(self):
        graph = read_run(self.source)[2]
        assertion = graph['assertions'][0]
        output = self.root / 'failed_review'
        with patch('biograph_steward.reviews.preserve_construction_plan', side_effect=ValueError('Fixture source race')):
            with self.assertRaisesRegex(ValueError, 'Fixture source race'):
                review_run(self.source, output, assertion['id'], 'provisional', 'Fixture reviewer', 'Source inspection')
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob('.planned-review-*')), [])

    def test_cli_moved_snapshot_uses_attached_runs_planner_trace(self):
        publication, attached, output = [self.root / name for name in ('publication', 'attached', 'moved_replay')]
        make_publication(publication)
        attach_assay(self.source, publication, attached)
        moved = self.root / 'copied_snapshot.json'
        moved.write_bytes((attached / 'snapshot.json').read_bytes())
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            code = main(['replay', '--snapshot', str(moved), '--assay-run', str(attached), '--out', str(output)])
        self.assertEqual(code, 0)
        self.assertEqual((output / 'construction_planner_trace.json').read_bytes(),
                         (self.source / 'construction_planner_trace.json').read_bytes())
        read_run(output)


if __name__ == '__main__':
    unittest.main()
