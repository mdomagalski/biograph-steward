"""Saved comparison persistence, protected HTTP access and replayable carryover."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from zipfile import ZipFile

from biograph_steward.__main__ import main
from biograph_steward.client import digest
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import build_graph, save_run
from biograph_steward.reviews import review_run
from biograph_steward.refresh_workflow import verify_refresh
from biograph_steward.webapp import create_server, login_return_path


class RefreshHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        snapshot = demo_snapshot()
        snapshot['targets'] = snapshot['targets'][:6]
        snapshot['query_settings']['max_targets'] = 6
        snapshot['retrieval'].update(total_targets_reported=6, records_retrieved=6)
        snapshot.pop('content_sha256'); snapshot['content_sha256'] = digest(snapshot)
        graph = save_run(snapshot, self.root/'initial')
        self.aid = next(a['id'] for a in graph['assertions'] if a['kind'] == 'disease_association'
                        and a['structurally_usable_evidence_ids'])
        review_run(self.root/'initial', self.root/'before', self.aid, 'accepted',
                   'Synthetic QA', 'Invented software example only')
        newer = deepcopy(snapshot); newer['created_at'] = '2030-01-01T00:00:00+00:00'
        newer.pop('content_sha256'); newer['content_sha256'] = digest(newer)
        save_run(newer, self.root/'after')
        self.server = create_server(0, self.root, access_token='synthetic-refresh-token-for-tests')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()

    def request(self, path, body=None, auth=True, **headers):
        if auth: headers['Authorization'] = 'Bearer synthetic-refresh-token-for-tests'
        if body is not None: headers['Content-Type'] = 'application/json'
        return build_opener(ProxyHandler({})).open(Request(self.url+path,
                    data=json.dumps(body).encode() if body is not None else None, headers=headers))

    def compare(self, **changes):
        body = {'before_run':'before', 'after_run':'after', 'carry_reviews':True, **changes}
        with self.request('/api/refresh-compare', body) as response: return json.loads(response.read())

    def test_http_carryover_report_download_and_originals_unchanged(self):
        original = {str(p.relative_to(self.root)):p.read_bytes()
                    for folder in ['before','after'] for p in (self.root/folder).rglob('*') if p.is_file()}
        result = self.compare(); run = self.root/result['run_id']
        assertion = next(a for a in result['graph']['assertions'] if a['id'] == self.aid)
        self.assertEqual(assertion['lifecycle_state'], 'accepted')
        self.assertTrue(assertion['review_history'])
        with self.request(result['report_url']) as response:
            self.assertIn('text/html', response.headers['Content-Type']); self.assertIn(b'comparison', response.read().lower())
        for name in ['graph.json','review_events.json','refresh_comparison.json',
                     'refresh_inputs/before/graph.json','refresh_inputs/after/graph.json']:
            with self.request(result['report_url']+name) as response:
                self.assertEqual(response.status,200);json.loads(response.read())
        with self.request('/api/refresh/'+result['run_id']+'/comparison.json') as response:
            self.assertEqual(json.loads(response.read()), result['comparison'])
        with self.request(result['download_url']) as response:
            names = ZipFile(BytesIO(response.read())).namelist()
            self.assertTrue(any(n.endswith('refresh_inputs/before/snapshot.json') for n in names))
            self.assertTrue(any(n.endswith('refresh_receipt.json') for n in names))
        with self.request('/api/run/'+result['run_id']) as response:
            self.assertEqual(json.loads(response.read())['graph'], result['graph'])
        self.assertEqual(original, {name:(self.root/name).read_bytes() for name in original})
        self.assertTrue((run/'refresh_comparison.json').exists())

    def test_no_carryover_is_default_and_cli_packet_replays_after_parents_move(self):
        result = self.compare(carry_reviews=False)
        self.assertEqual(next(a for a in result['graph']['assertions'] if a['id']==self.aid)['lifecycle_state'], 'candidate')
        with redirect_stdout(StringIO()):
            self.assertEqual(main(['refresh-compare','--before',str(self.root/'before'),
                                   '--after',str(self.root/'after'),'--carry-reviews','--out',str(self.root/'cli')]),0)
            (self.root/'before').rename(self.root/'moved-before'); (self.root/'after').rename(self.root/'moved-after')
            self.assertEqual(main(['refresh-verify','--run',str(self.root/'cli')]),0)

    def test_auth_scope_input_types_and_external_parent_symlink_rejected(self):
        for path in ['/api/refresh-runs','/api/refresh-history','/api/refresh/missing/',
                     '/api/refresh-archive/'+'0'*64+'/']:
            with self.assertRaises(HTTPError) as ctx: self.request(path,auth=False)
            self.assertEqual(ctx.exception.code,401)
        with self.assertRaises(HTTPError) as ctx:
            self.request('/api/refresh-compare',{'before_run':'before','after_run':'after','carry_reviews':False},auth=False)
        self.assertEqual(ctx.exception.code,401)
        for changes in [{'before_run':'../before'},{'after_run':'missing'},{'carry_reviews':'yes'},
                        {'carry_reviews':1},{'arbitrary_policy':'relaxed'}]:
            with self.assertRaises(HTTPError) as ctx: self.compare(**changes)
            self.assertEqual(ctx.exception.code,400)
        with tempfile.TemporaryDirectory() as outside:
            (self.root/'external').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(HTTPError) as ctx: self.compare(before_run='external')
            self.assertEqual(ctx.exception.code,400)
        self.assertEqual(login_return_path('/api/refresh/example/'),'/api/refresh/example/')
        archive_path = '/api/refresh-archive/'+'a'*64+'/'
        self.assertEqual(login_return_path(archive_path), archive_path)
        self.assertEqual(login_return_path('https://example.com/api/refresh/example/'),'/')

    def test_corrupted_comparison_rejected_on_report_graph_and_download(self):
        result=self.compare(); folder=self.root/result['run_id']
        (folder/'refresh_comparison.json').write_text('{}')
        for path in [result['report_url'],result['download_url'],'/api/run/'+result['run_id']]:
            with self.assertRaises(HTTPError) as ctx: self.request(path)
            self.assertEqual(ctx.exception.code,400)

    def test_archive_remains_readable_after_runtime_change_but_replay_stays_blocked(self):
        result = self.compare(); folder = self.root/result['run_id']
        receipt = verify_refresh(folder)
        original = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        changed = {**receipt['code_hashes'], 'civic_context': '0'*64}
        with patch('biograph_steward.refresh_workflow._code_hashes', return_value=changed):
            with self.request('/api/refresh-history') as response:
                item = json.loads(response.read())['comparisons'][0]
            self.assertEqual(item['integrity'], 'passed')
            self.assertFalse(item['runtime_compatible'])
            self.assertEqual(item['current_replay'], 'not_performed')
            self.assertNotIn('replay_report_url', item)
            for path in [result['report_url'], result['download_url'], '/api/run/'+result['run_id']]:
                with self.assertRaises(HTTPError) as error: self.request(path)
                self.assertEqual(error.exception.code, 409)
                payload = json.loads(error.exception.read())
                self.assertEqual(payload['error_code'], 'refresh_runtime_mismatch')
                self.assertEqual(payload['archive_url'], item['report_url'])
            with self.request(item['report_url']) as response:
                text = response.read().decode()
                self.assertIn('Read-only comparison archive', text)
                self.assertIn('Current implementation differs', text)
                self.assertIn("default-src 'none'", response.headers['Content-Security-Policy'])
            for name in ['graph.json', 'review_events.json', 'refresh_comparison.json',
                         'refresh_inputs/before/graph.json', 'refresh_inputs/after/graph.json']:
                with self.request(item['report_url']+name) as response:
                    self.assertEqual(response.read(), original[name])
            self.assertEqual(original, {p.relative_to(folder).as_posix(): p.read_bytes()
                                       for p in folder.rglob('*') if p.is_file()})
            (folder/'refresh_report.html').write_text('changed')
            with self.request('/api/refresh-history') as response:
                invalid = json.loads(response.read())['comparisons'][0]
            self.assertEqual(invalid['integrity'], 'failed')
            self.assertNotIn('report_url', invalid)
            with self.assertRaises(HTTPError) as error: self.request(item['report_url'])
            self.assertEqual(error.exception.code, 400)

    def test_nested_archive_discovery_is_bounded_and_skips_symlinks(self):
        result = self.compare(); folder = self.root/result['run_id']
        nested = self.root/'live_collection'/'returned'/'comparison'
        nested.parent.mkdir(parents=True)
        folder.rename(nested)
        (self.root/'alias').symlink_to(nested, target_is_directory=True)
        with self.request('/api/refresh-history') as response:
            items = json.loads(response.read())['comparisons']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['name'], 'live_collection/returned/comparison')
        self.assertNotIn('run_id', items[0])
        with self.request(items[0]['report_url']) as response:
            self.assertEqual(response.status, 200)
        too_deep = self.root/'one'/'two'/'three'/'four'
        too_deep.parent.mkdir(parents=True)
        nested.rename(too_deep)
        with self.request('/api/refresh-history') as response:
            self.assertEqual(json.loads(response.read())['comparisons'], [])
        with self.assertRaises(HTTPError) as error: self.request(items[0]['report_url'])
        self.assertEqual(error.exception.code, 404)

    def test_workspace_list_skips_non_workbench_and_malformed_manifests(self):
        (self.root/'invalid').mkdir();(self.root/'invalid/run_manifest.json').write_text('[]')
        bad = self.root/'nonfinite';bad.mkdir()
        (bad/'snapshot.json').write_text('{}')
        (bad/'run_manifest.json').write_text('{"data_kind":"live_pharos","graph_format":"v3","review_event_count":NaN}')
        with self.request('/api/refresh-runs') as response:
            data=json.loads(response.read())
        self.assertTrue({'before','after'} <= {r['run_id'] for r in data['runs']})
        self.assertNotIn('invalid',{r['run_id'] for r in data['runs']})
        self.assertNotIn('nonfinite',{r['run_id'] for r in data['runs']})

    def test_missing_receipt_cannot_bypass_verification_or_be_reused(self):
        result=self.compare();folder=self.root/result['run_id']
        (folder/'refresh_receipt.json').unlink()
        for path in [result['report_url'],result['download_url'],'/api/run/'+result['run_id']]:
            with self.assertRaises(HTTPError) as ctx:self.request(path)
            self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError) as ctx:self.compare(before_run=result['run_id'])
        self.assertEqual(ctx.exception.code,400)
        with self.request('/api/refresh-runs') as response:
            self.assertNotIn(result['run_id'],{r['run_id'] for r in json.loads(response.read())['runs']})


if __name__ == '__main__': unittest.main()
