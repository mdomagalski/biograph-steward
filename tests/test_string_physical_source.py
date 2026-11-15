"""Invented native bulk files exercise identity, source semantics and replay."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import string_physical_source as physical
from biograph_steward.client import digest, write_json
from biograph_steward.evidence_extension import publish_extension, prepare_extension
from biograph_steward.file_utils import sha
from biograph_steward.graph import build_graph, save_run
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.inspection import inspect_selection
from biograph_steward.questions import answer_question, graph_basis, save_answer, verify_answer
from biograph_steward.reviews import read_run, review_run
from test_assay_attachment import cohort_snapshot


def source_fixture(folder, snapshot, *, reciprocal=False):
    folder.mkdir()
    ids = [r['uniprot'] for r in snapshot['targets']]
    sids = {a: '9606.ENSP' + str(i + 1).zfill(11) for i, a in enumerate(ids)}
    sequences = {a: 'M' + 'ACDEFG'[i] * 4 for i, a in enumerate(ids)}
    canonical = ''.join('>sp|' + a + '|INVENTED_' + a + ' OX=9606\n' + seq + '\n' for a, seq in sequences.items())
    if reciprocal:
        canonical += '>sp|P15056|OUTSIDE_SCOPE OX=9606\nMBBBB\n'
    rows = ['#string_protein_id\talias\tsource\n']
    rows += [sids[a] + '\t' + a + '\tUniProt_AC\n' for a in ids if a != 'P01116']
    if reciprocal:
        rows.append(sids['P00533'] + '\tP15056\tUniProt_AC\n')
    source = ''.join('>' + sids[a] + '\n' + (seq if a != 'P01112' else 'MQQQQ') + '\n' for a, seq in sequences.items())
    a, b, c, bad, missing, absent = ids
    links = 'protein1 protein2 combined_score\n'
    for x, y, score in [(a, b, 800), (a, c, 0), (a, bad, 999), (a, missing, 999)]:
        links += sids[x] + ' ' + sids[y] + ' ' + str(score) + '\n'
        links += sids[y] + ' ' + sids[x] + ' ' + str(score) + '\n'
    values = {'canonical': canonical, 'sequences': source, 'aliases': ''.join(rows), 'physical': links}
    files = {}
    for role, text in values.items():
        name = physical.NAMES[role]; raw = text.encode()
        path = folder / name
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith('.gz') else raw)
        files[role] = {'path': str(path), 'sha256': sha(path), 'url': 'https://example.org/invented/' + name}
    return {'release': '12.5', 'canonical_release': 'invented_reference_1', 'files': files}


class NativePhysicalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.snapshot = cohort_snapshot()
        self.publication = self.root / 'publication'
        self.sources = source_fixture(self.root / 'bulk', self.snapshot)

    def publish(self):
        physical.publish_sources(self.snapshot, self.sources, self.publication)
        return physical.load_publication(self.publication)

    def workspace(self):
        self.publish()
        source, target = self.root / 'original', self.root / 'physical'
        baseline = save_run(self.snapshot, source)
        graph = publish_extension(source, {'string_physical': self.publication}, target)
        return source, target, baseline, graph

    def test_complete_source_replay_keeps_zero_missing_and_identity_abstentions_distinct(self):
        manifest, projection, files = self.publish()
        self.assertEqual(projection['scope']['possible_unordered_pairs'], 15)
        self.assertEqual(projection['summary']['complete_human_source_scan']['source_rows'], 8)
        ledger = {tuple(r['products']): r for r in projection['pair_ledger']}
        key = lambda b: tuple(sorted(('UniProtKB:P04637', 'UniProtKB:' + b)))
        self.assertEqual(ledger[key('P00533')]['native_physical_score'], 800)
        self.assertEqual(ledger[key('P00533')]['physical_score_0_to_1'], .8)
        self.assertEqual(projection['summary']['score_scales']['native_physical_score'], 'integer_0_to_1000')
        self.assertEqual(ledger[key('P01111')]['native_physical_score'], 0.)
        self.assertEqual(ledger[key('P01111')]['state'], 'native_physical_association')
        self.assertEqual(ledger[key('P04626')]['state'], 'native_physical_pair_not_listed')
        self.assertIsNone(ledger[key('P04626')]['native_physical_score'])
        for accession, reason in [('P01112', 'full_sequence_mismatch'), ('P01116', 'missing_direct_UniProt_AC_alias')]:
            self.assertEqual(projection['mappings'][accession]['admission'], reason)
            self.assertEqual(ledger[key(accession)]['state'], 'identity_unavailable')
            self.assertIsNone(ledger[key(accession)]['native_physical_score'])
        self.assertIsNone(projection['summary']['selection_threshold'])
        self.assertTrue(all('source/' + n in files for n in physical.NAMES.values()))
        self.assertFalse(manifest['automatic_pruning'])

    def test_reciprocal_uniqueness_uses_full_canonical_reference_not_only_cohort(self):
        other = source_fixture(self.root / 'reciprocal', self.snapshot, reciprocal=True)
        physical.publish_sources(self.snapshot, other, self.publication)
        _, projection, _ = physical.load_publication(self.publication)
        self.assertEqual(projection['mappings']['P00533']['admission'], 'ambiguous_reciprocal_canonical_accessions')
        self.assertEqual(projection['summary']['canonical_reference_proteins'], 7)

    def test_exact_pins_immutability_and_raw_replay_reject_even_resealed_projection(self):
        self.publish()
        with self.assertRaises(ValueError): physical.publish_sources(self.snapshot, self.sources, self.publication)
        path = self.publication / 'projection.json'; projection = json.loads(path.read_text())
        projection['pair_ledger'][0]['native_physical_score'] = .999
        projection['content_sha256'] = digest({k:v for k,v in projection.items() if k != 'content_sha256'})
        write_json(path, projection)
        mpath = self.publication / 'publication.json'; manifest = json.loads(mpath.read_text())
        manifest['projection_sha256'] = projection['content_sha256']; manifest['files']['projection.json'] = sha(path)
        manifest['content_sha256'] = digest({k:v for k,v in manifest.items() if k != 'content_sha256'})
        write_json(mpath, manifest)
        with self.assertRaisesRegex(ValueError, 'complete source replay'): physical.load_publication(self.publication)

    def test_incomplete_manifests_fail_before_publishing_or_retrieving(self):
        for sources in (None, {}, {**self.sources, 'canonical_release': None},
                {**self.sources, 'files': {**self.sources['files'], 'physical': {'path': 'missing'}}}):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                physical.publish_sources(self.snapshot, sources, self.publication)
        self.assertFalse(self.publication.exists())

    def test_source_byte_change_invalidates_integrity_and_content_cache(self):
        self.publish()
        path = self.publication / 'source' / physical.NAMES['physical']
        path.write_bytes(gzip.compress(b'protein1 protein2 combined_score\ninvalid\n', mtime=0))
        with self.assertRaises(ValueError): physical.load_publication(self.publication)

    def test_native_physical_extension_preserves_original_records_and_functional_query(self):
        source, target, baseline, graph = self.workspace()
        original = {r['id']: r for r in baseline['edges']}
        self.assertTrue(all(r == next(e for e in graph['edges'] if e['id'] == k) for k,r in original.items()))
        self.assertEqual(read_run(source)[2], baseline)
        self.assertEqual(read_run(target)[2], graph)
        self.assertEqual(len([e for e in graph['edges'] if e.get('extension_source_kind') == 'string_physical']), 2)
        for e in graph['edges']:
            if e.get('extension_source_kind') == 'string_physical':
                self.assertEqual(e['evidence_record']['network_type'], 'physical')
                self.assertFalse(e['biologically_validated'])
                self.assertIs(type(e['source_scores_raw']['physical_combined_score']), int)
                self.assertEqual(e['source_scores_raw']['physical_combined_score'] / 1000, e['evidence_record']['physical_score_0_to_1'])
        plain_before = answer_question(baseline, 'P04637', view='candidates')
        plain_after = answer_question(graph, 'P04637', view='candidates')
        self.assertEqual(plain_before['results'], plain_after['results'])
        self.assertEqual(plain_before['summary'], plain_after['summary'])

    def test_native_question_can_show_pairs_missing_original_functional_paths_without_promoting(self):
        _, target, baseline, graph = self.workspace(); before = deepcopy(graph)
        with patch('biograph_steward.physical_ranking.collect_ranking', side_effect=AssertionError('No live scores')):
            answer = answer_question(graph, 'P04637', view='candidates', template='native_string_physical.v1')
        self.assertEqual(answer['matching_proteins'], 2)
        self.assertIsNone(answer['plan']['disease'])
        self.assertTrue(all(c['review_state'] == 'candidate' for c in answer['citations']))
        self.assertTrue(all('STRING 12.5' in s['text'] and 'co-complex' in s['text'] for s in answer['summary']))
        self.assertNotIn('Pharos reports', ' '.join(s['text'] for s in answer['summary']))
        accepted = answer_question(graph, 'P04637', view='accepted', template='native_string_physical.v1')
        self.assertEqual(accepted['returned_proteins'], 0)
        self.assertEqual(accepted['availability']['inspectable_proteins'], 2)
        self.assertEqual(graph, before)
        missing = answer_question(graph, 'P01112', view='candidates', template='native_string_physical.v1')
        self.assertEqual(missing['returned_proteins'], 0)
        self.assertEqual(missing['plan']['selected_coverage']['anchor_identity']['admission'], 'full_sequence_mismatch')
        self.assertIn('missing results do not establish biological absence', missing['overview'])
        self.assertEqual(answer['plan']['selected_coverage']['anchor_pair_states']['native_physical_association'], 2)
        path = self.root / 'saved_question'; save_answer(answer, path)
        saved = json.loads((path / 'question.json').read_text()); verify_answer(saved)
        self.assertEqual(saved, answer)
        for kwargs in ({'ranking': 'physical'}, {'relations': ['shared_pathways']}):
            with self.assertRaises(ValueError): answer_question(graph, 'P04637', template='native_string_physical.v1', **kwargs)
        with self.assertRaises(ValueError): answer_question(baseline, 'P04637', template='native_string_physical.v1')

    def test_reviewed_native_source_is_separate_from_old_functional_states(self):
        _, target, _, graph = self.workspace()
        native = next(a for a in graph['assertions'] if a.get('extension_source_kind') == 'string_physical')
        changed = review_run(target, self.root / 'reviewed', native['id'], 'accepted', 'Invented reviewer', 'Invented fixture only')
        answer = answer_question(changed, 'P04637', view='accepted', template='native_string_physical.v1')
        self.assertEqual(answer['returned_proteins'], 1)
        self.assertTrue(all(a['lifecycle_state'] == 'candidate' for a in changed['assertions'] if not a.get('extension_source_kind')))

    def test_inspection_and_portable_graph_export_keep_complete_source_and_ledger(self):
        _, target, _, graph = self.workspace()
        edge = next(e for e in graph['edges'] if e.get('extension_source_kind') == 'string_physical')
        inspection = inspect_selection(graph, edge['id'], run_id=target.name)
        sections = [s for s in inspection['sections'] if s['title'] == 'Native STRING physical association']
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]['fields']['network_type'], 'physical')
        self.assertTrue(any('/api/extension-source/physical/extension_sources/string_physical/projection.json' in link['url'] for link in inspection['links']))
        packet = self.root / 'packet'; export_packet(target, packet)
        loaded = load_packet(packet)
        self.assertTrue((packet / 'source/extension_sources/string_physical/source/canonical.fasta').is_file())
        self.assertTrue(loaded)

class NativePhysicalHttpTests(unittest.TestCase):
    def test_authenticated_saved_query_reopen_source_download_and_tamper_rejection(self):
        from io import BytesIO
        import threading
        from urllib.error import HTTPError
        from urllib.request import Request, ProxyHandler, build_opener
        from zipfile import ZipFile
        from biograph_steward.webapp import create_server
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); snapshot = cohort_snapshot()
            sources = source_fixture(root / 'bulk', snapshot)
            publication = root / 'publication'; physical.publish_sources(snapshot, sources, publication)
            source = root / 'original'; save_run(snapshot, source)
            run = root / 'physical'; publish_extension(source, {'string_physical': publication}, run)
            original_hash = sha(run / 'graph.json')
            server = create_server(0, root, access_token='invented-native-physical-test')
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            opener = build_opener(ProxyHandler({})); url = 'http://127.0.0.1:' + str(server.server_port)
            def request(path, body=None, auth=True):
                headers = {'Authorization': 'Bearer invented-native-physical-test'} if auth else {}
                if body is not None: headers['Content-Type'] = 'application/json'
                return opener.open(Request(url + path, json.dumps(body).encode() if body is not None else None, headers))
            body = {'run_id': 'physical', 'protein': 'P04637', 'template': 'native_string_physical.v1', 'view': 'candidates'}
            try:
                with self.assertRaises(HTTPError) as caught: request('/api/question', body, False)
                self.assertEqual(caught.exception.code, 401); caught.exception.close()
                with patch('biograph_steward.physical_ranking.collect_ranking', side_effect=AssertionError('No live source request')):
                    with request('/api/question', body) as response: result = json.loads(response.read())
                    self.assertEqual(result['answer']['returned_proteins'], 2)
                    with request('/api/question/' + result['question_id']) as response:
                        self.assertEqual(json.loads(response.read()), result)
                    with request('/api/download/' + result['question_id']) as response:
                        with ZipFile(BytesIO(response.read())) as archive:
                            self.assertIn('question.json', {Path(n).name for n in archive.namelist()})
                source_path = '/api/extension-source/physical/extension_sources/string_physical/source/' + physical.NAMES['physical']
                with request(source_path) as response:
                    self.assertEqual(response.read(), (publication / 'source' / physical.NAMES['physical']).read_bytes())
                    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(sha(run / 'graph.json'), original_hash)
                raw = run / 'extension_sources/string_physical/source' / physical.NAMES['physical']
                raw.write_bytes(raw.read_bytes() + b'tampered')
                with self.assertRaises(HTTPError) as caught: request('/api/question/' + result['question_id'])
                self.assertEqual(caught.exception.code, 400); caught.exception.close()
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
