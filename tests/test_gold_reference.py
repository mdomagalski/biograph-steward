"""Reference alignment checks using invented labels, never biological outcomes."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.__main__ import main
from biograph_steward.client import digest, write_json
from biograph_steward.demo import demo_snapshot
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.gold_reference import align_reference, mapping_template
from biograph_steward.graph import save_run


class GoldReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.packet = self.root / 'run', self.root / 'packet'
        self.graph = save_run(demo_snapshot(), self.run)
        self.manifest = export_packet(self.run, self.packet)
        self.template = mapping_template(self.packet, self.root / 'template')
        self.reference, self.mapping = self.root / 'reference.tsv', self.root / 'mapping.json'
        self.output = self.root / 'aligned'

    def prepare(self, rows=None, contract=None, fields=None):
        value = deepcopy(contract or self.template)
        rows = rows if rows is not None else [
            {'reference_id': 'invented-1', 'label': 'invented_true', 'edge_id': self.graph['edges'][0]['id']}]
        with self.reference.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]),
                                    delimiter='\t' if value['delimiter'] == 'tab' else ',')
            writer.writeheader()
            writer.writerows(rows)
        value['reference'] = {'name': 'Invented reference', 'source': 'test fixture only',
                              'version': 'fixture-v1', 'sha256': sha(self.reference),
                              'kind': 'synthetic_fixture', 'baseline_version': None}
        write_json(self.mapping, value)
        return value

    def align(self):
        return align_reference(self.packet, self.reference, self.mapping, self.output)

    def records(self):
        return [json.loads(line) for line in (self.output / 'alignment.jsonl').read_text().splitlines()]

    def qualified(self, unit='evidence_edge', target=None):
        target = target or next(a for a in self.graph['assertions'] if len(a['evidence_edge_ids']) > 1)
        contract = deepcopy(self.template)
        contract.update(unit=unit, match_mode='qualified_identity', columns={key: key for key in
            ('reference_id', 'label', 'subject', 'predicate', 'object', 'kind', 'qualifiers')})
        row = {key: target[key] for key in ('subject', 'predicate', 'object', 'kind')}
        row.update(reference_id='invented-1', label='opaque-0', qualifiers=json.dumps(target['qualifiers']))
        return contract, row

    def test_exact_id_alignment_preserves_bytes_labels_and_missing_rows_without_scoring(self):
        rows = [{'reference_id': 'invented-1', 'label': '0', 'edge_id': self.graph['edges'][0]['id'], 'note': '=raw'},
                {'reference_id': 'invented-2', 'label': '', 'edge_id': 'edge:not-found', 'note': 'absent'}]
        self.prepare(rows)
        source = self.reference.read_bytes()
        report = self.align()
        self.assertEqual(report['summary']['status_counts'],
                         {'matched': 1, 'unmatched': 1, 'ambiguous': 0, 'reference_collision': 0})
        self.assertEqual(report['summary']['empty_label_rows'], 1)
        self.assertEqual(report['summary']['rows_scored'], 0)
        self.assertIsNone(report['metrics'])
        self.assertFalse(report['biological_accuracy_measured'])
        self.assertEqual(self.records()[0]['raw_label'], '0')
        self.assertEqual([r['raw_reference_row'] for r in self.records()], rows)
        self.assertEqual((self.output / 'reference_input.txt').read_bytes(), source)
        self.assertEqual(self.reference.read_bytes(), source)
        self.assertEqual(load_packet(self.output / 'baseline_packet'), load_packet(self.packet))
        for name, expected in report['files'].items():
            self.assertEqual(sha(self.output / name), expected)
        self.assertEqual(report['content_sha256'], digest({k: v for k, v in report.items() if k != 'content_sha256'}))

    def test_incomplete_template_is_not_an_organizer_reference(self):
        self.prepare()
        write_json(self.mapping, self.template)
        with self.assertRaisesRegex(ValueError, 'nonempty text'):
            self.align()
        self.assertFalse(self.output.exists())

    def test_wrong_baseline_artifact_version_and_invented_scoring_contract_rejected(self):
        original = self.prepare()
        variants = []
        for key in ('packet_id', 'snapshot_sha256', 'graph_sha256', 'database_version'):
            changed = deepcopy(original); changed['baseline'][key] = 'different'
            variants.append(changed)
        changed = deepcopy(original); changed['reference']['sha256'] = 'a' * 64; variants.append(changed)
        changed = deepcopy(original); changed['reference']['baseline_version'] = 'other-version'; variants.append(changed)
        changed = deepcopy(original); changed['purpose'] = 'scientific_accuracy'; variants.append(changed)
        changed = deepcopy(original); changed['reference']['kind'] = 'organizer_reference'; variants.append(changed)
        changed = deepcopy(original); changed['label_mapping'] = {'0': False}; variants.append(changed)
        for value in variants:
            with self.subTest(value=value):
                write_json(self.mapping, value)
                with self.assertRaises(ValueError):
                    self.align()
                self.assertFalse(self.output.exists())

    def test_table_shape_duplicate_headers_and_reference_ids_rejected(self):
        original = self.prepare()
        for text in ('reference_id\tlabel\tlabel\n', 'reference_id\tlabel\n1\t0\n',
                     'reference_id\tlabel\tedge_id\n1\t0\ta\textra\n',
                     'reference_id\tlabel\tedge_id\n1\t0\n',
                     'reference_id\tlabel\tedge_id\n1\t0\ta\n1\t1\tb\n',
                     'reference_id\tlabel\tedge_id\n 1\t0\ta\n'):
            with self.subTest(text=text):
                self.reference.write_text(text)
                value = deepcopy(original); value['reference']['sha256'] = sha(self.reference)
                write_json(self.mapping, value)
                with self.assertRaises(ValueError):
                    self.align()
                self.assertFalse(self.output.exists())
        self.reference.write_bytes(b'\xff')
        original['reference']['sha256'] = sha(self.reference)
        write_json(self.mapping, original)
        with self.assertRaisesRegex(ValueError, 'UTF-8'):
            self.align()

    def test_qualified_identity_is_ambiguous_for_multiple_evidence_records(self):
        contract, row = self.qualified()
        self.prepare([row], contract)
        report = self.align()
        self.assertEqual(report['summary']['status_counts']['ambiguous'], 1)
        self.assertEqual(report['summary']['uniquely_matched_baseline_units'], 0)
        self.assertGreater(len(self.records()[0]['matched_target_ids']), 1)

    def test_same_qualified_claim_matches_assertion_without_adjudicating_evidence(self):
        contract, row = self.qualified('assertion')
        self.prepare([row], contract)
        report = self.align()
        self.assertEqual(report['summary']['status_counts']['matched'], 1)
        record = self.records()[0]
        self.assertEqual(len(record['matched_target_ids']), 1)
        self.assertGreater(len(record['matched_evidence_edge_ids']), 1)
        self.assertFalse(record['label_interpreted'])
        self.assertFalse(record['scored'])

    def test_qualifiers_cannot_be_omitted_or_invented(self):
        contract, row = self.qualified()
        base = json.loads(row['qualifiers'])
        missing = deepcopy(base); missing.pop('species')
        extra = {**base, 'unrecognized': 'value'}
        for qualifiers in (json.dumps(missing), json.dumps(extra), '[]',
                           '{"disease": null, "disease": null}', '{"disease": 1e999}'):
            with self.subTest(qualifiers=qualifiers):
                self.prepare([{**row, 'qualifiers': qualifiers}], contract)
                with self.assertRaisesRegex(ValueError, 'qualified identity'):
                    self.align()
                self.assertFalse(self.output.exists())

    def test_disease_change_reversal_and_missing_node_remain_unmatched(self):
        contract, row = self.qualified('assertion')
        qualifiers = json.loads(row['qualifiers']); qualifiers['disease'] = 'invented:different'
        rows = [{**row, 'reference_id': 'different-context', 'qualifiers': json.dumps(qualifiers)},
                {**row, 'reference_id': 'reversed', 'subject': row['object'], 'object': row['subject']},
                {**row, 'reference_id': 'unknown', 'subject': 'invented:node'}]
        self.prepare(rows, contract)
        report = self.align()
        self.assertEqual(report['summary']['status_counts']['unmatched'], 3)
        self.assertEqual(self.records()[2]['reason'], 'endpoint_not_in_baseline')

    def test_multiple_reference_rows_cannot_double_count_a_target(self):
        target = self.graph['edges'][0]['id']
        self.prepare([{'reference_id': 'first', 'label': 'invented_yes', 'edge_id': target},
                      {'reference_id': 'second', 'label': 'invented_no', 'edge_id': target}])
        report = self.align()
        self.assertEqual(report['summary']['status_counts']['reference_collision'], 2)
        self.assertEqual(report['summary']['uniquely_matched_baseline_units'], 0)
        self.assertTrue(report['target_collisions'][0]['different_raw_labels'])

    def test_comma_bom_and_no_label_column_supported_explicitly(self):
        contract = deepcopy(self.template)
        contract['delimiter'] = 'comma'; contract['columns']['label'] = None
        value = self.prepare([{'reference_id': 'invented-1', 'edge_id': self.graph['edges'][0]['id']}], contract)
        self.reference.write_bytes(b'\xef\xbb\xbf' + self.reference.read_bytes())
        value['reference']['sha256'] = sha(self.reference); write_json(self.mapping, value)
        report = self.align()
        self.assertEqual(report['summary']['status_counts']['matched'], 1)
        self.assertIsNone(self.records()[0]['raw_label'])

    def test_input_change_during_alignment_never_produces_sealed_report(self):
        self.prepare()
        from biograph_steward import gold_reference
        original = gold_reference.align_rows

        def change(*args):
            result = original(*args)
            self.reference.write_text('changed after parsing')
            return result

        with patch.object(gold_reference, 'align_rows', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'changed while exporting'):
                self.align()
        self.assertFalse((self.output / 'report.json').exists())

    def test_output_and_symlink_inputs_do_not_replace_saved_material(self):
        self.prepare()
        with self.assertRaises(ValueError):
            align_reference(self.packet, self.reference, self.mapping, self.packet / 'nested')
        linked = self.root / 'linked.tsv'; linked.symlink_to(self.reference)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            align_reference(self.packet, linked, self.mapping, self.output)
        self.assertFalse(self.output.exists())

    def test_cli_export_verify_template_decisions_alignment_and_invalid_hash(self):
        commands = [
            ['gold-export', '--run', str(self.run), '--out', str(self.root / 'cli_packet')],
            ['gold-verify', '--packet', str(self.root / 'cli_packet')],
            ['gold-reference-template', '--packet', str(self.packet), '--out', str(self.root / 'cli_template')],
            ['gold-decisions', '--packet', str(self.packet), '--decisions', str(self.packet / 'decisions.template.json'),
             '--out', str(self.root / 'cli_decisions')],
        ]
        self.prepare()
        commands.append(['gold-align', '--packet', str(self.packet), '--reference', str(self.reference),
                         '--mapping', str(self.mapping), '--out', str(self.output)])
        for command in commands:
            with self.subTest(command=command), redirect_stdout(StringIO()) as stream:
                self.assertEqual(main(command), 0)
                self.assertIsInstance(json.loads(stream.getvalue()), dict)
        self.reference.write_text('tampered')
        with redirect_stderr(StringIO()) as stream:
            self.assertEqual(main(commands[-1]), 1)
        self.assertIn('hash', stream.getvalue())


if __name__ == '__main__':
    unittest.main()
