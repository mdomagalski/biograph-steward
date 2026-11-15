import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.file_utils import sha
from tools.reference_accuracy import ppi_references as p


CANONICAL = {'P00001': 'MAAA', 'P00002': 'MCCC'}


def native(**updates):
    row = {'SNOOPPI_final_label': 'positive', '_source_split': 'positive',
           '_source_row_1based': 1, 'SNOOPPI_Pair_ID': 'invented_pair',
           'SNOOPPI_Labeled_Pair_ID': 'invented_positive_pair',
           'MI0915_final_label': 'positive', 'seq_sort_origin_categories': 'exact_seq_sort_seen_in_original_intact',
           'unique_interaction_mi_terms': 'MI:0407 (direct interaction)',
           'feature_relationship_types': None, 'feature_relationship_summary': None,
           'wildtype_SNOOPPI_final_label': None, 'intact_interaction_ids': 'invented_interaction',
           'pubmed_ids': '1', 'publication_year_min': '2000', 'publication_year_max': '2000',
           'assays_unique': 'MI:0096 (pull down)'}
    for side, accession in zip(('A', 'B'), CANONICAL):
        row.update({'partner_' + side + '_species': '9606 (human)',
                    'partner_' + side + '_uniprot_ids': accession + '-0',
                    'partner_' + side + '_sequence': CANONICAL[accession],
                    'partner_' + side + '_mol_type': 'protein',
                    'partner_' + side + '_host_context': 'In vitro'})
    row.update(updates)
    return row


def prepare(row):
    return p.canonical_frame([row], set(CANONICAL), CANONICAL)


