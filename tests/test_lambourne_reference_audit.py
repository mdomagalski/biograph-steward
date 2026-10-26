"""Synthetic identity-only contracts; never open the public assay outcomes."""
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


SPEC = importlib.util.spec_from_file_location(
    "audit_lambourne_reference", Path(__file__).resolve().parents[1] / "scripts/audit_lambourne_reference.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

P1, P2, P3, P4, P5, P6 = [f"P0000{i}" for i in range(1, 7)]
A, B, C, D = [f"ENSG{i:011d}" for i in range(1, 5)]


def panel_row(a=P1, b=P2, *, source1="Zhang_et_al", source2="Zhang_et_al",
              preprint="True", published="True", opaque=b"\xff\x80", ad=None, db=None):
    fields = [a.encode(), b.encode(), (ad or a[-1:]).encode(), (db or b[-1:]).encode(),
              source1.encode(), source2.encode(), opaque, preprint.encode(), published.encode()]
    return b"\t".join(fields)


def panel(*rows):
    return audit.HEADER + b"\n" + b"\n".join(rows) + b"\n"


class IdentityParsingTests(unittest.TestCase):
    def test_non_utf8_outcome_is_never_decoded_or_exported(self):
        one = audit.panel_identities(panel(panel_row(opaque=b"\xff\x80")))
        two = audit.panel_identities(panel(panel_row(opaque=b"arbitrary_uninterpreted_text")))
        self.assertEqual(one, two)
        self.assertNotIn("result", one[0])
        self.assertNotIn("arbitrary_uninterpreted_text", json.dumps(two))

    def test_duplicate_source_headers_preserve_both_independent_columns(self):
        row, = audit.panel_identities(panel(panel_row(source1="first", source2="second")))
        self.assertEqual(row["source_dataset_column_5"], "first")
        self.assertEqual(row["source_dataset_column_6"], "second")

    def test_reciprocal_duplicate_and_self_rows_remain_identifiable(self):
        rows = audit.panel_identities(panel(panel_row(), panel_row(P2, P1), panel_row(), panel_row(P1, P1)))
        self.assertEqual([r["source_row"] for r in rows], [2, 3, 4, 5])
        self.assertEqual([(r["uniprot_a"], r["uniprot_b"]) for r in rows],
                         [(P1, P2), (P2, P1), (P1, P2), (P1, P1)])

    def test_missing_control_accessions_are_explicit_nulls_and_orfs_are_preserved(self):
        rows = audit.panel_identities(panel(panel_row(a="None", ad="93"),
                                           panel_row(a="NULL", b="", ad="94", db="95")))
        self.assertIsNone(rows[0]["uniprot_a"])
        self.assertEqual(rows[0]["uniprot_b"], P2)
        self.assertEqual(rows[0]["ad_orf_id"], "93")
        self.assertIsNone(rows[1]["uniprot_a"])
        self.assertIsNone(rows[1]["uniprot_b"])
        self.assertEqual(rows[1]["ad_orf_id"], "94")

    def test_schema_width_identity_and_nomination_errors_fail_closed(self):
        malformed = [
            audit.HEADER.replace(b"source_dataset\tsource_dataset", b"source_dataset\tdeduplicated") + b"\n" + panel_row(),
            panel(panel_row() + b"\textra"),
            panel(panel_row().rsplit(b"\t", 1)[0]),
            panel(panel_row(a="TP53")),
            panel(panel_row(published="yes")),
            audit.HEADER + b"\n",
        ]
        for raw in malformed:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                audit.panel_identities(raw)


class OverlapTests(unittest.TestCase):
    def test_gene_projection_is_symmetric_and_preserves_shared_products(self):
        actual = audit.projected_pairs({audit.pair(A, B), audit.pair(C, B)},
                                       {A: {P1, P3}, B: {P2}, C: {P3}})
        self.assertEqual(actual, {audit.pair(P1, P2), audit.pair(P3, P2)})
        self.assertEqual(actual, audit.projected_pairs({(B, A), (B, C)},
                         {A: {P1, P3}, B: {P2}, C: {P3}}))

    def test_ambiguous_author_crosswalk_flags_possible_overlap_without_choosing_gene(self):
        crosswalk = {P1: {A, C}, P2: {B}}
        originals = {audit.pair(C, B)}
        self.assertTrue(audit.gene_pair_match((P1, P2), crosswalk, originals))
        self.assertTrue(audit.gene_pair_match((P2, P1), crosswalk, originals))
        self.assertEqual(crosswalk[P1], {A, C})
        self.assertFalse(audit.gene_pair_match((P1, P3), crosswalk, originals))

    def test_mapping_preserves_multiple_values_and_deduplicates_exact_repeats(self):
        raw = f"uniprot_ac\tensembl_gene_id\n{P1}\t{A}\n{P1}\t{C}\n{P1}\t{A}\n".encode()
        self.assertEqual(audit.mapping(raw, b"uniprot_ac\tensembl_gene_id")[P1], {A, C})

    def test_known_pharos_match_takes_priority_over_missing_endpoint_query(self):
        p = audit.pair(P1, P2)
        self.assertEqual(audit.pharos_status(p, {p: [{}]}, set()), "present_in_saved_raw_ppi")

    def test_missing_saved_match_is_distinguished_from_unqueried(self):
        p = audit.pair(P1, P2)
        self.assertEqual(audit.pharos_status(p, {}, {P1, P2}), "not_found_both_endpoints_queried")
        self.assertEqual(audit.pharos_status(p, {}, {P1}), "not_found_one_endpoint_queried")
        self.assertEqual(audit.pharos_status(p, {}, set()), "unassessed_neither_endpoint_queried")

    def test_requested_but_unresolved_is_not_called_unqueried(self):
        p = audit.pair(P1, P2)
        self.assertEqual(audit.pharos_status(p, {}, set(), {P1}), "unassessed_requested_endpoint_unresolved")
        self.assertEqual(audit.pharos_status(p, {}, set(), {P1, P2}), "unassessed_requested_endpoint_unresolved")
        self.assertEqual(audit.pharos_status(p, {}, {P1}, {P1, P2}), "not_found_one_endpoint_queried")

    def test_sorted_uniprot_columns_do_not_assert_ad_db_assignment(self):
        row, = audit.panel_identities(panel(panel_row(ad="2", db="1")))
        self.assertTrue(audit.orf_pair_matches(row, {P1: {"1"}, P2: {"2"}}))
        self.assertFalse(audit.orf_pair_matches(row, {P1: {"9"}, P2: {"2"}}))
        self.assertIsNone(audit.orf_pair_matches({**row, "uniprot_a": None}, {P2: {"2"}}))


class SourceReceiptTests(unittest.TestCase):
    def sources(self, folder):
        entries = []
        for name in (audit.PANEL, audit.ORF_MAP, audit.GENE_MAP):
            raw = b"synthetic artifact bytes\xff"
            destination = folder / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            entries.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                            "git_blob_sha1": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest(),
                            "url": f"https://raw.githubusercontent.com/CCSB-DFCI/ai-interactome-experimental-assessment/{audit.COMMIT}/{name}"})
        receipt = folder / "receipt.json"
        receipt.write_text(json.dumps({"commit": audit.COMMIT, "files": entries}))
        return receipt

    def test_pin_and_byte_fingerprints_are_checked_without_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            receipt = self.sources(folder)
            blobs, hashes = audit.verified_author_files(folder, receipt)
            self.assertEqual(set(blobs), {audit.PANEL, audit.ORF_MAP, audit.GENE_MAP})
            self.assertEqual(set(hashes), set(blobs))
            (folder / audit.PANEL).write_bytes(b"changed bytes")
            with self.assertRaisesRegex(ValueError, "pinned retrieval receipt"):
                audit.verified_author_files(folder, receipt)

    def test_wrong_commit_url_blob_or_duplicate_receipt_is_rejected(self):
        for fault in ("commit", "url", "blob", "duplicate"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                path = self.sources(folder)
                receipt = json.loads(path.read_text())
                if fault == "commit":
                    receipt["commit"] = "unreviewed-release"
                elif fault == "url":
                    receipt["files"][0]["url"] = "https://example.org/unpinned.tsv"
                elif fault == "blob":
                    receipt["files"][0]["git_blob_sha1"] = "0" * 40
                else:
                    receipt["files"].append(dict(receipt["files"][0]))
                path.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    audit.verified_author_files(folder, path)


class AggregateAuditTests(unittest.TestCase):
    def run_synthetic(self, *, incorrect_count=False, retained_without_raw=False, registry_mismatch=False,
                      incomplete=False, missing_controls=False, unresolved_request=False,
                      corrupt_endpoint_counts=False, unexpected_subject=False, wrong_exclusion_count=False):
        author = {
            audit.PANEL: panel(panel_row(), panel_row(P2, P1),
                panel_row(P3, P4, source1="other", source2="other"),
                panel_row(P1, P3, source2="different"),
                panel_row(P2, P4, published="False"),
                panel_row(P5, P6, published="NULL")),
            audit.ORF_MAP: b"uniprot_ac\torf_id\n" + b"".join(f"{p}\t{p[-1]}\n".encode() for p in (P1, P2, P3, P4, P5, P6)),
            audit.GENE_MAP: f"uniprot_ac\tensembl_gene_id\n{P1}\t{A}\n{P1}\t{C}\n{P2}\t{B}\n{P3}\t{C}\n{P4}\t{D}\n".encode(),
        }
        if missing_controls:
            author[audit.PANEL] += panel_row(a="None", ad="93", source1="control", source2="control") + b"\n"
            author[audit.PANEL] += panel_row(a="None", ad="94", source1="control", source2="control") + b"\n"
        ppi = {"target": {"uniprot": P1}, "type": "STRING, BioPlex", "props": []}
        second_ppi = {"target": {"uniprot": P4}, "type": "STRING", "props": []}
        chunk = {"target_resolution": [{"requested_uniprot": p, "status": "resolved"} for p in (P1, P2, P3, P4)],
                 "retrieval_coverage": {"targets": [{"uniprot": p, "family": "ppis", "status": "complete",
                                                       "available": 2 if p == P2 else 0,
                                                       "retrieved": 2 if p == P2 else 0,
                                                       "retained": 1 if p == P2 else 0,
                                                       "excluded_by_scope": 1 if p == P2 else 0} for p in (P1, P2, P3, P4)]},
                 "raw": [(P2, ppi, "raw/0"), (P2, second_ppi, "raw/1")],
                 "retained": [(P2, ppi, "retained/0")]}
        requested = [P1, P2, P3, P4]
        if incomplete:
            chunk["retrieval_coverage"]["targets"][0]["status"] = "partial"
        if corrupt_endpoint_counts:
            # Global totals remain correct, but the wrong endpoint appears covered.
            for row in chunk["retrieval_coverage"]["targets"][:2]:
                row["retrieved"] = row["available"] = 1
                row["excluded_by_scope"] = 1 - row["retained"]
        if unexpected_subject:
            chunk["raw"][1] = (P5, second_ppi, "raw/1")
        if wrong_exclusion_count:
            chunk["retrieval_coverage"]["targets"][1]["excluded_by_scope"] = 0
        if unresolved_request:
            requested.append(P5)
            chunk["target_resolution"].append({"requested_uniprot": P5, "status": "not_found"})
        if retained_without_raw:
            chunk["retained"][0] = (P1, second_ppi, "retained/0")
        plan = {"content_sha256": "plan", "chunk_size": len(requested)}
        saved = {"content_sha256": "saved", "families": {"ppis": {"retrieved": 3 if incorrect_count else 2, "retained": 1}}}
        zip_reader = MagicMock()
        zip_reader.__enter__.return_value.read.side_effect = {
            audit.TRAIN_MEMBER: f"source,target\n{A},{B}\n".encode(),
            audit.PANEL_MEMBER: f"source\ttarget\tfreq\tscore_assay1\tscore_assay2\tscore_assay3\n{C}\t{D}\t".encode() + b"\xff\t\xff\t\xff\t\xff\n",
        }.__getitem__
        args = SimpleNamespace(sources=Path("invented-source"), receipts=Path("invented-receipt"),
                               archive=Path("invented-archive"), registry=Path("invented-registry"), pharos=Path("invented-pharos"))
        replacements = {
            "verified_author_files": (author, {k: "synthetic" for k in author}),
            "sha": audit.ARCHIVE_SHA256,
            "load_registry": ({"registry_sha256": "registry"}, object()),
            "map_identifiers": [{"ensembl_gene_id": g, "confirmed_reviewed_products": [f"UniProtKB:{p}" for p in ps]}
                                for g, ps in ((A, [P1, P3]), (B, [P2]), (C, [P3]), (D, [P4]))],
            "verified_header": (plan, {"db_version": "synthetic"}, saved,
                                {"registry_sha256": "wrong" if registry_mismatch else "registry"},
                                requested, ["chunk"]),
            "verified_chunk": chunk,
            "utcnow": "fixed-test-time",
        }
        with ExitStack() as stack:
            for name, value in replacements.items():
                stack.enter_context(patch.object(audit, name, return_value=value))
            stack.enter_context(patch.object(audit.zipfile, "ZipFile", return_value=zip_reader))
            stack.enter_context(patch.object(audit, "source_rows", side_effect=lambda *unused: iter(chunk["raw"])))
            stack.enter_context(patch.object(audit, "retained_rows", side_effect=lambda *unused: iter(chunk["retained"])))
            return audit.audit(args)

    def test_nomination_group_uses_both_source_columns_and_flag_without_outcome_eligibility(self):
        report, rows, pairs = self.run_synthetic()
        all_rows = report["groups"]["entire_author_export"]
        selected = report["groups"]["published_af_rf_nominations"]
        self.assertEqual(all_rows["source_rows"], 6)
        self.assertEqual(selected["source_rows"], 2)
        self.assertEqual(selected["distinct_unordered_product_pairs"], 1)
        self.assertEqual(selected["duplicate_or_reciprocal_mapped_rows"], 1)
        self.assertEqual(selected["author_crosswalk_ambiguous_endpoint_pairs"], 1)
        self.assertEqual(selected["huri_either_mapping_match_pairs"], 1)
        self.assertFalse(report["outcome_fields_decoded"])
        self.assertFalse(report["assay_eligibility_determined"])
        self.assertFalse(report["performance_evaluated"])
        self.assertFalse(report["independence_established"])
        self.assertEqual(report["author_orf_crosswalk_mismatch_rows"], [])
        self.assertEqual(len(rows), 6)
        self.assertEqual(len(pairs), 5)

    def test_reverse_raw_match_and_retained_view_are_recorded_separately(self):
        report, _, pairs = self.run_synthetic()
        exposed = next(p for p in pairs if p["products"] == [P1, P2])
        self.assertEqual(exposed["pharos_status"], "present_in_saved_raw_ppi")
        self.assertTrue(exposed["pharos_retained_match"])
        self.assertEqual(exposed["pharos_matches"]["raw"][0]["subject"], P2)
        self.assertEqual(exposed["pharos_matches"]["raw"][0]["providers"], ["BioPlex", "STRING"])
        raw_only = next(p for p in pairs if p["products"] == [P2, P4])
        self.assertFalse(raw_only["pharos_retained_match"])
        self.assertEqual(raw_only["pharos_status"], "present_in_saved_raw_ppi")
        self.assertEqual(report["pharos_raw_records_scanned"], 2)
        self.assertEqual(report["pharos_retained_records_scanned"], 1)

    def test_manifest_count_registry_binding_and_retained_lineage_fail_closed(self):
        for kwargs in ({"incorrect_count": True}, {"retained_without_raw": True}, {"registry_mismatch": True}, {"incomplete": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_synthetic(**kwargs)

    def test_missing_controls_are_not_collapsed_into_a_false_shared_pair(self):
        report, rows, pairs = self.run_synthetic(missing_controls=True)
        entire = report["groups"]["entire_author_export"]
        self.assertEqual(entire["source_rows"], 8)
        self.assertEqual(entire["rows_missing_product_identity"], 2)
        self.assertEqual(entire["duplicate_or_reciprocal_mapped_rows"], 1)
        self.assertEqual(len(rows), 8)
        self.assertEqual(len(pairs), 5)
        self.assertTrue(all(all(p["products"]) for p in pairs))

    def test_requested_and_resolved_coverage_counts_are_separate(self):
        _, _, pairs = self.run_synthetic(unresolved_request=True)
        p = next(row for row in pairs if row["products"] == [P5, P6])
        self.assertEqual(p["queried_endpoints"], 0)
        self.assertEqual(p["requested_endpoints"], 1)
        self.assertEqual(p["pharos_status"], "unassessed_requested_endpoint_unresolved")

    def test_per_target_counts_and_subjects_cannot_hide_behind_matching_global_totals(self):
        for kwargs in ({"corrupt_endpoint_counts": True}, {"unexpected_subject": True}, {"wrong_exclusion_count": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_synthetic(**kwargs)


if __name__ == "__main__":
    unittest.main()
