"""Invented native TSVs test source contracts, not biological accuracy."""
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import bioplex_source as bp
from biograph_steward.client import digest, write_json


def sealed(value):
    value = {k: v for k, v in value.items() if k != "content_sha256"}
    return {**value, "content_sha256": digest(value)}


def companion(a="1", b="2", ua="P00533", ub="P01116", **updates):
    value = dict(GeneA=a, GeneB=b, UniprotA=ua, UniprotB=ub,
                 SymbolA="invented A", SymbolB="invented B", pW="0.01", pNI="0.09", pInt="0.90")
    return {**value, **updates}


def directed(a="1", b="2", **updates):
    value = {"Bait GeneID": a, "Bait Symbol": "invented bait",
             "Prey GeneID": b, "Prey Symbol": "invented prey"}
    return {**value, **updates}


def raw(rows, columns):
    out = StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, delimiter="\t", lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def baseline():
    snapshot = sealed({"data_kind": "live_pharos", "targets": [{"uniprot": a} for a in ["P00533", "P01116"]]})
    graph = {"snapshot_sha256": snapshot["content_sha256"],
             "nodes": [{"id": "UniProtKB:" + a, "category": "biolink:Protein"} for a in ["P00533", "P01116"]],
             "edges": [{"id": "original_pharos", "subject": "UniProtKB:P01116", "object": "UniProtKB:P00533",
                        "record_kind": "protein_interaction", "original_score": "0.999"}],
             "assertions": [{"id": "original_assertion"}], "review_events": [{"original": True}]}
    return snapshot, graph


class BioPlexReaderTests(unittest.TestCase):
    def parse(self, c=None, d=None, accessions=None):
        return bp.parse_release(raw(c if c is not None else [companion()], bp.COMPANION_COLUMNS),
                                raw(d if d is not None else [directed()], bp.DIRECTED_COLUMNS),
                                accessions or ["P00533", "P01116"])

    def test_native_bait_roles_not_companion_order_or_causality(self):
        result = self.parse([companion(a="2", b="1", ua="P01116", ub="P00533")])
        row = result["observations"][0]
        self.assertEqual((row["bait"]["gene_id"], row["bait"]["uniprot"]), ("1", "UniProtKB:P00533"))
        self.assertEqual(row["prey"]["gene_id"], "2")
        self.assertIsNone(row["graph_edge_id"])
        self.assertEqual(row["source_scores_raw"]["pInt"], "0.90")
        self.assertEqual(row["score_scope"], "native_undirected_gene_pair_not_bait_direction_specific")

    def test_native_reciprocal_rows_preserved_not_invented(self):
        self.assertEqual(self.parse()["summary"]["selected_source_observations"], 1)
        result = self.parse(d=[directed(), directed("2", "1")])
        self.assertEqual(result["summary"]["selected_source_observations"], 2)
        self.assertEqual(result["summary"]["selected_unique_pairs"], 1)
        self.assertNotEqual(*(r["id"] for r in result["observations"]))

    def test_global_conflicting_gene_mapping_quarantines_tested_row(self):
        result = self.parse([companion(), companion("1", "3", "P15056", "P04637")],
                            [directed(), directed("1", "3")])
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["summary"]["quarantined_gene_ids"], 1)

    def test_any_blank_accession_contaminates_gene_globally(self):
        result = self.parse([companion(), companion("1", "3", "", "P04637")],
                            [directed(), directed("1", "3")])
        self.assertEqual(result["observations"], [])

    def test_noninjective_literal_and_invalid_gene_assignment_quarantine(self):
        for bad_gene in ["3", ""]:
            with self.subTest(bad_gene=bad_gene):
                c = [companion(), companion(bad_gene, "4", "P00533", "P04637")]
                d = [directed()] + ([directed(bad_gene, "4")] if bad_gene else [])
                self.assertEqual(self.parse(c, d)["observations"], [])

    def test_isoform_suffix_is_not_stripped_or_symbol_mapped(self):
        result = self.parse([companion(ua="P00533-2")])
        self.assertEqual(result["observations"], [])
        literal = self.parse([companion(ua="P00533-2")], accessions=["P00533-2", "P01116"])
        self.assertEqual(literal["observations"][0]["bait"]["literal_uniprot_accession"], "P00533-2")

    def test_duplicate_companion_scores_preserve_all_no_first_choice(self):
        row = self.parse([companion(), companion(pInt="0.85", pNI="0.14")])["observations"][0]
        self.assertEqual(row["source_scores_raw"], {})
        self.assertEqual(len(row["companion_records"]), 2)
        self.assertEqual([r["source_scores_raw"]["pInt"] for r in row["companion_records"]], ["0.90", "0.85"])

    def test_full_gene_pair_inventory_must_match(self):
        with self.assertRaisesRegex(ValueError, "inventories differ"):
            self.parse([companion(), companion("1", "3", "P00533", "P04637")])

    def test_class_score_validation_without_new_threshold(self):
        self.assertEqual(self.parse([companion(pInt="0.1")])["summary"]["selected_source_observations"], 1)
        for score in ["", "nan", "inf", "1.01", "-0.01"]:
            with self.subTest(score=score), self.assertRaises(ValueError):
                self.parse([companion(pInt=score)])

    def test_quoted_newline_and_row_digest_are_literal(self):
        d = directed(**{"Bait Symbol": 'invented "quoted"\nname'})
        row = self.parse(d=[d])["observations"][0]
        self.assertEqual(row["bait"]["symbol"], d["Bait Symbol"])
        self.assertEqual(row["directed_record"]["decoded_source_row_sha256"], digest(d))
        self.assertEqual(row["directed_record"]["source_row_ordinal"], 2)

    def test_wrong_header_width_or_scope_rejected(self):
        with self.assertRaises(ValueError):
            bp.parse_release(b"wrong\theader\n", raw([directed()], bp.DIRECTED_COLUMNS), ["P00533", "P01116"])
        c = raw([companion()], bp.COMPANION_COLUMNS) + b"too\tfew\n"
        with self.assertRaises(ValueError):
            bp.parse_release(c, raw([directed()], bp.DIRECTED_COLUMNS), ["P00533", "P01116"])
        with self.assertRaises(ValueError):
            self.parse(accessions=["P01116", "P00533"])


class BioPlexPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.c, self.d, self.publication = [self.root / name for name in ["companion.tsv", "directed.tsv", "publication"]]
        self.c.write_bytes(raw([companion()], bp.COMPANION_COLUMNS))
        self.d.write_bytes(raw([directed()], bp.DIRECTED_COLUMNS))
        self.snapshot, self.graph = baseline()
        for name, value in [("COMPANION_SHA256", hashlib.sha256(self.c.read_bytes()).hexdigest()),
                            ("DIRECTED_SHA256", hashlib.sha256(self.d.read_bytes()).hexdigest())]:
            p = patch.object(bp, name, value); p.start(); self.addCleanup(p.stop)
        self.manifest = bp.publish_release(self.c, self.d, self.snapshot, self.publication)

    def reseal(self):
        value = json.loads((self.publication / "publication.json").read_text())
        value["files"] = {p.relative_to(self.publication).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in self.publication.rglob("*") if p.is_file() and p.name != "publication.json"}
        write_json(self.publication / "publication.json", sealed(value))

    def test_private_publication_and_context_only_prepare_do_not_mutate(self):
        before = deepcopy((self.snapshot, self.graph))
        manifest, projection, files = bp.load_publication(self.publication)
        value = bp.prepare(self.snapshot, self.graph, manifest, projection)
        self.assertEqual(value["nodes"], []); self.assertEqual(value["edges"], [])
        self.assertEqual((self.snapshot, self.graph), before)
        row = value["observations"][0]
        self.assertEqual(row["baseline_pair_edge_ids"], ["original_pharos"])
        self.assertIsNone(row["graph_edge_id"])
        self.assertFalse(row["biologically_validated"])
        self.assertIsNone(row["independent_evidence_count"])
        self.assertTrue(row["source_locators"][0]["locator"].startswith("extension_sources/bioplex/"))
        self.assertIsNone(manifest["source_license"]["license"])
        self.assertFalse(manifest["public_raw_data_export_authorized"])
        self.assertEqual(files[bp.COMPANION_FILE], self.c.read_bytes())
        self.assertIn("exact row-level clone", row["context_qualification"])
        self.assertFalse(row["context_review"]["human_expert_reviewed"])
        self.assertIn("not an identifier supplied", row["cell_line_id_basis"])
        self.assertIn("Primary abstract", next(c for c in row["citations"] if c["id"] == "PMID:8044777")["inspected_scope"])

    def test_native_byte_tamper_rejected_even_outer_resealed(self):
        p = self.publication / bp.COMPANION_FILE
        p.write_bytes(p.read_bytes().replace(b"0.90", b"0.99"))
        self.reseal()
        with self.assertRaisesRegex(ValueError, "pinned native source bytes"):
            bp.load_publication(self.publication)

    def test_projection_score_tamper_rejected_even_outer_resealed(self):
        p = self.publication / "projection.json"
        projection = json.loads(p.read_text())
        projection["observations"][0]["source_scores_raw"]["pInt"] = "0.99"
        write_json(p, sealed(projection)); self.reseal()
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            bp.load_publication(self.publication)

    def test_scope_snapshot_and_missing_pair_reject(self):
        manifest, projection, _ = bp.load_publication(self.publication)
        changed = sealed({**self.snapshot, "changed": True})
        with self.assertRaisesRegex(ValueError, "exactly this primary snapshot"):
            bp.prepare(changed, self.graph, manifest, projection)
        changed_graph = deepcopy(self.graph); changed_graph["edges"] = []
        with self.assertRaisesRegex(ValueError, "already represented"):
            bp.prepare(self.snapshot, changed_graph, manifest, projection)

    def test_rights_or_false_flags_cannot_be_strengthened(self):
        manifest, projection, _ = bp.load_publication(self.publication)
        for field in ["public_raw_data_export_authorized", "independent_validation_performed"]:
            changed = sealed({**manifest, field: True})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "private source preparation"):
                bp.prepare(self.snapshot, self.graph, changed, projection)
        p = self.publication / bp.INTAKE_FILE
        intake = json.loads(p.read_text()); intake["source_license"]["license"] = "MIT"
        write_json(p, sealed(intake)); self.reseal()
        with self.assertRaisesRegex(ValueError, "rights metadata"):
            bp.load_publication(self.publication)

    def test_no_source_symlink_capture(self):
        link = self.root / "linked.tsv"; link.symlink_to(self.c)
        with self.assertRaises(ValueError):
            bp.publish_release(link, self.d, self.snapshot, self.root / "linked_publication")


if __name__ == "__main__":
    unittest.main()