class PPIReferencePreparationTests(unittest.TestCase):
    def test_exact_original_controls_may_carry_ptm_counterpart_relationships(self):
        r = native(feature_relationship_types='ptm',
                   feature_relationship_summary='wildtype_label=positive; modified_label=negative',
                   wildtype_SNOOPPI_final_label='positive',
                   seq_sort_origin_categories='exact_seq_sort_seen_in_original_intact | derived_from_ptm_feature')
        result = prepare(r)
        self.assertEqual(len(result['canonical_gold']), 1)
        self.assertEqual(result['canonical_gold'][0]['reference_label'], 'positive')

    def test_exact_mutant_negative_is_retained_but_not_canonical_wildtype_false(self):
        result = prepare(native(SNOOPPI_final_label='negative', _source_split='negative',
                                partner_A_sequence='MATA', partner_A_uniprot_ids='P00001-0_mutated',
                                seq_sort_origin_categories='derived_from_mutation_feature'))
        self.assertEqual(result['canonical_gold'], [])
        self.assertEqual(result['experimental_state_sensitivity'][0]['reference_label'], 'negative')
        self.assertFalse(result['experimental_state_sensitivity'][0]['eligible_canonical_gold'])

    def test_ptm_encoded_sequence_is_not_stripped_to_match_canonical(self):
        result = prepare(native(partner_A_sequence='<M1+MI:0170>AAA'))
        self.assertEqual(result['canonical_gold'], [])
        self.assertIn('A_assayed_sequence_not_exact_full_canonical', result['all_base_pair_candidates'][0]['exclusion_reasons'])

    def test_inferred_binding_region_variant_is_not_experimentally_verified_gold(self):
        result = prepare(native(SNOOPPI_final_label='negative',
                                seq_sort_origin_categories='derived_from_binding_site_feature'))
        self.assertEqual(result['canonical_gold'], [])
        self.assertEqual(result['experimental_state_sensitivity'], [])
        self.assertTrue(result['all_base_pair_candidates'][0]['inferred_binding_region_sequence'])

    def test_ambiguous_accession_does_not_pick_matching_candidate(self):
        result = prepare(native(partner_A_uniprot_ids='P00001-0 | P00003-0'))
        self.assertEqual(result['canonical_gold'], [])
        self.assertIn('ambiguous_base_accession', result['all_base_pair_candidates'][0]['exclusion_reasons'])

    def test_unknown_author_label_never_becomes_negative(self):
        with self.assertRaisesRegex(ValueError, 'unknown author'):
            prepare(native(SNOOPPI_final_label='unknown'))
        with self.assertRaisesRegex(ValueError, 'unknown split'):
            p.native_snooppi('unused.parquet', 'unknown')

    def test_native_isoform_stays_literal_and_cannot_join_base_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); path = root / 'manual.tsv'
            path.write_text('P00001-2\tP00002\t123\tMI:0096 - pull down\n')
            negative = p.manual_negative_rows(path, 'unfiltered_manual_expert_curated_primary', root=root)
            self.assertEqual(negative[0]['pair'], ('P00001-2', 'P00002'))
            panel, _ = p.manual_frame([], negative, set(CANONICAL), set(CANONICAL))
            self.assertEqual(panel, [])

    def test_pmc_publication_is_preserved_without_pmid_guess(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); path = root / 'manual.tsv'
            path.write_text('P00001\tP00002\tPMC123\tMI:0096 - pull down\n')
            negative = p.manual_negative_rows(path, 'unfiltered_manual_expert_curated_primary', root=root)
            self.assertEqual(negative[0]['publication_namespace'], 'PMCID')
            self.assertEqual(negative[0]['publication_id_raw'], 'PMC123')
            self.assertIsNone(negative[0]['PMID'])

    def test_opposing_manual_and_positive_curations_become_unknown(self):
        positive = prepare(native())['canonical_gold']
        negative = [{'pair': ('P00001', 'P00002'), 'PMID': '2',
                     'source_filter_status': 'unfiltered_manual_expert_curated_primary'}]
        panel, _ = p.manual_frame(positive, negative, set(CANONICAL), set(CANONICAL))
        self.assertEqual(panel[0]['reference_label'], 'unknown')
        self.assertTrue(panel[0]['conflict_rule_applied'])
        self.assertFalse(panel[0]['generic_functional_association_truth_label'])

    def test_absence_of_manual_or_positive_row_does_not_create_negative_pair(self):
        panel, _ = p.manual_frame([], [], set(CANONICAL), set(CANONICAL))
        self.assertEqual(panel, [])

    def test_source_pin_is_checked_before_parser(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); path = root / 'source.json'; path.write_text('{}')
            spec = {'file': str(path), 'sha256': sha(path)}
            path.write_text(json.dumps({'changed': True}))
            with self.assertRaisesRegex(ValueError, 'byte pin differs'):
                p.checked(spec, root)

    def test_source_changed_during_preparation_cannot_receive_complete_receipt(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root) as folder:
            base = Path(folder); inputs = base / 'inputs'; inputs.mkdir()
            def spec(name, content, **metadata):
                path = inputs / name; path.write_text(content)
                return {'file': str(path), 'sha256': sha(path), **metadata}
            fasta = spec('canonical.fasta', 'invented fixture', expected_records=2)
            positive = spec('positive.parquet', 'invented fixture', expected_rows=1)
            negative = spec('negative.parquet', 'invented fixture', expected_rows=0)
            frames = spec('frames.json', json.dumps({'cohort': list(CANONICAL)}),
                          key_path=['cohort'], expected_proteins=2)
            manual = spec('manual.tsv', 'P00001\tP00002\t123\tMI:0096 - pull down\n',
                          status='unfiltered_manual_expert_curated_primary', expected_rows=1)
            config = {'format': p.FORMAT, 'source_profile': p.SOURCE_PROFILE,
                      'producer_source': {'file': str(Path(p.__file__).resolve()), 'sha256': sha(p.__file__)},
                      'canonical_fasta': fasta, 'snooppi': {'positive': positive, 'negative': negative},
                      'frames': {'cohort': frames}, 'manual_negative_sources': [manual]}
            path = inputs / 'configuration.json'; path.write_text(json.dumps(config))
            original = p.canonical_frame
            def mutate(*args):
                result = original(*args)
                Path(fasta['file']).write_text('changed after reader admitted original source')
                return result
            with patch.object(p, 'human_canonical_sequences', return_value=CANONICAL), \
                 patch.object(p, 'native_snooppi', side_effect=lambda path, label: [native()] if label == 'positive' else []), \
                 patch.object(p, 'canonical_frame', side_effect=mutate):
                with self.assertRaisesRegex(ValueError, 'reference source changed'):
                    p.run(path, sha(path), base / 'result', root=root)
            self.assertFalse((base / 'result/preparation_receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
