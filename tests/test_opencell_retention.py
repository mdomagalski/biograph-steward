"""Invented confirmation fixtures; never open deposited OpenCell call rows."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha

SPEC = importlib.util.spec_from_file_location("assess_opencell_retention",
    Path(__file__).resolve().parents[1] / "scripts/assess_opencell_retention.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def write_tsv(path, columns, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def pair(left, right):
    left, right = sorted(("UniProtKB:" + left, "UniProtKB:" + right))
    return "ppi:" + digest({"subject": left, "object": right})[:24], left, right


def fixture(root, *, large=False):
    source = root / "source"; source.mkdir()
    policy = root / "policy.json"
    write_json(policy, {"reference_calls_opened": False,
                       "primary_candidate": "STRING11_organism_native_experimental_channel"})
    if large:
        specifications = [(f"P{10001+i%20:05d}", f"Q{10001+i:05d}", "eligible") for i in range(160)]
        metadata = [{"metadata": {"target_name": f"BAIT{i}", "ensg_id": f"ENSG{i}", "cell_line_id": i},
                     "uniprot_metadata": {"uniprot_id": f"P{10001+i:05d}"}} for i in range(20)]
    else:
        specifications = [("P10001", f"Q{10001+i:05d}", "eligible") for i in range(5)]
        specifications += [("P10001", "Q10007", "protected"), ("P10001", "Q10008", "quarantined")]
        metadata = [{"metadata": {"target_name": "BAIT", "ensg_id": "ENSG1", "cell_line_id": 1, "transcript_id": "ENST1"},
                     "uniprot_metadata": {"uniprot_id": "P10001"}}]
    graph, weighted, qualification_rows, nodes = [], [], [], set()
    for i, (left, right, state) in enumerate(specifications):
        uid, subject, obj = pair(left, right)
        eligible = state == "eligible"
        row = {"pair_id": uid, "subject": subject, "object": obj, "edge_id": "edge:" + str(i),
               "source_bundle": "BioPlex,STRINGDB" if state == "protected" else "STRINGDB",
               "weight": "0.8", "pruning_eligible": str(eligible).lower()}
        graph.append(row); nodes.update((subject, obj))
        if state != "quarantined":
            weighted.append({name: row[name] for name in
                             ("subject", "object", "weight", "pair_id", "edge_id", "source_bundle", "pruning_eligible")})
        qualification_rows.append({"pair_id": uid, "subject": subject, "object": obj,
            "original_pruning_eligible": state != "protected", "qualified_pruning_eligible": eligible,
            "original_source_protected": state == "protected", "ranking_background_present": state != "quarantined",
            "qualification_reasons": ["synthetic_mapping_quarantine"] if state == "quarantined" else []})
    write_tsv(source / "graph_pairs.tsv", runner.PAIR_COLUMNS, graph)
    write_tsv(source / "network_nodes.tsv", runner.NODE_COLUMNS,
              [{"node_id": node, "resolution_status": "resolved", "canonical_graph_node_present": "true"} for node in sorted(nodes)])
    write_tsv(source / "weighted_pairs.tsv",
              ("subject", "object", "weight", "pair_id", "edge_id", "source_bundle", "pruning_eligible"), weighted)
    (source / "source_pair_qualification.jsonl").write_text("".join(json.dumps(row) + "\n" for row in qualification_rows))
    eligible_count = sum(row["pruning_eligible"] == "true" for row in graph)
    source_receipt = runner.seal({"format": runner.SOURCE_FORMAT, "new_assay_calls_accessed": False,
        "original_graph_modified": False, "node_universe_preserved": True,
        "original_source_pairs": len(graph), "qualified_rankable_pairs": eligible_count,
        "abstain_retained_pairs": len(graph)-eligible_count, "qualified_weighted_pairs": len(weighted),
        "retained_rankable_budget": eligible_count*4//5, "candidate_policy_sha256": sha(policy),
        "qualified_inputs_sha256": {name: sha(source / name) for name in
            ("graph_pairs.tsv", "network_nodes.tsv", "weighted_pairs.tsv", "source_pair_qualification.jsonl")}})
    write_json(source / "source_qualification.json", source_receipt)
    membership = root / "membership.tsv"
    member_rows = []
    for i, row in enumerate(graph):
        item = {"pair_id": row["pair_id"], **{arm: "true" for arm in runner.ARMS}}
        if row["pruning_eligible"] == "true":
            for arm in runner.ARMS[1:]:
                if large:
                    # Equal128/160 source budgets;100 invented positives.
                    lost = set(range(100, 132))
                    if arm == "native_top80": lost = set(range(90, 100)) | set(range(100, 122))
                    if arm == "pa_top80": lost = set(range(80, 100)) | set(range(100, 112))
                else:
                    lost = {0 if arm == "native_top80" else 1 if arm == "pa_top80" else 2}
                item[arm] = str(i not in lost).lower()
        member_rows.append(item)
    write_tsv(membership, ("pair_id", *runner.ARMS), member_rows)
    native = root / "calls.csv"; raw = root / "raw.csv"; meta = root / "metadata.json"
    write_json(meta, metadata)
    calls, identities = [], []
    if large:
        for i in range(100):
            calls.append({"": str(i), "target": f"BAIT{i%20}", "prey": f"PREY{i}"})
            identities.append([i, "P000", f"BAIT{i%20}", f"PREY{i}", f"Q{10001+i:05d}", "UNREAD", "UNREAD"])
    else:
        labels = [("BAIT", "GOOD1", "Q10001"), ("BAIT", "GOOD1", "Q10001"),
                  ("BAIT", "GOOD2", "Q10002"), ("BAIT", "AMBIGUOUS", "Q10003;Q10004"),
                  ("BAIT", "PROTECTED", "Q10007"), ("BAIT", "QUARANTINED", "Q10008"),
                  ("BAIT", "ABSENT", "Q19999"), ("UNKNOWN", "UNMAPPED", "Q10001")]
        for i, (target, prey, up) in enumerate(labels):
            calls.append({"": str(i), "target": target, "prey": prey})
            identities.append([i, "P000", target, prey, up, "UNREAD", "UNREAD"])
    with native.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["", "target", "prey"])
        writer.writeheader(); writer.writerows(calls)
    with raw.open("w", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(runner.RAW_COLUMNS); writer.writerows(identities)
    return {"source": source, "membership": membership, "calls": native, "raw": raw, "metadata": meta, "policy": policy}


class OpenCellRetentionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def freeze(self, data, **kwargs):
        return runner.freeze(data["source"], data["membership"], data["calls"], data["raw"],
                             data["metadata"], data["policy"], self.root / "frozen", **kwargs)

    def score(self, protocol):
        return runner.score(self.root / "frozen", protocol["content_sha256"], self.root / "results", allow_reference_calls=True)

    def test_freeze_does_not_parse_reference_calls_or_statistics(self):
        data = fixture(self.root)
        data["calls"].write_text("This is opaque during freeze, not even a valid CSV.\n")
        with patch.object(runner, "load_native_calls", side_effect=AssertionError("Reference opened")):
            protocol = self.freeze(data)
        self.assertFalse(protocol["reference_calls_opened"])
        self.assertEqual(protocol["input_files"]["native_calls"]["sha256"], sha(data["calls"]))

    def test_tampered_reference_is_rejected_before_outcome_access(self):
        data = fixture(self.root); protocol = self.freeze(data)
        data["calls"].write_text(data["calls"].read_text() + "changed\n")
        with patch.object(runner, "load_native_calls", side_effect=AssertionError("Reference opened")):
            with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                self.score(protocol)
        self.assertFalse((self.root / "results").exists())

    def test_tampered_vector_artifact_is_rejected(self):
        data = fixture(self.root); vector = self.root / "scores.tsv"; vector.write_text("opaque vector\n")
        protocol = self.freeze(data, artifacts={"native_vector": vector})
        vector.write_text("different vector\n")
        with self.assertRaisesRegex(ValueError, "Frozen input changed"):
            self.score(protocol)

    def test_protocol_commitment_and_explicit_reference_access_are_required(self):
        data = fixture(self.root); protocol = self.freeze(data)
        with self.assertRaisesRegex(ValueError, "allow-reference-calls"):
            runner.score(self.root / "frozen", protocol["content_sha256"], self.root / "results")
        with self.assertRaisesRegex(ValueError, "protocol"):
            runner.score(self.root / "frozen", "0"*64, self.root / "results", allow_reference_calls=True)

    def test_membership_cannot_prune_protected_or_quarantined_pairs(self):
        data = fixture(self.root)
        rows = runner.tsv(data["membership"], ("pair_id", *runner.ARMS))
        rows[-1][runner.PRIMARY] = "false"
        write_tsv(data["membership"], ("pair_id", *runner.ARMS), rows)
        with self.assertRaisesRegex(ValueError, "Protected or quarantined"):
            self.freeze(data)

    def test_exact_global_budget_is_checked_before_reference_access(self):
        data = fixture(self.root)
        rows = runner.tsv(data["membership"], ("pair_id", *runner.ARMS))
        for row in rows: row[runner.PRIMARY] = "true"
        write_tsv(data["membership"], ("pair_id", *runner.ARMS), rows)
        with self.assertRaisesRegex(ValueError, "budget"):
            self.freeze(data)

    def test_weighted_field_drift_is_rejected_even_with_resealed_source_receipt(self):
        changes = {"subject": "UniProtKB:P19999", "object": "UniProtKB:Q19999",
                   "edge_id": "edge:changed", "source_bundle": "BioPlex",
                   "pruning_eligible": "false", "weight": "0.80"}
        for field, value in changes.items():
            with self.subTest(field=field):
                folder = self.root / field; folder.mkdir()
                data = fixture(folder)
                path = data["source"] / "weighted_pairs.tsv"
                columns = ("subject", "object", "weight", "pair_id", "edge_id", "source_bundle", "pruning_eligible")
                rows = runner.tsv(path, columns); rows[0][field] = value
                write_tsv(path, columns, rows)
                receipt_path = data["source"] / "source_qualification.json"
                receipt = runner.read_json(receipt_path); receipt.pop("content_sha256")
                receipt["qualified_inputs_sha256"]["weighted_pairs.tsv"] = sha(path)
                write_json(receipt_path, runner.seal(receipt))
                with self.assertRaisesRegex(ValueError, "Weighted row differs"):
                    self.freeze(data)

    def test_incomplete_same_label_bait_evidence_quarantines_all_calls_and_is_preserved(self):
        data = fixture(self.root)
        metadata = runner.read_json(data["metadata"])
        metadata.append({"metadata": {"target_name": "BAIT", "ensg_id": "ENSG2", "cell_line_id": 2},
                         "uniprot_metadata": {}})
        write_json(data["metadata"], metadata)
        metrics = self.score(self.freeze(data))["metrics"]
        self.assertEqual(metrics["primary_unique_eligible_positive_pairs"], 0)
        ledger = [json.loads(line) for line in (self.root / "results/call_mapping_ledger.jsonl").read_text().splitlines()]
        self.assertEqual(ledger[0]["mapping_status"], "missing_or_ambiguous_bait_source_identity")
        self.assertEqual(len(ledger[0]["source_bait_metadata_rows"]), 2)
        self.assertEqual(ledger[0]["source_bait_metadata_rows"][1]["metadata"]["ensg_id"], "ENSG2")

    def test_invalid_same_label_identity_is_not_overridden_by_later_complete_row(self):
        complete = {"metadata": {"target_name": "BAIT", "ensg_id": "ENSG1"},
                    "uniprot_metadata": {"uniprot_id": "P10001"}}
        for invalid in [
            {"metadata": {"target_name": "BAIT", "ensg_id": "ENSG2"}, "uniprot_metadata": {}},
            {"metadata": {"target_name": "BAIT"}, "uniprot_metadata": {"uniprot_id": "P10001"}},
            {"metadata": {"target_name": "BAIT", "ensg_id": "INVALID"}, "uniprot_metadata": {"uniprot_id": "P10001"}},
        ]:
            for rows in ([invalid, complete], [complete, invalid]):
                identities, details = runner.bait_indexes(rows)
                self.assertEqual(identities["BAIT"], set())
                self.assertEqual(len(details["BAIT"]), 2)

    def test_complete_ledger_dedup_and_separate_source_categories(self):
        data = fixture(self.root); report = self.score(self.freeze(data)); metrics = report["metrics"]
        self.assertEqual(metrics["native_call_rows_preserved"], 8)
        self.assertEqual(metrics["primary_unique_eligible_positive_pairs"], 2)
        self.assertEqual(metrics["evaluation_category_row_counts"],
                         {"mapping_unresolved": 2, "qualified_eligible": 3, "source_absent": 1, "source_protected": 1, "source_quarantined": 1})
        self.assertEqual(metrics["arms"][runner.PRIMARY]["positive_pairs_retained"], 2)
        self.assertEqual(metrics["arms"]["native_top80"]["positive_pairs_retained"], 1)
        self.assertEqual(metrics["arms"]["pa_top80"]["positive_pairs_retained"], 1)
        self.assertEqual(metrics["primary_decision"], "unscorable_insufficient_coverage")
        self.assertFalse(metrics["raw_noncalls_evaluated"])
        ledger = [json.loads(line) for line in (self.root / "results/call_mapping_ledger.jsonl").read_text().splitlines()]
        self.assertEqual(len(ledger), 8)
        self.assertEqual(ledger[0]["source_bait_metadata_rows"][0]["metadata"]["transcript_id"], "ENST1")
        self.assertFalse(report["raw_native_call_file_copied"])

    def test_macro_excludes_zero_denominator_baits_and_keeps_them_in_table(self):
        data = fixture(self.root); metrics = self.score(self.freeze(data))["metrics"]
        self.assertEqual(metrics["all_exact_author_bait_labels"], 2)
        self.assertEqual(metrics["evaluable_exact_author_bait_labels"], 1)
        self.assertEqual(metrics["zero_denominator_bait_labels"], 1)
        self.assertEqual(metrics["arms"][runner.PRIMARY]["macro_bait_retention"], 1)
        self.assertEqual(metrics["arms"]["native_top80"]["macro_bait_retention"], .5)
        self.assertEqual(metrics["paired_primary_vs_control"]["native_top80"]["baits_improved"], 1)
        with (self.root / "results/per_bait_descriptive.tsv").open() as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(next(row for row in rows if row["target"] == "UNKNOWN")[runner.PRIMARY+"_retention"], "")

    def test_reciprocal_calls_share_micro_pair_but_keep_bait_orientation(self):
        data = fixture(self.root)
        metadata = runner.read_json(data["metadata"])
        metadata.append({"metadata": {"target_name": "REVERSE", "ensg_id": "ENSG2"},
                         "uniprot_metadata": {"uniprot_id": "Q10001"}})
        write_json(data["metadata"], metadata)
        with data["calls"].open("a", newline="") as handle:
            csv.writer(handle).writerow([8, "REVERSE", "BAIT"])
        with data["raw"].open("a", newline="") as handle:
            csv.writer(handle).writerow([8, "P001", "REVERSE", "BAIT", "P10001", "UNREAD", "UNREAD"])
        metrics = self.score(self.freeze(data))["metrics"]
        self.assertEqual(metrics["native_call_rows_preserved"], 9)
        self.assertEqual(metrics["primary_unique_eligible_positive_pairs"], 2)
        self.assertEqual(metrics["evaluable_exact_author_bait_labels"], 2)
        with (self.root / "results/per_bait_descriptive.tsv").open() as handle:
            reverse = next(row for row in csv.DictReader(handle, delimiter="\t") if row["target"] == "REVERSE")
        self.assertEqual(reverse["eligible_positive_partners"], "1")

    def test_conflicting_accessions_across_attempts_are_quarantined(self):
        identities = {"BAIT": {("ENSG1", "P10001")}}
        row = {"source_line": 2, "source_index": "0", "target": "BAIT", "prey": "PREY"}
        raw = {("BAIT", "PREY"): {"raw_rows": 2, "experiments": {"P001", "P002"},
                                    "protein_groups": {("Q10001",), ("Q10002",)}}}
        resolved = runner.resolve_call(row, identities, {}, raw)
        self.assertEqual(resolved["mapping_status"], "inconsistent_or_invalid_prey_source_accession")
        self.assertNotIn("pair", resolved)

    def test_no_native_calls_yields_unscorable_without_division_or_negative_labels(self):
        data = fixture(self.root); data["calls"].write_text(",target,prey\n")
        metrics = self.score(self.freeze(data))["metrics"]
        self.assertEqual(metrics["native_call_rows_preserved"], 0)
        self.assertEqual(metrics["primary_decision"], "unscorable_insufficient_coverage")
        self.assertIsNone(metrics["arms"][runner.PRIMARY]["micro_retention"])
        self.assertIsNone(metrics["arms"][runner.PRIMARY]["macro_bait_retention"])

    def test_unresolved_inventory_identifier_is_not_counted_as_a_source_graph_node(self):
        data = fixture(self.root)
        nodes = runner.tsv(data["source"] / "network_nodes.tsv", runner.NODE_COLUMNS)
        canonical_count = len(nodes)
        nodes.append({"node_id": "UniProtKB:Q29999", "resolution_status": "not_found", "canonical_graph_node_present": "false"})
        write_tsv(data["source"] / "network_nodes.tsv", runner.NODE_COLUMNS, nodes)
        qualification = runner.read_json(data["source"] / "source_qualification.json")
        qualification.pop("content_sha256")
        qualification["qualified_inputs_sha256"]["network_nodes.tsv"] = sha(data["source"] / "network_nodes.tsv")
        write_json(data["source"] / "source_qualification.json", runner.seal(qualification))
        protocol = self.freeze(data)
        self.assertEqual(protocol["source_nodes"], canonical_count)
        self.assertEqual(protocol["method_inventory_nodes"], canonical_count+1)
        report = self.score(protocol)
        self.assertEqual(report["source_nodes_preserved"], canonical_count)
        self.assertEqual(report["metrics"]["arms"][runner.PRIMARY]["node_records_preserved"], canonical_count)

    def test_dates_isoforms_constructs_and_ambiguous_groups_are_not_guessed(self):
        identities = {"BAIT": {("ENSG1", "P10001")}}
        row = {"source_line": 2, "source_index": "0", "target": "BAIT", "prey": "2-Sep"}
        raw = {("BAIT", "2-Sep"): {"raw_rows": 1, "experiments": {"P001"}, "protein_groups": {("Q10001-2",)}}}
        resolved = runner.resolve_call(row, identities, {}, raw)
        self.assertEqual(resolved["prey"], "2-Sep")
        self.assertEqual(resolved["prey_uniprot_id"], "Q10001-2")
        missing = runner.resolve_call({**row, "target": "BAIT_N"}, identities, {}, raw)
        self.assertEqual(missing["mapping_status"], "missing_or_ambiguous_bait_source_identity")
        raw[("BAIT", "2-Sep")]["protein_groups"] = {("Q10001", "Q10002")}
        ambiguous = runner.resolve_call(row, identities, {}, raw)
        self.assertNotIn("pair", ambiguous)

    def test_full_coverage_gate_and_both_controls_required(self):
        data = fixture(self.root, large=True); metrics = self.score(self.freeze(data))["metrics"]
        self.assertEqual(metrics["primary_unique_eligible_positive_pairs"], 100)
        self.assertEqual(metrics["evaluable_exact_author_bait_labels"], 20)
        self.assertEqual(metrics["primary_decision"], "bounded_positive_retention_gain")
        self.assertEqual(metrics["paired_primary_vs_control"]["native_top80"]["positive_pair_count_difference"], 10)
        self.assertEqual(metrics["paired_primary_vs_control"]["pa_top80"]["positive_pair_count_difference"], 20)
        self.assertEqual({metrics["arms"][arm]["source_pairs_retained"] for arm in runner.ARMS[1:]}, {128})

    def test_tie_against_either_control_fails_utility_gate(self):
        data = fixture(self.root, large=True)
        rows = runner.tsv(data["membership"], ("pair_id", *runner.ARMS))
        for row in rows: row["pa_top80"] = row[runner.PRIMARY]
        write_tsv(data["membership"], ("pair_id", *runner.ARMS), rows)
        metrics = self.score(self.freeze(data))["metrics"]
        self.assertTrue(metrics["coverage_gate_passed"])
        self.assertFalse(metrics["primary_utility_gate_passed"])
        self.assertEqual(metrics["primary_decision"], "no_gain_over_both_controls")


if __name__ == "__main__":
    unittest.main()
