"""Invented comparators and assay observations only; never open study outcomes."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import assess_lambourne_corroboration as assessment
from biograph_steward import lambourne_outcomes


def lookup_row(index, state=assessment.STATES[0], *, bundle="STRINGDB", huri=False, inmc=False):
    products = [f"P{index * 2:05d}", f"P{index * 2 + 1:05d}"]
    identity = {"source_row": index + 2, "uniprot_a": products[0], "uniprot_b": products[1],
                "ad_orf_id": str(index * 2 + 1), "db_orf_id": str(index * 2 + 2),
                "source_dataset_column_5": "Zhang_et_al", "source_dataset_column_6": "Zhang_et_al",
                "in_biorxiv_version": "True", "in_published_version": "True"}
    return {"products": products, "identity": identity, "source_row": identity["source_row"],
            "pharos_status": state, "resolved_endpoint_count": 1 if state == assessment.STATES[2] else 2,
            "pharos_matches": {"raw": [{"record": {"type": bundle}}] if state == assessment.STATES[0] else []},
            "previous_pharos_status": "unassessed", "huri_registry_projected_match": huri,
            "huri_author_crosswalk_match": False, "inmc_registry_projected_match": False,
            "inmc_author_crosswalk_match": inmc}


def assay_row(comparator, status):
    evaluable = status in {"detected", "not_detected"}
    return {"products": comparator["products"], "source_row": comparator["source_row"],
            "assay_status": status, "evaluable": evaluable,
            "detected": status == "detected" if evaluable else None}


class ComparatorTests(unittest.TestCase):
    def test_fixed_presence_states_and_original_exposures(self):
        source = [lookup_row(2, assessment.STATES[2]), lookup_row(1, assessment.STATES[1], inmc=True),
                  lookup_row(0, huri=True, bundle="BioPlex,STRINGDB")]
        result = assessment.make_comparator(source)
        self.assertEqual([r["comparator"] for r in result], [1, 0, None])
        self.assertEqual(result[0]["provider_bundles"], ["BioPlex,STRINGDB"])
        self.assertTrue(result[0]["huri_overlap"])
        self.assertTrue(result[1]["inmc_overlap"])
        self.assertEqual(result[2]["provider_bundles"], [])
        self.assertEqual(result[0]["identity"], source[2]["identity"])
        self.assertEqual(result[0]["lookup_record_sha256"], assessment.digest(source[2]))

    def test_duplicate_pair_and_identity_mismatch_rejected(self):
        row = lookup_row(0)
        with self.assertRaises(ValueError):
            assessment.make_comparator([row, copy.deepcopy(row)])
        for field, value in (("products", list(reversed(row["products"]))), ("source_row", 500)):
            altered = copy.deepcopy(row); altered[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                assessment.make_comparator([altered])

    def test_presence_resolution_and_flags_cannot_be_coerced(self):
        cases = [("resolved_endpoint_count", 1), ("huri_author_crosswalk_match", "False"),
                 ("pharos_matches", {"raw": []}), ("pharos_status", "not_a_state")]
        for field, value in cases:
            row = lookup_row(0); row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                assessment.make_comparator([row])

    def test_provider_required_for_represented_pair(self):
        with self.assertRaises(ValueError):
            assessment.make_comparator([lookup_row(0, bundle="")])


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.comparator = assessment.make_comparator([
            lookup_row(0, huri=True), lookup_row(1, bundle="BioPlex,STRINGDB"), lookup_row(2),
            lookup_row(3, assessment.STATES[1], inmc=True), lookup_row(4, assessment.STATES[1]),
            lookup_row(5, assessment.STATES[2])])
        statuses = ["detected", "not_detected", "ambiguous_sequence_confirmation",
                    "not_detected", "test_failed", "detected"]
        self.assay = [assay_row(comp, status) for comp, status in zip(self.comparator, statuses)]

    def test_exclusions_and_unresolved_are_preserved_in_different_denominators(self):
        joined = assessment.join_assay(self.comparator, self.assay)
        result = assessment.summarize(joined)
        overall = result["overall"]
        self.assertEqual(overall["pairs"], 6)
        self.assertEqual(overall["assay_evaluable"], 4)
        self.assertEqual(overall["assay_excluded"], 2)
        self.assertEqual(overall["comparator_evaluable"], 3)
        self.assertEqual(overall["detection_rate"], 0.5)
        groups = result["by_lookup_state"]
        self.assertEqual(groups[assessment.STATES[0]]["detection_rate"], 0.5)
        self.assertEqual(groups[assessment.STATES[1]]["detection_rate"], 0)
        self.assertEqual(groups[assessment.STATES[2]]["detection_rate"], 1)
        self.assertEqual(groups[assessment.STATES[2]]["comparator_evaluable"], 0)
        self.assertEqual(sum(overall["assay_statuses"].values()), 6)
        self.assertEqual(set(overall["assay_statuses"]), set(assessment.ASSAY_STATES))

    def test_provider_bundles_and_exposure_combinations_remain_distinct(self):
        result = assessment.summarize(assessment.join_assay(self.comparator, self.assay))
        self.assertEqual(set(result["by_provider_bundle"]), {"STRINGDB", "BioPlex,STRINGDB"})
        self.assertEqual(result["by_provider_bundle"]["BioPlex,STRINGDB"]["pairs"], 1)
        exposure = result["by_exposure_combination_and_lookup"]
        self.assertEqual(exposure["huri=True,inmc=False"][assessment.STATES[0]]["pairs"], 1)
        self.assertEqual(exposure["huri=False,inmc=True"][assessment.STATES[1]]["pairs"], 1)
        self.assertEqual(exposure["huri=True,inmc=True"][assessment.STATES[0]]["pairs"], 0)
        self.assertIsNone(exposure["huri=True,inmc=True"][assessment.STATES[0]]["detection_rate"])
        self.assertEqual(result["by_mapping_flag"]["inmc_author_crosswalk_match"]["True"]["pairs"], 1)

    def test_zero_and_excluded_only_groups_are_not_zero_detection_claims(self):
        empty = assessment.group_counts([])
        self.assertEqual(empty["pairs"], 0)
        self.assertIsNone(empty["detection_rate"])
        joined = assessment.join_assay([self.comparator[2]], [self.assay[2]])
        self.assertIsNone(assessment.group_counts(joined)["detection_rate"])
        self.assertEqual(assessment.group_counts(joined)["assay_excluded"], 1)

    def test_exact_population_and_source_row_required(self):
        for rows in (self.assay[:-1], self.assay + [self.assay[0]]):
            with self.assertRaises(ValueError):
                assessment.join_assay(self.comparator, rows)
        rows = copy.deepcopy(self.assay); rows[0]["source_row"] += 100
        with self.assertRaises(ValueError):
            assessment.join_assay(self.comparator, rows)

    def test_status_eligibility_and_detection_must_agree(self):
        contradictory = [("detected", False, None), ("not_detected", True, True),
                         ("detected", True, False), ("test_failed", True, False),
                         ("ambiguous_sequence_confirmation", False, False),
                         ("unexpected_new_status", False, None)]
        for status, evaluable, detected in contradictory:
            row = assay_row(self.comparator[0], status)
            row.update(evaluable=evaluable, detected=detected)
            with self.subTest(status=status, evaluable=evaluable, detected=detected), self.assertRaises(ValueError):
                assessment.join_assay([self.comparator[0]], [row])


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.freeze = self.base / "freeze"; self.freeze.mkdir()
        self.out = self.base / "result"
        self.comparator = assessment.make_comparator([lookup_row(0)])
        self.protocol = assessment.seal({"format": assessment.FORMAT, "synthetic_only": True})
        assessment.write_json(self.freeze / "protocol.json", self.protocol)
        self.files = {"source/panel.tsv": b"SYNTHETIC PUBLISHED BYTES", "source/raw_human.tsv": b"SYNTHETIC RAW BYTES",
                      "source/orf_map.tsv": b"SYNTHETIC MAP BYTES",
                      "identity/identity_rows.json": json.dumps([self.comparator[0]["identity"]]).encode()}
        self.adapted = {"scoring_allowed": True, "rows": [assay_row(self.comparator[0], "detected")]}

    def validation(self):
        return mock.patch.object(assessment, "validate_freeze", return_value=(self.protocol, self.files, self.comparator))

    def test_predecode_validation_failure_never_calls_adapter(self):
        with mock.patch.object(assessment, "validate_freeze", side_effect=ValueError("invalid source binding")), \
                mock.patch.object(lambourne_outcomes, "adapt_outcomes") as decoder:
            with self.assertRaises(ValueError):
                assessment.run(self.freeze, self.out)
        decoder.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_source_tamper_is_rejected_before_adapter(self):
        (self.freeze / "source.tsv").write_bytes(b"INVENTED BEFORE")
        protocol = assessment.seal({"files": assessment.file_inventory(self.freeze, "protocol.json")})
        assessment.write_json(self.freeze / "protocol.json", protocol)
        (self.freeze / "source.tsv").write_bytes(b"INVENTED AFTER")
        with mock.patch.object(lambourne_outcomes, "adapt_outcomes") as decoder, self.assertRaises(ValueError):
            assessment.run(self.freeze, self.out)
        decoder.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_exposure_precedes_adapter_and_success_replays(self):
        def adapt(*args):
            exposure = assessment.read(self.out / "exposure_started.json")
            self.assertTrue(exposure["outcomes_consumed_for_future_development"])
            self.assertEqual(args[0], self.files["source/panel.tsv"])
            self.assertEqual(args[1], self.files["source/raw_human.tsv"])
            return self.adapted
        with self.validation(), mock.patch.object(lambourne_outcomes, "adapt_outcomes", side_effect=adapt):
            report = assessment.run(self.freeze, self.out)
            replayed = assessment.verify(self.freeze, self.out)
        self.assertEqual(report, replayed)
        self.assertFalse(report["study_independence_established"])
        self.assertFalse(report["steward_improvement_tested"])
        self.assertEqual(report["summary"]["overall"]["detection_rate"], 1)

    def test_reconciliation_failure_keeps_audit_and_consumption_without_metrics(self):
        blocked = {"scoring_allowed": False, "rows": [], "issue": "synthetic mismatch"}
        with self.validation(), mock.patch.object(lambourne_outcomes, "adapt_outcomes", return_value=blocked), self.assertRaises(ValueError):
            assessment.run(self.freeze, self.out)
        self.assertEqual(assessment.read(self.out / "assay_audit.json"), blocked)
        failure = assessment.read(self.out / "failure.json")
        assessment.require_seal(failure)
        self.assertTrue(failure["outcomes_consumed_for_future_development"])
        self.assertFalse(failure["metrics_emitted"])
        self.assertFalse((self.out / "report.json").exists())
        self.assertFalse((self.out / "rows.json").exists())

    def test_adapter_exception_keeps_failure_receipt(self):
        with self.validation(), mock.patch.object(lambourne_outcomes, "adapt_outcomes", side_effect=ValueError("synthetic malformed raw input")), self.assertRaises(ValueError):
            assessment.run(self.freeze, self.out)
        self.assertTrue((self.out / "exposure_started.json").is_file())
        failure = assessment.read(self.out / "failure.json")
        self.assertEqual(failure["status"], "blocked_after_outcome_access")
        self.assertFalse(failure["metrics_emitted"])

    def test_interrupt_after_access_is_recorded_as_consumed_failure(self):
        with self.validation(), mock.patch.object(lambourne_outcomes, "adapt_outcomes", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            assessment.run(self.freeze, self.out)
        failure = assessment.read(self.out / "failure.json")
        self.assertTrue(failure["outcomes_consumed_for_future_development"])
        self.assertFalse(failure["metrics_emitted"])

    def test_sealed_result_file_mutation_blocks_replay(self):
        with self.validation(), mock.patch.object(lambourne_outcomes, "adapt_outcomes", return_value=self.adapted):
            assessment.run(self.freeze, self.out)
            (self.out / "rows.json").write_text("[]")
            with self.assertRaises(ValueError):
                assessment.verify(self.freeze, self.out)

    def test_second_execution_cannot_reopen_same_freeze_but_verify_can_replay(self):
        with self.validation(), mock.patch.object(lambourne_outcomes, "adapt_outcomes", return_value=self.adapted) as decoder:
            assessment.run(self.freeze, self.out)
            self.assertEqual(decoder.call_count, 1)
            with self.assertRaises(ValueError):
                assessment.run(self.freeze, self.base / "second_result")
            self.assertEqual(decoder.call_count, 1)
            assessment.verify(self.freeze, self.out)
            self.assertEqual(decoder.call_count, 2)

    def test_failed_first_execution_also_prevents_new_execution(self):
        with self.validation(), mock.patch.object(lambourne_outcomes, "adapt_outcomes", side_effect=ValueError("synthetic mismatch")) as decoder:
            with self.assertRaises(ValueError):
                assessment.run(self.freeze, self.out)
            with self.assertRaises(ValueError):
                assessment.run(self.freeze, self.base / "second_result")
            self.assertEqual(decoder.call_count, 1)


class FreezeIntegrityTests(unittest.TestCase):
    """Real integrity gate with small invented source pins, never real data."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve(); self.freeze = self.base / "freeze"; self.freeze.mkdir()
        lookup = [lookup_row(0)]
        files = {"source/panel.tsv": b"INVENTED PUBLISHED", "source/raw_human.tsv": b"INVENTED RAW",
                 "source/orf_map.tsv": b"INVENTED MAP", "source/author_preprocessing.py": b"# INVENTED CODE"}
        for name, raw in files.items():
            target = self.freeze / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        documents = {"identity/identity_rows.json": [lookup[0]["identity"]], "identity/pair_exposure.json": [],
                     "lookup/pair_lookup.json": lookup, "comparator.json": assessment.make_comparator(lookup),
                     "specification.json": assessment.specification(),
                     "lookup/retrieval_source.json": assessment.seal({"synthetic_only": True, "db_version": "invented"}),
                     "lookup/retrieval_plan.json": assessment.seal({"synthetic_only": True, "profile": "ppi"}),
                     "lookup/retrieval_summary.json": assessment.seal({"synthetic_only": True, "files": {}}),
                     "lookup/retrieval_context_targets.json": {"synthetic_only": True, "products": lookup[0]["products"]},
                     "verification/synthetic_author_replay.json": {
                         "passed": True, "synthetic_only": True, "actual_outcomes_decoded": False,
                         "pandas": "1.4.3", "numpy": "1.23.0", "failures": 0, "errors": 0, "skipped": 0,
                         "tests_run": 24, "truth_table_cases": 36,
                         "implementation_sha256": assessment.sha(ROOT / "biograph_steward/lambourne_outcomes.py"),
                         "author_full_source_sha256": assessment.AUTHOR_CODE_SHA}}
        for name, value in documents.items():
            target = self.freeze / name; target.parent.mkdir(parents=True, exist_ok=True); assessment.write_json(target, value)
        for prefix, names in (("identity", ("identity_rows.json", "pair_exposure.json")), ("lookup", ("pair_lookup.json",))):
            report = {"output_sha256": {name: assessment.sha(self.freeze / prefix / name) for name in names}}
            if prefix == "lookup":
                report.update(retrieval_source_sha256=assessment.sha(self.freeze / "lookup/retrieval_source.json"),
                              retrieval_plan_sha256=documents["lookup/retrieval_plan.json"]["content_sha256"],
                              retrieval_summary_sha256=documents["lookup/retrieval_summary.json"]["content_sha256"],
                              inventory_sha256=assessment.sha(self.freeze / "lookup/retrieval_context_targets.json"))
            assessment.write_json(self.freeze / prefix / "report.json", report)
        self.source_hashes = {name: assessment.sha(self.freeze / name) for name in assessment.SOURCE_HASHES}
        self.expected = {assessment.STATES[0]: 1}
        self.protocol = {"format": assessment.FORMAT, "outcomes_decoded": False,
                         "implementation_sha256": {name: assessment.sha(ROOT / name) for name in assessment.CODE},
                         "python": assessment.platform.python_version(), "population": 1, "lookup_counts": self.expected}
        self.reseal()
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(assessment, "SOURCE_HASHES", self.source_hashes))
        stack.enter_context(mock.patch.object(assessment, "RAW_SHA", self.source_hashes["source/raw_human.tsv"]))
        stack.enter_context(mock.patch.object(assessment, "EXPECTED", self.expected))

    def reseal(self):
        self.protocol["files"] = assessment.file_inventory(self.freeze, "protocol.json")
        assessment.write_json(self.freeze / "protocol.json", assessment.seal(self.protocol))

    def test_bound_synthetic_bundle_passes_without_outcome_decoder(self):
        with mock.patch.object(lambourne_outcomes, "adapt_outcomes") as decoder:
            protocol, files, comparator = assessment.validate_freeze(self.freeze)
        decoder.assert_not_called()
        self.assertEqual(protocol["population"], 1)
        self.assertEqual(files["source/raw_human.tsv"], b"INVENTED RAW")
        self.assertEqual(comparator[0]["comparator"], 1)

    def test_resealing_source_mutation_does_not_change_reviewed_source_pin(self):
        (self.freeze / "source/panel.tsv").write_bytes(b"INVENTED ALTERED PUBLICATION")
        self.reseal()
        with mock.patch.object(lambourne_outcomes, "adapt_outcomes") as decoder, self.assertRaises(ValueError):
            assessment.run(self.freeze, self.base / "result")
        decoder.assert_not_called()
        self.assertFalse((self.base / "result").exists())

    def test_resealing_identity_output_does_not_bypass_original_audit(self):
        assessment.write_json(self.freeze / "identity/identity_rows.json", [])
        self.reseal()
        with self.assertRaises(ValueError):
            assessment.validate_freeze(self.freeze)

    def test_resealing_retrieval_metadata_does_not_bypass_audited_lineage(self):
        for name in ("source", "plan", "summary", "context_targets"):
            path = self.freeze / f"lookup/retrieval_{name}.json"
            original = path.read_bytes()
            changed = assessment.read(path); changed["synthetic_tampered_metadata"] = True
            if "content_sha256" in changed:
                assessment.seal(changed)
            assessment.write_json(path, changed); self.reseal()
            with self.subTest(name=name), self.assertRaises(ValueError):
                assessment.validate_freeze(self.freeze)
            path.write_bytes(original)
        self.reseal()
        assessment.validate_freeze(self.freeze)

    def test_resealing_changed_comparator_does_not_bypass_lookup_reproduction(self):
        rows = assessment.read(self.freeze / "comparator.json"); rows[0]["comparator"] = 0
        assessment.write_json(self.freeze / "comparator.json", rows); self.reseal()
        with self.assertRaises(ValueError):
            assessment.validate_freeze(self.freeze)

    def test_changed_runtime_and_specification_are_not_admitted(self):
        self.protocol["python"] = "0.0.0-synthetic-different-runtime"; self.reseal()
        with self.assertRaises(ValueError):
            assessment.validate_freeze(self.freeze)
        self.protocol["python"] = assessment.platform.python_version()
        specification = assessment.specification(); specification["study_independence_established"] = True
        assessment.write_json(self.freeze / "specification.json", specification); self.reseal()
        with self.assertRaises(ValueError):
            assessment.validate_freeze(self.freeze)

    def test_author_replay_proof_must_cover_pinned_runtime_and_current_adapter(self):
        path = self.freeze / "verification/synthetic_author_replay.json"
        proof = assessment.read(path)
        for key, value in (("passed", False), ("pandas", "2.0.0"), ("truth_table_cases", 35),
                           ("implementation_sha256", "0" * 64), ("actual_outcomes_decoded", True)):
            changed = dict(proof); changed[key] = value
            assessment.write_json(path, changed); self.reseal()
            with self.subTest(key=key), self.assertRaises(ValueError):
                assessment.validate_freeze(self.freeze)
    def test_symlink_member_rejected_even_when_target_bytes_match(self):
        source = self.freeze / "source/panel.tsv"; copied = self.base / "copy.tsv"
        copied.write_bytes(source.read_bytes()); source.unlink(); source.symlink_to(copied)
        with self.assertRaises(ValueError):
            assessment.validate_freeze(self.freeze)


if __name__ == "__main__":
    unittest.main()
