"""Invented, tiny published assessments test preview fidelity, never biology."""
from copy import deepcopy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

from biograph_steward import pruning_preview as preview
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publish_pruning_preview", ROOT / "scripts/publish_pruning_preview.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)
from assess_ppi_pruning import select_arms, metrics_for_rows, graph_utility


def seal(value):
    return {**value, "content_sha256": digest(value)}


def make_preview(root, *, with_targets=True):
    """Return root/assessment/pruning_preview from invented completed artifacts."""
    root = Path(root).resolve()
    inputs = root / "inputs"; inputs.mkdir()
    groups = []
    proteins = ["UniProtKB:P%05d" % n for n in range(1, 10)]
    pairs = [(proteins[0], proteins[i], ["STRINGDB"], i / 10) for i in range(1, 6)]
    pairs += [(proteins[1], proteins[2], ["BioPlex", "STRINGDB"], .7),
              (proteins[3], proteins[4], ["BioPlex"], None)]
    for n, (a, b, sources, native) in enumerate(pairs, 1):
        groups.append({"pair_id": preview.exact_pair(a, b), "subject": a, "object": b,
            "edge_ids": ["edge:" + str(n)], "providers": sources,
            "native_score": native, "ne_score": None if native is None else 1 - native,
            "eligible": sources == ["STRINGDB"]})
    groups.sort(key=lambda row: row["pair_id"])
    group_file = inputs / "groups.json"; write_json(group_file, groups)
    by_pair = {g["pair_id"]: g for g in groups}
    selections, diagnostics = select_arms(by_pair)
    observations = []
    cases = [(proteins[0], proteins[1], "detected"),
             (proteins[0], proteins[5], "not_detected"),
             (proteins[0], proteins[2], "test_failed"),
             (proteins[1], proteins[2], "not_detected"),
             (proteins[6], proteins[7], "detected"),
             (proteins[6], proteins[8], "failed_sequence_confirmation")]
    for n, (a, b, state) in enumerate(cases, 100):
        uid = preview.exact_pair(a, b); group = by_pair.get(uid)
        evaluable = state in {"detected", "not_detected"}
        arms = {arm: {"decision": ("keep" if uid in selections[arm] else "prune")
                      if group and group["eligible"] else "abstain",
                      "retained": None if group is None else
                          (uid in selections[arm] if group["eligible"] else True)} for arm in preview.ARMS}
        observations.append({"pair_id": uid, "products": [a.removeprefix("UniProtKB:"), b.removeprefix("UniProtKB:")],
            "source_row": n, "assay_status": state, "assay_evaluable": evaluable,
            "detected": (state == "detected") if evaluable else None,
            "graph_present": group is not None, "pruning_eligible": bool(group and group["eligible"]),
            "source_providers": group["providers"] if group else [],
            "scores": {"native": group["native_score"] if group else None,
                       "ne": group["ne_score"] if group else None}, "arms": arms,
            "constructs": {"ad_orf_id": str(n + 1000), "db_orf_id": str(n + 2000),
                           "protein_to_construct_orientation_inferred": False},
            "exposure": {"huri_overlap": False, "inmc_overlap": False,
                         "consumed_intact_exact_pair": False}})
    metrics = metrics_for_rows(observations)
    targets = inputs / "targets.tsv"
    with targets.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("id", "symbol", "name"), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for n, uid in enumerate(proteins[:6], 1):
            writer.writerow({"id": uid, "symbol": "GENE%d" % n, "name": "Invented protein %d" % n})
    source = seal({"format": "biograph-steward.ppi-pruning-source.v1",
                   "counts": {"requested_accessions": 9}, "source_bindings": {"database_version": "invented_source"},
                   "graph_sha256": "a" * 64})
    source_file = inputs / "source.json"; write_json(source_file, source)
    proofs = {}
    for arm in preview.ARMS:
        kept = [g for g in groups if not g["eligible"] or g["pair_id"] in selections[arm]]
        edges = sorted(eid for g in kept for eid in g["edge_ids"])
        graph = {"nodes": [{"id": uid} for uid in proteins[:6]],
                 "edges": [{"subject": g["subject"], "object": g["object"]} for g in kept]}
        proofs[arm] = {"retained_edge_ids_sha256": digest(edges), "retained_edges": len(edges),
                       "all_protected_source_edges_retained": True, "protected_source_edges": 2,
                       "utility": graph_utility(graph)}
    protocol = seal({"format": preview.SOURCE_FORMAT, "status": "frozen", "outcomes_loaded": False,
        "created_at": "2026-01-01T00:00:00+00:00", "graph_sha256": "a" * 64, "packet_id": "packet:invented",
        "source_protocol_sha256": source["content_sha256"], "arms": proofs, "diagnostics": diagnostics,
        "files": {"pair_groups.json": sha(group_file)},
        "input_inventories": {"source": {"ordinary_run/targets.tsv": sha(targets)}}})
    protocol_file = inputs / "protocol.json"; write_json(protocol_file, protocol)
    results = inputs / "results"; results.mkdir()
    write_json(results / "metrics.json", metrics)
    (results / "pair_accounting.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in observations))
    (results / "report.html").write_text("<p>Invented test fixture only</p>")
    write_json(results / "outcome_access_receipt.json", {"purpose": "Invented fixture only"})
    result = seal({"format": preview.SOURCE_FORMAT + ".result", "status": "completed",
        "created_at": "2026-01-01T00:00:00+00:00", "protocol_sha256": protocol["content_sha256"],
        "actual_retained_graph_contrast_verified": True, "original_source_unchanged": True,
        "independent_validation": False, "scientific_accuracy_established": False,
        "files": {path.name: sha(path) for path in results.iterdir()}})
    write_json(results / "report.json", result)
    output = root / "assessment/pruning_preview"
    publisher.publish_preview(results, protocol_file, group_file, output,
                              targets=targets if with_targets else None, source_protocol=source_file)
    return output


class PruningPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_real_publisher_builds_default_original_and_separate_scope(self):
        folder = make_preview(self.root)
        summary = preview.load_preview(folder)
        self.assertEqual(summary["default_arm"], "unpruned")
        self.assertFalse(summary["scope"]["current_workspace_applied"])
        self.assertEqual(summary["scope"]["source_edge_count"], 7)
        self.assertEqual(summary["scope"]["preview_pair_count"], 9)
        self.assertEqual(summary["scope"]["source_version"], "invented_source")
        self.assertEqual(preview.list_previews(self.root)["previews"][0]["id"], "assessment")
        self.assertEqual(preview.query_pairs(folder, selection="removed")["total"], 0)

    def test_all_missingness_and_exclusion_states_remain_distinct(self):
        folder = make_preview(self.root)
        for selection, count in (("all", 9), ("measured", 4), ("excluded", 2), ("uncovered", 2),
                                 ("unassessed", 3), ("protected", 2)):
            self.assertEqual(preview.query_pairs(folder, selection=selection)["total"], count)
        uncovered = preview.query_pairs(folder, selection="uncovered")["rows"]
        self.assertTrue(all(not row["edge_ids"] and row["arms"]["native_top80"]["retained"] is None for row in uncovered))
        excluded = preview.query_pairs(folder, selection="excluded")["rows"]
        self.assertTrue(all(row["assay"]["detected"] is None and not row["assay"]["evaluable"] for row in excluded))
        self.assertEqual(preview.query_pairs(folder, arm="native_top80", selection="detections_removed")["total"], 1)
        self.assertEqual(preview.query_pairs(folder, arm="ne_top80", selection="detections_removed")["total"], 0)

    def test_pair_detail_preserves_evidence_constructs_and_source_bound_search(self):
        folder = make_preview(self.root)
        result = preview.query_pairs(folder, arm="native_top80", search="P00001 P00002")
        self.assertEqual(result["total"], 1)
        row = result["rows"][0]
        self.assertEqual(row["labels"]["subject"], "GENE1 · Invented protein 1")
        self.assertEqual(preview.query_pairs(folder, search="GENE1 GENE2")["total"], 1)
        detail = preview.pair_detail(folder, row["pair_id"])
        self.assertEqual(detail["edge_ids"], ["edge:1"])
        self.assertEqual(detail["native_score"], .1)
        self.assertEqual(detail["assay"]["source_row"], 100)
        self.assertFalse(detail["assay"]["constructs"]["protein_to_construct_orientation_inferred"])
        self.assertFalse(detail["arms"]["native_top80"]["retained"])
        self.assertTrue(detail["arms"]["ne_top80"]["retained"])
        self.assertEqual(preview.query_pairs(folder, search="P00001 P00002", offset=1)["rows"], [])

    def test_labels_are_optional_and_never_inferred(self):
        folder = make_preview(self.root, with_targets=False)
        self.assertEqual(preview.query_pairs(folder, search="GENE1")["total"], 0)
        row = preview.query_pairs(folder, search="P00001 P00002")["rows"][0]
        self.assertEqual(row["labels"]["subject"], "UniProtKB:P00001")

    def test_cache_cannot_hide_same_mtime_tampering_or_leak_mutations(self):
        folder = make_preview(self.root)
        summary = preview.load_preview(folder); summary["scope"]["source_edge_count"] = -1
        row = preview.query_pairs(folder, search="P00001 P00002")["rows"][0]
        row["arms"]["unpruned"]["retained"] = False
        self.assertEqual(preview.load_preview(folder)["scope"]["source_edge_count"], 7)
        self.assertTrue(preview.query_pairs(folder, search="P00001 P00002")["rows"][0]["arms"]["unpruned"]["retained"])
        path = folder / "summary.json"; before = path.stat()
        path.write_bytes(path.read_bytes().replace(b"Fixed", b"Fuxed", 1))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            preview.load_preview(folder)
        self.assertEqual(preview.list_previews(self.root)["previews"], [])

    def test_frozen_edge_commitments_reject_resealed_decision_change(self):
        folder = make_preview(self.root)
        path = folder / "dispositions.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        first = next(row for row in rows if row["arms"]["native_top80"] == "prune")
        other = next(row for row in rows if row["arms"]["native_top80"] == "keep")
        first["arms"]["native_top80"], other["arms"]["native_top80"] = "keep", "prune"
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        manifest = json.loads((folder / "manifest.json").read_text()); manifest.pop("content_sha256")
        manifest["files"]["dispositions.jsonl"] = sha(path)
        write_json(folder / "manifest.json", seal(manifest))
        with self.assertRaisesRegex(ValueError, "actual frozen graph"):
            preview.load_preview(folder)

    def test_invalid_query_download_symlink_and_overwrite_are_rejected(self):
        folder = make_preview(self.root)
        for kwargs in ({"limit": 101}, {"offset": -1}, {"arm": "new_threshold"}, {"selection": "false_edges"}, {"search": "x" * 201}, {"search": "bad\x7fquery"}, {"search": "bad\nquery"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                preview.query_pairs(folder, **kwargs)
        with self.assertRaises(ValueError): preview.pair_detail(folder, "../graph.json")
        with self.assertRaisesRegex(KeyError, "not found"):
            preview.pair_detail(folder, "ppi:" + "f" * 24)
        with self.assertRaises(ValueError): preview.read_download(folder, "pair_groups.json")
        self.assertEqual(json.loads(preview.read_download(folder, "metrics.json"))["dataset_status"], "consumed_development")
        target = folder / "metrics.json"; original = self.root / "saved.json"; target.rename(original); target.symlink_to(original)
        with self.assertRaises(ValueError): preview.load_preview(folder)
        with self.assertRaises(ValueError):
            publisher.publish_preview(self.root / "inputs/results", self.root / "inputs/protocol.json", self.root / "inputs/groups.json", folder)


if __name__ == "__main__":
    unittest.main()
