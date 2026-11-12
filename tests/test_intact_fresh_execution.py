"""Invented-only fresh runner controls; selected reference bodies stay unopened."""
from copy import deepcopy
import hashlib
from http.client import IncompleteRead
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from scripts import run_intact_fresh_evaluation as fresh
from scripts import run_intact_final_evaluation as original
from scripts.intact_final_common import provenance_audit, study_ids
from tests.test_intact_evidence_fidelity import fixture
from tests.test_intact_final_execution import inventory, note, xml_record, xref


class Response:
    def __init__(self, body=b'invented source bytes', *, url=None, headers=None, status=200, partial=False):
        self.body, self.url, self.status, self.partial = body, url, status, partial
        self.headers = headers if headers is not None else {'Content-Length': str(len(body))}

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def geturl(self): return self.url
    def read(self, maximum):
        if self.partial: raise IncompleteRead(self.body[:3], 99)
        return self.body[:maximum]


class Opener:
    def __init__(self, response): self.response, self.calls = response, []
    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.response.url is None: self.response.url = request.full_url
        return self.response


def identity(db, value, qualifier='MI:0356'):
    return {'database': {'name': db}, 'id': value, 'qualifier': {'mi_id': qualifier}}


def metadata_fixture(root):
    """Invented bound metadata for prepare/verify; no ignored captures needed."""
    def write(name, body):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body) if isinstance(body, dict) else body)
        return path

    directory = write('metadata/directory.html', '<html>Invented directory metadata.</html>')
    selection = write('metadata/selection.json', {
        'selected': [{'publication_id': 'pubmed:' + pmid,
                      'original_metadata_rank': index + 9,
                      'url': fresh.SOURCE_BASES['mitab'] + pmid + '.txt'}
                     for index, pmid in enumerate(fresh.FRESH)],
        'bindings': {'directory_metadata': {
            'path': str(directory.relative_to(root)), 'sha256': fresh.sha(directory)}}})
    consumed = write('metadata/consumed.json', inventory())
    license_path = write('metadata/LICENSE.md', 'Invented license metadata; not a source license.')
    archived = write('archive/invented.py', '# Invented archived implementation.\n')
    archive = write('archive/receipt.json', {'files': [{
        'archived_path': str(archived.relative_to(root)), 'sha256': fresh.sha(archived)}]})
    implementation = write('scripts/intact_final_common.py', '# Invented implementation binding.\n')
    # These tracked metadata documents are part of every checkout. Preserve the
    # production protocol pins, rather than supplying historical source files.
    for name in (original.PROTOCOL, original.AMENDMENT):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((fresh.ROOT / name).read_bytes())
    return ({'ROOT': root, 'SELECTION': selection, 'SELECTION_SHA': fresh.sha(selection),
             'INVENTORY': consumed, 'INVENTORY_SHA': fresh.sha(consumed),
             'ARCHIVE': archive, 'ARCHIVE_SHA': fresh.sha(archive),
             'LICENSE_PATH': license_path, 'ACCESS_MARKER': root / 'access.json'},
            {str(implementation): fresh.sha(implementation)})


