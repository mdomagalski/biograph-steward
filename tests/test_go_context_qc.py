"""Invented producer packets test source-bound display, not GO rule accuracy."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import canonical, digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward import go_context_qc as qc
from biograph_steward.go_qualification import GAF_FIELDS, native_record


def make_qc(folder, report, native, *, normalized=None, unsatisfiable=()):
    """Small invented output of the existing producer's recorded schema."""
    folder.mkdir()
    normalized = normalized or {}
    changes, calls, taxon, lookups, lines = [], [], [], [], []
    for row in native:
        after = normalized.get(row['id'], [row['raw_line']])
        columns = sorted({i+1 for line in after for i, (old, new) in
                          enumerate(zip(row['raw_fields'], line.split('\t'))) if old != new})
        changes.append({'native_record_id': row['id'], 'source_line': row['source_line'],
            'before': row['raw_line'], 'after_base_rules': after, 'base_rule_filtered': not bool(after),
            'base_literal_output_changed': bool(after) and after != [row['raw_line']],
            'changed_gaf_columns': columns})
        lines.extend(after)
        for rule in sorted(qc.RULES):
            calls.append({'native_record_id': row['id'], 'rule': rule,
                'result_type': 'WARNING' if rule == 'GORULE:0000061' and 4 in columns else 'PASS',
                'message': 'Invented selected-rule output'})
        taxon.append({'native_record_id': row['id'], 'negated_annotation_exempt': row['negated'],
            'result_type': 'PASS', 'message': 'Invented taxon output'})
        if not row['negated']:
            flagged = row['id'] in unsatisfiable
            lookups.append({'native_record_id': row['id'], 'typed_extension_key_converted': flagged,
                'explicit_sparse_delta_match': flagged, 'satisfiable': False if flagged else None,
                'taxon_problem': False if flagged else None, 'additional_inferences': 0 if flagged else None})
    for name, rows in [('native_row_changes.jsonl', changes), ('official_rule_calls.jsonl', calls),
                       ('official_lifecycle_calls.jsonl', [])]:
        (folder/name).write_text(''.join(canonical(row)+'\n' for row in rows))
    gaf = '!gaf-version: 2.2\n'+'\n'.join(lines)+'\n'
    for name in ['base_validated_native.gaf', 'validated_native.gaf']:
        (folder/name).write_text(gaf)
    write_json(folder/'official_report.json', {})
    from collections import Counter
    proof = {'producer_execution_sha256': '1'*64, 'coverage_execution_sha256': '2'*64,
        'coverage_file_sha256': '3'*64, 'normal_absent_keys_materialized_as_pass_entries': False,
        'covered_non_not_associations': sum(not row['negated'] for row in native),
        'negated_exempt_associations': sum(row['negated'] for row in native)}
    write_json(folder/'taxon_rule.json', {'requested': True,
        'status': 'executed_with_proven_sparse_delta_parser_coverage',
        'published_inference_entries_modified': False, 'results': taxon,
        'non_not_associations': sum(not row['negated'] for row in native),
        'negated_exempt_associations': sum(row['negated'] for row in native),
        'missing_key_associations': 0,
        'actual_lookup_calls': lookups, 'sparse_proof': proof})
    output = {'format': qc.FORMAT, 'status': 'completed',
        'source_context_report_sha256': report['content_sha256'], 'packet_id': report['packet_id'],
        'ontobio_version': '2.9.12', 'prefixcommons_version': '0.1.12',
        'explicit_qc_rule_selectors': ['0000022', '0000061'],
        'official_methods_recorded_without_rule_body_changes': True,
        'native_gaf_and_ontology_release_match': True, 'native_gaf_go_version': 'Invented-2026-01-01',
        'scientific_accuracy_measured': False, 'independent_biological_validation': False,
        'source_graph_changed': False, 'historical_pharos_qualifiers_backfilled': False,
        'unrecorded_network_allowed': False,
        'taxon_rule_status': 'executed_with_proven_sparse_delta_parser_coverage',
        # Byte hashes deliberately differ from execution-receipt content seals.
        'input_files': {'inference_execution': {'sha256': '4'*64},
                        'parser_execution': {'sha256': '5'*64}, 'parser_coverage': {'sha256': '3'*64}},
        'base_validated_native_gaf_sha256': sha(folder/'base_validated_native.gaf'),
        'counts': {'native_input_records': len(native), 'base_output_associations': len(lines),
            'final_output_associations': len(lines),
            'base_filtered_native_records': sum(not row['after_base_rules'] for row in changes),
            'base_literal_changed_native_records': sum(row['base_literal_output_changed'] for row in changes),
            'field_change_records': {name: sum(i in row['changed_gaf_columns'] for row in changes)
                                    for i, name in qc.FIELD_NAMES.items()},
            'rule_invocations': {rule: dict(Counter(row['result_type'] for row in calls if row['rule'] == rule))
                                 for rule in qc.RULES}},
        'limits': ['Invented fixture; no real biological result.'],
        'files': {name: sha(folder/name) for name in qc.FILES}}
    output['content_sha256'] = digest(output)
    write_json(folder/'report.json', output)
    return output


class SavedGoQCTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = {'content_sha256': 'a'*64, 'packet_id': 'packet:'+'b'*64}
        base = ['UniProtKB', 'P12345', 'INVENTED', 'part_of', 'GO:0005794', 'PMID:1',
                'IDA', '', 'C', 'Invented protein', '', 'protein', 'taxon:9606',
                '20260101', 'GO_Central', 'part_of(CL:0000639)', 'UniProtKB:P12345']
        self.native = []
        for i in range(3):
            fields = list(base)
            fields[4] = 'GO:0005794' if i == 0 else 'GO:0070062'
            if i == 2: fields[3] = 'NOT|located_in'
            parsed = dict(zip(GAF_FIELDS, fields))
            for key in ('Qualifier', 'DB:Reference', 'With', 'Synonym', 'Taxon_ID'):
                parsed[key] = parsed[key].split('|')
            self.native.append(native_record(i+5, '\t'.join(fields), fields, parsed, 'c'*64))
        changed = list(self.native[0]['raw_fields']); changed[3] = 'located_in'
        self.folder = self.root/'qc'
        make_qc(self.folder, self.context, self.native,
                normalized={self.native[0]['id']: ['\t'.join(changed)]},
                unsatisfiable={self.native[1]['id']})

    def reseal(self):
        report = __import__('json').loads((self.folder/'report.json').read_text())
        report['files'] = {name: sha(self.folder/name) for name in qc.FILES}
        report.pop('content_sha256'); report['content_sha256'] = digest(report)
        write_json(self.folder/'report.json', report)

    def test_changes_rules_and_unsatisfiable_context_stay_separate_and_read_only(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        original = deepcopy(self.native)
        summary, rows = qc.load_saved_qc(self.folder, self.context, self.native)
        self.assertEqual(summary['status'], 'verified_saved_output')
        self.assertEqual(rows[self.native[0]['id']]['normalization']['changed_columns'],
            [{'column': 4, 'field': 'relation', 'before': 'part_of', 'after_values': ['located_in']}])
        self.assertTrue(rows[self.native[1]['id']]['extension_unsatisfiable'])
        self.assertEqual(rows[self.native[1]['id']]['taxon_result']['result_type'], 'PASS')
        self.assertIsNone(rows[self.native[0]['id']]['semantic_lookup_results'][0]['satisfiable'])
        self.assertTrue(rows[self.native[2]['id']]['taxon_result']['negated_annotation_exempt'])
        self.assertFalse(rows[self.native[2]['id']]['extension_unsatisfiable'])
        self.assertFalse(summary['historical_record_repaired'])
        self.assertFalse(summary['independent_biological_accuracy_established'])
        self.assertEqual(self.native, original)
        self.assertEqual({p.name: p.read_bytes() for p in self.folder.iterdir()}, before)

    def test_wrong_frame_tampered_output_extra_files_and_symlinks_fail(self):
        with self.assertRaisesRegex(ValueError, 'source frame'):
            qc.load_saved_qc(self.folder, {**self.context, 'content_sha256': 'd'*64}, self.native)
        path = self.folder/'official_report.json'; old = path.read_bytes(); path.write_bytes(old+b' ')
        with self.assertRaisesRegex(ValueError, 'output bytes'):
            qc.load_saved_qc(self.folder, self.context, self.native)
        path.write_bytes(old)
        extra = self.folder/'extra'; extra.write_text('unbound')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            qc.load_saved_qc(self.folder, self.context, self.native)
        extra.unlink(); extra.symlink_to(path)
        with self.assertRaisesRegex(ValueError, 'inventory'):
            qc.load_saved_qc(self.folder, self.context, self.native)

    def test_resealed_row_context_change_missing_rule_or_sparse_pass_cannot_hide(self):
        import json
        file = self.folder/'native_row_changes.jsonl'; old = file.read_bytes()
        rows = [json.loads(line) for line in file.read_text().splitlines()]
        rows[0]['before'] += 'x'; file.write_text(''.join(canonical(row)+'\n' for row in rows)); self.reseal()
        with self.assertRaisesRegex(ValueError, 'row identity'):
            qc.load_saved_qc(self.folder, self.context, self.native)
        file.write_bytes(old); self.reseal()
        rules = self.folder/'official_rule_calls.jsonl'; old = rules.read_bytes()
        rules.write_bytes(b'\n'.join(old.splitlines()[1:])+b'\n'); self.reseal()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            qc.load_saved_qc(self.folder, self.context, self.native)
        rules.write_bytes(old); self.reseal()
        taxon = self.folder/'taxon_rule.json'; value = json.loads(taxon.read_text())
        value['actual_lookup_calls'][0]['satisfiable'] = True
        write_json(taxon, value); self.reseal()
        with self.assertRaisesRegex(ValueError, 'missing sparse'):
            qc.load_saved_qc(self.folder, self.context, self.native)


if __name__ == '__main__':
    unittest.main()
