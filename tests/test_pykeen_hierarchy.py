"""Invented path/split tests; the native integration test uses optional pins."""

import importlib.util
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_pykeen_hierarchy.py"
SPEC = importlib.util.spec_from_file_location("smoke_pykeen_hierarchy", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def has_native_runtime():
    try:
        return version("pykeen") == "1.11.1" and version("torch") == "2.6.0"
    except PackageNotFoundError:
        return False


class HierarchyFixtureTests(unittest.TestCase):
    def test_intervention_only_adds_hierarchy_and_reserved_pairs_stay_out(self):
        data = smoke.fixture()
        base = set(data["base_adjacency"])
        hierarchy = set(data["hierarchy_adjacency"])
        self.assertEqual(hierarchy - base, {("go_child", "is_a", "go_parent")})
        self.assertFalse(base - hierarchy)
        for rows in (base, hierarchy, set(data["supervision"])):
            self.assertFalse(rows & set(data["reserved_and_development"]))
        self.assertTrue(set(data["supervision"]) <= base)
        self.assertEqual(len(data["supervision"]), 12)
        self.assertEqual(len(set(data["entities"].values())), 9)
        for rows in (base, hierarchy):
            self.assertTrue(all(s in data["entities"] and o in data["entities"] and r in data["relations"]
                                for s, r, o in rows))

    def test_fixture_directed_path_requires_reverse_messages(self):
        data = smoke.fixture()
        rows = set(data["hierarchy_adjacency"])
        self.assertIn(("gene0", "encodes", "product0"), rows)
        self.assertIn(("product0", "annotated_to", "go_child"), rows)
        self.assertIn(("go_child", "is_a", "go_parent"), rows)
        self.assertFalse(any(s == "go_parent" for s, _, _ in rows))
        self.assertNotIn(("gene0", "annotated_to", "go_parent"), rows)

    @unittest.skipUnless(has_native_runtime(), "Optional pinned PyKEEN 1.11.1 / torch 2.6.0 runtime")
    def test_native_receptive_field_cache_and_train_prediction_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.dict(os.environ, {"PYSTOW_HOME": str(root / "cache"),
                                          "PYKEEN_HOME": str(root / "cache" / "pykeen")}):
                report = smoke.run(root)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["biomedical_inputs_used"])
        self.assertFalse(report["biological_quality_measured"])
        probe = report["transport_probe"]
        self.assertEqual(probe["1"]["maximum_absolute_difference_by_entity"]["gene0"], 0)
        self.assertEqual(probe["2"]["maximum_absolute_difference_by_entity"]["gene0"], 0)
        self.assertEqual(probe["3"]["maximum_absolute_difference_by_entity"]["gene0"], 2)
        self.assertTrue(report["module_direction_probe"]["fwd"]["parent_signal_reaches_gene"])
        self.assertFalse(report["module_direction_probe"]["bwd"]["parent_signal_reaches_gene"])
        self.assertTrue(all(report["cache_check"].values()))
        base, hierarchy = (report["trained_arms"][arm] for arm in ("base", "hierarchy"))
        self.assertEqual((base["adjacency_triples"], hierarchy["adjacency_triples"]), (14, 15))
        self.assertEqual(base["initial_parameters_sha256"], hierarchy["initial_parameters_sha256"])
        self.assertEqual(base["positive_batches_sha256"], hierarchy["positive_batches_sha256"])
        self.assertNotEqual(base["adjacency_sha256"], hierarchy["adjacency_sha256"])
        for arm in (base, hierarchy):
            self.assertEqual(arm["layers"], 3)
            self.assertEqual(arm["supervision_triples"], 12)
            self.assertEqual(arm["optimizer_steps"], 2)
            self.assertGreater(arm["reserved_or_dev_negative_proposals_removed"], 0)
            self.assertTrue(arm["prediction_did_not_add_query_edges"])
            self.assertTrue(arm["training_invalidated_cache"])


if __name__ == "__main__":
    unittest.main()