class FreshAccountingTests(unittest.TestCase):
    def test_original_scope_guard_stays_closed(self):
        self.assertEqual(study_ids('reserved_final'), fresh.RESERVED)
        with self.assertRaises(ValueError): study_ids(fresh.SPLIT)
        self.assertEqual(fresh.POLICY['maximum_source_eligible_rows'], 64)
        self.assertEqual(fresh.POLICY['maximum_pair_batches'], 32)
        self.assertEqual(fresh.POLICY['maximum_pharos_attempts_total'], 224)

    def test_full_alias_hit_propagates_through_existing_dataset_components(self):
        a, b = fresh.FRESH[:2]
        first = xml_record(pmid=a, annotation=note('Primary dataset'),
                           xrefs=[identity('pdb', 'INVENTED'), xref('pubmed', b)])
        second = xml_record(pmid=b, annotation=note('Subsidiary dataset'), xrefs=[xref('pubmed', a)])
        consumed = inventory(evidence_ids=[['pdb', 'INVENTED']])
        records = {a: [first], b: [second]}
        old = provenance_audit(records, [], consumed)
        self.assertEqual(old['excluded_publication_ids'], [])
        result = fresh.complete_alias_audit(records, [], consumed)
        self.assertEqual(result['excluded_publication_ids'], sorted([a, b]))
        self.assertEqual(result['ambiguous_dataset_statements'], [])
        self.assertEqual(result['full_qualified_alias_evidence'][0]['exact_consumed_alias_overlap'], [('pdb', 'INVENTED')])
        self.assertTrue(result['complete_identity_aliases_checked'])
        self.assertEqual(result['qualified_alias_rule'], fresh.ALIAS_RULE)

    def test_generic_see_also_is_not_identity_but_explicit_imex_remains(self):
        row = xml_record(xrefs=[identity('pdb', 'INVENTED', 'MI:0361')])
        row['evidence']['imex_id'] = 'IM-INVENTED'
        self.assertEqual(fresh.qualified_aliases(row['evidence']), {('imex', 'IM-INVENTED')})
        result = fresh.complete_alias_audit({fresh.FRESH[0]: [row]}, [], inventory(evidence_ids=[['pdb', 'INVENTED']]))
        self.assertFalse(result['excluded_publication_ids'])
        self.assertEqual(result['study_independence'], 'unverified')

    def test_all_source_eligible_rows_count_before_study_exclusion(self):
        refs = fixture()[0]
        repeated = [deepcopy(refs[0]) for _ in range(65)]
        with self.assertRaises(fresh.BudgetExceeded): fresh.check_work_budget(repeated, [])
        fresh.check_work_budget(repeated[:64], [])

    def test_pair_budget_does_not_pick_a_favorable_subset(self):
        refs = [deepcopy(fixture()[0][0]) for _ in range(33)]
        for index, ref in enumerate(refs):
            ref['reader_record']['source_fields']['primary_ids_a']['values'][0]['id'] = 'P%05d' % (10000 + index)
        with self.assertRaises(fresh.BudgetExceeded): fresh.check_work_budget(refs, [])
        fresh.check_work_budget(refs[:32], [])

    def test_missing_mandatory_code_is_not_silently_dropped(self):
        original_ordinary = fresh.ordinary
        def ordinary(path):
            if str(path).endswith('tests/test_intact_fresh_execution.py'):
                raise ValueError('invented missing required implementation')
            return original_ordinary(path)
        with patch.object(fresh, 'ordinary', ordinary), self.assertRaises(ValueError):
            fresh.code_bindings()


