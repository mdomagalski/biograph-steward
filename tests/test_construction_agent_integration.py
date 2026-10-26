"""Plan-to-publication and authenticated handoff using invented API responses."""
from contextlib import redirect_stdout, redirect_stderr
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from zipfile import ZipFile

from biograph_steward.__main__ import main
from biograph_steward.client import PharosClient, digest
from biograph_steward.construction import run_planned_construction, verify_construction_run
from biograph_steward.construction_planning import save_construction_plan
from biograph_steward.gold_packet import load_packet
from biograph_steward.reviews import read_run
from test_construction_planning import scope, proposal, abstention, planner
import test_construction_http as http_fixtures
from test_pharos_inventory import InventoryAPI


def two_protein_plan(output=None):
    ids = ['P04637', 'P00533']
    return planner(output or proposal(accessions=ids)).plan(scope(accessions=ids))


class ConstructionAgentPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.api = InventoryAPI()
        self.client = PharosClient(transport=self.api)

    def test_plan_and_graph_remain_bound_in_publication_and_packet(self):
        trace = two_protein_plan()
        result = run_planned_construction(self.client, trace, self.root / 'published')
        receipt = verify_construction_run(self.root / 'published')
        self.assertEqual(receipt['selection_mode'], 'validated_model_plan')
        self.assertFalse(receipt['llm_used'])  # injected test model is not live inference
        self.assertFalse(receipt['execution_llm_used'])
        self.assertEqual(receipt['planning_trace_sha256'], digest(trace))
        self.assertEqual(read_run(self.root / 'published')[2], result['graph'])
        packet = self.root / 'published/gold_packet'
        load_packet(packet)
        self.assertEqual(json.loads((packet / 'source/construction_planner_trace.json').read_text()), trace)
        trace_path = self.root / 'published/construction_planner_trace.json'
        original = trace_path.read_bytes()
        trace_path.write_text('{}')
        with self.assertRaises(ValueError):
            verify_construction_run(self.root / 'published')
        trace_path.write_bytes(original)
        trace_path.unlink()
        with self.assertRaises(ValueError):
            read_run(self.root / 'published')

    def test_abstention_and_existing_output_never_fetch(self):
        for trace in [two_protein_plan(abstention()), two_protein_plan()]:
            out = self.root / ('abstention' if trace['status'] == 'abstained' else 'occupied')
            if trace['status'] != 'abstained':
                out.mkdir()
            with self.assertRaises(ValueError):
                run_planned_construction(self.client, trace, out)
        self.assertEqual(self.api.calls, [])

    def test_cli_plan_execute_and_replay_preserve_selection_provenance(self):
        model = planner(proposal(accessions=['P04637', 'P00533']))
        out = self.root / 'plan'
        with patch('biograph_steward.construction_planning.configured_construction_planner', return_value=model), redirect_stdout(StringIO()):
            self.assertEqual(main(['construction-plan', '--question', 'Retrieve interaction candidates.',
                '--accessions', 'P04637', 'P00533', '--focus-uniprot', 'P04637', '--out', str(out)]), 0)
        with patch('biograph_steward.__main__.PharosClient', return_value=self.client), redirect_stdout(StringIO()):
            self.assertEqual(main(['construction-execute', '--plan', str(out / 'construction_planner_trace.json'),
                                  '--out', str(self.root / 'built')]), 0)
            self.assertEqual(main(['replay', '--snapshot', str(self.root / 'built/snapshot.json'),
                                  '--out', str(self.root / 'replayed')]), 0)
        read_run(self.root / 'replayed')
        self.assertEqual((out / 'construction_planner_trace.json').read_bytes(),
                         (self.root / 'replayed/construction_planner_trace.json').read_bytes())


class ConstructionAgentHttpTests(unittest.TestCase):
    setUp = http_fixtures.ConstructionHttpTests.setUp
    tearDown = http_fixtures.ConstructionHttpTests.tearDown
    request = http_fixtures.ConstructionHttpTests.request

    def plan(self, output=None):
        model = planner(output or proposal(accessions=['P04637', 'P00533']))
        with patch('biograph_steward.construction_planning.configured_construction_planner', return_value=model):
            with self.request('/api/construction-plan', scope(accessions=['P04637', 'P00533'])) as response:
                return json.loads(response.read())

    def test_plan_build_export_and_download(self):
        planned = self.plan()
        with self.request('/api/download/' + planned['plan_id']) as response:
            with ZipFile(BytesIO(response.read())) as archive:
                self.assertTrue(any(name.endswith('/construction_planner_trace.json') for name in archive.namelist()))
        with patch('biograph_steward.webapp.PharosClient', return_value=PharosClient(transport=self.api)):
            with self.request('/api/construct', {'mode': 'planned', 'plan_id': planned['plan_id']}) as response:
                built = json.loads(response.read())
        with self.request('/api/submission-export', {'run_id': built['run_id']}) as response:
            exported = json.loads(response.read())
        self.assertEqual(exported['report']['counts']['prune'], 0)
        self.assertEqual(exported['report']['counts']['abstain'], len(built['graph']['edges']))
        with self.request(exported['download_url']) as response:
            with ZipFile(BytesIO(response.read())) as archive:
                self.assertTrue(any(name.endswith('/retained_graph.json') for name in archive.namelist()))
                self.assertTrue(any(name.endswith('/source/construction_planner_trace.json') for name in archive.namelist()))

    def test_invalid_authorization_scope_override_and_abstention_do_not_fetch(self):
        with patch('biograph_steward.construction_planning.configured_construction_planner') as configured:
            with self.assertRaises(HTTPError) as error:
                self.request('/api/construction-plan', scope(), auth=False)
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
            with self.assertRaises(HTTPError) as error:
                self.request('/api/construction-plan', scope(accessions=['TP53']))
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
            configured.assert_not_called()
        planned = self.plan(abstention())
        for body in [
            {'mode': 'planned', 'plan_id': planned['plan_id']},
            {'mode': 'planned', 'plan_id': planned['plan_id'], 'accessions': ['P04637']},
            {'mode': 'planned', 'plan_id': '../outside'},
        ]:
            with self.assertRaises(HTTPError) as error:
                self.request('/api/construct', body)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        self.assertEqual(self.api.calls, [])

    def test_changed_saved_plan_fails_before_retrieval(self):
        planned = self.plan()
        path = self.root / planned['plan_id'] / 'construction_planner_trace.json'
        trace = json.loads(path.read_text())
        trace['construction_request']['accessions'] = ['P01116']
        path.write_text(json.dumps(trace))
        with self.assertRaises(HTTPError) as error:
            self.request('/api/construct', {'mode': 'planned', 'plan_id': planned['plan_id']})
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        self.assertEqual(self.api.calls, [])


if __name__ == '__main__':
    unittest.main()
