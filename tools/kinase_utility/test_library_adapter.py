"""Synthetic source-contract checks; no biological reference or real data."""
import csv
from io import StringIO
import unittest

from library_adapter import HEADER, canonical_window, qualify_library, map_ensembl_measurement_identifier
from test_pilot_methods import fixture, gene, protein


def encoded(rows):
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def row(**changes):
    return {**dict(source="ALPHA", target="BETA_S2", target_protein="BETA", position="S2", mor="1",
                   sequence="______MSTYS____"), **changes}


class LibraryAdapterTests(unittest.TestCase):
    def run_adapter(self, rows, missing=("NA",)):
        registry, captured = fixture()
        return qualify_library(encoded(rows), registry=registry, sequence_reference=captured,
                               sequence_missing_tokens=missing)

    def test_terminal_window_and_duplicate_support_do_not_add_weight(self):
        self.assertEqual(canonical_window("MSTYS", 2), "______MSTYS____")
        result = self.run_adapter([row(), row()])
        self.assertEqual(result["summary"]["compatible_rows"], 2)
        self.assertEqual(result["summary"]["unique_memberships"], 1)
        self.assertEqual(result["memberships"][0]["supporting_row_ordinals"], [1, 2])
        self.assertFalse(result["independent_experiment_count_established"])

    def test_explicit_missing_flank_is_unreported_but_present_conflict_blocks(self):
        result = self.run_adapter([row(sequence="ABSENT"), row(sequence="_______STYS____")], missing=("ABSENT",))
        self.assertEqual(result["rows"][0]["flank_reporting"], "unreported")
        self.assertEqual(result["rows"][0]["status"], "compatible_membership")
        self.assertIn("present_flank_conflicts_with_canonical_reference", result["rows"][1]["reasons"])
        self.assertEqual(self.run_adapter([row(sequence="NA")], missing=())["summary"]["compatible_rows"], 0)

    def test_inconsistent_site_incidence_and_unknown_genes_do_not_get_rescued(self):
        for item in [row(target="BETA_T3"), row(mor="-1"), row(position="S2;T3", target="BETA_S2;T3"),
                     row(source="UNKNOWN"), row(position="T2", target="BETA_T2")]:
            self.assertEqual(self.run_adapter([item])["summary"]["compatible_rows"], 0)

    def test_source_contract_is_explicit_and_other_genes_work(self):
        result = self.run_adapter([row(source="GAMMA", target="DELTA_Y4", target_protein="DELTA", position="Y4",
                                       sequence=canonical_window("MSTYS", 4))])
        self.assertEqual(result["candidates"][0]["gene"], "GAMMA")
        registry, captured = fixture()
        with self.assertRaises(ValueError):
            qualify_library(b"wrong,header\na,b\n", registry=registry, sequence_reference=captured,
                            sequence_missing_tokens=["NA"])

    def test_four_field_measurement_is_not_mistaken_for_a_flank_or_canonical_isoform(self):
        g = gene(2, "BETA"); g["ensembl_gene_id"] = "ENSG00000000002"
        registry, captured = fixture([g], [protein(2, "BETA")])
        result = map_ensembl_measurement_identifier("BETA|S2|ENSG00000000002|ENSP00000000002",
                                                  registry=registry, sequence_reference=captured)
        self.assertEqual(result["status"], "qualified")
        self.assertEqual(result["ensembl_protein_correspondence"], "not_assessed")
        self.assertFalse(result["experimental_proteoform_identity_established"])
        for identifier in ["BETA|S2|ENSG00000000003|ENSP00000000002", "BETA|S2|NA|NA",
                           "BETA|S2|PEPTIDE|PEPTIDE", "BETA_S2|BETA|S2"]:
            result = map_ensembl_measurement_identifier(identifier, registry=registry, sequence_reference=captured)
            self.assertNotEqual(result["status"], "qualified")


if __name__ == "__main__":
    unittest.main()
