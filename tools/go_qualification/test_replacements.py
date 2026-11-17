"""GO repair compatibility/novelty checks using synthetic records only."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from biograph_steward import go_ontology_qualification as ontology
from tools.go_qualification.audit_replacements import audit, candidate_gaf, classify


def edge(uid, term='GO:0000002', evidence='IDA', assigner='TEST'):
    return {'id': uid, 'assertion_id': 'assertion:' + uid, 'record_kind': 'go_annotation',
            'subject': 'UniProtKB:P12345', 'object': term,
            'evidence_record': {'goid': term, 'evidence': evidence, 'assigned_by': assigner, 'type': 'P'}}


def node(term, target=None):
    return {'id': ontology.GO_IRI + term[3:], 'meta':
            ({'deprecated': True, 'basicPropertyValues': [{'pred': ontology.REPLACED_BY,
              'val': ontology.GO_IRI + target[3:]}]} if target else {})}


def native(uid='native:1', evidence='IDA', **changes):
    row = {'id': uid, 'subject': 'UniProtKB:P12345', 'go_id': 'GO:0000001',
           'evidence_code': evidence, 'assigned_by': 'TEST', 'aspect': 'P',
           'source_line': int(uid.rsplit(':', 1)[-1]), 'negated': False,
           'gene_product_form_id': None, 'annotation_extension_raw': '', 'with_from_raw': '',
           'taxon_ids': ['taxon:9606']}
    return {**row, **changes}


def fixture(edges=None):
    graph = {'edges': edges or [edge('old')]}
    nodes = {'GO:0000001': node('GO:0000001'),
             'GO:0000002': node('GO:0000002', 'GO:0000001'),
             'GO:0000003': node('GO:0000003', 'GO:0000001')}
    proposals = [{'edge_id': e['id'], **ontology.classify_term(e['object'], nodes)['replacement_proposal']}
                 for e in graph['edges']]
    return graph, nodes, proposals


class ReplacementTests(unittest.TestCase):
    def run_case(self, rows=None, retained=None, graph_edges=None):
        graph, nodes, proposals = fixture(graph_edges)
        before = deepcopy((graph, nodes, proposals, rows, retained))
        result = classify(graph, retained or {'edges': []}, proposals,
                          rows if rows is not None else [native()], nodes)
        self.assertEqual((graph, nodes, proposals, rows, retained), before)
        return result

    def test_supported_new_concept_remains_a_native_candidate_not_a_graph_edit(self):
        rows, concepts, additions, counts = self.run_case()
        self.assertEqual(counts['qualified_nonduplicate_concepts'], 1)
        self.assertEqual([r['id'] for r in additions], ['native:1'])
        self.assertFalse(rows[0]['proposal_applied'])
        self.assertFalse(rows[0]['historical_native_record_identity_established'])

    def test_concept_overlap_is_not_projection_or_evidence_identity(self):
        rows, _, additions, counts = self.run_case(retained={'edges': [edge('kept', 'GO:0000001', 'TAS')]})
        self.assertTrue(rows[0]['concept_already_present'])
        self.assertEqual(rows[0]['retained_same_projection_edge_ids'], [])
        self.assertEqual(counts['qualified_nonduplicate_concepts'], 0)
        self.assertEqual(additions, [])

    def test_native_other_assigner_is_diagnostic_not_strict_support(self):
        rows, _, additions, _ = self.run_case(rows=[native(assigned_by='OTHER')])
        self.assertEqual(rows[0]['status'], 'same_subject_term_only_projection_fields_differ')
        self.assertEqual(additions, [])

    def test_no_match_is_unknown_and_not_a_false_label(self):
        rows, _, additions, _ = self.run_case(rows=[])
        self.assertEqual(rows[0]['status'], 'no_native_subject_replacement_term')
        self.assertFalse(rows[0]['biological_truth_assessed'])
        self.assertEqual(additions, [])

    def test_nonexperimental_curation_not_called_invalid(self):
        rows, _, additions, _ = self.run_case(rows=[native(evidence='TAS')], graph_edges=[edge('old', evidence='TAS')])
        self.assertEqual(rows[0]['native_projection_status'], 'one_compatible_native_record')
        self.assertEqual(rows[0]['status'], 'strict_native_candidates_outside_experimental_context_scope')
        self.assertEqual(rows[0]['native_context_eligibility'][0]['excluded_because'], ['not_experimental_evidence_code'])
        self.assertEqual(additions, [])

    def test_context_and_isoform_are_not_collapsed(self):
        for change in ({'annotation_extension_raw': 'occurs_in(CL:0000001)'},
                       {'gene_product_form_id': 'UniProtKB:P12345-2'},
                       {'taxon_ids': ['taxon:9606', 'taxon:10090']},
                       {'with_from_raw': 'UniProtKB:Q12345'}):
            with self.subTest(change=change):
                rows, _, additions, _ = self.run_case(rows=[native(**change)])
                self.assertFalse(rows[0]['qualified_unopposed_experimental_support'])
                self.assertEqual(additions, [])

    def test_eligible_NOT_is_held_not_a_refutation_of_historical_existence(self):
        rows, _, additions, _ = self.run_case(rows=[native(), native('native:2', negated=True)])
        self.assertEqual(rows[0]['status'], 'opposing_eligible_NOT_held_unresolved')
        self.assertEqual(additions, [])

    def test_converging_proposals_do_not_multiply_concepts_or_native_evidence(self):
        rows, concepts, additions, counts = self.run_case(graph_edges=[edge('old1'), edge('old2', 'GO:0000003')])
        self.assertEqual(counts['proposals'], 2)
        self.assertEqual(counts['distinct_subject_replacement_concepts'], 1)
        self.assertEqual(counts['qualified_nonduplicate_native_records'], 1)
        self.assertEqual(len(additions), 1)

    def test_opposing_projection_blocks_convergent_concept_candidate(self):
        rows, concepts, additions, _ = self.run_case(
            graph_edges=[edge('old1'), edge('old2', 'GO:0000003', 'IMP')],
            rows=[native(), native('native:2', 'IMP', negated=True)])
        self.assertFalse(concepts[0]['qualified_nonduplicate_concept'])
        self.assertEqual(additions, [])

    def test_forged_or_incomplete_replacement_inventory_rejected(self):
        graph, nodes, proposals = fixture()
        for altered in ([], [{**proposals[0], 'to_id': 'GO:0000009'}], proposals + proposals):
            with self.subTest(altered=altered), self.assertRaisesRegex(ValueError, 'ontology replay'):
                classify(graph, {'edges': []}, altered, [native()], nodes)

    def test_pins_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, filename in [('q', 'go_ontology_qualification.json'), ('r', 'report.json'), ('c', 'go_context_qualification.json')]:
                (root / name).mkdir(); (root / name / filename).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'explicit report pins'):
                audit(root/'q', root/'r', root/'c', root/'output', qualification_sha256='0'*64,
                      retained_sha256='0'*64, context_sha256='0'*64)
            self.assertFalse((root/'output').exists())

    def test_standard_gaf_subset_preserves_native_bodies_and_rejects_not(self):
        source_hash = '1' * 64
        raw = '\t'.join(['DB', 'P12345', 'TEST', 'involved_in', 'GO:0000001', 'PMID:1',
                         'IDA', '', 'P', 'Synthetic protein', '', 'protein', 'taxon:9606',
                         '20260101', 'TEST', '', ''])
        row = native(source_gaf_sha256=source_hash, raw_line=raw)
        out = candidate_gaf(['!gaf-version: 2.2', '!generated-by: SYNTHETIC'], [row], source_hash)
        self.assertEqual([line for line in out.splitlines() if not line.startswith('!')], [raw])
        self.assertIn('not the complete source release', out)
        with self.assertRaisesRegex(ValueError, 'outside qualified scope'):
            candidate_gaf(['!gaf-version: 2.2'], [{**row, 'negated': True}], source_hash)


if __name__ == '__main__':
    unittest.main()