class FreshSourceTransportTests(unittest.TestCase):
    def test_exact_bounded_source_bytes_and_receipt_preserved_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); opener = Opener(Response())
            path = fresh.fetch_source(fresh.FRESH[0], 'mitab', root, opener=opener)
            self.assertEqual(path.read_bytes(), b'invented source bytes')
            self.assertEqual(len(opener.calls), 1)
            receipt = json.loads((root / (fresh.FRESH[0] + '_mitab_http_receipt.json')).read_text())
            self.assertEqual(receipt['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(receipt['attempt'], 1)
            self.assertEqual(receipt['outcome'], 'opaque_bytes_saved_not_decoded')
            self.assertEqual(opener.calls[0][0].get_header('Accept-encoding'), 'identity')

    def test_wrong_scope_fails_without_transport(self):
        for pmid, kind in [('11111111', 'mitab'), (fresh.FRESH[0], 'alternate')]:
            with tempfile.TemporaryDirectory() as tmp:
                opener = Opener(Response())
                with self.assertRaises(ValueError): fresh.fetch_source(pmid, kind, Path(tmp), opener=opener)
                self.assertFalse(opener.calls)

    def test_source_redirect_compression_empty_and_partial_fail_without_retry(self):
        for response in [Response(url='https://example.org/redirect'), Response(body=b''),
                         Response(headers={'Content-Encoding': 'gzip'}),
                         Response(headers={'Content-Length': '999'}), Response(partial=True)]:
            with self.subTest(response=response), tempfile.TemporaryDirectory() as tmp:
                opener = Opener(response); root = Path(tmp)
                with self.assertRaises(ValueError): fresh.fetch_source(fresh.FRESH[0], 'mitab', root, opener=opener)
                self.assertEqual(len(opener.calls), 1)
                receipt = json.loads((root / (fresh.FRESH[0] + '_mitab_http_receipt.json')).read_text())
                self.assertEqual(receipt['outcome'], 'failed')
                if response.partial:
                    self.assertTrue((root / (fresh.FRESH[0] + '.partial.txt')).is_file())

    def test_body_overrun_retains_only_bounded_failure_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = {**fresh.POLICY, 'maximum_mitab_bytes': 8}
            opener = Opener(Response(b'invented-long-body', headers={}))
            with patch.object(fresh, 'POLICY', policy), self.assertRaises(ValueError):
                fresh.fetch_source(fresh.FRESH[0], 'mitab', Path(tmp), opener=opener)
            self.assertEqual(len((Path(tmp) / (fresh.FRESH[0] + '.txt')).read_bytes()), 9)


class PharosBudgetTests(unittest.TestCase):
    def test_counts_actual_open_calls_no_cache_retry_or_redirect_and_preserves_ca(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); opener = Opener(Response(b'{"data": {}}'))
            handlers = []
            def build(*values): handlers.extend(values); return opener
            with patch.object(fresh, 'build_opener', build), patch.object(fresh.ssl, 'create_default_context', return_value=object()) as ssl_context, patch.dict(fresh.os.environ, {'SSL_CERT_FILE': '/invented-approved-ca.pem'}):
                client = fresh.BudgetPharos(root, {'attempts': 0})
                for _ in range(7): self.assertEqual(client.execute('invented query'), {})
                with self.assertRaises(fresh.BudgetExceeded): client.execute('eighth query')
                self.assertEqual(len(opener.calls), 7)
                self.assertIsNone(client.cache_dir); self.assertEqual(client.retries, 0)
                ssl_context.assert_called_with(cafile='/invented-approved-ca.pem')
                self.assertTrue(any(isinstance(handler, original.NoRedirect) for handler in handlers))
                with self.assertRaises(ValueError):
                    next(handler for handler in handlers if isinstance(handler, original.NoRedirect)).redirect_request(None, None, None, None, None, None)
            self.assertEqual(len(list(root.glob('pharos_attempt_*_receipt.json'))), 7)

    def test_failed_transport_attempts_count_and_total_budget_precedes_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = []
            def fail(payload): seen.append(payload); raise OSError('invented transport failure')
            total = {'attempts': 0}; client = fresh.BudgetPharos(Path(tmp), total, transport=fail)
            for _ in range(7):
                with self.assertRaises(OSError): client.execute('invented query')
            with self.assertRaises(fresh.BudgetExceeded): client.execute('invented query')
            self.assertEqual(len(seen), 7); self.assertEqual(total['attempts'], 7)
        with tempfile.TemporaryDirectory() as tmp:
            client = fresh.BudgetPharos(Path(tmp), {'attempts': 224}, transport=lambda _: self.fail('must not open'))
            with self.assertRaises(fresh.BudgetExceeded): client.execute('invented query')

    def test_partial_pharos_body_is_preserved_not_imputed(self):
        with tempfile.TemporaryDirectory() as tmp:
            opener = Opener(Response(b'{"data": {}}', partial=True))
            with patch.object(fresh, 'build_opener', return_value=opener), self.assertRaises(ValueError):
                fresh.BudgetPharos(Path(tmp), {'attempts': 0}).execute('invented query')
            self.assertEqual(len(opener.calls), 1)
            self.assertEqual((Path(tmp) / 'pharos_attempt_01_body.json').read_bytes(), b'{"d')


class ExecutionBoundaryTests(unittest.TestCase):
    def test_fatal_budget_hook_stops_before_later_batches_or_metrics(self):
        refs = fixture()[0][:2]
        refs[1]['reader_record']['source_fields']['primary_ids_a']['values'][0]['id'] = 'P99999'
        wrappers = [{'reader_record': ref['reader_record']} for ref in refs]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); freeze_path = root / 'freeze.json'; freeze_path.write_text('{}')
            controls = root / 'controls.json'; controls.write_text('{}')
            # _execute assembles publication metadata before the budget hook.
            # Supply only invented metadata in an isolated root, so this guard
            # never depends on a locally captured historical IntAct license.
            for name in (original.PROTOCOL, original.AMENDMENT,
                         original.BASE + '/sources/IntAct_license.md'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('Invented publication metadata; no source rows.')
            freeze = {'assessment_split': fresh.SPLIT, 'publication_ids': list(fresh.FRESH),
                      'consumed_inventory': str(controls), 'controls_report': str(controls),
                      'xml_controls_report': str(controls), 'mitab_runtime': {}, 'xml_runtime': {},
                      'implementation_sha256': {}}
            seen = []
            def fail(folder): seen.append(folder); raise fresh.BudgetExceeded('invented fixed budget stop')
            with patch.object(original, 'ROOT', root), patch('biograph_steward.intact_final_publication.publish_material'), self.assertRaises(fresh.BudgetExceeded):
                original._execute(freeze, freeze_path, fresh.sha(freeze_path), root,
                    source_loader=lambda *args: (wrappers, [r['ledger'] for r in refs], {}, {}, [], []),
                    lineage_auditor=lambda *args: {'excluded_publication_ids': [], 'ambiguous_dataset_statements': []},
                    freeze_verifier=lambda *args: None, pharos_factory=fail,
                    fatal_exception=fresh.BudgetExceeded)
            self.assertEqual(len(seen), 1)
            self.assertFalse((root / 'report.json').exists())

    def test_one_shot_marker_survives_unscored_failure_and_renamed_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); marker = root / 'global_access.json'
            for name in ('first', 'second'):
                folder = root / name; folder.mkdir(); (folder / 'execution_freeze.json').write_text('{}')
            with patch.object(fresh, 'ACCESS_MARKER', marker), patch.object(fresh, 'verify_freeze', return_value={}), patch.object(original, '_execute', side_effect=fresh.BudgetExceeded('invented stop')) as flow:
                with self.assertRaises(fresh.BudgetExceeded): fresh.execute(root / 'first/execution_freeze.json', 'a' * 64)
                with self.assertRaises(FileExistsError): fresh.execute(root / 'second/execution_freeze.json', 'b' * 64)
                self.assertEqual(flow.call_count, 1)
            result = json.loads((root / 'first/execution/failure.json').read_text())
            self.assertIsNone(result['metrics'])
            self.assertEqual(len(result['selected_study_access']), 4)
            self.assertTrue(marker.is_file())

    def test_verify_freeze_rejects_resealed_scope_and_metadata_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); paths = []
            for index in range(5):
                path = root / ('control_%d.json' % index); path.write_text('{}'); paths.append(path)
            metadata, bindings = metadata_fixture(root)
            review = {'flow_controls_sha256': fresh.sha(paths[2]), 'rehearsal_report_sha256': fresh.sha(paths[3])}
            with patch.multiple(fresh, **metadata), patch.object(fresh, 'code_bindings', return_value=bindings), patch.object(fresh, '_verified_report', return_value=review), patch.object(fresh, 'verify_controls_report'), patch.object(fresh, 'verify_xml_controls'), patch.object(original, '_runtime', return_value={'invented': 'reader'}):
                freeze = fresh.prepare(root / 'freeze', *paths)
                path = root / 'freeze/execution_freeze.json'
                self.assertEqual(fresh.verify_freeze(path, fresh.sha(path)), freeze)
                for mutate in [lambda f: f['source_urls'][fresh.FRESH[0]].update(mitab='https://example.org/changed'),
                               lambda f: f.update(source_fidelity_only=False), lambda f: f.update(protocol_sha256='0' * 64),
                               lambda f: f['metadata_sha256'].pop(str(fresh.INVENTORY)),
                               lambda f: f.update(undocumented='extra')]:
                    changed = deepcopy(freeze); mutate(changed)
                    changed = fresh.seal({key: value for key, value in changed.items() if key != 'content_sha256'})
                    path.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError): fresh.verify_freeze(path, fresh.sha(path))

    def test_controls_gate_requires_nonempty_tests_and_bound_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); (root / 'controls.log').write_text('invented passing log')
            value = {'format': 'biograph-steward.intact-fresh-controls.v1', 'status': 'passed',
                     'fresh_sources_accessed': False, 'implementation_sha256': {}, 'tests_run': 1,
                     'skips': 0, 'log_sha256': fresh.sha(root / 'controls.log')}
            path = root / 'report.json'; path.write_text(json.dumps(fresh.seal(value)))
            with patch.object(fresh, 'code_bindings', return_value={}):
                self.assertEqual(fresh._verified_report(path, value['format'])['tests_run'], 1)
                for changes in ({'tests_run': 0}, {'skips': 1}, {'log_sha256': '0' * 64}):
                    path.write_text(json.dumps(fresh.seal({**value, **changes})))
                    with self.assertRaises(ValueError): fresh._verified_report(path, value['format'])


if __name__ == '__main__': unittest.main()
