"""Invented identifier-only fixtures contain no CRISPR/coessentiality outcomes."""
from copy import deepcopy
import unittest

from tools.coessentiality_feasibility.identifiers import native_order, map_targets
from tools.coessentiality_feasibility.chromosome import canonical_chromosome
from test_cohort_mapping import gene, protein, registry


class CoessentialityIdentifierTests(unittest.TestCase):
    def test_native_cytoband_ranges_preserve_only_explicit_same_chromosome(self):
        for location, expected in [("2p21-p16.3", "2"), ("16p12.2-p12.1", "16"), ("2p21-2q22.1", "2"),
                                   ("Xq13.1", "X"), ("1p36.3", "1"), ("22q11.2", "22")]:
            self.assertEqual(canonical_chromosome(location), expected)
        for location in (None, "", "mitochondrial", "2p21-3q22", "2p21 or 3q22", "chr2", "23p21", "02p21", " 2p21"):
            self.assertIsNone(canonical_chromosome(location))

    def test_entire_author_order_is_required_not_a_convenient_name_subset(self):
        rows = native_order("OLD_A\nB\n", "Broad_ID,OLD_A (1),B (2)\n")
        self.assertEqual(rows[0]["native_ncbi_gene_id"], "1")
        with self.assertRaisesRegex(ValueError, "order differs"):
            native_order("B\nOLD_A\n", "Broad_ID,OLD_A (1),B (2)\n")

    def test_observation_rows_missing_native_IDs_and_duplicate_names_fail_closed(self):
        for text, header in [("A\n", "Broad_ID,A (1)\nACH-1,0.3\n"),
                             ("A\n", "Broad_ID,A\n"), ("A\nA\n", "Broad_ID,A (1),A (2)\n")]:
            with self.subTest(text=text, header=header), self.assertRaises(ValueError):
                native_order(text, header)

    def test_native_Entrez_ID_survives_symbol_change_without_alias_inference(self):
        reg = registry([gene("HGNC:1", "NEW_A")], [protein("P00001", "HGNC:1", "NEW_A")])
        order = native_order("OLD_A\n", "Broad_ID,OLD_A (1)\n")
        value = map_targets([{"uniprot": "P00001", "sym": "PHAROS_OLD"}], reg, order)[0]
        self.assertEqual(value["matrix_eligibility"], "exact_native_Entrez_ID")
        self.assertEqual(value["native_matrix_gene"]["native_symbol"], "OLD_A")
        self.assertEqual(value["current_HGNC_symbol"], "NEW_A")
        self.assertFalse(value["gene_protein_identity_claimed"])
        self.assertFalse(value["native_symbol_alias_matching_performed"])

    def test_current_symbol_identity_cannot_override_wrong_or_missing_native_Entrez_ID(self):
        reg = registry([gene("HGNC:1", "A")], [protein("P00001", "HGNC:1", "A")])
        for order in [native_order("A\n", "Broad_ID,A (999)\n"),
                      native_order("A\nB\n", "Broad_ID,A (1),B (1)\n")]:
            value = map_targets([{"uniprot": "P00001"}], reg, order)[0]
            self.assertIsNone(value["native_matrix_gene"])

    def test_two_explicit_products_can_map_to_one_gene_without_becoming_same_protein(self):
        reg = registry([gene("HGNC:1", "A", products="P00001|P00002")],
                       [protein("P00001", "HGNC:1", "A"), protein("P00002", "HGNC:1", "A")])
        targets = [{"uniprot": "P00001"}, {"uniprot": "P00002"}]; before = deepcopy(targets)
        rows = map_targets(targets, reg, native_order("A\n", "Broad_ID,A (1)\n"))
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["subject"], rows[1]["subject"])
        self.assertEqual({x["native_matrix_gene"]["matrix_index"] for x in rows}, {0})
        self.assertEqual(targets, before)
        with self.assertRaisesRegex(ValueError, "repeat"):
            map_targets(targets + targets[:1], reg, native_order("A\n", "Broad_ID,A (1)\n"))


if __name__ == "__main__":
    unittest.main()
