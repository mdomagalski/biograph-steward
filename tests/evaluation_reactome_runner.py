"""Fixed Reactome learner guards and actual installed-native invented controls."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reactome_runner", ROOT / "scripts/run_reactome_context.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def reseal(value):
    value.pop("content_sha256", None)
    value["content_sha256"] = runner.digest(value)
    return value


class ContractTests(unittest.TestCase):
    def test_selected_schedule_is_500_updates_in_six_full_runs(self):
        full = runner.schedule(99394, mode="full")
        self.assertEqual((full["runs"], full["updates_per_arm_seed"], full["total_updates"]), (6, 500, 3000))
        resource = runner.schedule(99394, mode="resource_check")
        self.assertEqual((resource["seeds"], resource["epochs"], resource["total_updates"]), ([17], 1, 50))
        with self.assertRaisesRegex(ValueError, "99,394"):
            runner.schedule(99393, mode="full")

    def test_exact_two_arm_vocabulary_and_missing_context_are_preserved(self):
        packet = runner.validate_inputs(runner.synthetic_fixture())
        self.assertEqual(set(packet["arms"]), set(runner.ARMS))
        self.assertIn("ENSG00000000007", packet["entities"])
        self.assertEqual(len(packet["candidates"]), 2)
        self.assertEqual(len(packet["masked_gene_pairs"]), 4)

    def test_forbidden_relation_delta_hierarchy_and_direct_product_pairs_fail(self):
        for triple in [("GO:9000001", "go_is_a", "GO:9000001"),
                       ("UniProtKB:INVENTED1", "interacts", "UniProtKB:INVENTED2")]:
            packet = runner.synthetic_fixture()
            packet["arms"][runner.ARMS[1]].append(triple)
            with self.subTest(triple=triple), self.assertRaisesRegex(ValueError, "Forbidden relation delta"):
                runner.validate_inputs(packet)

    def test_missing_arm_vocabulary_duplicates_and_unknown_endpoints_fail(self):
        for mutate in (lambda p: p["arms"].pop(runner.ARMS[0]),
                       lambda p: p["entities"].append(p["entities"][0]),
                       lambda p: p["entities"].remove("REACT:R-HSA-9000001"),
                       lambda p: p["relations"].remove(runner.RELATION)):
            packet = runner.synthetic_fixture()
            mutate(packet)
            with self.assertRaises(ValueError):
                runner.validate_inputs(packet)

    def test_both_literal_or_equivalent_pair_orientations_are_masked(self):
        for a, b in runner.synthetic_fixture()["masked_gene_pairs"]:
            for first, second in ((a, b), (b, a)):
                packet = runner.synthetic_fixture()
                edge = (first, "interacts", second)
                packet["supervision"].append(edge)
                for arm in runner.ARMS:
                    packet["arms"][arm].append(edge)
                with self.subTest(edge=edge), self.assertRaisesRegex(ValueError, "Held-out"):
                    runner.validate_inputs(packet)

    def test_mask_omissions_outcome_fields_and_duplicate_queries_fail(self):
        for mutate in (lambda p: p["masked_gene_pairs"].pop(0),
                       lambda p: p["candidates"][0].update(label=True),
                       lambda p: p["candidates"].append(deepcopy(p["candidates"][0]))):
            packet = runner.synthetic_fixture()
            mutate(packet)
            with self.assertRaises(ValueError):
                runner.validate_inputs(packet)

    def test_source_code_and_graph_validation_are_mandatory_before_runtime(self):
        with patch.object(runner, "validate_prepared_packet", side_effect=ValueError("changed source/hash")), \
                patch.object(runner, "runtime_binding") as native:
            with self.assertRaisesRegex(ValueError, "source/hash"):
                runner.run("invented_graph", "not_created", device="cpu", resource_check=True)
            native.assert_not_called()

    def test_full_execution_without_separate_freeze_does_not_fit_or_create_output(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, "validate_packet", return_value={}), \
                patch.object(runner, "_fit") as fit:
            output = Path(temp) / "no_output"
            with self.assertRaisesRegex(ValueError, "separate frozen"):
                runner.run("invented_graph", output, device="cpu")
            fit.assert_not_called()
            self.assertFalse(output.exists())

    def test_unsafe_output_symlinks_and_nonfinite_json_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "link").symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlinks"):
                runner._output(root / "link" / "bad")
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            runner.strict_json(b'{"loss":NaN}')


class InstalledNativeTests(unittest.TestCase):
    """Required native checks: missing installed dependencies are errors, never skips."""
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name).resolve()
        os.environ.setdefault("PYSTOW_HOME", str(cls.root / "cache"))
        os.environ.setdefault("PYKEEN_HOME", str(cls.root / "cache" / "pykeen"))
        cls.output = cls.root / "synthetic"
        cls.report = runner.run_synthetic(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_native_pairing_scores_transport_and_cache(self):
        runner.validate_proof(self.report, mode="synthetic_check")
        self.assertEqual(self.report["schedule"]["total_updates"], 24)
        self.assertFalse(self.report["biomedical_inputs_used"])
        self.assertEqual(self.report["transport_probe"]["pathway_to_product_to_gene_hops"], 2)
        self.assertEqual(self.report["transport_probe"]["complete_gene_product_pathway_product_gene_hops"], 4)
        self.assertFalse(self.report["transport_probe"]["three_layers_claim_four_hop_transport"])
        self.assertEqual(self.report["transport_probe"]["model"], runner.MODEL)
        self.assertEqual(self.report["transport_probe"]["decomposition"], "bases")
        self.assertEqual(self.report["transport_probe"]["other_product_to_pathway_to_product_to_gene_hops"], 3)
        for row in self.report["arms"]:
            self.assertEqual(row["optimizer_state_steps"], [4])
            self.assertEqual(row["negative_proposals"], 12 * 2 * 16)
            self.assertGreater(row["negative_proposals_filtered"], 0)
            scores = json.loads((self.output / row["scores_file"]).read_text())
            self.assertEqual(len(scores), 3)
            for score in scores:
                self.assertAlmostEqual(score["forward"], score["reverse"], places=5)

    def test_incomplete_runs_changed_fingerprints_nonfinite_losses_and_bad_seals_fail(self):
        mutations = [lambda p: p["arms"].pop(),
                     lambda p: p["arms"][1].update(seed=43),
                     lambda p: p["arms"][0].update(optimizer_state_steps=[3]),
                     lambda p: p["arms"][0].update(losses=[float("inf"), 1.0]),
                     lambda p: p["arms"][0].update(negative_filter_mask_sha256="a" * 64),
                     lambda p: p["arms"][0].update(negative_proposal_sha256="b" * 64),
                     lambda p: p.update(implementation_sha256={}),
                     lambda p: p["cache_probe"].update(status="failed"),
                     lambda p: p.update(mode="resource_check")]
        for mutate in mutations:
            proof = deepcopy(self.report)
            mutate(proof)
            with self.assertRaises(ValueError):
                reseal(proof)
                runner.validate_proof(proof, mode="synthetic_check")
        proof = deepcopy(self.report)
        proof["status"] = "changed_without_reseal"
        with self.assertRaisesRegex(ValueError, "seal"):
            runner.validate_proof(proof, mode="synthetic_check")

    def test_patched_installed_native_source_invalidates_synthetic_execution_proof(self):
        execution = deepcopy(self.report["execution"])
        runner.validate_proof(self.report, mode="synthetic_check", execution=execution)
        execution["device"] = "cuda:0"
        execution["platform"] = "invented_other_platform"
        # A CPU proof can support another intended device when native source is identical.
        runner.validate_proof(self.report, mode="synthetic_check", execution=execution)
        execution["installed_sources_sha256"]["pykeen.nn.message_passing"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "sources differ"):
            runner.validate_proof(self.report, mode="synthetic_check", execution=execution)

    def test_native_factory_rejects_unknown_or_deduplicated_triples(self):
        packet = runner.synthetic_fixture()
        entities = {name: i for i, name in enumerate(packet["entities"])}
        relations = {name: i for i, name in enumerate(packet["relations"])}
        rows = packet["supervision"]
        factory = runner.native_factory(rows, entities, relations)
        self.assertEqual(factory.entity_to_id, entities)
        self.assertEqual(factory.num_entities, len(entities))
        self.assertEqual(factory.num_relations, 5)
        for bad in (rows + [rows[0]], rows + [("unknown", "interacts", packet["entities"][0])]):
            with self.assertRaisesRegex(ValueError, "unknown IDs or duplicate"):
                runner.native_factory(bad, entities, relations)

    def test_native_typed_sampler_empty_context_relation_offsets_are_not_sampled(self):
        from pykeen.sampling import PseudoTypedNegativeSampler
        from pykeen.sampling.filtering import PythonSetFilterer
        packet = runner.synthetic_fixture()
        entities = {name: i for i, name in enumerate(packet["entities"])}
        relations = {name: i for i, name in enumerate(packet["relations"])}
        factory = runner.native_factory(packet["supervision"], entities, relations)
        sampler = PseudoTypedNegativeSampler(mapped_triples=factory.mapped_triples,
                num_entities=factory.num_entities, num_relations=factory.num_relations, num_negs_per_pos=16,
                filterer=PythonSetFilterer(mapped_triples=factory.mapped_triples))
        for relation, index in relations.items():
            if relation != "interacts":
                self.assertEqual(len(set(sampler.offsets[2 * index:2 * index + 3].tolist())), 1)
        negatives, mask = sampler.sample(factory.mapped_triples)
        self.assertEqual(tuple(negatives.shape), (12, 16, 3))
        self.assertEqual(tuple(mask.shape), (12, 16))
        self.assertEqual(set(negatives[:, :, 1].flatten().tolist()), {relations["interacts"]})
        observed = set(factory.mapped_triples[:, [0, 2]].flatten().tolist())
        self.assertLessEqual(set(negatives[:, :, [0, 2]].flatten().tolist()), observed)

    def test_resource_branch_never_constructs_or_predicts_queries_on_invented_case(self):
        # This tiny branch test is explicitly not a real-resource proof and produces no report.
        packet = runner.validate_inputs(runner.synthetic_fixture())
        settings = {"epochs": 1, "batch_size": 12, "seeds": [17], "updates_per_arm_seed": 1, "runs": 2, "total_updates": 2}
        output = self.root / "invented_resource_branch"
        output.mkdir()
        with patch.object(runner, "schedule", return_value=settings), \
                patch("pykeen.predict.predict_triples", side_effect=AssertionError("resource path predicted")), \
                runner.native_logging(output):
            rows, actual = runner._fit(packet, output, execution=self.report["execution"], mode="resource_check")
        self.assertEqual(actual, settings)
        self.assertFalse(any("scores_file" in row or "query_sha256" in row for row in rows))
        self.assertFalse(list(output.glob("*_scores.json")))


if __name__ == "__main__":
    unittest.main()
