"""Invented source qualification controls; never biological negative labels."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.demo import demo_snapshot
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import export_packet, load_decisions
from biograph_steward.graph import save_run
from tools.pathway_history import prepare_decisions as module


def scope_fixture():
    graph = {"edges": []}
    history = {"connections": {}}
    for i, status in enumerate(["compatible_gene_level_xref", "explicitly_encoded_protein_xref", "unresolved"]):
        key = ("UniProtKB:P04637", f"WP{i+1}_r99")
        claim = {"subject": key[0], "full_source_id": key[1], "status": status,
            "original_edge_ids": [], "original_assertion_ids": [], "native_model_sha256": "a" * 64,
            "native_model_file": "models/" + key[1] + ".gpml", "content_sha256": "b" * 64}
        for j in range(2 if i == 0 else 1):
            eid, aid = f"edge:{i}-{j}", f"assertion:{i}"
            edge = {"id": eid, "subject": key[0], "assertion_id": aid, "record_kind": "pathway_membership",
                "object": "pharos.pathway:1", "evidence_record": {"type": "WikiPathways", "sourceID": key[1], "pwid": 1}}
            graph["edges"].append(edge)
            claim["original_edge_ids"].append(eid)
            claim["original_assertion_ids"].append(aid)
        history["connections"][key] = claim
    graph["edges"].append({"id": "edge:other", "record_kind": "disease_association", "subject": "UniProtKB:P04637"})
    return graph, history


def synthetic_replay(history, subject, source_id):
    return {"status": history["connections"][(subject, source_id)]["status"],
        "model": {"gpml_sha256": "a" * 64}, "selected_archive_proof": {"synthetic_mock": True},
        "schema_reexecuted_in_consumer": False, "assessment": {"synthetic_mock": True}}


class SourceFaithfulDecisionTests(unittest.TestCase):
    def test_native_positives_keep_unknown_and_other_families_abstain(self):
        graph, history = scope_fixture()
        before = deepcopy((graph, history))
        decisions, traces, replayed = module.decision_rows(graph, history, replay=synthetic_replay)
        self.assertEqual([d["decision"] for d in decisions], ["keep", "keep", "keep", "abstain", "abstain"])
        self.assertEqual(len(replayed), 2)
        self.assertEqual(len(traces), 4)
        self.assertTrue(all(d["confidence"] is None for d in decisions))
        self.assertTrue(all(not t["biological_negative_asserted"] for t in traces))
        self.assertEqual((graph, history), before)

    def test_each_native_positive_connection_replays_once_without_merging_rows(self):
        graph, history = scope_fixture()
        with patch.object(module, "query_history", wraps=synthetic_replay) as replay:
            decisions, traces, _ = module.decision_rows(graph, history, replay=replay)
        self.assertEqual(replay.call_count, 2)
        self.assertEqual(len({d["edge_id"] for d in decisions}), len(graph["edges"]))
        self.assertEqual([t["edge_id"] for t in traces[:2]], ["edge:0-0", "edge:0-1"])

    def test_native_positive_replay_mismatch_stops_before_keeping(self):
        graph, history = scope_fixture()
        def wrong(*args):
            return {**synthetic_replay(*args), "status": "unresolved"}
        with self.assertRaisesRegex(ValueError, "did not replay"):
            module.decision_rows(graph, history, replay=wrong)

    def test_missing_and_added_edges_cannot_silently_change_history_scope(self):
        graph, history = scope_fixture()
        graph["edges"][0]["id"] = "edge:changed"
        with self.assertRaisesRegex(ValueError, "not bound"):
            module.decision_rows(graph, history, replay=synthetic_replay)
        graph, history = scope_fixture()
        graph["edges"] = graph["edges"][1:]
        with self.assertRaisesRegex(ValueError, "coverage differ"):
            module.decision_rows(graph, history, replay=synthetic_replay)

    def test_real_gold_retention_keeps_abstentions_and_source_payloads(self):
        # Native-history verification itself has separate archive/registry
        # integration tests. Here a supplied empty history isolates the real
        # Gold saving/reloading contract on its invented, non-Wiki demo graph.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = save_run(demo_snapshot(), root / "run")
            export_packet(root / "run", root / "packet")
            history = root / "history"
            history.mkdir()
            report = {"source_graph_file_sha256": sha(root / "packet/source/graph.json"),
                "counts": {"original_rows": 0}, "content_sha256": "d" * 64}
            for name in ("resource_coverage.jsonl", "claim_assessments.jsonl", "edge_assessments.jsonl"):
                (history / name).write_text("")
            write_json(history / "historical_verification.json", report)
            supplied = {"report": report, "connections": {}}
            with patch.object(module, "load_history_packet", return_value=supplied):
                result = module.prepare_decisions(root / "packet", history, root / "out", history_content_sha256="d" * 64)
            _, retained = load_decisions(root / "out/retained")
            self.assertEqual(retained["nodes"], graph["nodes"])
            self.assertEqual(retained["edges"], graph["edges"])
            self.assertEqual(retained["assertions"], graph["assertions"])
            self.assertEqual(result["counts"]["prune"], 0)
            self.assertEqual(result["counts"]["abstain"], len(graph["edges"]))
            self.assertFalse(result["scientific_review_states_promoted"])

    def test_wrong_exact_source_graph_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_run(demo_snapshot(), root / "run")
            export_packet(root / "run", root / "packet")
            with patch.object(module, "load_history_packet", return_value={"report": {"source_graph_file_sha256": "0" * 64}}):
                with self.assertRaisesRegex(ValueError, "exact original graph"):
                    module.prepare_decisions(root / "packet", root / "history", root / "out", history_content_sha256="d" * 64)
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
