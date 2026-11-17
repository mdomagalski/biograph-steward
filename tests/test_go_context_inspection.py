"""Source-bound native inspection on invented, sealed GOA sidecars."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import go_context_inspection as inspection
from biograph_steward import go_qualification as go, gold_packet
from biograph_steward.client import canonical, digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from test_go_native_qualification import record
from test_normalization import fixture


class NativeContextInspectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        run, self.packet, self.context = (self.root / name for name in ("run", "packet", "context"))
        self.graph = save_run(fixture(), run)
        gold_packet.export_packet(run, self.packet)
        edge = next(row for row in self.graph["edges"] if row["record_kind"] == "go_annotation")
        self.protein, self.term = edge["subject"], edge["object"]
        self.gaf = self.root / "invented.gaf.gz"
        self.headers = ["!gaf-version: 2.2", "!generated-by: INVENTED", "!date-generated: 2026-01-01"]
        fields = record()["raw_fields"]
        fields[1], fields[4] = self.protein.removeprefix("UniProtKB:"), self.term
        fields[6], fields[8], fields[14] = (edge["evidence_record"][key] for key in ("evidence", "type", "assigned_by"))
        relation = {"P": "involved_in", "F": "enables", "C": "located_in"}[fields[8]]
        fields[3] = "NOT|" + relation
        positive = list(fields)
        positive[3], positive[15], positive[16] = relation, "", ""
        another = list(positive)
        another[4] = "GO:1234567"
        outside = list(positive)
        outside[1] = "P99999"
        all_fields = [fields, positive, another, outside]
        with gzip.open(self.gaf, "wt", newline="") as stream:
            stream.write("\n".join(self.headers + ["\t".join(row) for row in all_fields]) + "\n")
        self.pin = sha(self.gaf)
        self.native = []
        for number, fields in enumerate(all_fields[:3], len(self.headers) + 1):
            parsed = dict(zip(go.GAF_FIELDS, fields))
            for key in ("Qualifier", "DB:Reference", "With", "Synonym", "Taxon_ID"):
                parsed[key] = parsed[key].split("|")
            self.native.append(go.native_record(number, "\t".join(fields), fields, parsed, self.pin))
        self.source = {"headers": self.headers, "total_source_rows": len(all_fields), "gaf_sha256": self.pin,
                       "parser": {"package": "biopython", "version": "1.88", "function": "Bio.UniProt.GOA.gafiterator"}}
        self.publish(self.context, self.native)

    def publish(self, output, native):
        # The native producer is separately tested with actual Biopython. This
        # fixture also permits coherently sealed missing-row counterexamples.
        with patch.object(go, "read_native_gaf", return_value=(native, self.source)):
            go.qualify_go_context(self.packet, self.gaf, output, expected_gaf_sha256=self.pin,
                                  source_url="https://example.invalid/invented.gaf.gz")

    def producer(self, path, accessions, pin):
        self.assertEqual(pin, self.pin)
        return ([deepcopy(row) for row in self.native
                 if row["subject"].removeprefix("UniProtKB:") in accessions], deepcopy(self.source))

    def inspect(self, protein=None, **kwargs):
        with patch.object(go, "read_native_gaf", side_effect=self.producer):
            return inspection.inspect_go_context(self.context, protein or self.protein, **kwargs)

    def reseal(self, update=None):
        report = json.loads((self.context / inspection.REPORT).read_text())
        report["files"] = {name: sha(self.context / name) for name in inspection.FILES}
        if update:
            update(report)
        report.pop("content_sha256")
        report["content_sha256"] = digest(report)
        write_json(self.context / inspection.REPORT, report)

    def test_native_query_preserves_all_not_positive_forms_references_and_source_pins(self):
        before = {p.relative_to(self.context).as_posix(): sha(p) for p in self.context.rglob("*") if p.is_file()}
        result = self.inspect(go_id=self.term)
        self.assertEqual(result["query"], {"protein": self.protein, "go_id": self.term})
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["records"], self.native[:2])
        self.assertEqual(result["counts"], {"positive_records": 1, "not_records": 1})
        self.assertEqual(result["records"][0]["reference_identifiers"], ["PMID:36949045", "OTHER:one"])
        self.assertEqual(result["source"]["gaf_sha256"], self.pin)
        self.assertFalse(result["original_gold_packet_revalidated"])
        self.assertFalse(result["historical_record_identity_established"])
        self.assertFalse(result["independent_biological_accuracy_established"])
        self.assertEqual(result["content_sha256"], digest({k:v for k,v in result.items() if k != "content_sha256"}))
        self.assertEqual(before, {p.relative_to(self.context).as_posix(): sha(p) for p in self.context.rglob("*") if p.is_file()})

    def test_exact_query_does_not_collapse_isoforms_or_expand_to_other_gaf_subjects(self):
        for protein in (self.protein + "-2", "UniProtKB:P99999"):
            with self.subTest(protein=protein), patch.object(go, "read_native_gaf", side_effect=self.producer) as producer:
                result = inspection.inspect_go_context(self.context, protein)
                self.assertEqual(producer.call_args.args[1], set())
                self.assertEqual(result["record_count"], 0)
                self.assertFalse(result["protein_in_preserved_scope"])
                self.assertFalse(result["biological_absence_inferred"])
        missing_term = self.inspect(go_id="GO:9999999")
        self.assertEqual(missing_term["status"], "no_matching_source_records")
        self.assertEqual(missing_term["protein_native_record_count"], 3)
        self.assertTrue(missing_term["protein_in_preserved_scope"])

    def test_shared_loader_verifies_complete_native_scope_without_optional_bio(self):
        with patch.object(go, "read_native_gaf", side_effect=AssertionError("No optional parser in loader")):
            report, rows, links = inspection.load_go_context(self.context)
        self.assertEqual(rows, self.native)
        self.assertEqual(len(links), report["counts"]["original_go_edges"])

    def test_invalid_query_rejected_before_any_context_read(self):
        for protein in (None, "P00001", "uniprotkb:P00001", " UniProtKB:P00001", "UniProtKB:notanid"):
            with self.subTest(protein=protein), patch.object(inspection, "load_go_context") as reader:
                with self.assertRaisesRegex(ValueError, "exact UniProtKB"):
                    inspection.inspect_go_context(self.context, protein)
                reader.assert_not_called()
        for term in ("GO_0000001", "GO:1", "GO:0000001 ", False):
            with self.subTest(term=term), self.assertRaisesRegex(ValueError, "exact GO"):
                self.inspect(go_id=term)

    def test_tampered_bytes_bad_seal_or_extra_paths_fail_before_optional_parser(self):
        path = self.context / "native_records.jsonl"
        old = path.read_bytes()
        path.write_bytes(old + b"\n")
        with patch.object(go, "read_native_gaf") as producer, self.assertRaisesRegex(ValueError, "source bytes"):
            inspection.inspect_go_context(self.context, self.protein)
        producer.assert_not_called()
        path.write_bytes(old)
        extra = self.context / "extra.txt"
        extra.write_text("not declared")
        with self.assertRaisesRegex(ValueError, "inventory"):
            inspection.load_go_context(self.context)
        extra.unlink()
        extra.mkdir()
        with self.assertRaisesRegex(ValueError, "inventory"):
            inspection.load_go_context(self.context)
        extra.rmdir()
        report = self.context / inspection.REPORT
        report.write_text(report.read_text().replace('"source_graph_mutated": false', '"source_graph_mutated": true'))
        with self.assertRaisesRegex(ValueError, "seal"):
            inspection.load_go_context(self.context)

    def test_coherently_sealed_missing_native_row_fails_raw_gaf_completeness(self):
        incomplete = self.root / "incomplete"
        self.publish(incomplete, self.native[1:])
        with self.assertRaisesRegex(ValueError, "completeness"):
            inspection.load_go_context(incomplete)

    def test_resealed_policy_count_and_native_field_changes_are_not_trusted(self):
        self.reseal(lambda report: report.update(scientific_accuracy_measured=True))
        with self.assertRaisesRegex(ValueError, "policy"):
            inspection.load_go_context(self.context)
        self.reseal(lambda report: report.update(scientific_accuracy_measured=False))
        self.reseal(lambda report: report["counts"].update(native_not_rows=0))
        with self.assertRaisesRegex(ValueError, "counts"):
            inspection.load_go_context(self.context)
        self.reseal(lambda report: report["counts"].update(native_not_rows=1))
        rows = deepcopy(self.native)
        rows[0]["negated"] = False
        (self.context / "native_records.jsonl").write_text("".join(canonical(row) + "\n" for row in rows))
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reconstruct"):
            inspection.load_go_context(self.context)

    def test_symlink_context_or_source_file_is_rejected(self):
        alias = self.root / "context-link"
        alias.symlink_to(self.context, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "ordinary nonsymlink"):
            inspection.load_go_context(alias)
        path = self.context / "source/annotations.gaf.gz"
        path.unlink()
        path.symlink_to(self.gaf)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            inspection.load_go_context(self.context)

    def test_resealed_candidate_selection_cannot_hide_competing_native_context(self):
        path = self.context / "edge_compatibilities.jsonl"
        links = [json.loads(line) for line in path.read_text().splitlines()]
        chosen = next(row for row in links if row["candidate_count"] == 2)
        chosen["native_record_ids"] = chosen["native_record_ids"][:1]
        chosen["candidate_count"] = 1
        chosen["status"] = "one_compatible_native_record"
        path.write_text("".join(canonical(row) + "\n" for row in links))
        self.reseal()
        with self.assertRaisesRegex(ValueError, "compatibility candidates"):
            inspection.load_go_context(self.context)

    def test_report_source_pin_and_required_gaf_metadata_are_checked(self):
        self.reseal(lambda report: report["source"].update(gaf_sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "GAF source pin"):
            inspection.load_go_context(self.context)
        self.reseal(lambda report: report["source"].update(gaf_sha256=self.pin,
            headers=["!gaf-version: 2.1", *self.headers[1:]]))
        with self.assertRaisesRegex(ValueError, "source metadata"):
            inspection.load_go_context(self.context)


if __name__ == "__main__":
    unittest.main()
