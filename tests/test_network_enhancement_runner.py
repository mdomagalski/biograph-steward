"""Outcome-free adapter guards; these tests do not simulate or certify NE biology."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_network_enhancement as runner


NODES = b"node_id\tresolution_status\nUniProtKB:A\tresolved\nUniProtKB:B\tresolved\nUniProtKB:C\tunresolved\n"
PAIRS = b"subject\tobject\tweight\tpair_id\tsource_bundle\nUniProtKB:B\tUniProtKB:A\t0.5\tp1\tSTRINGDB\n"


class NetworkEnhancementAdapterTests(unittest.TestCase):
    def test_preserves_declared_isolate_and_original_orientation(self):
        nodes, pairs = runner.load_inputs(NODES, PAIRS)
        self.assertEqual(nodes, ["UniProtKB:A", "UniProtKB:B", "UniProtKB:C"])
        self.assertEqual((pairs[0]["subject"], pairs[0]["object"]), ("UniProtKB:B", "UniProtKB:A"))

    def test_reciprocal_duplicate_is_not_silently_summed(self):
        raw = PAIRS + b"UniProtKB:A\tUniProtKB:B\t0.5\tp2\tSTRINGDB\n"
        with self.assertRaises(ValueError):
            runner.load_inputs(NODES, raw)

    def test_invalid_weights_and_undeclared_endpoints_are_rejected(self):
        for raw in [PAIRS.replace(b"0.5", value) for value in [b"nan", b"inf", b"-0.1", b"0"]] + [
                PAIRS.replace(b"UniProtKB:B\tUniProtKB:A", b"UniProtKB:D\tUniProtKB:A"),
                PAIRS.replace(b"UniProtKB:B\tUniProtKB:A", b"UniProtKB:A\tUniProtKB:A")]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                runner.load_inputs(NODES, raw)

    def test_outcome_fields_are_not_predictor_inputs(self):
        for header in [b"label", b"outcome", b"detected", b"assay_score"]:
            raw = PAIRS.replace(b"source_bundle", header)
            with self.subTest(header=header), self.assertRaises(ValueError):
                runner.load_inputs(NODES, raw)

    def test_score_projection_preserves_zero_and_uncalibrated_weights(self):
        nodes, pairs = runner.load_inputs(NODES, PAIRS)
        self.assertEqual(runner.project_scores(b"2\t1\t0\n", nodes, pairs), [("p1", 0.0)])
        self.assertEqual(runner.project_scores(b"2\t1\t12.5\n", nodes, pairs), [("p1", 12.5)])

    def test_runtime_cannot_add_drop_or_reorder_original_pairs(self):
        nodes, pairs = runner.load_inputs(NODES, PAIRS)
        for raw in [b"", b"1\t2\t.5\n", b"2\t3\t.5\n", b"2\t1\t.5\n2\t3\t.2\n", b"2\t1\tnan\n"]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                runner.project_scores(raw, nodes, pairs)

    def test_container_uses_immutable_cpu_image_and_offline_readonly_inputs(self):
        command = runner.docker_command(Path("/source"), Path("/result"))
        for flag in ["--network=none", "--pull=never", "--memory=3g", "--cpus=1", "--read-only"]:
            self.assertIn(flag, command)
        self.assertIn(runner.OCTAVE_IMAGE, command)
        self.assertIn("type=bind,src=/source,dst=/author,readonly", command)
        self.assertIn("type=bind,src=/result/input,dst=/input,readonly", command)
        self.assertFalse(any("gpu" in part for part in command))


if __name__ == "__main__":
    unittest.main()
