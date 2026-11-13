"""Invented source packets test blind-frame provenance, not biological gold."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from tools.grounding_claims import prepare


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def simplejson_fixture_module():
    # These fixtures contain only ordinary JSON integers/strings, no Decimal.
    # Optional lossless decimal/runtime behavior is verified by the real audit.
    module = ModuleType('simplejson')

    def dumps(value, **kwargs):
        kwargs.pop('use_decimal', None)
        return json.dumps(value, **kwargs)

    def loads(value, **kwargs):
        kwargs.pop('use_decimal', None)
        return json.loads(value, **kwargs)

    module.dumps, module.loads = dumps, loads
    return module


def projected(statement, evidence):
    return {'status': 'ready', 'source_api': 'invented',
            'pmid': evidence.get('pmid'), 'text': evidence['text'],
            'agents': [{'status': 'ready', 'assigned': {'namespace': 'HGNC', 'id': '900000001'}}]}


class Packet:
    """Small entirely invented source packet, with no reference labels."""
    def __init__(self, root):
        self.root = root
        self.join = root / 'join'
        self.join.mkdir()
        self.exposure = root / 'exposure.json'
        self.group_a, self.group_b = 'a' * 64, 'b' * 64
        self.identities = [('-9007199254740993', '9223372036854775806', '101'),
                           ('22', '-9223372036854775806', '102'),
                           ('33', '44', '103')]
        self.statements, pairs = [], []
        for ordinal, (pa, source, pmid) in enumerate(self.identities):
            evidence = {'source_hash': int(source), 'pmid': pmid,
                        'text_refs': {'PMID': pmid}, 'source_api': 'invented',
                        'text': 'Invented alpha activates beta.',
                        'annotations': {'agents': {'raw_text': ['Invented alpha'],
                                                  'raw_grounding': [{'HGNC': '900000001'}]}}}
            statement = {'type': 'Activation', 'matches_hash': pa,
                         'evidence': [evidence], 'belief': 0.5}
            statement_sha = sha256(encoded(statement)).hexdigest()
            self.statements.append({'corpus_ordinal': ordinal,
                                    'statement': statement,
                                    'canonical_statement_sha256': statement_sha})
            pairs.append({'pa_hash': pa, 'source_hash': source, 'matched': True,
                          'curation_record_ordinals': [ordinal],
                          'evidence_payload_variant_count': 1,
                          'statement_payload_variant_count': 1,
                          'source_origin_payload_variant_count': 1,
                          'all_occurrences_have_explicit_all_HGNC_origins': True,
                          'evidence_occurrences': [{
                              'corpus_ordinal': ordinal, 'evidence_ordinal': 0,
                              'canonical_statement_sha256': statement_sha,
                              'canonical_evidence_sha256': sha256(encoded(evidence)).hexdigest(),
                              'publication': {'native_publication_values': {'pmid': pmid, 'text_refs.PMID': pmid},
                                              'qualified_PMIDs': [pmid],
                                              'PMID_fields_conflict': False,
                                              'malformed_nonempty_PMID_fields': [],
                                              'single_PMID_consensus': pmid,
                                              'publication_group_tokens': ['PMID:' + pmid]}}]})
        self.write_statements()
        self.write('pair_join_inventory.json', {'pairs': pairs})
        self.write('exposure_groups.json', {'groups': [
            {'group_id': self.group_a,
             'pair_ids': [pa + ':' + source for pa, source, _ in self.identities[:2]],
             'candidate_tokens': ['PMID:101', 'PMID:102', 'statement-family:invented-a']},
            {'group_id': self.group_b,
             'pair_ids': [self.identities[2][0] + ':' + self.identities[2][1]],
             'candidate_tokens': ['PMID:103', 'statement-family:invented-b']}]})
        self.exposure.write_text(json.dumps({'labels_inspected': False, 'tokens': ['PMID:101']}))
        self.reseal()

    def write(self, name, value):
        (self.join / name).write_text(json.dumps(value))

    def read(self, name):
        return json.loads((self.join / name).read_text())

    def write_statements(self):
        (self.join / 'selected_statements.jsonl').write_bytes(
            b''.join(encoded(row) + b'\n' for row in self.statements))

    def reseal(self):
        report = {'curation_tag_comment_or_correctness_fields_used': False,
                  'grounder_or_model_predictions_run': False,
                  'all_original_pair_IDs_joined': True,
                  'outputs': {name: {'SHA256': sha256((self.join / name).read_bytes()).hexdigest()}
                              for name in ('pair_join_inventory.json', 'selected_statements.jsonl', 'exposure_groups.json')}}
        report['content_sha256'] = digest(report)
        self.write('join_report.json', report)

    def run(self, name='out', **kwargs):
        with patch.dict('sys.modules', {'simplejson': simplejson_fixture_module()}):
            return prepare.prepare(self.join, self.exposure, self.root / name,
                                   projector=kwargs.pop('projector', projected), **kwargs)

    def cases(self, name='out'):
        with gzip.open(self.root / name / 'cases.jsonl.gz', 'rt') as stream:
            return [json.loads(line) for line in stream]


class GroundingClaimPrepareTests(unittest.TestCase):
    def test_signed_native_IDs_reject_boolean_float_and_noncanonical_strings(self):
        for value in [True, False, 1.0, -1.0, None, [], {}, '+1', '01', '-0', ' 1', '1 ', '1e3']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare.signed_id(value)
        for value in [0, -1, '-9007199254740993', '9223372036854775806']:
            self.assertEqual(prepare.signed_id(value), str(value))

    def test_split_is_deterministic_validated_and_exposed_group_is_development(self):
        group = 'f' * 64
        self.assertEqual(prepare.split_for_group(group), prepare.split_for_group(group))
        self.assertIn(prepare.split_for_group(group), {'development', 'test'})
        self.assertEqual(prepare.split_for_group(group, exposed=True), 'development')
        for value in ['f' * 63, 'g' * 64, None, 1, True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare.split_for_group(value)

    def test_full_group_is_forced_to_development_and_large_IDs_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); result = packet.run()
            cases = packet.cases()
            self.assertEqual(result['primary_cases'], 3)
            self.assertFalse(result['label_categories_inspected'])
            self.assertFalse(result['predictions_run'])
            self.assertEqual([row['split'] for row in cases[:2]], ['development', 'development'])
            self.assertEqual(cases[0]['pa_hash'], '-9007199254740993')
            self.assertEqual(cases[0]['source_hash'], '9223372036854775806')
            self.assertEqual(cases[0]['case_id'], 'indra:-9007199254740993:9223372036854775806')
            self.assertEqual(json.loads((packet.root / 'out/requested_pmids.json').read_text()), ['101', '102', '103'])

    def test_reordering_source_groups_does_not_change_split_assignment(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); packet.run('first')
            before = {row['case_id']: row['split'] for row in packet.cases('first')}
            groups = packet.read('exposure_groups.json'); groups['groups'].reverse()
            packet.write('exposure_groups.json', groups); packet.reseal(); packet.run('second')
            self.assertEqual(before, {row['case_id']: row['split'] for row in packet.cases('second')})

    def test_input_byte_tampering_is_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp))
            with (packet.join / 'selected_statements.jsonl').open('ab') as stream:
                stream.write(b' ')
            with self.assertRaisesRegex(ValueError, 'joined file differs'):
                packet.run()
            self.assertFalse((packet.root / 'out').exists())

    def test_resealed_selected_content_still_needs_original_canonical_commitment(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); packet.statements[0]['statement']['evidence'][0]['text'] = 'Invented changed source.'
            packet.write_statements(); packet.reseal()
            with self.assertRaisesRegex(ValueError, 'Statement differs'):
                packet.run()

    def test_resealed_source_identity_change_cannot_replace_original_hash_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); row = packet.statements[0]
            row['statement']['evidence'][0]['source_hash'] = 999
            row['canonical_statement_sha256'] = sha256(encoded(row['statement'])).hexdigest()
            packet.write_statements(); packet.reseal()
            with self.assertRaises(ValueError):
                packet.run()

    def test_resealed_occurrence_evidence_hash_must_match_selected_native_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); inventory = packet.read('pair_join_inventory.json')
            inventory['pairs'][0]['evidence_occurrences'][0]['canonical_evidence_sha256'] = '0' * 64
            packet.write('pair_join_inventory.json', inventory); packet.reseal()
            with self.assertRaises(ValueError):
                packet.run()

    def test_resealed_occurrence_statement_hash_must_match_selected_native_source(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); inventory = packet.read('pair_join_inventory.json')
            inventory['pairs'][0]['evidence_occurrences'][0]['canonical_statement_sha256'] = '0' * 64
            packet.write('pair_join_inventory.json', inventory); packet.reseal()
            with self.assertRaises(ValueError):
                packet.run()

    def test_resealed_publication_context_cannot_change_the_source_PMID(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); inventory = packet.read('pair_join_inventory.json')
            inventory['pairs'][0]['evidence_occurrences'][0]['publication']['single_PMID_consensus'] = '999'
            packet.write('pair_join_inventory.json', inventory); packet.reseal()
            with self.assertRaises(ValueError):
                packet.run()

    def test_resealed_boolean_evidence_ordinal_is_not_an_integer_source_locator(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); inventory = packet.read('pair_join_inventory.json')
            inventory['pairs'][0]['evidence_occurrences'][0]['evidence_ordinal'] = False
            packet.write('pair_join_inventory.json', inventory); packet.reseal()
            with self.assertRaises(ValueError):
                packet.run()

    def test_resealed_boolean_or_float_payload_counts_do_not_pass_as_one(self):
        for value in [True, 1.0]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                packet = Packet(Path(temp)); inventory = packet.read('pair_join_inventory.json')
                inventory['pairs'][0]['evidence_payload_variant_count'] = value
                packet.write('pair_join_inventory.json', inventory); packet.reseal()
                with self.assertRaises(ValueError):
                    packet.run()

    def test_native_projection_unresolved_case_is_retained_in_coverage_not_fabricated(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp))
            def projector(statement, evidence):
                return {'status': 'unresolved', 'agents': [], 'source_api': 'invented'}
            result = packet.run(projector=projector)
            self.assertEqual(result['primary_cases'], 0)
            self.assertEqual(result['outside_primary_counts'], {'native_projection_unresolved': 3})
            self.assertEqual(len(json.loads((packet.root / 'out/frame_coverage.json').read_text())), 3)
            self.assertEqual(packet.cases(), [])

    def test_unblinded_exposure_or_source_join_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp))
            packet.exposure.write_text(json.dumps({'labels_inspected': True, 'tokens': []}))
            with self.assertRaisesRegex(ValueError, 'source-only'):
                packet.run('unblinded_exposure')
            packet.exposure.write_text(json.dumps({'labels_inspected': False, 'tokens': []}))
            report = packet.read('join_report.json'); report['grounder_or_model_predictions_run'] = True
            report.pop('content_sha256'); report['content_sha256'] = digest(report)
            packet.write('join_report.json', report)
            with self.assertRaisesRegex(ValueError, 'label-blind'):
                packet.run('unblinded_join')

    def test_cross_group_source_token_reuse_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); groups = packet.read('exposure_groups.json')
            groups['groups'][1]['candidate_tokens'].append('PMID:101')
            packet.write('exposure_groups.json', groups); packet.reseal()
            with self.assertRaisesRegex(ValueError, 'crosses groups'):
                packet.run()

    def test_source_changes_during_preparation_prevent_a_completed_frame_report(self):
        with tempfile.TemporaryDirectory() as temp:
            packet = Packet(Path(temp)); changed = False
            def projector(statement, evidence):
                nonlocal changed
                if not changed:
                    with (packet.join / 'selected_statements.jsonl').open('ab') as stream:
                        stream.write(b' ')
                    changed = True
                return projected(statement, evidence)
            with self.assertRaisesRegex(ValueError, 'source changed'):
                packet.run(projector=projector)
            self.assertFalse((packet.root / 'out/report.json').exists())


if __name__ == '__main__':
    unittest.main()
