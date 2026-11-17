"""Invented source/reader rows only; fresh PMIDs are labels, not source access."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.assay_attachment import attach_assay, load_publication
from biograph_steward.assay_questions import answer_assay_question
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.graph import save_run
from biograph_steward.intact_evidence import build_evidence as development_build
from biograph_steward.intact_final_publication import (
    FRESH, FRESH_SPLIT, FRESH_FORMAT, FRESH_ALIAS_RULE, FORMAT, CONSUMED_FORMAT,
    FRESH_SELECTION_SHA, CONSUMED_INVENTORY_SHA, build_evidence, publish_material, load_projection,
)
from biograph_steward.questions import save_answer
from scripts.evaluate_intact_evidence_fidelity import evaluate_rows
from test_assay_attachment import cohort_snapshot
from test_intact_final_publication import ROOT, RESERVED, encode, seal, sha, material


def _replace_ids(value):
    if isinstance(value, dict):
        return {_replace_ids(key): _replace_ids(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_ids(item) for item in value]
    if isinstance(value, str):
        for old, new in zip(RESERVED, FRESH):
            value = value.replace(old, new)
    return value


def _rebind(files, bindings, inspection):
    bindings['execution_freeze_sha256'] = sha(files['execution_freeze.json'])
    inspection['bindings']['execution_freeze_sha256'] = bindings['execution_freeze_sha256']
    files['inspection_report.json'] = encode(inspection)
    bindings['result_sha256'] = sha(files['inspection_report.json'])
    bindings['provenance_overlap_sha256'] = sha(files['provenance_overlap.json'])


def fresh_material(*, empty=False):
    """Adapt the existing invented fixture; only tracked safe metadata is read."""
    files, _, bindings, inspection, records, ledger = material(empty=empty)
    files = {name: raw for name, raw in files.items() if not name.startswith(('source/', 'reader/'))}
    bindings, records, ledger = map(_replace_ids, (bindings, records, ledger))
    catalog = []
    for pmid, record, item in zip(FRESH, records, ledger):
        row = record['reader_record']
        source_name, reader_name = 'source/' + pmid + '.txt', 'reader/' + pmid + '.jsonl'
        files[source_name] = (row['raw_line'] + '\n').encode()
        files[reader_name] = (json.dumps(row) + '\n').encode()
        source_sha, reader_sha = sha(files[source_name]), sha(files[reader_name])
        record['artifact_sha256'] = source_sha
        item['artifact_sha256'] = source_sha
        item['raw_row_sha256'] = sha(row['raw_line'].encode())
        bindings['source_sha256'][pmid] = source_sha
        bindings['reader_sha256'][pmid] = reader_sha
        catalog.append({'publication_id': 'pubmed:' + pmid, 'artifact_sha256': source_sha,
                        'source_file': source_name, 'reader_file': reader_name, 'reader_sha256': reader_sha})
    files['row_ledger.jsonl'] = b''.join((json.dumps(item) + '\n').encode() for item in ledger)
    bindings['ledger_sha256'] = sha(files['row_ledger.jsonl'])
    files['fresh_selection.json'] = (ROOT / 'docs/evaluations/intact_fresh_reference_20261027_selection.json').read_bytes()
    files['consumed_inventory.json'] = (ROOT / 'docs/evaluations/intact_consumed_inventory_v2_20261027.json').read_bytes()
    assert sha(files['fresh_selection.json']) == FRESH_SELECTION_SHA
    assert sha(files['consumed_inventory.json']) == CONSUMED_INVENTORY_SHA
    aliases = []
    for pmid in FRESH:
        xml = b'<invented source="synthetic-only"/>\n'
        files['provenance/' + pmid + '.xml'] = xml
        evidence = {'identifiers': [
            {'database': {'name': 'intact'}, 'id': 'INVENTED-' + pmid,
             'qualifier': {'mi_id': 'MI:0356'}}], 'xrefs': []}
        stream = [
            {'format': 'biograph-steward.intact-xml-evidence.v1', 'record_kind': 'evidence',
             'evidence_sequence': 1, 'evidence': evidence},
            {'format': 'biograph-steward.intact-xml-evidence.v1', 'record_kind': 'file_summary',
             'input_sha256': sha(xml), 'input_bytes': len(xml), 'evidence_count': 1}]
        files['provenance/' + pmid + '_reader.jsonl'] = b''.join(
            (json.dumps(row) + '\n').encode() for row in stream)
        aliases.append({'publication_id': pmid, 'evidence_sequence': 1,
                        'identity_ids': [['intact', 'INVENTED-' + pmid]],
                        'exact_consumed_alias_overlap': []})
    audit = {'format': 'biograph-steward.intact-complete-qualified-alias-audit.v1',
        'status': 'bounded_audit_complete_independence_unverified',
        'complete_identity_aliases_checked': True, 'consumed_inventory_sha256': CONSUMED_INVENTORY_SHA,
        'qualified_alias_rule': FRESH_ALIAS_RULE, 'full_qualified_alias_evidence': aliases,
        'excluded_publication_ids': [], 'ambiguous_dataset_statements': [], 'study_independence': 'unverified'}
    files['provenance_overlap.json'] = encode(audit)
    bindings.update(assessment_split=FRESH_SPLIT, publication_ids=list(FRESH),
        fresh_selection_sha256=FRESH_SELECTION_SHA, consumed_inventory_sha256=CONSUMED_INVENTORY_SHA)
    freeze = {'format': 'biograph-steward.intact-fresh-execution-freeze.v1',
        'publication_ids': list(FRESH), 'assessment_split': FRESH_SPLIT, 'pre_access': True,
        'fresh_selection_sha256': FRESH_SELECTION_SHA, 'consumed_inventory_sha256': CONSUMED_INVENTORY_SHA,
        'scientific_accuracy_measured': False, 'independent_validation_performed': False,
        'invented_test_fixture': True}
    files['execution_freeze.json'] = encode(seal(freeze))
    inspection = deepcopy(inspection)
    inspection.update(status='fresh_inspected_not_fidelity_scored', publication_ids=list(FRESH))
    _rebind(files, bindings, inspection)
    return files, catalog, bindings, inspection, records, ledger


class FreshPublicationTests(unittest.TestCase):
    def test_separate_fresh_envelope_preserves_the_complete_ordinary_flow(self):
        files, catalog, bindings, inspection, records, ledger = fresh_material()
        before = deepcopy((files, catalog, bindings, inspection))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            manifest = publish_material(files, catalog, bindings, inspection, root / 'publication')
            self.assertEqual(manifest['format'], FRESH_FORMAT)
            _, evidence, reopened = load_publication(root / 'publication')
            self.assertEqual(len(evidence['observations']), 4)
            self.assertTrue(evidence['summary']['source_fidelity_only'])
            self.assertFalse(evidence['summary']['independent_biological_validation_performed'])
            self.assertFalse(evidence['summary']['biological_prediction_improvement_measured'])
            self.assertIn('Fresh source-fidelity assessment', reopened['index.html'].decode())
            save_run(cohort_snapshot(), root / 'cohort')
            graph = attach_assay(root / 'cohort', root / 'publication', root / 'attached')
            answer = answer_assay_question(graph, source_run='attached')
            save_answer(answer, root / 'answer')
            export_packet(root / 'attached', root / 'packet')
            load_packet(root / 'packet')
            exported = [json.loads(line) for line in (root / 'packet/assay_observations.jsonl').read_text().splitlines()]
            answer_export = [json.loads(line) for line in (root / 'answer/assay_evidence.jsonl').read_text().splitlines()]
            references = [{'ledger': item, 'reader_record': record['reader_record']}
                          for item, record in zip(ledger, records)]
            evaluated = evaluate_rows(references, graph['assay_observations'], answer['results'],
                exported, answer_export, (root / 'answer/report.html').read_text(), graph_edges=graph['edges'])
            self.assertEqual(len(evaluated['rows']), 4)
            self.assertTrue(all(row['strict_fidelity'] for row in evaluated['rows']))
            for name in ('fresh_selection.json', 'consumed_inventory.json', 'provenance_overlap.json'):
                copied = list((root / 'packet').rglob(name))
                self.assertTrue(copied, name)
                self.assertTrue(all(path.read_bytes() == files[name] for path in copied))
        self.assertEqual((files, catalog, bindings, inspection), before)

    def test_empty_eligibility_remains_a_complete_four_study_source_publication(self):
        files, catalog, bindings, inspection, _, _ = fresh_material(empty=True)
        with tempfile.TemporaryDirectory() as tmp:
            publish_material(files, catalog, bindings, inspection, Path(tmp).resolve() / 'publication')
            _, evidence, _ = load_publication(Path(tmp).resolve() / 'publication')
            self.assertEqual(evidence['summary']['primary_eligible'], 0)
            self.assertEqual(evidence['summary']['excluded_evidence'], 4)
            self.assertEqual(len(evidence['row_ledger']), 4)
            self.assertEqual(evidence['bindings']['publication_ids'], list(FRESH))

    def test_fresh_cannot_use_historical_envelopes_or_relax_old_development_guard(self):
        files, catalog, bindings, inspection, records, ledger = fresh_material()
        with self.assertRaises(ValueError):
            development_build(records, ledger, bindings)
        for changes in ({'assessment_split': 'reserved_final'},
                        {'assessment_split': 'consumed_reserved_replay'},
                        {'publication_ids': list(reversed(FRESH))},
                        {'fresh_selection_sha256': '0' * 64},
                        {'consumed_inventory_sha256': '0' * 64}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                build_evidence(records, ledger, {**bindings, **changes})
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve() / 'publication'
            manifest = publish_material(files, catalog, bindings, inspection, folder)
            _, _, complete = load_publication(folder)
            for envelope in (FORMAT, CONSUMED_FORMAT):
                with self.subTest(envelope=envelope), self.assertRaises(ValueError):
                    load_projection({**manifest, 'format': envelope}, complete)

    def test_missing_metadata_freeze_controls_or_alias_source_cannot_publish(self):
        files, catalog, bindings, inspection, _, _ = fresh_material()
        for name in ('fresh_selection.json', 'consumed_inventory.json', 'provenance_overlap.json',
                     'execution_freeze.json', 'xml_controls_report.json',
                     'provenance/' + FRESH[0] + '_reader.jsonl'):
            changed = dict(files)
            changed.pop(name)
            with self.subTest(missing=name), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp).resolve() / 'invalid'
                with self.assertRaises((ValueError, KeyError)):
                    publish_material(changed, catalog, bindings, inspection, output)
                self.assertFalse(output.exists())

    def test_resealed_freeze_cannot_change_claim_or_metadata_scope(self):
        for change in ({'pre_access': False}, {'scientific_accuracy_measured': True},
                       {'independent_validation_performed': True},
                       {'fresh_selection_sha256': '0' * 64},
                       {'consumed_inventory_sha256': '0' * 64}):
            files, catalog, bindings, inspection, _, _ = fresh_material()
            freeze = json.loads(files['execution_freeze.json'])
            freeze.pop('content_sha256')
            files['execution_freeze.json'] = encode(seal({**freeze, **change}))
            _rebind(files, bindings, inspection)
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                publish_material(files, catalog, bindings, inspection, Path(tmp).resolve() / 'invalid')

    def test_resealed_incomplete_or_unresolved_alias_audit_is_rejected(self):
        for change in ({'complete_identity_aliases_checked': False},
                       {'full_qualified_alias_evidence': []},
                       {'qualified_alias_rule': 'All xrefs without qualifications'},
                       {'consumed_inventory_sha256': '0' * 64},
                       {'ambiguous_dataset_statements': [{'reason': 'invented unresolved source link'}]},
                       {'study_independence': 'independent'}):
            files, catalog, bindings, inspection, _, _ = fresh_material()
            files['provenance_overlap.json'] = encode({**json.loads(files['provenance_overlap.json']), **change})
            _rebind(files, bindings, inspection)
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                publish_material(files, catalog, bindings, inspection, Path(tmp).resolve() / 'invalid')

    def test_generic_see_also_is_not_identity_but_complete_structural_overlap_requires_exclusion(self):
        for qualifier in ('MI:0361', 'MI:0356'):
            files, catalog, bindings, inspection, _, _ = fresh_material()
            inventory = json.loads(files['consumed_inventory.json'])
            database, accession = inventory['evidence_ids'][0]
            name = 'provenance/' + FRESH[0] + '_reader.jsonl'
            stream = [json.loads(line) for line in files[name].splitlines()]
            stream[0]['evidence']['xrefs'].append({'database': {'name': database}, 'id': accession,
                                                 'qualifier': {'mi_id': qualifier}})
            files[name] = b''.join((json.dumps(row) + '\n').encode() for row in stream)
            audit = json.loads(files['provenance_overlap.json'])
            if qualifier == 'MI:0356':
                entry = audit['full_qualified_alias_evidence'][0]
                entry['identity_ids'] = sorted(entry['identity_ids'] + [[database, accession]])
                entry['exact_consumed_alias_overlap'] = [[database, accession]]
            files['provenance_overlap.json'] = encode(audit)
            _rebind(files, bindings, inspection)
            with self.subTest(qualifier=qualifier), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                if qualifier == 'MI:0356':
                    with self.assertRaisesRegex(ValueError, 'study exclusion'):
                        publish_material(files, catalog, bindings, inspection, root / 'missing-exclusion')
                    self.assertFalse((root / 'missing-exclusion').exists())
                    audit['excluded_publication_ids'] = [FRESH[0]]
                    files['provenance_overlap.json'] = encode(audit)
                    _rebind(files, bindings, inspection)
                publish_material(files, catalog, bindings, inspection, root / 'publication')
                _, evidence, _ = load_publication(root / 'publication')
                # Study qualification affects assessment accounting; original
                # source observations remain in the complete publication.
                self.assertEqual(len(evidence['observations']), 4)

    def test_raw_xml_fingerprint_and_complete_reader_framing_are_required(self):
        for change in ('raw_xml', 'missing_summary', 'wrong_evidence_count'):
            files, catalog, bindings, inspection, _, _ = fresh_material()
            name = 'provenance/' + FRESH[0] + '_reader.jsonl'
            stream = [json.loads(line) for line in files[name].splitlines()]
            if change == 'raw_xml':
                files['provenance/' + FRESH[0] + '.xml'] += b'altered'
            elif change == 'missing_summary':
                stream.pop()
            else:
                stream[-1]['evidence_count'] = 2
            files[name] = b''.join((json.dumps(row) + '\n').encode() for row in stream)
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                publish_material(files, catalog, bindings, inspection, Path(tmp).resolve() / 'invalid')


if __name__ == '__main__':
    unittest.main()
