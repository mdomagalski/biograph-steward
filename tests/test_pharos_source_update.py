"""Invented source controls; no ignored runs, network, model or GPU needed."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from io import StringIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import ENDPOINT, VERSION, PharosClient, digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward.pharos400_identity import SOURCE_URL, select_rows
from biograph_steward.pharos_source_update import (capture_pair_details, verify_pair_details,
    publish_source_update, verify_source_update)


def invented_identity_intake(folder, pair):
    folder.mkdir()
    raw = ("id,uniprot_id,uniprot_isoform,canonical_isoform_status,tdl\n"
           + "".join("TEST" + str(n) + "," + uid + ",,canonical,Tbio\n" for n, uid in enumerate(pair)))
    subset = select_rows(iter(StringIO(raw, newline="")), pair,
        source_sha256=hashlib.sha256(raw.encode()).hexdigest(), source_bytes=len(raw.encode()))
    contract = {"url": SOURCE_URL, "method": "GET", "source_version": "pharos400",
        "allowed_exact_identifiers": pair, "selection_fields": ["uniprot_id", "uniprot_isoform"],
        "network": {"retries": 0, "follow_redirects": False}}
    write_json(folder / "request_contract.json", contract)
    write_json(folder / "selected_rows.json", subset)
    receipt = {"status": "complete", "http_status": 200, "url": SOURCE_URL, "final_url": SOURCE_URL,
        "request_contract_sha256": sha(folder / "request_contract.json"),
        "selected_rows_sha256": sha(folder / "selected_rows.json"), "http_headers": {},
        "source_sha256": subset["source_sha256"], "source_bytes": subset["source_bytes"],
        "source_data_row_count": subset["source_data_row_count"], "csv_header": subset["csv_header"],
        "selected_ids": pair, "selected_row_count": len(pair)}
    write_json(folder / "http_receipt.json", receipt)


class SourceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace, self.overlap, self.details, self.identities, self.output = [self.root / n
            for n in ("workspace", "overlap", "details", "identities", "output")]
        self.workspace.mkdir(); self.overlap.mkdir()
        self.pair = ["P01111", "P01112"]
        snapshot = {"endpoint": ENDPOINT, "db_version": "pharos319",
                    "targets": [{"uniprot": uid, "tdl": "Tdark"} for uid in self.pair]}
        write_json(self.workspace / "snapshot.json", snapshot)
        self.original = {"pharos_endpoint": ENDPOINT, "pharos_database_version": "pharos319",
            "source_workspace": str(self.workspace), "summary": {"workspace_observations": 1},
            "records": [{"observation_id": "INVENTED", "products": ["UniProtKB:" + u for u in self.pair],
                "pair_representation": "represented_in_bounded_baseline",
                "shared_supporting_publication_identifiers": [], "baseline_record_identity_overlap": None,
                "baseline_experiment_identity_overlap": None, "additional_context_fields_available": ["assay_method"],
                "experiment_lineage": "unresolved"}]}
        self.original["content_sha256"] = digest(self.original)
        write_json(self.overlap / "report.json", self.original)
        # Existing overlap verification is tested separately; use its invented
        # checked return here to isolate this supplement's sources and replay.
        mock = patch("biograph_steward.pharos_source_update.verify_overlap", return_value=self.original)
        self.addCleanup(mock.stop); mock.start()

    def client(self, *, versions=("pharos319", "pharos319"), evidence=None, mismatch=False, graphql_error=False):
        versions = iter(versions)
        def transport(payload):
            if payload["query"] == VERSION:
                return {"data": {"dbVersion": next(versions)}}
            if graphql_error:
                return {"data": {"forward": []}, "errors": [{"message": "partial source failure"}]}
            rows = {}
            for name, pair in (("forward", self.pair), ("reverse", self.pair[::-1])):
                rows[name] = [{"uniprot": "P04637" if mismatch else pair[0], "otherUniprot": pair[1],
                    "evidence": evidence, "interaction_type": None, "p_wrong": 0, "ppitypes": "STRINGDB"}]
            return {"data": rows}
        return PharosClient(cache_dir=None, retries=0, transport=transport)

    def capture(self, **kwargs):
        return capture_pair_details(self.overlap, self.details, self.client(**kwargs))

    def publish(self, **kwargs):
        self.capture(**kwargs)
        invented_identity_intake(self.identities, self.pair)
        return publish_source_update(self.overlap, self.details, self.identities, self.output)

    def test_capture_preserves_explicit_nulls_zeros_and_both_directions(self):
        value = self.capture()
        self.assertEqual(value["db_version_before"], "pharos319")
        self.assertEqual(len(value["requests"]), 3)
        rows = value["requests"][1]["response"]["data"]
        self.assertIsNone(rows["forward"][0]["evidence"])
        self.assertEqual(rows["reverse"][0]["p_wrong"], 0)
        self.assertTrue(all(r["loaded_from_cache"] is False for r in value["requests"]))
        self.assertEqual(verify_pair_details(self.details, self.overlap), value)

    def test_version_drift_preserves_failure_without_valid_supplement(self):
        with self.assertRaisesRegex(ValueError, "version changed"):
            self.capture(versions=("pharos319", "pharos400"))
        receipt = json.loads((self.details / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(len(receipt["requests"]), 3)
        with self.assertRaises(ValueError):
            verify_pair_details(self.details, self.overlap)

    def test_partial_graphql_error_never_accepted(self):
        with self.assertRaisesRegex(RuntimeError, "partial data rejected"):
            self.capture(graphql_error=True)
        self.assertEqual(json.loads((self.details / "receipt.json").read_text())["status"], "failed")

    def test_mismatched_returned_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different protein"):
            self.capture(mismatch=True)
        self.assertEqual(json.loads((self.details / "receipt.json").read_text())["status"], "failed")

    def test_resealed_source_with_wrong_pair_is_rejected(self):
        self.capture()
        path = self.details / "receipt.json"
        value = json.loads(path.read_text())
        record = value["requests"][1]
        record["response"]["data"]["forward"][0]["otherUniprot"] = "P04637"
        record["response_sha256"] = digest(record["response"])
        value["content_sha256"] = digest({k: v for k, v in value.items() if k != "content_sha256"})
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, "different protein"):
            verify_pair_details(self.details, self.overlap)

    def test_publish_replays_and_preserves_sources_and_original_classifications(self):
        before = (self.workspace / "snapshot.json").read_bytes()
        overlap_before = (self.overlap / "report.json").read_bytes()
        value = self.publish()
        self.assertEqual(value["summary"]["mapping_rows"], 2)
        self.assertEqual(value["summary"]["pair_details_null_evidence_rows"], 2)
        self.assertEqual(value["records"], self.original["records"])
        self.assertIsNone(value["summary"]["independent_evidence_count"])
        self.assertEqual(value["summary"]["graph_relationships_updated"], 0)
        self.assertEqual(value["baseline_target_annotations"][0]["tdl"], "Tdark")
        self.assertEqual(value["identity_projection"]["endpoints"][0]["source_row"]["row"]["tdl"], "Tbio")
        self.assertEqual(verify_source_update(self.output), value)
        self.assertEqual(before, (self.workspace / "snapshot.json").read_bytes())
        self.assertEqual(overlap_before, (self.overlap / "report.json").read_bytes())

    def test_nonempty_untyped_evidence_never_becomes_independent_support(self):
        value = self.publish(evidence="INVENTED:looks-like-an-identifier")
        self.assertEqual(value["summary"]["pair_details_null_evidence_rows"], 0)
        self.assertIsNone(value["pair_details"]["baseline_record_identity_overlap"])
        self.assertIsNone(value["pair_details"]["independent_evidence_count"])
        self.assertEqual(value["pair_details"]["experiment_lineage"], "unresolved")

    def test_changed_input_and_resealed_wrong_classification_rejected(self):
        self.publish()
        path = self.output / "report.json"
        value = json.loads(path.read_text())
        value["summary"]["experiment_lineage"] = "independent"
        value["content_sha256"] = digest({k: v for k, v in value.items() if k != "content_sha256"})
        write_json(path, value)
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["report.json"] = sha(path)
        manifest["content_sha256"] = digest({k: v for k, v in manifest.items() if k != "content_sha256"})
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "do not replay"):
            verify_source_update(self.output)

    def test_output_cannot_be_nested_in_source_workspace(self):
        self.capture(); invented_identity_intake(self.identities, self.pair)
        with self.assertRaisesRegex(ValueError, "outside input"):
            publish_source_update(self.overlap, self.details, self.identities, self.workspace / "bad")

    def test_symlinked_input_is_rejected(self):
        self.publish()
        (self.identities / "extra").symlink_to(self.identities / "selected_rows.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            verify_source_update(self.output)

    def test_cli_offline_roundtrip_does_not_construct_live_client(self):
        from biograph_steward.__main__ import main
        self.capture(); invented_identity_intake(self.identities, self.pair)
        output, error = StringIO(), StringIO()
        with patch("biograph_steward.__main__.PharosClient", side_effect=AssertionError("No live client")):
            with redirect_stdout(output), redirect_stderr(error):
                code = main(["pharos-source-update", "--overlap", str(self.overlap), "--details", str(self.details),
                    "--identities", str(self.identities), "--out", str(self.output)])
            self.assertEqual(code, 0, error.getvalue())
            with redirect_stdout(StringIO()), redirect_stderr(error):
                code = main(["pharos-source-update-verify", "--report", str(self.output)])
            self.assertEqual(code, 0, error.getvalue())


if __name__ == "__main__":
    unittest.main()
