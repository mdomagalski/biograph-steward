"""Invented source data: artifact replay, CLI and protected browser workflow."""
from contextlib import redirect_stdout
from html import escape
from io import StringIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from biograph_steward.__main__ import main
from biograph_steward.client import digest, write_json
from biograph_steward.crc_pilot import sha
from biograph_steward.literature import collect_literature
from biograph_steward.source_fact_workflow import (build_source_facts, load_fact_artifact,
    save_fact_check, render_comparison)
from biograph_steward.fact_comparison import compare_claim
from biograph_steward.source_facts import compile_source
from biograph_steward.webapp import create_server, login_return_path

CLAIM = 'Sotorasib monotherapy had a reported response rate of 31.5% in evaluable patients.'
TOKEN = 'invented-token-for-source-fact-tests'


def fixture(root):
    xml = ('<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>90000123</PMID><Article>'
           '<ArticleTitle>INVENTED &lt;script&gt; title</ArticleTitle><Abstract>'
           '<AbstractText Label="METHODS">Patients with mutant KRAS G13D received sotorasib monotherapy '
           'or sotorasib in combination with panitumumab.</AbstractText>'
           '<AbstractText Label="RESULTS">Évaluation. In the monotherapy group (18 evaluable patients), '
           'a response was reported in 31.5% of patients. In the combination-therapy group '
           '(12 evaluable patients), the response was 67% of patients.</AbstractText>'
           '</Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>').encode()
    literature = root / 'literature'
    collect_literature(['90000123'], literature, transport=lambda _: xml)
    facts = root / 'facts'
    build_source_facts(literature, '90000123', facts)
    return literature, facts


def reseal(folder):
    manifest = json.loads((folder / 'source_fact_manifest.json').read_text())
    manifest['files'] = {name: sha(folder / name) for name in manifest['files']}
    manifest['artifact_sha256'] = digest({k: v for k, v in manifest.items() if k != 'artifact_sha256'})
    write_json(folder / 'source_fact_manifest.json', manifest)


