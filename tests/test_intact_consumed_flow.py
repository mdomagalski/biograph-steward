"""Invented-only controls; no historical interaction source/reader body is read."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from scripts.intact_final_common import RESERVED, summarize
from scripts.replay_intact_consumed_flow import (FORMAT, ORIGIN_SHA, SPLIT,
    BudgetPharos, audit_consumed, evaluate_missing, flow_policy, run_batches,
    validate_policy)
from tests.test_intact_evidence_fidelity import fixture
from tests.test_intact_final_execution import inventory, note, xml_record


def encode(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def consumed_material(*, empty=False):
    """Use only invented source fixture rows; real PMIDs are scope constants."""
    from tests.test_intact_final_publication import material
    files, catalog, bindings, inspection, records, ledger = material()
    # Two eligible fixture rows; the remaining complete source rows are retained.
    for number, row in enumerate(ledger):
        row["eligible"] = not empty and number < 2
        row["exclusion_reasons"] = [] if row["eligible"] else ["invented_outside_scope"]
    files["row_ledger.jsonl"] = b"".join((json.dumps(row) + "\n").encode() for row in ledger)
    origin = {"format": "invented_original_metadata_only", "implementation_sha256": {"invented.py": "a" * 64}}
    origin["content_sha256"] = digest(origin)
    files["origin_execution_freeze.json"] = encode(origin)
    invented_origin_sha = hashlib.sha256(files["origin_execution_freeze.json"]).hexdigest()
    historical = {"format": "invented_historical_code_receipt", "source_data": False,
        "frozen_execution_sha256": invented_origin_sha,
        "files": [{"source_path": "invented.py", "sha256": "a" * 64}]}
    historical["content_sha256"] = digest(historical)
    files["historical_code_archive_receipt.json"] = encode(historical)
    history_sha = hashlib.sha256(files["historical_code_archive_receipt.json"]).hexdigest()
    freeze = {"format": FORMAT, "assessment_split": SPLIT, "publication_ids": list(RESERVED),
        "origin_reserved_freeze_sha256": invented_origin_sha, "pre_captured_stream_access": True,
        "scientific_accuracy_measured": False, "historical_code_receipt_sha256": history_sha,
        "invented_test_fixture": True}
    freeze["content_sha256"] = digest(freeze)
    files["execution_freeze.json"] = encode(freeze)
    inspection.update(status="consumed_development_inspected_not_final_score", assessment_split=SPLIT,
        interpretation="Invented controls for consumed development only; no real reference rows.")
    inspection["bindings"]["execution_freeze_sha256"] = hashlib.sha256(files["execution_freeze.json"]).hexdigest()
    files["inspection_report.json"] = encode(inspection)
    bindings.update(assessment_split=SPLIT, origin_reserved_freeze_sha256=invented_origin_sha,
        historical_code_receipt_sha256=history_sha)
    for filename, key in (("execution_freeze.json", "execution_freeze_sha256"),
        ("row_ledger.jsonl", "ledger_sha256"), ("inspection_report.json", "result_sha256")):
        bindings[key] = hashlib.sha256(files[filename]).hexdigest()
    return files, catalog, bindings, inspection, records, ledger


class ConsumedAccountingTests(unittest.TestCase):
    def test_complete_fixed_policy_has_no_hidden_model_or_reader_access(self):
        policy = flow_policy(False)
        self.assertEqual(policy["publication_split"], SPLIT)
        self.assertFalse(policy["new_IntAct_retrieval"])
        self.assertFalse(policy["new_Java_reader_calls"])
        self.assertFalse(policy["model_calls"])
        self.assertFalse(policy["GPU_runs"])
        for key, bad in (("retries", 1), ("maximum_queries_total", 15),
                         ("maximum_pair_batches", 3), ("cache", "fallback")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_policy({**policy, key: bad})

    def test_fresh_access_requires_prior_explicit_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                BudgetPharos(flow_policy(False), Path(directory), {"attempts": 0})

    def test_actual_attempt_budget_includes_failed_calls_and_has_no_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            total = {"attempts": 0}; seen = []
            def transport(payload):
                seen.append(payload)
                raise RuntimeError("invented network failure")
            client = BudgetPharos(flow_policy(True), Path(directory), total, transport=transport)
            for _ in range(7):
                with self.assertRaises(RuntimeError):
                    client.execute("invented query")
            with self.assertRaises(ValueError):
                client.execute("invented query")
            self.assertEqual(len(seen), 7)
            self.assertEqual(total["attempts"], 7)
            self.assertEqual(client.retries, 0)
            self.assertIsNone(client.cache_dir)
            self.assertEqual(len(list(Path(directory).glob("pharos_attempt_*.json"))), 7)

    def test_total_budget_applies_across_native_clients(self):
        with tempfile.TemporaryDirectory() as directory:
            client = BudgetPharos(flow_policy(True), Path(directory), {"attempts": 14},
                                  transport=lambda _: self.fail("budget must precede network"))
            with self.assertRaises(ValueError):
                client.execute("invented query")

    def test_missing_outputs_are_misses_for_all_original_eligible_rows(self):
        refs = fixture()[0][:2]
        metrics = summarize(evaluate_missing(refs), refs, RESERVED)
        self.assertEqual(metrics["strict_fidelity"]["denominator"], 2)
        self.assertEqual(metrics["strict_fidelity"]["numerator"], 0)
        self.assertEqual(metrics["coverage"]["numerator"], 0)

    def test_downstream_exception_keeps_original_denominator_without_fallback(self):
        refs = fixture()[0][:2]
        calls = []
        def broken_construct(request, output):
            calls.append(request)
            raise RuntimeError("invented deterministic failure")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("biograph_steward.assay_attachment.load_publication", return_value=({}, {}, {})):
                evaluation, preservation, failures, attempts = run_batches(refs, root / "publication", root,
                    flow_policy(False), construct=broken_construct)
        self.assertEqual(len(calls), 1)
        self.assertEqual(attempts, 0)
        self.assertEqual(failures[0]["source_eligible_rows_retained_in_denominator"], 2)
        self.assertEqual(summarize(evaluation, refs, RESERVED)["strict_fidelity"]["denominator"], 2)
        self.assertFalse(preservation)

    def test_zero_eligible_remains_not_evaluable(self):
        refs = fixture()[0][:2]
        for ref in refs:
            ref["ledger"]["eligible"] = False
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("biograph_steward.assay_attachment.load_publication", return_value=({}, {}, {})):
                evaluation, _, failures, attempts = run_batches(refs, root / "publication", root, flow_policy(False))
        metrics = summarize(evaluation, refs, RESERVED)
        self.assertIsNone(metrics["strict_fidelity"]["value"])
        self.assertEqual(metrics["strict_fidelity"]["status"], "unevaluated_empty_stratum")
        self.assertFalse(failures)
        self.assertEqual(attempts, 0)

    def test_consumed_lineage_is_disclosed_without_removing_rows(self):
        xml = {RESERVED[0]: [xml_record(pmid=RESERVED[0])]}
        audit = audit_consumed(xml, [], inventory())
        self.assertIn(RESERVED[0], audit["excluded_publication_ids"])
        self.assertTrue(audit["known_consumed_studies_not_removed_from_source_fidelity_denominator"])
        self.assertFalse(audit["independent_reference_qualification"])
        self.assertEqual(audit["study_independence"], "unverified")

    def test_ambiguous_qualified_lineage_remains_a_stop(self):
        xml = {RESERVED[0]: [xml_record(pmid=RESERVED[0], annotation=note("Subsidiary dataset is described elsewhere"))]}
        audit = audit_consumed(xml, [], inventory())
        self.assertEqual(audit["status"], "blocked_ambiguous_dataset_lineage")
        self.assertTrue(audit["ambiguous_dataset_statements"])

    def test_source_eligible_budget_does_not_select_convenient_subset(self):
        refs = fixture()[0]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                run_batches(refs, Path(directory) / "publication", Path(directory), flow_policy(False))


class ConsumedPublicationFlowTests(unittest.TestCase):
    def test_truthful_consumed_manifest_and_ordinary_full_flow(self):
        from biograph_steward.assay_attachment import load_publication
        from biograph_steward.graph import save_run
        from biograph_steward.intact_final_publication import publish_material
        from tests.test_assay_attachment import cohort_snapshot
        files, catalog, bindings, inspection, records, ledger = consumed_material()
        before = deepcopy((files, catalog, bindings, inspection))
        refs = [{"ledger": item, "reader_record": row["reader_record"]} for item, row in zip(ledger, records)]
        # Only the expected historical-metadata hash changes for this invented
        # fixture; production source/scope/loader checks execute unchanged.
        with patch("biograph_steward.intact_final_publication.ORIGIN_RESERVED_SHA", bindings["origin_reserved_freeze_sha256"]), tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); publication = root / "publication"
            publish_material(files, catalog, bindings, inspection, publication)
            manifest, evidence, captured = load_publication(publication)
            self.assertEqual(manifest["format"], "biograph-steward.intact-consumed-evidence-publication.v1")
            self.assertEqual(manifest["bindings"]["assessment_split"], SPLIT)
            self.assertEqual(len(evidence["row_ledger"]), 4)
            self.assertEqual(len(evidence["observations"]), 2)
            self.assertFalse(evidence["summary"]["reserved_final_rows_opened"])
            self.assertEqual((files, catalog, bindings, inspection), before)
            def invented_construct(request, output):
                save_run(cohort_snapshot(), output)
            evaluation, preservation, failures, attempts = run_batches(refs, publication, root,
                flow_policy(False), construct=invented_construct)
            self.assertFalse(failures)
            self.assertEqual(attempts, 0)
            self.assertTrue(preservation)
            self.assertTrue(all(check["passed"] for check in preservation + evaluation["global_checks"]))
            self.assertEqual(summarize(evaluation, refs, RESERVED)["strict_fidelity"]["numerator"], 2)
            packet = root / "batch_0001/packet"
            packet_manifest = json.loads((packet / "packet_manifest.json").read_text())
            self.assertIn("intact_final_publication", packet_manifest["implementation_sha256"])
            for name, raw in captured.items():
                self.assertEqual((packet / "source/assay_source" / name).read_bytes(), raw)

    def test_consumed_mode_cannot_impersonate_old_reserved_format_or_status(self):
        from biograph_steward.assay_attachment import load_publication
        from biograph_steward.intact_final_publication import publish_material
        files, catalog, bindings, inspection, _, _ = consumed_material()
        inspection["status"] = "final_inspected_not_fidelity_scored"
        files["inspection_report.json"] = encode(inspection)
        bindings["result_sha256"] = hashlib.sha256(files["inspection_report.json"]).hexdigest()
        with patch("biograph_steward.intact_final_publication.ORIGIN_RESERVED_SHA", bindings["origin_reserved_freeze_sha256"]), tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                publish_material(files, catalog, bindings, inspection, Path(directory) / "publication")

    def test_complete_source_bytes_and_consumed_freeze_cannot_be_removed(self):
        from biograph_steward.intact_final_publication import publish_material
        files, catalog, bindings, inspection, _, _ = consumed_material()
        for missing in ("execution_freeze.json", "source/" + RESERVED[0] + ".txt", "reader/" + RESERVED[1] + ".jsonl"):
            changed = dict(files); changed.pop(missing)
            with patch("biograph_steward.intact_final_publication.ORIGIN_RESERVED_SHA", bindings["origin_reserved_freeze_sha256"]), tempfile.TemporaryDirectory() as directory:
                with self.subTest(missing=missing), self.assertRaises((ValueError, KeyError)):
                    publish_material(changed, catalog, bindings, inspection, Path(directory) / "publication")


if __name__ == "__main__":
    unittest.main()
