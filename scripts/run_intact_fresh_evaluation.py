#!/usr/bin/env python3
"""One separately frozen fresh IntAct fidelity assessment using existing methods.

Controls and consumed rehearsal never access the selected fresh sources. Only
execute, after an externally recorded complete freeze, may retrieve them once.
This checks preservation of supplied curation, not independent biological truth.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from http.client import HTTPException, IncompleteRead
import io
import json
import os
from pathlib import Path
import ssl
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import ENDPOINT, PharosClient, canonical, digest, utcnow
from scripts import run_intact_final_evaluation as original
from scripts import replay_intact_consumed_flow as consumed_flow
from scripts.intact_final_common import (AMENDMENT_SHA, PROTOCOL_SHA, RESERVED,
    assess_alignment, load_json, ordinary, participant_pair, provenance_audit,
    save_new, seal, sha)
from scripts.inspect_intact_development import assess, source_lines, verify_controls_report
from scripts.inspect_intact_xml_development import assess_development_xml, xml_evidence_ids
from scripts.intact_identity_projection import complete_identity_ids, compare_identity_projection
from scripts.validate_intact_xml_provenance import parse_transport, verify_controls as verify_xml_controls

FORMAT = 'biograph-steward.intact-fresh-execution-freeze.v1'
RESULT_FORMAT = 'biograph-steward.intact-fresh-fidelity.v1'
SPLIT = 'fresh_source_fidelity'
FRESH = ('39938803', '40108405', '40752540', '40088780')
SELECTION = ROOT / 'docs/evaluations/intact_fresh_reference_20261027_selection.json'
SELECTION_SHA = '90e84d56fbbe043db2437a29df895608215d20de40c0b784c70db95140be5a98'
INVENTORY = ROOT / 'docs/evaluations/intact_consumed_inventory_v2_20261027.json'
INVENTORY_SHA = '60e0a4db76cdda74279da1280e45c43b40413b435d25120141da0b8e38369dbc'
ARCHIVE = ROOT / 'runs/intact_fresh_implementation_archive_20261027/receipt.json'
ARCHIVE_SHA = 'af4c5c281fcb1a7b02cd32e4a5a85a413050019e7d920f7ed5ff2fbc257cfc8c'
ACCESS_MARKER = ROOT / 'runs/intact_fresh_source_access_20261027.json'
ALIAS_RULE = 'All MI:0356 database identities; IMEx MI:0662 and explicit imex_id; no generic see-also'
LICENSE_PATH = ROOT / original.BASE / 'sources/IntAct_license.md'
SOURCE_BASES = {'mitab': 'https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psimitab/pmid/2025/',
                'xml': 'https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psi25/pmid/2025/'}
POLICY = {'maximum_source_eligible_rows': 64, 'maximum_pair_batches': 32,
          'maximum_pharos_attempts_per_pair': 7, 'maximum_pharos_attempts_total': 224,
          'maximum_mitab_bytes': 65536, 'maximum_xml_bytes': 2097152,
          'maximum_reader_stdout_bytes': 64 * 1024 * 1024,
          'source_attempts': 1, 'source_timeout_seconds': 90, 'reader_timeout_seconds': 120,
          'redirects': False, 'source_encoding': 'identity', 'cache': None, 'retries': 0,
          'pharos_timeout_seconds': 30, 'maximum_pharos_response_bytes': 25_000_000,
          'pharos_endpoint': ENDPOINT, 'profile': 'ppi', 'ppi_limit_per_target': 5000,
          'other_context_limits': 0, 'question_template': 'qualified_assay_evidence.v1',
          'question_scope': 'all attached rows; all local states; no cap',
          'pair_order': 'lexical exact unordered primary-accession pairs; isoforms retained',
          'budget_breach': 'stop_unscored_no_subset_no_replacement',
          'article_status_scope': 'Preserved IntAct source annotations only; no selected-publication body, abstract or external status lookup. Missing correction/retraction annotations are unknown, not clearance.',
          'model_calls': 0, 'GPU_runs': 0}


class BudgetExceeded(ValueError):
    """A frozen work bound stops the assessment rather than selecting survivors."""


def code_bindings():
    names = {Path(__file__).resolve(), ROOT / 'scripts/intact_identity_projection.py',
             ROOT / 'scripts/replay_intact_consumed_flow.py',
             ROOT / 'tests/test_intact_fresh_execution.py',
             ROOT / 'tests/test_intact_fresh_publication.py'}
    names.update(original.implementation_paths())
    names.update((ROOT / 'tests/fixtures/intact_reader').glob('*'))
    names.update((ROOT / 'tests/fixtures/intact_xml').glob('*'))
    return {str(path): sha(ordinary(path)) for path in sorted(names)}


def _python():
    return {'executable': str(Path(sys.executable).resolve()), 'version': sys.version,
            'sha256': sha(Path(sys.executable).resolve())}


def selection_metadata():
    """Only the exact saved metadata selection, never a selected source body."""
    if sha(ordinary(SELECTION)) != SELECTION_SHA or sha(ordinary(INVENTORY)) != INVENTORY_SHA:
        raise ValueError('Fixed fresh selection or expanded consumed inventory changed.')
    selected = load_json(SELECTION)
    if (tuple(entry['publication_id'].removeprefix('pubmed:') for entry in selected['selected']) != FRESH
            or [entry['original_metadata_rank'] for entry in selected['selected']] != [9, 10, 11, 12]):
        raise ValueError('Use all four exact remaining metadata-selected studies in original order.')
    for entry, pmid in zip(selected['selected'], FRESH):
        if entry['url'] != SOURCE_BASES['mitab'] + pmid + '.txt':
            raise ValueError('Fixed source URL differs.')
    directory = selected['bindings']['directory_metadata']
    if sha(ordinary(ROOT / directory['path'])) != directory['sha256']:
        raise ValueError('Original directory metadata changed.')
    return selected


def qualified_aliases(evidence):
    return complete_identity_ids(evidence) | xml_evidence_ids(evidence)


def complete_alias_audit(xml_by_study, records, inventory):
    audit = provenance_audit(xml_by_study, records, inventory, identity_projector=qualified_aliases)
    known = {tuple(item) for item in inventory['evidence_ids']}
    table = []
    for pmid, rows in xml_by_study.items():
        for row in rows:
            ids = qualified_aliases(row['evidence'])
            table.append({'publication_id': pmid, 'evidence_sequence': row['evidence_sequence'],
                          'identity_ids': sorted(ids), 'exact_consumed_alias_overlap': sorted(ids & known)})
    audit.update(format='biograph-steward.intact-complete-qualified-alias-audit.v1',
                 complete_identity_aliases_checked=True, consumed_inventory_sha256=INVENTORY_SHA,
                 qualified_alias_rule=ALIAS_RULE, full_qualified_alias_evidence=table,
                 article_status_scope=POLICY['article_status_scope'])
    return audit


def check_work_budget(references, _qualified=None):
    eligible = [ref for ref in references if ref['ledger']['eligible']]
    pairs = {participant_pair(ref['reader_record']) for ref in eligible}
    if (len(eligible) > POLICY['maximum_source_eligible_rows']
            or len(pairs) > POLICY['maximum_pair_batches']):
        raise BudgetExceeded('Fixed source-row/pair budget exceeded; stop unscored without subsetting or replacement.')


def fetch_source(pmid, kind, output, *, opener=None):
    """Preserve one exact bounded source response before any decoding."""
    if pmid not in FRESH or kind not in SOURCE_BASES:
        raise ValueError('Only the exact predeclared fresh source URLs may be retrieved.')
    maximum = POLICY['maximum_mitab_bytes' if kind == 'mitab' else 'maximum_xml_bytes']
    suffix = '.txt' if kind == 'mitab' else '.xml'
    url = SOURCE_BASES[kind] + pmid + suffix
    output = Path(output)
    receipt = {'publication_id': pmid, 'kind': kind, 'url': url, 'started_at': utcnow(),
               'maximum_bytes': maximum, 'attempt': 1, 'redirects': False, 'retries': False}
    save_new(output / (pmid + '_' + kind + '_retrieval_started.json'), receipt)
    body = b''
    try:
        request = Request(url, headers={'User-Agent': 'BioGraph-Steward/IntAct-fresh-fidelity', 'Accept-Encoding': 'identity'})
        with (opener or build_opener(original.NoRedirect())).open(request, timeout=POLICY['source_timeout_seconds']) as response:
            receipt.update(status=response.status, final_url=response.geturl(), headers=dict(response.headers))
            if response.status != 200 or response.geturl() != url:
                raise ValueError('Source must return exact HTTP200 without redirects.')
            if response.headers.get('Content-Encoding', 'identity').lower() not in {'', 'identity'}:
                raise ValueError('Compressed source is outside the bounded identity-byte contract.')
            declared = response.headers.get('Content-Length')
            if declared is not None and (not declared.isascii() or not declared.isdecimal() or int(declared) > maximum):
                raise ValueError('Invalid or over-bound source Content-Length.')
            try:
                body = response.read(maximum + 1)
            except IncompleteRead as exc:
                body = exc.partial[:maximum + 1]
                with (output / (pmid + '.partial' + suffix)).open('xb') as stream:
                    stream.write(body)
                receipt.update(partial_bytes=len(body), partial_sha256=hashlib.sha256(body).hexdigest())
                raise ValueError('Incomplete source response; partial bytes preserved.') from exc
            with (output / (pmid + suffix)).open('xb') as stream:
                stream.write(body)
            receipt.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            if not body or len(body) > maximum or (declared is not None and int(declared) != len(body)):
                raise ValueError('Empty, oversized or incomplete source body; no replacement.')
            receipt['outcome'] = 'opaque_bytes_saved_not_decoded'
    except (OSError, ValueError, HTTPError, HTTPException) as exc:
        receipt.update(outcome='failed', error_type=type(exc).__name__, error=str(exc))
        if isinstance(exc, HTTPError):
            receipt.update(status=exc.code, headers=dict(exc.headers))
        save_new(output / (pmid + '_' + kind + '_http_receipt.json'), receipt)
        raise
    save_new(output / (pmid + '_' + kind + '_http_receipt.json'), receipt)
    return output / (pmid + suffix)


class BudgetPharos(PharosClient):
    """Native GraphQL validation with counted, no-redirect single HTTP attempts."""
    def __init__(self, folder, total, *, transport=None):
        self.folder, self.total, self.attempts = Path(folder), total, 0
        self.injected_transport = transport
        super().__init__(endpoint=ENDPOINT, cache_dir=None, timeout=POLICY['pharos_timeout_seconds'],
                         retries=0, transport=self._counted)

    def _counted(self, payload):
        if (self.attempts >= POLICY['maximum_pharos_attempts_per_pair']
                or self.total['attempts'] >= POLICY['maximum_pharos_attempts_total']):
            raise BudgetExceeded('Fixed actual Pharos HTTP attempt budget exhausted; no retries or fallback.')
        self.attempts += 1; self.total['attempts'] += 1
        prefix = self.folder / ('pharos_attempt_%02d' % self.attempts)
        receipt = {'started_at': utcnow(), 'endpoint': ENDPOINT, 'request': payload,
                   'attempt': self.attempts, 'global_attempt': self.total['attempts'], 'redirects': False, 'retries': False}
        save_new(str(prefix) + '_started.json', receipt)
        body = b''
        try:
            if self.injected_transport is not None:
                response = self.injected_transport(payload)
                body = canonical(response).encode()
                receipt['transport'] = 'invented_control_dependency_injection'
            else:
                context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or None)
                opener = build_opener(HTTPSHandler(context=context), original.NoRedirect())
                request = Request(ENDPOINT, data=canonical(payload).encode(), method='POST',
                                  headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                                           'Accept-Encoding': 'identity', 'User-Agent': 'BioGraph-Steward/IntAct-fresh-fidelity'})
                with opener.open(request, timeout=self.timeout) as incoming:
                    receipt.update(status=incoming.status, final_url=incoming.geturl(), headers=dict(incoming.headers))
                    if incoming.status != 200 or incoming.geturl() != ENDPOINT:
                        raise ValueError('Pharos must return exact HTTP200 without redirect.')
                    if incoming.headers.get('Content-Encoding', 'identity').lower() not in {'', 'identity'}:
                        raise ValueError('Unsupported compressed Pharos response.')
                    declared = incoming.headers.get('Content-Length')
                    if declared is not None and (not declared.isascii() or not declared.isdecimal()):
                        raise ValueError('Invalid Pharos Content-Length.')
                    if declared is not None and int(declared) > POLICY['maximum_pharos_response_bytes']:
                        raise BudgetExceeded('Pharos response byte budget exceeded.')
                    try:
                        body = incoming.read(POLICY['maximum_pharos_response_bytes'] + 1)
                    except IncompleteRead as exc:
                        body = exc.partial[:POLICY['maximum_pharos_response_bytes'] + 1]
                        raise ValueError('Incomplete Pharos response; partial bytes preserved.') from exc
                    if len(body) > POLICY['maximum_pharos_response_bytes']:
                        raise BudgetExceeded('Pharos response byte budget exceeded.')
                    if not body or (declared is not None and int(declared) != len(body)):
                        raise ValueError('Empty, oversized or incomplete Pharos response.')
                response = json.loads(body)
            receipt['outcome'] = 'response_preserved_native_validation_pending'
            return response
        except BaseException as exc:
            receipt.update(outcome='failed', error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            with Path(str(prefix) + '_body.json').open('xb') as stream:
                stream.write(body)
            receipt.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            save_new(str(prefix) + '_receipt.json', receipt)


def inspect_sources(freeze, freeze_path, expected_sha, output):
    records, ledger, xml, files, catalog, studies = [], [], {}, {}, [], []
    for pmid in FRESH:
        verify_freeze(freeze_path, expected_sha)
        save_new(output / (pmid + '_exposure_started.json'), {'publication_id': pmid, 'created_at': utcnow(),
                 'execution_freeze_sha256': expected_sha, 'state': 'consumed_before_source_retrieval_or_read'})
        source = fetch_source(pmid, 'mitab', output)
        verify_freeze(freeze_path, expected_sha)
        provenance = fetch_source(pmid, 'xml', output)
        verify_freeze(freeze_path, expected_sha)
        parsed = original.java_read(freeze['mitab_runtime'], 'org.biograph.IntactReader', source, output / (pmid + '_reader'))
        verify_freeze(freeze_path, expected_sha)
        xml_parsed = original.java_read(freeze['xml_runtime'], 'org.biograph.IntactXmlReader', provenance, output / (pmid + '_xml_reader'))
        verify_freeze(freeze_path, expected_sha)
        if len(parsed.stdout) > POLICY['maximum_reader_stdout_bytes'] or len(xml_parsed.stdout) > POLICY['maximum_reader_stdout_bytes']:
            raise ValueError('Reader output bound exceeded; retained source and streams, no score.')
        if parsed.returncode:
            raise ValueError('Official MITAB reader failed; preserve consumed status.')
        raw = source.read_bytes(); rows = [json.loads(line) for line in parsed.stdout.decode('utf-8').splitlines()]
        lines = source_lines(raw)
        if len(rows) != len(lines):
            raise ValueError('Every physical source row requires one official reader record.')
        artifact = hashlib.sha256(raw).hexdigest(); refs = []
        for number, (line, row) in enumerate(zip(lines, rows), 1):
            if row.get('line_number') != number or row.get('raw_line') != line or row.get('raw_cells') != line.split('\t'):
                raise ValueError('Raw source cells, line or side orientation differs.')
            item = {'publication_id': 'pubmed:' + pmid, 'artifact_sha256': artifact, 'release': '2026-10-17',
                    'source_line': number, 'raw_row_sha256': hashlib.sha256(line.encode()).hexdigest(), **assess(row, pmid)}
            ledger.append(item)
            records.append({'publication_id': item['publication_id'], 'artifact_sha256': artifact,
                            'source_file': 'source/' + pmid + '.txt', 'reader_file': 'reader/' + pmid + '.jsonl', 'reader_record': row})
            refs.append({'ledger': item, 'reader_record': row})
        xml_rows, summary, _ = parse_transport(xml_parsed.stdout)
        if (assess_development_xml(summary, xml_rows, xml_parsed.returncode)['quarantined']
                or summary.get('input_sha256') != sha(provenance) or summary.get('input_bytes') != provenance.stat().st_size):
            raise ValueError('Official XML source fingerprint or diagnostics block reference projection.')
        comparison = compare_identity_projection(pmid, refs, xml_rows)
        save_new(output / (pmid + '_identity_projection.json'), comparison)
        errors = comparison['join_errors'] + assess_alignment(comparison['development_identity_comparison'], refs, xml_rows)
        if errors:
            save_new(output / (pmid + '_projection_errors.json'), errors)
            raise ValueError('Unresolved corrected cross-format comparison; stop unscored, no repair.')
        xml[pmid] = xml_rows
        files.update({'source/' + pmid + '.txt': raw, 'reader/' + pmid + '.jsonl': parsed.stdout,
                      'provenance/' + pmid + '.xml': provenance.read_bytes(),
                      'provenance/' + pmid + '_reader.jsonl': xml_parsed.stdout})
        for kind in ('mitab', 'xml'):
            name = pmid + '_' + kind + '_http_receipt.json'
            files['provenance/' + name] = (output / name).read_bytes()
        catalog.append({'publication_id': 'pubmed:' + pmid, 'artifact_sha256': artifact,
                        'source_file': 'source/' + pmid + '.txt', 'reader_file': 'reader/' + pmid + '.jsonl',
                        'reader_sha256': hashlib.sha256(parsed.stdout).hexdigest()})
        studies.append({'publication_id': 'pubmed:' + pmid, 'physical_rows': len(rows),
                        'source_evidence_rows': sum(ref['ledger']['kind'] == 'evidence' for ref in refs),
                        'source_eligible_rows': sum(ref['ledger']['eligible'] for ref in refs),
                        'xml_evidence_objects': len(xml_rows)})
    return records, ledger, xml, files, catalog, studies


def publication_extras(freeze, output):
    audit = (output / 'provenance_overlap.json').read_bytes()
    return ({'fresh_selection.json': SELECTION.read_bytes(), 'consumed_inventory.json': INVENTORY.read_bytes(),
             'provenance_overlap.json': audit},
            {'fresh_selection_sha256': SELECTION_SHA, 'consumed_inventory_sha256': INVENTORY_SHA,
             'provenance_overlap_sha256': hashlib.sha256(audit).hexdigest()})


def controls(output):
    output = Path(output); output.mkdir(exist_ok=False)
    stream = io.StringIO(); suite = unittest.TestSuite()
    sys.path.insert(0, str(ROOT / 'tests'))
    for name in ('tests.test_intact_fresh_execution', 'tests.test_intact_fresh_publication',
                 'tests.test_intact_identity_projection', 'tests.test_intact_final_execution'):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (output / 'controls.log').write_text(stream.getvalue())
    report = seal({'format': 'biograph-steward.intact-fresh-controls.v1', 'created_at': utcnow(),
                   'status': 'passed' if result.wasSuccessful() and not result.skipped else 'failed',
                   'tests_run': result.testsRun, 'skips': len(result.skipped), 'fresh_sources_accessed': False,
                   'implementation_sha256': code_bindings(), 'log_sha256': sha(output / 'controls.log')})
    save_new(output / 'report.json', report)
    return report


def _verified_report(path, fmt):
    path = ordinary(path); value = load_json(path)
    if (value.get('format') != fmt or value.get('status') != 'passed'
            or value.get('fresh_sources_accessed') is not False
            or value.get('content_sha256') != digest({key: val for key, val in value.items() if key != 'content_sha256'})
            or value.get('implementation_sha256') != code_bindings()):
        raise ValueError('A passing exact-implementation pre-access report is required: ' + str(path))
    if fmt == 'biograph-steward.intact-fresh-controls.v1':
        if (type(value.get('tests_run')) is not int or value['tests_run'] < 1 or value.get('skips') != 0
                or sha(ordinary(path.parent / 'controls.log')) != value.get('log_sha256')):
            raise ValueError('Complete nonempty controls and their unchanged log are required.')
    if fmt == 'biograph-steward.intact-fresh-adapter-rehearsal.v1':
        result_path = ordinary(path.parent / 'execution/flow_result.json')
        contract_path = ordinary(path.parent / 'rehearsal_freeze.json')
        if (sha(result_path) != value.get('flow_result_sha256')
                or sha(contract_path) != value.get('rehearsal_freeze_sha256')):
            raise ValueError('Rehearsal result or complete contract bytes changed.')
        result, contract = load_json(result_path), load_json(contract_path)
        den = result.get('source_accounting', {}).get('final_assessment_eligible_rows')
        evaluation = result.get('row_evaluation') or {}
        checks = (evaluation.get('global_checks') or []) + (result.get('source_preservation_checks') or [])
        if (result.get('status') != 'passed' or result.get('assessment_split') != 'consumed_reserved_replay'
                or type(den) is not int or den < 1 or len(evaluation.get('rows') or []) != den
                or result.get('metrics') != value.get('metrics') or result.get('source_accounting') != value.get('source_accounting')
                or result.get('flow_failures') or not checks or any(item.get('passed') is not True for item in checks)
                or any(row.get('completed') is not True or row.get('strict_fidelity') is not True for row in evaluation.get('rows', []))
                or any(result.get('metrics', {}).get(name, {}).get(key) != den
                       for name in ('coverage', 'strict_fidelity') for key in ('numerator', 'denominator'))
                or contract.get('implementation_sha256') != code_bindings() or contract.get('flow_policy') != POLICY
                or contract.get('fresh_sources_accessed') is not False
                or result.get('content_sha256') != digest({k: v for k, v in result.items() if k != 'content_sha256'})
                or contract.get('content_sha256') != digest({k: v for k, v in contract.items() if k != 'content_sha256'})):
            raise ValueError('Complete passing rehearsal rows, output inventory and source preservation are required.')
    return value


def rehearse(output, historical_code_receipt, saved_cohort_snapshot, flow_controls):
    """Run the same flow hooks on explicitly consumed bytes, without networking.

    Fresh-split publication/capture guards are covered by invented controls.
    Captured real PMIDs keep their consumed split and original source identities.
    """
    _verified_report(flow_controls, 'biograph-steward.intact-fresh-controls.v1')
    selection_metadata()
    output = Path(output).absolute(); output.mkdir(exist_ok=False)
    base = consumed_flow.prepare(output / 'consumed_base', historical_code_receipt, allow_pharos=False)
    base_path = output / 'consumed_base/consumed_flow_freeze.json'; base_sha = sha(base_path)
    snapshot_path = ordinary(saved_cohort_snapshot)
    # These inputs are already consumed. Hash this explicitly supplied snapshot,
    # never discover an arbitrary source directory or inspect a fresh reference.
    freeze = seal({'format': 'biograph-steward.intact-fresh-adapter-rehearsal-freeze.v1',
        'created_at': utcnow(), 'pre_captured_stream_access': True,
        'fresh_sources_accessed': False, 'python_runtime': _python(),
        'implementation_sha256': code_bindings(), 'flow_policy': deepcopy(POLICY),
        'consumed_base_contract': str(base_path), 'consumed_base_sha256': base_sha,
        'saved_cohort_snapshot': str(snapshot_path), 'saved_cohort_sha256': sha(snapshot_path),
        'consumed_inventory_sha256': INVENTORY_SHA, 'flow_controls_sha256': sha(ordinary(flow_controls))})
    freeze_path = output / 'rehearsal_freeze.json'; save_new(freeze_path, freeze)
    freeze_sha = sha(freeze_path)
    execution = output / 'execution'; execution.mkdir()
    save_new(execution / 'started.json', {'created_at': utcnow(), 'rehearsal_freeze_sha256': freeze_sha,
        'assessment_split': 'consumed_reserved_replay', 'fresh_sources_accessed': False})
    clients = []

    def verify(_path, _expected):
        if (str(ordinary(_path)) != str(base_path) or _expected != base_sha
                or sha(freeze_path) != freeze_sha or code_bindings() != freeze['implementation_sha256']
                or _python() != freeze['python_runtime'] or sha(snapshot_path) != freeze['saved_cohort_sha256']
                or sha(INVENTORY) != INVENTORY_SHA or sha(ordinary(flow_controls)) != freeze['flow_controls_sha256']):
            raise ValueError('Consumed rehearsal contract, code, runtime or supplied inputs changed.')
        consumed_flow.verify_contract(base_path, base_sha)

    def loader(_freeze, _path, _expected, folder):
        verify(_path, _expected)
        records, ledger, xml, files, catalog, studies, errors = consumed_flow.inspect_captured(base, folder)
        if errors:
            raise ValueError('Corrected consumed reference comparison still has errors.')
        return records, ledger, xml, files, catalog, studies

    def auditor(xml, records, inventory):
        value = complete_alias_audit(xml, records, inventory)
        value['would_exclude_known_consumed_publication_ids'] = value['excluded_publication_ids']
        value['excluded_publication_ids'] = []
        value.update(retained_for_consumed_engineering_replay=True,
                     final_study_exclusion_policy_not_applied_to_consumed_rehearsal=True)
        return value

    def extras(_freeze, folder):
        return ({'origin_execution_freeze.json': consumed_flow.ORIGIN.read_bytes(),
                 'historical_code_archive_receipt.json': ordinary(base['historical_code_receipt']).read_bytes(),
                 'fresh_adapter_rehearsal.json': freeze_path.read_bytes(),
                 'consumed_inventory_v2.json': INVENTORY.read_bytes(),
                 'provenance_overlap.json': (folder / 'provenance_overlap.json').read_bytes()},
                {'origin_reserved_freeze_sha256': consumed_flow.ORIGIN_SHA,
                 'historical_code_receipt_sha256': base['historical_code_receipt_sha256'],
                 'fresh_adapter_rehearsal_sha256': freeze_sha})

    def factory(_folder):
        from biograph_steward.construction import _RecordedClient, verify_construction_snapshot
        snapshot = load_json(snapshot_path); verify_construction_snapshot(snapshot)
        client = _RecordedClient(snapshot); clients.append(client)
        if len(client.envelopes) > POLICY['maximum_pharos_attempts_per_pair']:
            raise ValueError('Consumed response trace exceeds the fixed per-pair request budget.')
        return client

    active = {**base, 'mitab_runtime': base['reader_runtime'], 'xml_runtime': base['xml_reader_runtime'],
              'consumed_inventory': str(INVENTORY)}
    try:
        result = original._execute(active, base_path, base_sha, execution, source_loader=loader,
            lineage_auditor=auditor, freeze_verifier=verify, pharos_factory=factory,
            publication_extras=extras, inspection_status='consumed_development_inspected_not_final_score',
            eligible_check=check_work_budget, fatal_exception=BudgetExceeded)
        if any(len(client.records) != len(client.envelopes) for client in clients):
            raise ValueError('Not every supplied consumed Pharos response was replayed exactly.')
        save_new(execution / 'flow_result.json', seal(result))
        report = seal({'format': 'biograph-steward.intact-fresh-adapter-rehearsal.v1', 'created_at': utcnow(),
            'status': 'passed' if result['status'] == 'passed' else 'failed',
            'fresh_sources_accessed': False, 'implementation_sha256': code_bindings(),
            'assessment_split': 'consumed_reserved_replay', 'new_IntAct_retrievals': 0,
            'new_Java_reader_calls': 0, 'new_Pharos_calls': 0,
            'replayed_Pharos_requests': sum(len(client.records) for client in clients),
            'rehearsal_freeze_sha256': freeze_sha, 'flow_result_sha256': sha(execution / 'flow_result.json'),
            'metrics': result['metrics'], 'source_accounting': result['source_accounting'],
            'scope': 'Corrected source comparison, full qualified aliases and ordinary construction/answer/export hooks on consumed inputs. Fresh transport/envelope paths tested with invented controls, not real fresh sources.'})
        save_new(output / 'report.json', report)
        return report
    except BaseException as exc:
        save_new(output / 'failure.json', seal({'format': 'biograph-steward.intact-fresh-adapter-rehearsal.v1',
            'created_at': utcnow(), 'status': 'failed', 'fresh_sources_accessed': False,
            'error_type': type(exc).__name__, 'error': str(exc), 'rehearsal_freeze_sha256': freeze_sha}))
        raise


def prepare(output, reader_controls, xml_controls, flow_controls, rehearsal_report, independent_review):
    selection_metadata()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or ACCESS_MARKER.exists() or ACCESS_MARKER.is_symlink():
        raise ValueError('Use one new immutable fresh freeze before any panel access.')
    mc, xc = load_json(ordinary(reader_controls)), load_json(ordinary(xml_controls))
    verify_controls_report(mc); verify_xml_controls(xc)
    mr, xr = original._runtime(mc), original._runtime(xc, True)
    _verified_report(flow_controls, 'biograph-steward.intact-fresh-controls.v1')
    _verified_report(rehearsal_report, 'biograph-steward.intact-fresh-adapter-rehearsal.v1')
    review = _verified_report(independent_review, 'biograph-steward.intact-fresh-independent-preaccess-review.v1')
    if (review.get('flow_controls_sha256') != sha(ordinary(flow_controls))
            or review.get('rehearsal_report_sha256') != sha(ordinary(rehearsal_report))):
        raise ValueError('Independent review must bind the actual controls and consumed rehearsal.')
    if sha(ordinary(ARCHIVE)) != ARCHIVE_SHA:
        raise ValueError('Pre-adaptation implementation archive changed.')
    for item in load_json(ARCHIVE)['files']:
        if sha(ordinary(ROOT / item['archived_path'])) != item['sha256']:
            raise ValueError('Preserved pre-adaptation implementation changed.')
    if sha(ROOT / original.PROTOCOL) != PROTOCOL_SHA or sha(ROOT / original.AMENDMENT) != AMENDMENT_SHA:
        raise ValueError('Original protocol or amendment changed.')
    paths = [ordinary(path) for path in (reader_controls, xml_controls, flow_controls, rehearsal_report, independent_review,
              SELECTION, INVENTORY, ARCHIVE, ROOT / original.PROTOCOL, ROOT / original.AMENDMENT, LICENSE_PATH)]
    bindings = code_bindings()
    output.mkdir(exist_ok=False)
    # Exact code archive only: never discover reference/source directories.
    for name, pin in bindings.items():
        path = ordinary(name); target = output / 'implementation' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(path.read_bytes())
        if sha(target) != pin:
            raise ValueError('Could not preserve exact frozen implementation.')
    freeze = seal({'format': FORMAT, 'created_at': utcnow(), 'pre_access': True, 'assessment_split': SPLIT,
        'publication_ids': list(FRESH), 'python_runtime': _python(), 'implementation_sha256': bindings,
        'metadata_sha256': {str(path): sha(path) for path in paths},
        'source_urls': {pmid: {kind: base + pmid + ('.txt' if kind == 'mitab' else '.xml')
                              for kind, base in SOURCE_BASES.items()} for pmid in FRESH},
        'controls_report': str(ordinary(reader_controls)), 'xml_controls_report': str(ordinary(xml_controls)),
        'flow_controls_report': str(ordinary(flow_controls)), 'rehearsal_report': str(ordinary(rehearsal_report)),
        'independent_review_report': str(ordinary(independent_review)),
        'mitab_runtime': mr, 'xml_runtime': xr, 'consumed_inventory': str(INVENTORY),
        'fresh_selection_sha256': SELECTION_SHA, 'consumed_inventory_sha256': INVENTORY_SHA,
        'protocol_sha256': PROTOCOL_SHA, 'amendment_sha256': AMENDMENT_SHA,
        'flow_policy': deepcopy(POLICY), 'access_marker': str(ACCESS_MARKER),
        'scientific_accuracy_measured': False, 'independent_validation_performed': False,
        'source_fidelity_only': True, 'study_independence': 'unverified'})
    save_new(output / 'execution_freeze.json', freeze)
    return freeze


def verify_freeze(path, expected_sha):
    path = ordinary(path)
    if sha(path) != expected_sha:
        raise ValueError('Externally recorded complete fresh freeze SHA differs.')
    freeze = load_json(path)
    fields = {'format', 'created_at', 'pre_access', 'assessment_split', 'publication_ids', 'python_runtime',
              'implementation_sha256', 'metadata_sha256', 'source_urls', 'controls_report', 'xml_controls_report',
              'flow_controls_report', 'rehearsal_report', 'independent_review_report', 'mitab_runtime', 'xml_runtime',
              'consumed_inventory', 'fresh_selection_sha256', 'consumed_inventory_sha256', 'protocol_sha256',
              'amendment_sha256', 'flow_policy', 'access_marker', 'scientific_accuracy_measured',
              'independent_validation_performed', 'source_fidelity_only', 'study_independence', 'content_sha256'}
    urls = {pmid: {kind: base + pmid + ('.txt' if kind == 'mitab' else '.xml')
                   for kind, base in SOURCE_BASES.items()} for pmid in FRESH}
    if (freeze.get('format') != FORMAT or freeze.get('assessment_split') != SPLIT
            or set(freeze) != fields or freeze.get('source_urls') != urls
            or freeze.get('pre_access') is not True or freeze.get('publication_ids') != list(FRESH)
            or freeze.get('fresh_selection_sha256') != SELECTION_SHA or freeze.get('consumed_inventory_sha256') != INVENTORY_SHA
            or freeze.get('flow_policy') != POLICY or freeze.get('access_marker') != str(ACCESS_MARKER)
            or freeze.get('scientific_accuracy_measured') is not False or freeze.get('independent_validation_performed') is not False
            or freeze.get('source_fidelity_only') is not True or freeze.get('study_independence') != 'unverified'
            or freeze.get('protocol_sha256') != PROTOCOL_SHA or freeze.get('amendment_sha256') != AMENDMENT_SHA
            or freeze.get('consumed_inventory') != str(INVENTORY)
            or freeze.get('content_sha256') != digest({key: value for key, value in freeze.items() if key != 'content_sha256'})
            or freeze.get('implementation_sha256') != code_bindings() or freeze.get('python_runtime') != _python()):
        raise ValueError('Fresh freeze scope, semantics, implementation or runtime differs.')
    expected_metadata = {str(ordinary(item)) for item in (SELECTION, INVENTORY, ARCHIVE,
        ROOT / original.PROTOCOL, ROOT / original.AMENDMENT, LICENSE_PATH,
        freeze['controls_report'], freeze['xml_controls_report'], freeze['flow_controls_report'],
        freeze['rehearsal_report'], freeze['independent_review_report'])}
    if set(freeze['metadata_sha256']) != expected_metadata:
        raise ValueError('Complete exact fresh metadata inventory is required.')
    for name, pin in freeze['metadata_sha256'].items():
        if sha(ordinary(name)) != pin:
            raise ValueError('Frozen fresh metadata changed: ' + name)
    for name, pin in freeze['implementation_sha256'].items():
        if sha(ordinary(path.parent / 'implementation' / Path(name).relative_to(ROOT))) != pin:
            raise ValueError('Frozen source implementation archive changed.')
    if original._runtime(load_json(freeze['controls_report'])) != freeze['mitab_runtime'] or original._runtime(load_json(freeze['xml_controls_report']), True) != freeze['xml_runtime']:
        raise ValueError('Exact official reader runtime changed.')
    return freeze


def execute(path, expected_sha):
    path = ordinary(path); freeze = verify_freeze(path, expected_sha)
    output = path.parent / 'execution'
    if output.exists() or output.is_symlink():
        raise ValueError('Fresh execution already started; preserve exposure without rerun.')
    save_new(ACCESS_MARKER, {'created_at': utcnow(), 'execution_freeze_sha256': expected_sha,
        'publication_ids': list(FRESH), 'state': 'one_shot_panel_consumed_before_any_source_access'})
    output.mkdir(exist_ok=False)
    save_new(output / 'started.json', {'created_at': utcnow(), 'execution_freeze_sha256': expected_sha,
                                      'assessment_split': SPLIT, 'no_replacement': True})
    total = {'attempts': 0}
    try:
        result = original._execute(freeze, path, expected_sha, output, source_loader=inspect_sources,
            lineage_auditor=complete_alias_audit, freeze_verifier=verify_freeze,
            pharos_factory=lambda folder: BudgetPharos(folder, total), publication_extras=publication_extras,
            inspection_status='fresh_inspected_not_fidelity_scored', eligible_check=check_work_budget,
            fatal_exception=BudgetExceeded)
        result.update(format=RESULT_FORMAT, Pharos_attempts=total['attempts'], fresh_sources_accessed=True,
                      fresh_assessment_completed=True, independent_validation_performed=False)
        save_new(output / 'report.json', seal(result))
        return result
    except BaseException as exc:
        save_new(output / 'failure.json', seal({'format': RESULT_FORMAT, 'created_at': utcnow(),
            'status': 'stopped_unscored_preserved_exposure', 'exception_type': type(exc).__name__, 'error': str(exc),
            'assessment_split': SPLIT, 'execution_freeze_sha256': expected_sha, 'metrics': None,
            'publication_ids': list(FRESH),
            'selected_study_access': [{'publication_id': pmid,
                'exposure_started': (output / (pmid + '_exposure_started.json')).is_file(),
                'mitab_receipt': (output / (pmid + '_mitab_http_receipt.json')).is_file(),
                'xml_receipt': (output / (pmid + '_xml_http_receipt.json')).is_file()} for pmid in FRESH],
            'Pharos_attempts': total['attempts'], 'panel_may_now_be_consumed': True, 'no_replacement': True,
            'scientific_accuracy_measured': False}))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('controls'); c.add_argument('--output', required=True)
    r = sub.add_parser('rehearse')
    for name in ('output', 'historical-code-receipt', 'saved-cohort-snapshot', 'flow-controls'):
        r.add_argument('--' + name, required=True)
    p = sub.add_parser('prepare')
    for name in ('output', 'reader-controls', 'xml-controls', 'flow-controls', 'rehearsal-report', 'independent-review'):
        p.add_argument('--' + name, required=True)
    e = sub.add_parser('execute'); e.add_argument('--freeze', required=True); e.add_argument('--expected-sha256', required=True)
    args = parser.parse_args(argv)
    result = (controls(args.output) if args.command == 'controls' else rehearse(args.output, args.historical_code_receipt,
        args.saved_cohort_snapshot, args.flow_controls) if args.command == 'rehearse' else prepare(args.output, args.reader_controls,
        args.xml_controls, args.flow_controls, args.rehearsal_report, args.independent_review) if args.command == 'prepare'
        else execute(args.freeze, args.expected_sha256))
    print(json.dumps({'status': result.get('status', 'frozen_before_source_access'), 'format': result['format']}))


if __name__ == '__main__':
    main()