class SourceFactWorkflowTests(unittest.TestCase):
    def test_cli_round_trip_preserves_input_and_refuses_output_reuse(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); literature, _ = fixture(root)
            before = {p.name: sha(p) for p in literature.iterdir()}
            facts = root / 'cli_facts'; check = root / 'cli_check'
            commands = [
                ['source-facts', '--literature', str(literature), '--pmid', '90000123', '--out', str(facts)],
                ['fact-check', '--facts', str(facts), '--claim', CLAIM.replace('31.5', '67'), '--out', str(check)],
                ['source-facts-verify', '--result', str(facts)],
                ['source-facts-verify', '--result', str(check)]]
            for command in commands:
                with redirect_stdout(StringIO()) as output:
                    self.assertEqual(main(command), 0)
                self.assertIsInstance(json.loads(output.getvalue()), dict)
            self.assertEqual(before, {p.name: sha(p) for p in literature.iterdir()})
            manifest, payload = load_fact_artifact(check)
            self.assertEqual(payload['comparison']['status'], 'review_report_difference')
            self.assertFalse(payload['comparison']['auto_approval']); self.assertEqual(manifest['model_requests'], 0)
            with self.assertRaises(ValueError): save_fact_check(facts, CLAIM, check)
            for claim in [None, 23, '', ' ' * 3, 'a' * 4001]:
                with self.assertRaises(ValueError): save_fact_check(facts, claim, root / 'invalid')
            self.assertFalse((root / 'invalid').exists())
            with self.assertRaises(ValueError): build_source_facts(literature, '888', root / 'missing')

    def test_rehashed_semantic_tampering_and_rehashed_report_tampering_fail_replay(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); _, facts = fixture(root)
            check = root / 'check'; save_fact_check(facts, CLAIM, check)
            path = facts / 'source_facts.json'; original = path.read_bytes()
            value = json.loads(original); value['records'][0]['value'] = '67'
            write_json(path, value); reseal(facts)
            with self.assertRaisesRegex(ValueError, 'replay|binding'): load_fact_artifact(facts)
            path.write_bytes(original); reseal(facts); load_fact_artifact(facts)
            # A comparison replays its embedded dossier even without the original directory.
            facts.rename(root / 'moved_facts'); load_fact_artifact(check)
            path = check / 'comparison.json'; value = json.loads(path.read_text())
            value['comparison']['status'] = 'review_report_difference'; write_json(path, value); reseal(check)
            with self.assertRaisesRegex(ValueError, 'comparison replay'): load_fact_artifact(check)
            other = root / 'other'; save_fact_check(root / 'moved_facts', CLAIM, other)
            (other / 'report.html').write_text('<script>fake approval</script>'); reseal(other)
            with self.assertRaisesRegex(ValueError, 'report replay'): load_fact_artifact(other)

    def test_embedded_dossier_cannot_retain_an_unrelated_parent_artifact_fingerprint(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); _, facts = fixture(root)
            check = root / 'check'; save_fact_check(facts, CLAIM, check)
            path = check / 'comparison.json'; value = json.loads(path.read_text())
            source = value['dossier']['paper']; source['title'] = 'A DIFFERENT INVENTED SOURCE'
            value['dossier'] = compile_source(source)
            value['comparison'] = compare_claim(CLAIM, value['dossier'])
            write_json(path, value)
            (check / 'report.html').write_text(render_comparison(value)); reseal(check)
            with self.assertRaisesRegex(ValueError, 'Embedded source-fact artifact binding'): load_fact_artifact(check)

    def test_source_and_claim_text_are_escaped_and_symlink_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); _, facts = fixture(root)
            html = (facts / 'report.html').read_text()
            self.assertIn('INVENTED &lt;script&gt; title', html)
            self.assertNotIn('INVENTED <script> title', html)
            claim = '</blockquote><script>alert(1)</script>'
            check = root / 'check'; save_fact_check(facts, claim, check)
            html = (check / 'report.html').read_text()
            self.assertIn(escape(claim), html); self.assertNotIn(claim, html)
            link = root / 'link'; link.symlink_to(facts, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'): load_fact_artifact(link)
            target = facts / 'source_facts.json'; target.rename(root / 'payload')
            target.symlink_to(root / 'payload')
            with self.assertRaisesRegex(ValueError, 'bytes'): load_fact_artifact(facts)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class SourceFactHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); _, self.facts = fixture(self.root)
        self.server = create_server(0, self.root, access_token=TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.auth = {'Authorization': 'Bearer ' + TOKEN}

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def request(self, path, *, body=None, headers=None, raw=None):
        data = json.dumps(body).encode() if body is not None else raw
        headers = {**({'Content-Type': 'application/json'} if body is not None else {}), **(headers or {})}
        try:
            response = build_opener(ProxyHandler({}), NoRedirect()).open(
                Request(self.base + path, data=data, headers=headers), timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            return response.code, response.headers, response.read()

    def test_protected_deep_link_login_and_cookie_origin_check_then_saved_comparison(self):
        route = '/api/source-facts/facts/'
        self.assertEqual(self.request('/api/source-facts')[0], 401)
        code, _, body = self.request(route, headers={'Accept': 'text/html'})
        self.assertEqual(code, 200); self.assertIn(('value="' + route + '"').encode(), body)
        code, headers, _ = self.request('/auth/login', raw=urlencode({'token': TOKEN, 'return_to': route}).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded', 'Origin': self.base})
        self.assertEqual(code, 303); self.assertEqual(headers['Location'], route)
        cookie = {'Cookie': headers['Set-Cookie'].split(';')[0]}
        code, _, body = self.request(route, headers=cookie)
        self.assertEqual(code, 200); self.assertIn(b'Check and save for review', body)
        for origin in [None, 'https://evil.example.org']:
            code, _, _ = self.request('/api/fact-check', body={'facts_id': 'facts', 'claim': CLAIM},
                headers={**cookie, **({'Origin': origin} if origin else {})})
            self.assertEqual(code, 403)
        before = set(self.root.iterdir())
        code, _, body = self.request('/api/fact-check', body={'facts_id': 'facts', 'claim': CLAIM},
            headers={**cookie, 'Origin': self.base})
        self.assertEqual(code, 200); data = json.loads(body)
        self.assertEqual(data['status'], 'limited_context_compatible')
        self.assertEqual(len(set(self.root.iterdir()) - before), 1)
        code, _, page = self.request(data['report_url'], headers=cookie)
        self.assertEqual(code, 200); self.assertIn(b'Every outcome requests review', page)
        self.assertEqual(login_return_path(data['report_url']), data['report_url'])
        self.assertEqual(login_return_path(data['report_url'] + 'comparison.json'), '/')
        _, payload = load_fact_artifact(self.root / data['check_id'])
        self.assertEqual(payload['comparison']['graph_mutations'], 0)

    def test_tampered_reports_withheld_and_browser_cannot_select_paths_or_other_kinds(self):
        code, _, data = self.request('/api/source-facts', headers=self.auth)
        self.assertEqual(code, 200); self.assertEqual(len(json.loads(data)['reports']), 1)
        before = set(self.root.iterdir())
        for body in [{'facts_id': '../facts', 'claim': CLAIM}, {'facts_id': 'facts', 'claim': CLAIM, 'out': '/tmp/x'},
                     {'facts_id': 'facts', 'claim': 2}]:
            self.assertEqual(self.request('/api/fact-check', body=body, headers=self.auth)[0], 400)
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertEqual(self.request('/api/fact-check/facts/', headers=self.auth)[0], 404)
        self.assertEqual(self.request('/api/source-facts/facts/comparison.json', headers=self.auth)[0], 404)
        (self.facts / 'report.html').write_text('altered')
        code, _, data = self.request('/api/source-facts', headers=self.auth)
        self.assertEqual(code, 200); data = json.loads(data)
        self.assertEqual(data['reports'], []); self.assertEqual(data['invalid_reports_withheld'], 1)
        self.assertEqual(self.request('/api/source-facts/facts/', headers=self.auth)[0], 400)
        self.assertEqual(self.request('/api/download/facts', headers=self.auth)[0], 400)
        self.assertEqual(self.request('/api/fact-check', body={'facts_id': 'facts', 'claim': CLAIM}, headers=self.auth)[0], 400)
        self.assertEqual(set(self.root.iterdir()), before)


if __name__ == '__main__':
    unittest.main()
