"""Invented source records test qualifier preservation, not biological truth."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet, go_qualification as go
from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from test_normalization import fixture


def record(number=8, **changes):
    fields = ["UniProtKB", "P00001", "G", "NOT|enables", "GO:0000001",
              "PMID:36949045|OTHER:one", "IPI", "UniProtKB:P00002,UniProtKB:P00003|UniProtKB:P00004",
              "F", "name", "name2|name3", "protein", "taxon:9606|taxon:10090", "20260101", "UniProt",
              "occurs_in(CL:0000001),part_of(GO:0000002)|occurs_in(CL:0000003)", "UniProtKB:P00001-2"]
    for key, value in changes.items():
        fields[int(key)] = value
    parsed = dict(zip(go.GAF_FIELDS, fields))
    for key in ("Qualifier", "DB:Reference", "With", "Synonym", "Taxon_ID"):
        parsed[key] = parsed[key].split("|")
    return go.native_record(number, "\t".join(fields), fields, parsed, "a" * 64)


def edge(**changes):
    result = {"id": "edge:test", "assertion_id": "assertion:test", "record_kind": "go_annotation",
              "subject": "UniProtKB:P00001", "object": "GO:0000001",
              "evidence_record": {"goid": "GO:0000001", "evidence": "IPI", "assigned_by": "UniProt", "type": "F"},
              "annotation_context": {"relation": None, "negated": None, "extensions": None}}
    result.update(changes)
    return result


class NativeRecordTests(unittest.TestCase):
    def test_exact_native_row_negation_form_reference_aliases_and_logical_groups_survive(self):
        row = record()
        self.assertEqual(row["raw_fields"], row["raw_line"].split("\t"))
        self.assertEqual(row["raw_line_sha256"], hashlib.sha256(row["raw_line"].encode()).hexdigest())
        self.assertEqual(row["qualifier_tokens"], ["NOT", "enables"])
        self.assertEqual(row["relation_literal"], "enables")
        self.assertTrue(row["negated"])
        self.assertEqual(row["gene_product_form_id"], "UniProtKB:P00001-2")
        self.assertEqual(row["reference_identifiers"], ["PMID:36949045", "OTHER:one"])
        self.assertIn("one cited reference", row["reference_group_semantics"])
        self.assertEqual(row["with_from_or_groups_raw"],
                         [["UniProtKB:P00002", "UniProtKB:P00003"], ["UniProtKB:P00004"]])
        self.assertEqual(row["extension_or_groups_raw"],
                         [["occurs_in(CL:0000001)", "part_of(GO:0000002)"], ["occurs_in(CL:0000003)"]])
        self.assertFalse(row["extension_semantic_validation_performed"])

    def test_first_taxon_controls_subject_and_reference_overlap_is_incomplete_exact_flag(self):
        row = record(**{"12": "taxon:10090|taxon:9606", "5": "PMID:369490450"})
        self.assertFalse(row["subject_taxon_is_human"])
        self.assertEqual(row["taxon_ids"], ["taxon:10090", "taxon:9606"])
        self.assertEqual(row["known_consumed_reference_ids"], [])
        self.assertFalse(row["reference_independence_established"])
        self.assertEqual(record()["known_consumed_reference_ids"], ["PMID:36949045"])

    def test_duplicate_native_content_remains_separate_by_source_line(self):
        a, b = record(8), record(9)
        self.assertEqual(a["raw_line"], b["raw_line"])
        self.assertNotEqual(a["id"], b["id"])

    def test_required_relation_native_columns_and_parser_binding_fail_closed(self):
        for changes in ({"3": ""}, {"3": "NOT"}, {"3": "NOT|NOT|enables"},
                        {"3": "enables|contributes_to"}, {"4": "GO:bad"}, {"12": "9606"}, {"5": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                record(**changes)
        row = record()
        with self.assertRaisesRegex(ValueError, "17 fields"):
            go.native_record(1, row["raw_line"], row["raw_fields"][:-1], row["parsed"], "a" * 64)
        parsed = deepcopy(row["parsed"])
        parsed["DB_Object_ID"] = "P00002"
        with self.assertRaisesRegex(ValueError, "differs from native"):
            go.native_record(1, row["raw_line"], row["raw_fields"], parsed, "a" * 64)


class CompatibilityTests(unittest.TestCase):
    def test_one_compatible_row_never_establishes_identity_or_backfills_original(self):
        graph = {"edges": [edge()]}
        before = deepcopy(graph)
        result = go.project_compatibilities(graph, [record()])[0]
        self.assertEqual(result["candidate_count"], 1)
        self.assertFalse(result["historical_record_identity_established"])
        self.assertFalse(result["original_qualifiers_backfilled"])
        self.assertEqual(result["pruning_decision"], "abstain")
        self.assertEqual(graph, before)

    def test_positive_and_not_contexts_are_all_preserved_instead_of_selecting_a_winner(self):
        rows = [record(8), record(9, **{"3": "enables", "16": "", "15": ""})]
        result = go.project_compatibilities({"edges": [edge()]}, rows)[0]
        self.assertEqual(result["native_record_ids"], [r["id"] for r in rows])
        self.assertEqual(result["candidate_polarities"], ["NOT", "positive"])
        self.assertTrue(result["both_positive_and_not_candidates"])
        self.assertEqual(result["candidate_product_forms"], ["", "UniProtKB:P00001-2"])
        self.assertEqual(result["candidate_count"], 2)
        self.assertFalse(result["biological_truth_assessed"])

    def test_all_projection_fields_are_exact_and_unmatched_is_unknown(self):
        for changes in ({"0": "OtherDB"}, {"1": "P00001-2"}, {"4": "GO:0000002"},
                        {"6": "IDA"}, {"14": "uniprot"}, {"8": "P"}):
            with self.subTest(changes=changes):
                result = go.project_compatibilities({"edges": [edge()]}, [record(**changes)])[0]
                self.assertEqual(result["candidate_count"], 0)
                self.assertEqual(result["status"], "no_compatible_native_record")
                self.assertEqual(result["pruning_decision"], "abstain")
        with self.assertRaisesRegex(ValueError, "repeat"):
            go.project_compatibilities({"edges": [edge()]}, [record(), record()])
        with self.assertRaisesRegex(ValueError, "exact source projection"):
            go.project_compatibilities({"edges": [edge(object="GO:0000002")]}, [])

    def test_unmatched_diagnostics_preserve_every_exact_subject_go_alternative_without_aliasing(self):
        rows = [record(8, **{"14": "UniProtKB"}),
                record(9, **{"6": "IDA", "14": "Other", "8": "P"})]
        value = go.project_compatibilities({"edges": [edge()]}, rows)[0]
        self.assertEqual(value["status"], "no_compatible_native_record")
        self.assertEqual(value["candidate_count"], 0)
        self.assertEqual(value["native_record_ids"], [])
        self.assertEqual(value["exact_subject_go_native_record_ids"], [r["id"] for r in rows])
        self.assertEqual(value["exact_subject_go_candidate_count"], 2)
        self.assertEqual(value["unmatched_projection_field_differences"], [
            {"native_record_id": rows[0]["id"], "differing_fields": ["assigned_by"]},
            {"native_record_id": rows[1]["id"], "differing_fields": ["evidence_code", "assigned_by", "aspect"]}])
        self.assertEqual(value["diagnostic_status"], "exact_subject_go_present_projection_fields_differ")
        self.assertEqual(value["pruning_decision"], "abstain")
        self.assertFalse(value["diagnostic_identity_established"])
        self.assertFalse(value["historical_record_identity_established"])

    def test_absent_subject_go_and_strict_matches_have_distinct_diagnostic_states(self):
        absent = go.project_compatibilities({"edges": [edge()]}, [record(**{"4": "GO:0000002"})])[0]
        self.assertEqual(absent["diagnostic_status"], "no_exact_subject_go_native_record")
        self.assertEqual(absent["exact_subject_go_native_record_ids"], [])
        self.assertEqual(absent["unmatched_projection_field_differences"], [])
        strict = go.project_compatibilities({"edges": [edge()]},
                                          [record(8), record(9, **{"14": "UniProtKB"})])[0]
        self.assertEqual(strict["status"], "one_compatible_native_record")
        self.assertEqual(strict["candidate_count"], 1)
        self.assertEqual(strict["exact_subject_go_candidate_count"], 2)
        self.assertEqual(strict["diagnostic_status"], "strict_projection_candidate_present")
        self.assertEqual(strict["unmatched_projection_field_differences"], [])


class NativePacketTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.run, self.packet, self.out = (self.root / name for name in ("run", "packet", "out"))
        self.graph = save_run(fixture(), self.run)
        self.manifest = gold_packet.export_packet(self.run, self.packet)
        self.before = {p.relative_to(self.packet).as_posix(): sha(p) for p in self.packet.rglob("*") if p.is_file()}
        self.gaf = self.root / "invented.gaf.gz"
        with gzip.open(self.gaf, "wt", newline="") as handle:
            handle.write("!gaf-version: 2.2\n!generated-by: INVENTED\n!date-generated: 2026-01-01\n" + record()["raw_line"] + "\n")
        self.pin = sha(self.gaf)
        self.source = {"headers": ["!gaf-version: 2.2"], "gaf_sha256": self.pin, "total_source_rows": 1,
                       "parser": {"package": "biopython", "version": "1.88", "function": "fixture-only"}}

    def qualify(self, **changes):
        # The writer is tested without an optional parser installation. Its
        # actual Biopython producer is exercised separately with the real GAF.
        with patch.object(go, "read_native_gaf", return_value=([], self.source)):
            return go.qualify_go_context(self.packet, self.gaf, changes.pop("output", self.out),
                                         expected_gaf_sha256=changes.pop("expected_gaf_sha256", self.pin), **changes)

    def test_complete_go_inventory_native_copy_and_source_graph_stay_unchanged(self):
        report = self.qualify()
        rows = [json.loads(line) for line in (self.out / "edge_compatibilities.jsonl").read_text().splitlines()]
        expected = {e["id"] for e in self.graph["edges"] if e.get("record_kind") == "go_annotation"}
        self.assertEqual({r["edge_id"] for r in rows}, expected)
        self.assertTrue(all(r["pruning_decision"] == "abstain" for r in rows))
        self.assertEqual(report["counts"]["no_compatible_native_record"], len(expected))
        self.assertEqual(report["counts"]["unmatched_with_exact_subject_go_native_records"], 0)
        self.assertEqual(report["counts"]["unmatched_without_exact_subject_go_native_records"], len(expected))
        self.assertEqual((self.out / "source/annotations.gaf.gz").read_bytes(), self.gaf.read_bytes())
        self.assertEqual(report["content_sha256"], digest({k:v for k,v in report.items() if k != "content_sha256"}))
        self.assertFalse(report["scientific_accuracy_measured"])
        self.assertFalse(report["original_qualifiers_backfilled"])
        self.assertEqual(self.before, {p.relative_to(self.packet).as_posix(): sha(p) for p in self.packet.rglob("*") if p.is_file()})

    def test_invalid_gold_packet_rejected_before_native_parser_or_output(self):
        (self.packet / "source/graph.json").write_text("{}")
        with patch.object(go, "read_native_gaf") as reader, self.assertRaises(ValueError):
            go.qualify_go_context(self.packet, self.gaf, self.out, expected_gaf_sha256=self.pin)
        reader.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_immutable_output_and_source_pin_are_required(self):
        for output in (self.packet, self.packet / "derived", self.root):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.qualify(output=output)
        for pin in (None, "bad", "0" * 64):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                go.read_native_gaf(self.gaf, {"P00001"}, pin)
        self.assertFalse(self.out.exists())

    def test_gaf_symlink_and_nonfile_inputs_are_rejected_before_parser_import(self):
        link = self.root / "gaf-link.gz"
        link.symlink_to(self.gaf)
        for path in (link, self.root, self.root / "missing.gaf.gz"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "ordinary nonsymlink"):
                go.read_native_gaf(path, {"P00001"}, self.pin)
        packet_link = self.root / "packet-link"
        packet_link.symlink_to(self.packet, target_is_directory=True)
        with patch.object(go, "read_native_gaf") as reader, self.assertRaises(ValueError):
            go.qualify_go_context(packet_link, self.gaf, self.out, expected_gaf_sha256=self.pin)
        reader.assert_not_called()
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
