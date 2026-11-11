"""Independent local HTTP checks for the optional source-backed ordering.

All proteins, provider responses and scores below are invented software fixtures.
The tests exercise persisted source replay, not scientific accuracy or usability.
"""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

from biograph_steward.client import PharosClient, digest
from biograph_steward.assertions import new_review_event
from biograph_steward.graph import save_run
from biograph_steward.questions import answer_question
from biograph_steward.webapp import create_server
from test_starter import MockAPI, resign


TOKEN = 'synthetic-physical-ranking-http-token'
ANCHOR = 'P04637'
PARTNERS = ['P00533', 'P01116', 'P15056', 'P31749']
PATHWAY_ONLY = 'P42336'


def snapshot_fixture():
    snapshot = PharosClient(transport=MockAPI(6)).build_snapshot('Test disease')
    ids = [row['uniprot'] for row in snapshot['targets']]
    for row in snapshot['targets']:
        row.pop('diseaseAssociationDetails')
        row['pathways'] = []
        row['pharos_context'] = {'metadata': {}, 'ppis': []}
    snapshot['disease'] = None
    snapshot['scope'] = {
        'kind': 'protein_cohort', 'name': 'Invented ranking HTTP cohort',
        'requested_uniprot': ids,
        'resolutions': [{'requested_uniprot': uid, 'status': 'resolved',
                         'returned_uniprot': uid} for uid in ids],
    }
    snapshot['targets'][0]['pharos_context']['ppis'] = [
        {'nid': i + 1, 'type': 'STRINGDB',
         'props': [{'name': 'Score', 'value': '900'}],
         'target': {'uniprot': uid, 'sym': 'TEST_' + str(i + 1)}}
        for i, uid in enumerate(PARTNERS)]
    pathway = {'pwid': 1, 'name': 'Invented shared pathway', 'type': 'Reactome',
               'sourceID': 'R-HSA-1'}
    snapshot['targets'][0]['pathways'] = [deepcopy(pathway)]
    snapshot['targets'][5]['pathways'] = [deepcopy(pathway)]
    return resign(snapshot)


def inventory(folder):
    return {str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob('*') if path.is_file()}


def collect_fixture_packet(graph, anchor, candidates, *, collector=None):
    """Run the real adapter against independently composed, invented TSV bytes."""
    if collector is None:
        from biograph_steward.physical_ranking import collect_ranking as collector
    from biograph_steward.string_component import MAPPING_COLUMNS, NETWORK_COLUMNS
    accessions = [ANCHOR, *PARTNERS, PATHWAY_ONLY]
    representatives = {uid: '9606.ENSPINVENTED' + str(i)
                       for i, uid in enumerate(accessions)}
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    def tsv(columns, rows):
        return ('\t'.join(columns) + '\n' + ''.join(
            '\t'.join(str(row[column]) for column in columns) + '\n'
            for row in rows)).encode()

    def fetcher(url, *, timeout, max_bytes):
        query = parse_qs(urlsplit(url).query)
        method = urlsplit(url).path.rsplit('/', 1)[-1]
        if method == 'version':
            body = (b'string_version\tstable_address\n'
                    b'12.5\thttps://version-12-5.string-db.org\n')
        elif method == 'get_string_ids':
            requested = query['identifiers'][0].split('\r')
            body = tsv(MAPPING_COLUMNS, [
                {'queryIndex': i, 'queryItem': uid, 'stringId': representatives[uid],
                 'ncbiTaxonId': 9606, 'taxonName': 'Homo sapiens',
                 'preferredName': 'INVENTED_' + uid, 'annotation': 'Invented HTTP fixture'}
                for i, uid in enumerate(requested)])
        elif method == 'network':
            selected = set(query['identifiers'][0].split('\r'))
            rows = []
            for uid, physical in zip(PARTNERS, (0.0, 0.8, 0.8, None)):
                a, b = representatives[ANCHOR], representatives[uid]
                if not {a, b} <= selected:
                    continue
                for left, right in ((a, b), (b, a)):
                    row = {column: '-' for column in NETWORK_COLUMNS}
                    row.update(stringId_A=left, stringId_B=right,
                        preferredName_A='INVENTED_' + left,
                        preferredName_B='INVENTED_' + right, ncbiTaxonId=9606, sign='n/a')
                    for column in NETWORK_COLUMNS:
                        if column.startswith('functional_'):
                            row[column] = 0.9 if column == 'functional_combined_score' else 0.0
                        elif column.startswith('physical_') and physical is not None:
                            row[column] = physical if column == 'physical_combined_score' else 0.0
                    rows.append(row)
            body = tsv(NETWORK_COLUMNS, rows)
        else:
            raise AssertionError('Unexpected provider method in HTTP test: ' + method)
        if len(body) > max_bytes:
            raise AssertionError('Invented response exceeds adapter body guard.')
        return {'status': 200, 'url': url, 'body': body,
                'headers': {'Content-Type': 'text/tab-separated-values',
                            'Content-Length': str(len(body)), 'string-api-version': '2'}}

    return collector(graph, anchor, candidates, fetcher=fetcher,
                     clock=lambda: now[0], sleep=sleep)


class PhysicalRankingHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'invented-source'
        self.graph = save_run(snapshot_fixture(), self.source)
        self.original = inventory(self.source)
        self.server = create_server(0, self.root, access_token=TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, *, auth=True):
        headers = {'Authorization': 'Bearer ' + TOKEN} if auth else {}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        return build_opener(ProxyHandler({})).open(Request(
            self.url + path, data=json.dumps(body).encode() if body is not None else None,
            headers=headers), timeout=10)

    def query(self, **changes):
        body = {'run_id': self.source.name, 'protein': ANCHOR,
                'view': 'candidates', 'relations': ['interactions', 'shared_pathways'],
                'max_results': 30, **changes}
        with self.request('/api/question', body) as response:
            return json.loads(response.read())

    def assert_bad_get(self, path):
        with self.assertRaises(HTTPError) as error:
            self.request(path)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def ranked_query(self, **changes):
        from biograph_steward.physical_ranking import collect_ranking
        with patch('biograph_steward.physical_ranking.collect_ranking',
                   side_effect=lambda *args: collect_fixture_packet(*args, collector=collect_ranking)) as collector:
            result = self.query(ranking='physical', **changes)
        return result, collector

    def rewrite_answer(self, result, mutate):
        target = self.root / result['question_id'] / 'question.json'
        answer = json.loads(target.read_text(encoding='utf-8'))
        mutate(answer)
        answer['answer_sha256'] = digest({k: v for k, v in answer.items() if k != 'answer_sha256'})
        target.write_text(json.dumps(answer), encoding='utf-8')
        return target

    def test_default_question_remains_identical_and_does_not_fetch(self):
        expected = answer_question(self.graph, ANCHOR, source_run=self.source.name,
            view='candidates', relations=['interactions', 'shared_pathways'], max_results=30)
        with patch('biograph_steward.physical_ranking.collect_ranking',
                   side_effect=AssertionError('Default questions cannot retrieve STRING.')) as collector:
            result = self.query()
            self.assertEqual(result['answer'], expected)
            collector.assert_not_called()
        self.assertEqual(inventory(self.source), self.original)

    def test_invalid_and_unauthorized_rankings_fail_before_source_access(self):
        with patch('biograph_steward.physical_ranking.collect_ranking') as collector:
            for value in ('binding', 'functional', '', None, True, {}, []):
                with self.subTest(ranking=value), self.assertRaises(HTTPError) as error:
                    self.query(ranking=value)
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            for changes in (
                    {'ranking': 'physical', 'ranking_source': {}},
                    {'ranking': 'physical', 'endpoint': 'https://untrusted.example/api'},
                    {'ranking': 'physical', 'relations': ['shared_pathways']}):
                with self.subTest(changes=changes), self.assertRaises(HTTPError) as error:
                    self.query(**changes)
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            with self.assertRaises(HTTPError) as error:
                self.request('/api/question', {'run_id': self.source.name,
                    'protein': ANCHOR, 'ranking': 'physical'}, auth=False)
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
            collector.assert_not_called()
        self.assertEqual(inventory(self.source), self.original)

    def test_provider_failure_is_visible_without_alphabetical_fallback(self):
        before = set(self.root.iterdir())
        with patch('biograph_steward.physical_ranking.collect_ranking',
                   side_effect=ValueError('Invented provider schema failure.')):
            with self.assertRaises(HTTPError) as error:
                self.query(ranking='physical')
            self.assertEqual(error.exception.code, 400)
            self.assertIn('Invented provider schema failure', error.exception.read().decode())
            error.exception.close()
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertEqual(inventory(self.source), self.original)

    def test_scores_sort_all_matches_before_limit_and_preserve_paths(self):
        ranked, collector = self.ranked_query(max_results=2)
        answer = ranked['answer']
        self.assertEqual(answer['plan']['ranking'], 'physical')
        self.assertEqual(answer['matching_proteins'], 5)
        self.assertEqual([r['protein']['id'] for r in answer['results']],
                         ['UniProtKB:P01116', 'UniProtKB:P15056'])
        self.assertEqual(len(collector.call_args.args[2]), 5)
        self.assertEqual(answer['omitted_proteins'], 3)
        self.assertEqual(answer['ranking']['numeric_scored'], 3)
        self.assertEqual(answer['ranking']['unranked_proteins'], 2)
        unranked = answer_question(self.graph, ANCHOR, source_run=self.source.name,
            view='candidates', relations=['interactions', 'shared_pathways'], max_results=30)
        by_id = {row['protein']['id']: row for row in unranked['results']}
        for row in answer['results']:
            old = by_id[row['protein']['id']]
            self.assertEqual(row['review_status'], old['review_status'])
            self.assertEqual(row['eligible_path_count'], old['eligible_path_count'])
            self.assertEqual([p['id'] for p in row['paths']], [p['id'] for p in old['paths']])
            self.assertEqual([p['assertion_ids'] for p in row['paths']],
                             [p['assertion_ids'] for p in old['paths']])
            self.assertEqual(row['physical_priority']['physical_score'], 0.8)
        self.assertEqual(inventory(self.source), self.original)

    def test_numeric_zero_precedes_unavailable_and_pathway_only_stays_unranked(self):
        result, _ = self.ranked_query()
        answer = result['answer']
        self.assertEqual([r['protein']['id'] for r in answer['results']],
            ['UniProtKB:P01116', 'UniProtKB:P15056', 'UniProtKB:P00533',
             'UniProtKB:P31749', 'UniProtKB:P42336'])
        by_id = {r['protein']['id']: r for r in answer['results']}
        zero = by_id['UniProtKB:P00533']['physical_priority']
        self.assertEqual(zero['state'], 'numeric')
        self.assertEqual(zero['physical_score'], 0.0)
        missing = by_id['UniProtKB:P31749']['physical_priority']
        self.assertEqual(missing['state'], 'physical_not_returned_under_profile')
        self.assertIsNone(missing['physical_score'])
        pathway = by_id['UniProtKB:P42336']
        self.assertEqual(pathway['physical_priority']['state'], 'not_interaction_path')
        self.assertFalse(pathway['physical_priority']['has_interaction'])
        self.assertIsNone(pathway['physical_priority']['physical_score'])
        self.assertEqual({p['kind'] for p in pathway['paths']}, {'shared_pathway'})
        self.assertTrue(all(c['review_state'] == 'candidate' for c in answer['citations']))
        self.assertEqual(inventory(self.source), self.original)

    def test_saved_packet_reopens_and_exports_without_new_source_calls(self):
        result, _ = self.ranked_query()
        answer, qid = result['answer'], result['question_id']
        with patch('biograph_steward.physical_ranking.collect_ranking',
                   side_effect=AssertionError('Reopening cannot requery the provider.')) as collector:
            with self.request('/api/question/' + qid) as response:
                self.assertEqual(json.loads(response.read()), result)
            with self.request('/api/download/' + qid) as response:
                with ZipFile(BytesIO(response.read())) as archive:
                    by_name = {Path(name).name: name for name in archive.namelist()}
                    self.assertTrue({'question.json', 'summary.txt', 'report.html', 'paths.tsv',
                                     'physical_ranking_source.json', 'physical_priority.tsv'} <= set(by_name))
                    exported = json.loads(archive.read(by_name['question.json']))
                    self.assertEqual(exported, answer)
                    packet = json.loads(archive.read(by_name['physical_ranking_source.json']))
                    self.assertEqual(packet, answer['physical_ranking_source'])
                    priority = archive.read(by_name['physical_priority.tsv']).decode()
                    self.assertTrue(all('UniProtKB:' + uid in priority for uid in [*PARTNERS, PATHWAY_ONLY]))
                    summary = archive.read(by_name['summary.txt']).decode()
                    html = archive.read(by_name['report.html']).decode()
                    self.assertIn('12.5', summary)
                    self.assertIn('12.5', html)
            collector.assert_not_called()
        self.assertEqual(inventory(self.source), self.original)

    def test_resealed_answer_with_changed_score_is_rejected_on_reopen_and_download(self):
        result, _ = self.ranked_query()
        self.rewrite_answer(result, lambda a: a['results'][0]['physical_priority'].update(physical_score=0.123))
        self.assert_bad_get('/api/question/' + result['question_id'])
        self.assert_bad_get('/api/download/' + result['question_id'])

    def test_resealed_answer_with_changed_raw_packet_is_rejected(self):
        result, _ = self.ranked_query()

        def mutate(answer):
            packet = answer['physical_ranking_source']
            request = next(row for row in packet['requests'] if row['kind'] == 'network')
            request['attempts'][0]['body_text'] += '\nINVALID\tROW\n'

        self.rewrite_answer(result, mutate)
        self.assert_bad_get('/api/question/' + result['question_id'])
        self.assert_bad_get('/api/download/' + result['question_id'])

    def test_missing_or_changed_exported_packet_is_rejected(self):
        result, _ = self.ranked_query()
        packet_path = self.root / result['question_id'] / 'physical_ranking_source.json'
        original = packet_path.read_bytes()
        packet_path.unlink()
        self.assert_bad_get('/api/question/' + result['question_id'])
        self.assert_bad_get('/api/download/' + result['question_id'])
        packet_path.write_bytes(original + b' ')
        # JSON-equivalent bytes are acceptable only if the exporter promises
        # content identity; a changed field must always fail.
        packet = json.loads(packet_path.read_text())
        packet['content_sha256'] = '0' * 64
        packet_path.write_text(json.dumps(packet))
        self.assert_bad_get('/api/question/' + result['question_id'])
        self.assert_bad_get('/api/download/' + result['question_id'])

    def test_changed_priority_table_is_rejected_on_reopen_and_download(self):
        result, _ = self.ranked_query()
        table_path = self.root / result['question_id'] / 'physical_priority.tsv'
        table_path.write_bytes(table_path.read_bytes() + b'INVENTED\tWRONG\tROW\n')
        self.assert_bad_get('/api/question/' + result['question_id'])
        self.assert_bad_get('/api/download/' + result['question_id'])

    def test_changed_readable_exports_are_rejected_on_reopen_and_download(self):
        result, _ = self.ranked_query()
        folder = self.root / result['question_id']
        for name in ('summary.txt', 'report.html', 'paths.tsv'):
            with self.subTest(export=name):
                target = folder / name
                original = target.read_bytes()
                try:
                    target.write_bytes(original + b'INVENTED ALTERED EXPORT\n')
                    self.assert_bad_get('/api/question/' + result['question_id'])
                    self.assert_bad_get('/api/download/' + result['question_id'])
                finally:
                    target.write_bytes(original)
        with self.request('/api/question/' + result['question_id']) as response:
            self.assertEqual(json.loads(response.read()), result)
        self.assertEqual(inventory(self.source), self.original)

    def test_source_review_drift_rejects_saved_ranking_without_new_retrieval(self):
        result, _ = self.ranked_query()
        assertion_id = result['answer']['results'][0]['paths'][0]['assertion_ids'][0]
        event = new_review_event(self.graph, assertion_id, 'accepted',
                                'Invented HTTP QA', 'Synthetic source drift check')
        (self.source / 'review_events.json').write_text(json.dumps([event]), encoding='utf-8')
        with patch('biograph_steward.physical_ranking.collect_ranking',
                   side_effect=AssertionError('Source drift cannot start another capture.')) as collector:
            self.assert_bad_get('/api/question/' + result['question_id'])
            self.assert_bad_get('/api/download/' + result['question_id'])
            collector.assert_not_called()


if __name__ == '__main__':
    unittest.main()
