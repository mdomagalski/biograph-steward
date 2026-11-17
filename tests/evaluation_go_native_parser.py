"""Official Biopython1.88 parser integration on invented native GAF records."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import Bio

from biograph_steward import go_qualification as go
from biograph_steward import gold_packet
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from test_go_native_qualification import record
from test_normalization import fixture


class OfficialNativeGAFParserTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / "invented.gaf.gz"

    def source(self, lines=None, *, newline="\n", headers=None):
        headers = headers or ["!gaf-version: 2.2", "!generated-by: INVENTED", "!date-generated: 2026-01-01",
                              "!go-version: https://example.invalid/invented-ontology"]
        lines = [record()["raw_line"]] if lines is None else lines
        with gzip.open(self.path, "wb") as handle:
            handle.write((newline.join(headers + lines) + newline).encode())
        return sha(self.path)

    def read(self, pin):
        return go.read_native_gaf(self.path, {"P00001"}, pin)

    def test_pinned_official_parser_preserves_native_headers_columns_and_real_line_numbers(self):
        self.assertEqual(Bio.__version__, go.PARSER_VERSION)
        pin = self.source()
        rows, source = self.read(pin)
        self.assertEqual(source["parser"]["function"], "Bio.UniProt.GOA.gafiterator")
        self.assertEqual(source["total_source_rows"], 1)
        self.assertEqual(rows[0]["source_line"], 5)
        self.assertEqual(rows[0]["raw_fields"], record()["raw_fields"])
        self.assertEqual(rows[0]["parsed"], record()["parsed"])
        self.assertTrue(rows[0]["negated"])
        self.assertEqual(source["gaf_sha256"], pin)
        self.assertEqual(source["headers"][3], "!go-version: https://example.invalid/invented-ontology")

    def test_crlf_and_blank_lines_do_not_silently_shift_native_records(self):
        raw = record()["raw_line"]
        rows, source = self.read(self.source(["", raw, raw], newline="\r\n"))
        self.assertEqual([r["source_line"] for r in rows], [6, 7])
        self.assertEqual(source["total_source_rows"], 2)
        self.assertEqual(rows[0]["raw_line"], raw)
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])

    def test_exact_subject_scope_does_not_collapse_isoforms_or_other_namespaces(self):
        lines = [record()["raw_line"], record(9, **{"1": "P00001-2"})["raw_line"],
                 record(10, **{"0": "OtherDB"})["raw_line"], record(11, **{"1": "P00002"})["raw_line"]]
        rows, source = self.read(self.source(lines))
        self.assertEqual(len(rows), 1)
        self.assertEqual(source["total_source_rows"], 4)
        self.assertEqual(rows[0]["subject"], "UniProtKB:P00001")

    def test_required_relation_and_column_boundaries_are_not_silently_accepted_by_permissive_parser(self):
        fields = deepcopy(record()["raw_fields"])
        fields[3] = ""
        for raw in ("\t".join(fields), record()["raw_line"] + "\textra", "short\trow"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.read(self.source([raw]))

    def test_unreviewed_gaf_format_and_missing_mandatory_metadata_fail_closed(self):
        for headers in (["!gaf-version: 2.1", "!generated-by: INVENTED", "!date-generated: 2026-01-01"],
                        ["!gaf-version: 2.2", "!date-generated: 2026-01-01"]):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.read(self.source(headers=headers))

    def test_source_pin_and_parser_version_are_enforced(self):
        pin = self.source()
        with self.assertRaisesRegex(ValueError, "source pin"):
            self.read("0" * 64)
        with patch.object(Bio, "__version__", "unreviewed"), self.assertRaisesRegex(ValueError, "1.88"):
            self.read(pin)

    def test_official_parser_to_verified_gold_sidecar_preserves_original_unknown_qualifiers(self):
        run, packet, output = (self.root / name for name in ("run", "packet", "output"))
        graph = save_run(fixture(), run)
        manifest = gold_packet.export_packet(run, packet)
        source = (packet / "source/graph.json").read_bytes()
        edge = next(e for e in graph["edges"] if e.get("record_kind") == "go_annotation")
        fields = record()["raw_fields"]
        fields[1] = edge["subject"].removeprefix("UniProtKB:")
        fields[4] = edge["object"]
        fields[6] = edge["evidence_record"]["evidence"]
        fields[8] = edge["evidence_record"]["type"]
        fields[14] = edge["evidence_record"]["assigned_by"]
        fields[3] = "NOT|" + {"P": "involved_in", "F": "enables", "C": "located_in"}[fields[8]]
        fields[7], fields[15], fields[16] = "", "", ""
        pin = self.source(["\t".join(fields)])
        report = go.qualify_go_context(packet, self.path, output, expected_gaf_sha256=pin)
        rows = [json.loads(line) for line in (output / "native_records.jsonl").read_text().splitlines()]
        links = [json.loads(line) for line in (output / "edge_compatibilities.jsonl").read_text().splitlines()]
        match = next(r for r in links if r["edge_id"] == edge["id"])
        self.assertEqual(report["packet_id"], manifest["packet_id"])
        self.assertEqual(report["counts"]["native_rows"], 1)
        self.assertEqual(match["native_record_ids"], [rows[0]["id"]])
        self.assertEqual(match["candidate_polarities"], ["NOT"])
        self.assertFalse(match["historical_record_identity_established"])
        self.assertIsNone(edge["annotation_context"]["negated"])
        self.assertEqual((packet / "source/graph.json").read_bytes(), source)
        self.assertEqual((output / "source/annotations.gaf.gz").read_bytes(), self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
