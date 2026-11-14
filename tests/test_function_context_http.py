"""Read-only contexts require explicit registration, authentication and exact bytes."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.function_context import FORMAT, digest, sha
from biograph_steward.webapp import _function_context_sources, create_server, report_html
from test_function_context import example
import test_function_context as context_fixtures


class FunctionContextHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'saved_model'
        (self.folder / 'queries').mkdir(parents=True)
        self.query = self.folder / 'queries/P00533.json'
        self.query.write_text(json.dumps(example()))
        self.manifest = {'format': FORMAT, 'publication_id': 'demo',
            'source_graph_modified': False, 'future_reference_labels_included': False,
            'downloads': {'example': 'queries/P00533.json'},
            'query_files': {'UniProtKB:P00533': 'queries/P00533.json'},
            'files': {'queries/P00533.json': {'sha256': sha(self.query), 'bytes': self.query.stat().st_size}}}
        self.manifest['content_sha256'] = digest(self.manifest)
        (self.folder / 'publication.json').write_text(json.dumps(self.manifest))
        self.index = {'format': 'biograph-steward.function-context-index.v1', 'publications': [
            {'id': 'saved_model', 'manifest_sha256': sha(self.folder / 'publication.json')}]}
        self.index_path = self.root / 'function_context_index.json'
        self.index_path.write_text(json.dumps(self.index))
        self.before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.server = create_server(0, self.root, access_token='invented-function-context-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def get(self, path, auth=True):
        headers = {'Authorization': 'Bearer invented-function-context-token'} if auth else {}
        return self.opener.open(Request(self.url + path, headers=headers))

    def error(self, path, status=400, **kwargs):
        with self.assertRaises(HTTPError) as caught:
            self.get(path, **kwargs)
        self.assertEqual(caught.exception.code, status)
        caught.exception.close()

    def test_registered_context_is_authenticated_exact_and_read_only(self):
        self.error('/api/function-contexts', 401, auth=False)
        with self.get('/api/function-contexts') as response:
            catalogue = json.loads(response.read())['contexts']
        self.assertEqual(catalogue[0]['id'], 'saved_model')
        self.assertEqual(catalogue[0]['proteins'][0]['id'], 'UniProtKB:P00533')
        self.assertNotIn(str(self.root), json.dumps(catalogue))
        with self.get('/api/function-context/saved_model/query/P00533') as response:
            value = json.loads(response.read())
        self.assertEqual(value['answer'], example())
        self.assertEqual(value['manifest_sha256'], self.index['publications'][0]['manifest_sha256'])
        with self.get('/api/function-context/saved_model/download/example') as response:
            self.assertEqual(response.read(), self.query.read_bytes())
            self.assertIn('attachment;', response.headers['Content-Disposition'])
        self.assertEqual(self.before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_no_discovery_outside_declared_source_or_query(self):
        self.error('/api/function-context/unregistered/query/P00533', 404)
        self.error('/api/function-context/saved_model/query/P01116')
        self.error('/api/function-context/saved_model/download/private_file')
        self.error('/api/function-context/saved_model/query/P00533?fit=true')
        self.error('/api/function-contexts?discover=true')
        self.index_path.unlink()
        with self.get('/api/function-contexts') as response:
            self.assertEqual(json.loads(response.read()), {'contexts': []})

    def test_changed_manifest_or_payload_fails_closed(self):
        self.query.write_text(self.query.read_text() + ' ')
        self.error('/api/function-contexts')
        self.error('/api/function-context/saved_model/query/P00533')
        self.query.write_bytes(self.before[Path('saved_model/queries/P00533.json')])
        manifest = self.folder / 'publication.json'
        manifest.write_text(manifest.read_text() + ' ')
        self.error('/api/function-contexts')

    def test_index_rejects_paths_duplicates_and_symlinks(self):
        row = self.index['publications'][0]
        for rows in ([{**row, 'id': '../saved_model'}], [row, row], [{**row, 'manifest_sha256': 'bad'}]):
            self.index_path.write_text(json.dumps({**self.index, 'publications': rows}))
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                _function_context_sources(self.root)
        self.index_path.write_text(json.dumps(self.index))
        self.folder.rename(self.root / 'actual')
        self.folder.symlink_to(self.root / 'actual', target_is_directory=True)
        self.error('/api/function-contexts')

    def test_optional_overlap_is_bound_to_exact_forecast_and_downloaded_separately(self):
        fixture = context_fixtures.DisplayNotesTests()
        fixture.fixture()
        self.manifest['input_source_pins'] = fixture.manifest['input_source_pins']
        self.manifest['source_versions'] = fixture.manifest['source_versions']
        self.manifest.pop('content_sha256')
        self.manifest['content_sha256'] = digest(self.manifest)
        manifest_path = self.folder / 'publication.json'
        manifest_path.write_text(json.dumps(self.manifest))
        report = fixture.report
        report['publication_manifest_sha256'] = sha(manifest_path)
        report['publication_content_sha256'] = self.manifest['content_sha256']
        report['content_sha256'] = digest(report)
        notes_folder = self.root / 'saved_notes'
        notes_folder.mkdir()
        notes_path = notes_folder / 'notes.json'
        notes_path.write_text(json.dumps(report))
        self.index['publications'][0].update(manifest_sha256=sha(manifest_path),
            display_notes={'id': 'saved_notes', 'file_sha256': sha(notes_path)})
        self.index_path.write_text(json.dumps(self.index))
        with self.get('/api/function-context/saved_model/query/P00533') as response:
            value = json.loads(response.read())
        self.assertEqual(value['answer'], example())
        self.assertFalse(value['display_notes']['forecast_modified'])
        self.assertEqual(value['display_notes']['queries']['UniProtKB:P00533'][0]['july2026_goa']
                         ['positive_matches'][0]['product_form'], 'UniProtKB:P00533-1')
        with self.get('/api/function-context/saved_model/download/annotation_overlap') as response:
            self.assertEqual(response.read(), notes_path.read_bytes())
        notes_path.write_text(notes_path.read_text() + ' ')
        self.error('/api/function-context/saved_model/query/P00533')
        self.error('/api/function-context/saved_model/download/annotation_overlap')
        with self.get('/api/function-context/saved_model/download/example') as response:
            self.assertEqual(response.read(), self.query.read_bytes())

    def test_generated_app_includes_inspector_without_new_top_level_navigation(self):
        html = report_html()
        self.assertIn('id="functionContextPanel"', html)
        self.assertIn('initializeFunctionContexts();', html)
        self.assertIn('Trace a historical function prediction', html)
        self.assertNotIn('data-workspace="function', html)


if __name__ == '__main__':
    unittest.main()
