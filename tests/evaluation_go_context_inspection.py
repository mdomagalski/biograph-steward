"""Actual Biopython to Gold sidecar to read-only native GO inspection."""
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import Bio

from biograph_steward import go_context_inspection as inspection
from biograph_steward import go_qualification as go, gold_packet
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from test_go_native_qualification import record
from test_normalization import fixture


class NativeGOInspectionIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        run, packet, self.context = (self.root / name for name in ("run", "packet", "context"))
        graph = save_run(fixture(), run)
        gold_packet.export_packet(run, packet)
        edge = next(row for row in graph["edges"] if row["record_kind"] == "go_annotation")
        self.protein, self.term = edge["subject"], edge["object"]
        fields = record()["raw_fields"]
        fields[1], fields[4] = self.protein.removeprefix("UniProtKB:"), self.term
        fields[6], fields[8], fields[14] = (edge["evidence_record"][key] for key in ("evidence", "type", "assigned_by"))
        relation = {"P": "involved_in", "F": "enables", "C": "located_in"}[fields[8]]
        fields[3] = "NOT|" + relation
        positive = list(fields)
        positive[3] = relation
        outside = list(positive)
        outside[1] = "P99999"
        gaf = self.root / "invented.gaf.gz"
        with gzip.open(gaf, "wt", newline="") as stream:
            stream.write("!gaf-version: 2.2\n!generated-by: INVENTED\n!date-generated: 2026-01-01\n")
            stream.write("\n".join("\t".join(row) for row in (fields, positive, outside)) + "\n")
        self.pin = sha(gaf)
        go.qualify_go_context(packet, gaf, self.context, expected_gaf_sha256=self.pin)

    def test_actual_native_parser_inspection_keeps_not_and_positive_without_gold_revalidation(self):
        self.assertEqual(Bio.__version__, go.PARSER_VERSION)
        before = {p.relative_to(self.context).as_posix(): sha(p) for p in self.context.rglob("*") if p.is_file()}
        with patch.object(gold_packet, "load_packet", side_effect=AssertionError("Original Gold not revalidated")):
            result = inspection.inspect_go_context(self.context, self.protein, go_id=self.term)
        self.assertEqual(result["record_count"], 2)
        self.assertEqual([row["negated"] for row in result["records"]], [True, False])
        self.assertTrue(result["queried_native_rows_replayed"])
        self.assertFalse(result["original_gold_packet_revalidated"])
        self.assertFalse(result["original_qualifiers_backfilled"])
        self.assertEqual(result["source"]["gaf_sha256"], self.pin)
        self.assertEqual(before, {p.relative_to(self.context).as_posix(): sha(p) for p in self.context.rglob("*") if p.is_file()})

    def test_actual_gaf_outside_preserved_scope_and_unknown_terms_do_not_imply_absence(self):
        outside = inspection.inspect_go_context(self.context, "UniProtKB:P99999")
        self.assertFalse(outside["protein_in_preserved_scope"])
        self.assertEqual(outside["record_count"], 0)
        self.assertFalse(outside["biological_absence_inferred"])
        missing = inspection.inspect_go_context(self.context, self.protein, go_id="GO:9999999")
        self.assertEqual(missing["record_count"], 0)
        self.assertEqual(missing["protein_native_record_count"], 2)
        self.assertFalse(missing["biological_absence_inferred"])


if __name__ == "__main__":
    unittest.main()
