"""Invented ontology metadata only; no experimental labels or model scores."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.function_context import digest as context_digest
from biograph_steward.go_content_currency import load_index, get_term, literal_flags, validate_term
from . import audit

AUTHOR = Path('runs/accuracy_next_20261113/cafa5_intake/evaluator_author_source/src/cafaeval/parser.py')


def dump(path, value):
    Path(path).write_text(json.dumps(value))


class LiteralCurrency(unittest.TestCase):
    def test_parent_and_scope_changes_do_not_create_biological_verdict(self):
        old = {'present': True, 'state': 'active', 'name': 'Old label', 'definition': 'Recorded definition',
               'namespace': 'molecular_function', 'synonyms': [{'scope': 'EXACT', 'value': 'alternate'}],
               'parents': [{'predicate': 'is_a', 'object': 'GO:0003674'}]}
        new = {**deepcopy(old), 'name': 'Revised label',
               'synonyms': [{'scope': 'RELATED', 'value': 'alternate'}],
               'parents': [{'predicate': 'part_of', 'object': 'GO:0003674'}]}
        flags = literal_flags(old, new)
        self.assertTrue(flags['name_changed']); self.assertTrue(flags['synonym_scope_or_text_records_changed'])
        self.assertTrue(flags['explicit_is_a_part_of_records_changed']); self.assertFalse(flags['definition_text_changed'])
        row = {'term_id': 'GO:0000001', 'scopes': ['invented'], 'graph_labels': ['Unknown-vintage label'],
               'historical': old, 'comparison': new, 'flags': flags, 'automatic_action': 'none',
               'semantic_equivalence_inferred': False, 'biological_falsehood_inferred': False}
        validate_term(row)
        tampered = deepcopy(row); tampered['flags']['definition_text_changed'] = True
        with self.assertRaises(ValueError): validate_term(tampered)
        old['definition'] = None
        self.assertIsNone(literal_flags(old, new)['definition_text_changed'])

    def fixture(self, folder):
        b = Path(folder); pub = b / 'saved'; (pub / 'queries').mkdir(parents=True)
        old = b / 'old.obo'; new = b / 'new.json.gz'
        old.write_text('format-version: 1.2\n\n[Term]\nid: GO:0000001\nname: Old label\nnamespace: molecular_function\ndef: "Recorded definition" []\nis_a: GO:0003674\n\n')
        nodes = [{'id': audit.PREFIX + x, 'type': 'CLASS', 'lbl': 'Invented root'}
                 for x in ('GO_0003674', 'GO_0005575', 'GO_0008150')]
        nodes.append({'id': audit.PREFIX + 'GO_0000001', 'type': 'CLASS', 'lbl': 'Revised label',
            'meta': {'definition': {'val': 'Recorded definition'}, 'basicPropertyValues': [
                {'pred': audit.OIO + 'hasOBONamespace', 'val': 'molecular_function'}]}})
        value = {'graphs': [{'id': 'http://purl.obolibrary.org/obo/go.owl',
            'meta': {'version': 'http://purl.obolibrary.org/obo/go/releases/2026-07-26/go.owl'},
            'nodes': nodes, 'edges': []}]}
        new.write_bytes(gzip.compress(json.dumps(value).encode()))
        graph = b / 'graph.json'; dump(graph, {'nodes': [{'id': 'GO:0000001', 'name': 'Unknown-vintage label'}],
            'edges': [{'object': 'GO:0000001', 'record_kind': 'go_annotation'}],
            'context': {'extension': 'occurs_in(GO:0005575)'}})
        training = b / 'training.gz'; training.write_bytes(gzip.compress(json.dumps({'invented': [['MFO', 'GO:0000001']]}).encode()))
        query = pub / 'queries/a.json'; dump(query, {'candidates': [{'GO_ID': 'GO:0000001'}]})
        m = {'format': 'biograph-steward.exact-onehop-LocalPlus-publication.v1',
            'files': {'downloads/training_snapshot.json.gz': {'sha256': audit.sha(training)},
                      'queries/a.json': {'sha256': audit.sha(query)}},
            'query_files': {'invented': 'queries/a.json'},
            'input_source_pins': {'ontology': {'sha256': audit.sha(old)}}}
        m['content_sha256'] = context_digest(m); dump(pub / 'publication.json', m)
        return b, old, new, graph, training, pub

    @unittest.skipUnless(AUTHOR.is_file(), 'optional immutable native reader is not present')
    def test_frame_freeze_native_reader_index_and_exact_lookup(self):
        with tempfile.TemporaryDirectory() as folder:
            b, old, new, graph, training, pub = self.fixture(folder)
            with patch.object(audit, 'OLD_SHA', audit.sha(old)), patch.object(audit, 'NEW_SHA', audit.sha(new)):
                frozen = audit.prepare(graph, training, pub, old, new, AUTHOR, b / 'frame')
                self.assertFalse(frozen['new_difference_aggregate_values_read'])
                result = audit.audit(b / 'frame/term_frame.json', b / 'frame/scope_freeze.json',
                    audit.sha(b / 'frame/scope_freeze.json'), old, new, AUTHOR, b / 'index')
                manifest, rows = load_index(b / 'index', audit.sha(b / 'index/publication.json'))
                self.assertEqual(manifest['term_count'], 2)
                answer = get_term(manifest, rows, 'GO:0000001')
                self.assertEqual(answer['term']['historical']['name'], 'Old label')
                self.assertEqual(answer['term']['comparison']['name'], 'Revised label')
                self.assertEqual(answer['source_versions']['graph_Pharos_GO_vintage'], 'UNKNOWN')
                self.assertFalse(answer['graph_or_prediction_modified'])
                self.assertEqual(answer['term']['graph_labels'], ['Unknown-vintage label'])
                with self.assertRaises(ValueError): get_term(manifest, rows, 'GO:9999999')
                raw = (b / 'index/terms.jsonl.gz').read_bytes()
                (b / 'index/terms.jsonl.gz').write_bytes(raw + b'changed')
                with self.assertRaises(ValueError): load_index(b / 'index', audit.sha(b / 'index/publication.json'))

    def test_historical_utf8_source_pin_and_obsolete_state_are_literal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'old.obo'
            path.write_text('[Term]\nid: GO:0000001\nname: obsolete example\nnamespace: molecular_function\nis_obsolete: true\nreplaced_by: GO:0000002\n\n')
            stanzas = audit.stanzas(path); row = audit.historical_record('GO:0000001', {}, stanzas)
            self.assertEqual(row['state'], 'obsolete'); self.assertIsNone(row['definition'])
            self.assertEqual(row['stanza_utf8_sha256'], hashlib.sha256(row['raw_stanza'].encode()).hexdigest())
            self.assertEqual(row['declared_replaced_by'], ['GO:0000002'])
            self.assertEqual(audit.historical_record('GO:9999999', {}, stanzas)['state'], 'not_found')

    def test_native_inspector_ids_and_extension_mentions_are_distinct_pinned_scopes(self):
        with tempfile.TemporaryDirectory() as folder:
            b, old, new, graph, training, pub = self.fixture(folder)
            native = b / 'native'; context = native / 'source/context'; context.mkdir(parents=True)
            records = context / 'native_records.jsonl'
            records.write_text(json.dumps({'go_id': 'GO:0000002',
                'annotation_extension_raw': 'occurs_in(GO:0000003)'}) + '\n')
            qualification = {'counts': {'native_rows': 1}, 'source': {'headers': ['!invented'],
                'provided_source_url': 'https://example.invalid/invented.gaf.gz',
                'source_url_authentication_performed': False}}
            qualification['content_sha256'] = digest(qualification)
            dump(context / 'go_context_qualification.json', qualification)
            manifest = {'format': 'biograph-steward.native-goa-source-publication.v1',
                'files': {str(p.relative_to(native)): audit.sha(p) for p in context.iterdir()}}
            manifest['content_sha256'] = digest(manifest); dump(native / 'publication.json', manifest)
            with patch.object(audit, 'OLD_SHA', audit.sha(old)), patch.object(audit, 'NEW_SHA', audit.sha(new)):
                frozen = audit.prepare(graph, training, pub, old, new, AUTHOR, b / 'frame', native_publication=native)
                frame = audit.read(b / 'frame/term_frame.json')
                rows = {r['term_id']: r for r in frame['terms']}
                self.assertEqual(frozen['term_count'], 4)
                self.assertIn('separate_native_GOA_primary_record', rows['GO:0000002']['scopes'])
                self.assertNotIn('separate_native_GOA_primary_record', rows['GO:0000003']['scopes'])
                self.assertIn('separate_native_GOA_literal_mention', rows['GO:0000003']['scopes'])
                self.assertFalse(frame['new_content_comparison_performed'])
                records.write_text(records.read_text() + '{}\n')
                with self.assertRaisesRegex(ValueError, 'bytes differ'):
                    audit.prepare(graph, training, pub, old, new, AUTHOR, b / 'bad', native_publication=native)


if __name__ == '__main__': unittest.main()
