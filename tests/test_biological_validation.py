"""Invented saved results verify provenance and claim scope, never biology."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward import biological_validation as validation
from biograph_steward.client import digest, write_json


def sealed(value):
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    return value


def make_comparison(root, *, qc=True):
    root = Path(root)
    source = sealed({'original_source_pairs': 8, 'qualified_rankable_pairs': 5,
        'retained_rankable_budget': 4, 'abstain_retained_pairs': 3,
        'qualified_rankable_removals': 1})
    selection = sealed({'source_qualification_sha256': source['content_sha256'],
        'reference_calls_opened': False, 'new_outcome_selection': False, 'source_graph_modified': False})
    for directory, name, data in [('source', 'source_qualification.json', source),
                                   ('selection', 'selection_receipt.json', selection)]:
        (root / directory).mkdir()
        write_json(root / directory / name, data)
    protocol = sealed({'format': validation.PROTOCOL, 'status': 'frozen', 'reference_calls_opened': False,
        'source_qualification_sha256': source['content_sha256'], 'source_nodes': 7, 'source_pairs': 8,
        'qualified_eligible_pairs': 5, 'eligible_retention_budget': 4, 'abstain_retained_pairs': 3,
        'arms': list(validation.LABELS), 'primary_candidate': 'human_experimental_top80',
        'controls': ['native_top80', 'pa_top80'], 'minimum_eligible_positive_pairs': 1,
        'minimum_evaluable_exact_bait_labels': 1, 'reference': 'Invented positive calls',
        'input_files': {'artifact_selection_receipt': {'sha256': hashlib.sha256(
            (root / 'selection/selection_receipt.json').read_bytes()).hexdigest()}}})

    def metrics(n=2):
        kept = {'unpruned': n, 'human_experimental_top80': n, 'native_top80': 1,
            'pa_top80': 0, 'ne_top80': n, 'mps_top80': 1, 'combined_experimental_top80': n}
        arms = {arm: {'positive_pairs_retained': k, 'eligible_positive_pairs': n,
            'positive_pairs_lost': n-k, 'micro_retention': k/n, 'isolated_proteins': 0,
            'source_pairs_retained': 8 if arm == 'unpruned' else 7,
            'source_pairs_removed': 0 if arm == 'unpruned' else 1} for arm, k in kept.items()}
        return {'arms': arms, 'primary_unique_eligible_positive_pairs': n,
            'evaluable_exact_author_bait_labels': 1, 'primary_utility_gate_passed': True,
            'coverage_gate_passed': True, 'precision_or_scientific_accuracy_established': False,
            'raw_noncalls_evaluated': False, 'primary_decision': 'Scoped retention gain',
            'native_call_rows_preserved': 4, 'mapping_status_counts': {'resolved': 2, 'unresolved': 2},
            'evaluation_category_row_counts': {'qualified_eligible': 2}, 'zero_denominator_bait_labels': 1}
    report = sealed({'format': validation.RESULT, 'status': 'completed',
        'protocol_sha256': protocol['content_sha256'], 'source_qualification_sha256': source['content_sha256'],
        'source_graph_changed': False, 'ranking_or_threshold_selection_performed': False,
        'primary_candidate': protocol['primary_candidate'], 'controls': protocol['controls'],
        'source_nodes_preserved': 7, 'claim_boundary': 'Positive coassociations only', 'metrics': metrics()})
    for directory, name, data in [('frozen', 'protocol.json', protocol), ('assessment', 'report.json', report)]:
        (root / directory).mkdir()
        write_json(root / directory / name, data)
    qc_root = None
    if qc:
        qc_root = root / 'qc'
        (qc_root / 'frozen').mkdir(parents=True)
        (qc_root / 'results').mkdir()
        qp = sealed({'format': 'biograph-steward.processed-opencell-consumed-qc.v1',
            'status': 'frozen_consumed_QC_correction',
            'original_protocol_sha256': protocol['content_sha256'],
            'policy': {'reference': 'Invented author-processed calls'}})
        qr = sealed({'format': 'biograph-steward.processed-opencell-consumed-qc.v1.result',
            'status': 'completed_consumed_QC_correction',
            'protocol_sha256': qp['content_sha256'], 'original_protocol_sha256': protocol['content_sha256'],
            'new_independent_confirmation': False, 'original_confirmation_modified': False,
            'new_winner_selected': False, 'memberships_source_weights_budgets_changed': False,
            'scientific_accuracy_precision_direct_binding_established': False,
            'resolutions': {'strict_per_call': metrics(), 'entry_family_per_call': metrics(3)}})
        for m in qr['resolutions'].values():
            m['evaluable_exact_author_bait_ENSGs'] = 1
            m['posthoc_fixed_rule_met'] = True
        sealed(qr)
        write_json(qc_root / 'frozen/protocol.json', qp)
        write_json(qc_root / 'results/report.json', qr)
    publication = root / 'comparison'
    validation.publish(root / 'assessment', root / 'frozen', root / 'source', root / 'selection',
                       publication, processed_qc=qc_root)
    return publication


def edit_bound(publication, name, mutate):
    """Reseal bytes and manifest, leaving semantic cross-bindings for the reader."""
    path = publication / name
    value = json.loads(path.read_text())
    mutate(value)
    if 'content_sha256' in value:
        sealed(value)
    write_json(path, value)
    manifest_path = publication / 'publication.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(manifest_path, sealed(manifest))


class BiologicalValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.publication = make_comparison(self.root)

    def test_processed_qc_is_current_but_not_a_second_confirmation(self):
        _, summary, files = validation.load_publication(self.publication)
        current = summary['current_processed_reference_check']
        self.assertFalse(current['new_independent_confirmation'])
        self.assertFalse(summary['scientific_accuracy_established'])
        self.assertEqual(current['strict']['primary_unique_eligible_positive_pairs'], 2)
        self.assertEqual(current['entry_family']['primary_unique_eligible_positive_pairs'], 3)
        html = validation.render_html(summary)
        self.assertIn('Same-study author-processed QC correction', html)
        self.assertIn('no qualified negative reference', html)
        self.assertIn('exact isoform, sequence, gene of origin or construct', html)
        self.assertNotIn('processed_calls.csv', files)

    def test_original_assessment_can_be_published_without_later_qc(self):
        other = self.root / 'other'; other.mkdir()
        publication = make_comparison(other, qc=False)
        _, summary, _ = validation.load_publication(publication)
        self.assertIsNone(summary['current_processed_reference_check'])
        self.assertIn('not asserted equal to the final', validation.render_html(summary))

    def test_byte_changes_missing_or_extra_files_and_symlinks_are_rejected(self):
        original = (self.publication / 'report.json').read_bytes()
        (self.publication / 'report.json').write_bytes(original + b' ')
        with self.assertRaises(ValueError): validation.load_publication(self.publication)
        (self.publication / 'report.json').write_bytes(original)
        (self.publication / 'raw_reference.csv').write_text('not allowed')
        with self.assertRaises(ValueError): validation.load_publication(self.publication)
        (self.publication / 'raw_reference.csv').unlink()
        alias = self.root / 'alias'; alias.symlink_to(self.publication, target_is_directory=True)
        with self.assertRaises(ValueError): validation.load_publication(alias)

    def test_resealed_different_denominator_or_budget_cannot_be_presented(self):
        edit_bound(self.publication, 'report.json', lambda d: d['metrics']['arms']['ne_top80'].update(eligible_positive_pairs=3))
        with self.assertRaises(ValueError): validation.load_publication(self.publication)

    def test_resealed_primary_or_controls_cannot_be_changed_after_evaluation(self):
        edit_bound(self.publication, 'report.json', lambda d: d.update(primary_candidate='ne_top80'))
        with self.assertRaises(ValueError): validation.load_publication(self.publication)

    def test_processed_qc_cannot_claim_another_fresh_confirmation(self):
        edit_bound(self.publication, 'processed_qc_report.json', lambda d: d.update(new_independent_confirmation=True))
        with self.assertRaises(ValueError): validation.load_publication(self.publication)

    def test_partial_qc_or_unsupported_accuracy_claim_is_rejected(self):
        edit_bound(self.publication, 'report.json', lambda d: d['metrics'].update(precision_or_scientific_accuracy_established=True))
        with self.assertRaises(ValueError): validation.load_publication(self.publication)

    def test_incomplete_or_internally_contradictory_qc_is_rejected(self):
        edit_bound(self.publication, 'processed_qc_report.json', lambda d: d.update(status='incomplete'))
        with self.assertRaises(ValueError): validation.load_publication(self.publication)

    def test_listing_skips_other_manifests_without_loading_workspace_graphs(self):
        (self.root / 'workspace').mkdir()
        (self.root / 'workspace/publication.json').write_text('{"format":"other"}')
        (self.root / 'workspace/graph.json').write_text('not graph JSON')
        rows = validation.list_publications(self.root)['comparisons']
        self.assertEqual([r['id'] for r in rows], ['comparison'])
        edit_bound(self.publication, 'processed_qc_report.json', lambda d: d.update(new_winner_selected=True))
        self.assertEqual(validation.list_publications(self.root)['comparisons'], [])


if __name__ == '__main__':
    unittest.main()
