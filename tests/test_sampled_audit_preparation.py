"""Probability-design and source-preservation checks for audit preparation."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import export_packet
from biograph_steward.graph import save_run
from test_normalization import fixture
from tools.sampled_audit.prepare import draw_sample, prepare
from tools.sampled_audit import prepare as preparation


class StratifiedSampleTests(unittest.TestCase):
    def test_selection_is_order_invariant_unique_and_covers_every_declared_stratum(self):
        population = [{"id": str(i), "kind": "rare" if i < 3 else "common"} for i in range(20)]
        strata, sample = draw_sample(population, {"rare": 2, "common": 4}, 81)
        self.assertEqual((strata, sample), draw_sample(list(reversed(population)), {"common": 4, "rare": 2}, 81))
        self.assertEqual(len({row["assertion_id"] for row in sample}), 6)
        self.assertEqual(Counter(row["stratum"] for row in sample), {"rare": 2, "common": 4})
        for row in sample:
            expected = {"rare": (2, 3), "common": (4, 17)}[row["stratum"]]
            self.assertEqual(row["inclusion_probability"], dict(zip(("numerator", "denominator"), expected)))
        self.assertEqual(sum(s["sample_size"] * s["population_size"] / s["sample_size"] for s in strata.values()), 20)

    def test_missing_strata_invalid_allocations_and_duplicate_population_ids_fail(self):
        population = [{"id": "a", "kind": "x"}, {"id": "b", "kind": "y"}]
        for allocation in ({"x": 1}, {"x": 1, "y": 1, "z": 1}, {"x": 0, "y": 1},
                           {"x": 2, "y": 1}, {"x": True, "y": 1}):
            with self.subTest(allocation=allocation), self.assertRaises(ValueError):
                draw_sample(population, allocation, 2)
        with self.assertRaises(ValueError):
            draw_sample([population[0], population[0]], {"x": 1}, 2)
        for seed in (-1, True, "2"):
            with self.assertRaises(ValueError):
                draw_sample(population, {"x": 1, "y": 1}, seed)


class AuditPreparationTests(unittest.TestCase):
    def test_changed_source_during_dossier_creation_cannot_get_a_completed_sample(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            graph = save_run(fixture(), root / "run")
            packet, output = root / "packet", root / "audit"
            export_packet(root / "run", packet)
            allocation = {a["kind"]: 1 for a in graph["assertions"]}
            inspect = preparation.inspect_selection

            def changed_source(*args):
                result = inspect(*args)
                source = packet / "source/graph.json"
                source.write_bytes(source.read_bytes() + b"\n")
                return result

            with patch.object(preparation, "inspect_selection", side_effect=changed_source):
                with self.assertRaises(ValueError):
                    prepare(packet, allocation, 81, output)
            self.assertTrue((output / "protocol.json").is_file())
            self.assertFalse((output / "sample_manifest.json").exists())

    def test_preparation_binds_verified_complete_assertions_and_never_generates_truth_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            run, packet, output = (root / n for n in ("run", "packet", "audit"))
            graph = save_run(fixture(), run)
            export_packet(run, packet)
            before = {p.relative_to(packet).as_posix(): sha(p) for p in packet.rglob("*") if p.is_file()}
            allocation = {kind: 1 for kind in {a["kind"] for a in graph["assertions"]}}
            report = prepare(packet, allocation, 81, output)
            protocol = json.loads((output / "protocol.json").read_text())
            self.assertEqual(report["population_size"], len(graph["assertions"]))
            self.assertFalse(report["scientific_accuracy_measured"])
            self.assertFalse(report["review_judgments_generated"])
            self.assertEqual(report["content_sha256"], digest({k:v for k,v in report.items() if k != "content_sha256"}))
            by_id = {a["id"]: a for a in graph["assertions"]}
            edges = {e["id"]: e for e in graph["edges"]}
            for raw in (output / "sample.jsonl").read_text().splitlines():
                item = json.loads(raw)
                dossier = json.loads((output / item["dossier_path"]).read_text())
                self.assertEqual(dossier["assertion"], by_id[item["assertion_id"]])
                self.assertEqual(dossier["source_edges"], [edges[e] for e in dossier["assertion"]["evidence_edge_ids"]])
                self.assertFalse(dossier["intervention_disposition_exposed"])
                self.assertEqual(dossier["content_sha256"], item["dossier_content_sha256"])
                self.assertEqual(dossier["content_sha256"], digest({k:v for k,v in dossier.items() if k != "content_sha256"}))
                self.assertEqual(dossier["protocol_content_sha256"], protocol["content_sha256"])
            for raw in (output / "reviews.template.jsonl").read_text().splitlines():
                review = json.loads(raw)
                self.assertIsNone(review["source_relative_support"])
                self.assertIsNone(review["primary_evidence_support"])
                self.assertEqual(review["independent_scientific_correctness"], "unreviewed")
            self.assertEqual(before, {p.relative_to(packet).as_posix(): sha(p) for p in packet.rglob("*") if p.is_file()})
            with self.assertRaises(ValueError):
                prepare(packet, allocation, 81, output)


if __name__ == "__main__":
    unittest.main()
