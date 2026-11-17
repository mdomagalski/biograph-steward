"""Synthetic-only safety and critical-field alignment checks; no reference access."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from scripts import inspect_intact_xml_development as inspect
from scripts import validate_intact_xml_provenance as validate


def term(mi, name=None):
    return {"mi_id": mi, "name": name or mi, "full_name": None}


def xref(db, accession, qualifier="MI:0356", secondary=False):
    return {"database": term(None, db), "id": accession,
            "qualifier": term(qualifier), "secondary": secondary}


def sample():
    """Independent invented source observations for alignment tests."""
    fields = {
        "evidence_ids": [xref("intact", "EBI-SYNTH")],
        "publication_ids": [xref("pubmed", "40075158")],
        "detection_methods": [term("MI:0018")],
        "interaction_types": [term("MI:0914")],
        "host_taxa": [{"taxid": 4932, "scientific_name": "yeast", "common_name": None}],
    }
    participants = []
    for side, accession, role in [("a", "P12345-2", "MI:0496"), ("b", "P12346", "MI:0498")]:
        fields.update({"primary_ids_" + side: [xref("uniprotkb", accession)],
                       "taxa_" + side: [{"taxid": 9606}],
                       "interactor_types_" + side: [term("MI:0326")],
                       "biological_roles_" + side: [term("MI:0499")],
                       "experimental_roles_" + side: [term(role)]})
        participants.append({"source_index": len(participants) + 1, "xml_id": len(participants) + 30,
            "interactor": {"identifiers": [xref("uniprotkb", accession)], "xrefs": [],
                           "type": term("MI:0326"), "organism": {"taxid": 9606}},
            "biological_role": term("MI:0499"), "experimental_roles": [{"term": term(role), "experiments": []}]})
    original = [{"ledger": {"kind": "evidence", "publication_id": "pubmed:40075158",
                            "artifact_sha256": "synthetic", "source_line": 2, "eligible": True},
                 "reader_record": {"source_fields": {name: {"values": values} for name, values in fields.items()},
                                   "interaction": {"negative": False}}}]
    rows = [{"record_kind": "evidence", "evidence_sequence": 1,
             "evidence": {"xml_id": 21, "identifiers": [xref("intact", "EBI-SYNTH")], "xrefs": [],
                          "imex_id": None, "negative": False, "interaction_types": [term("MI:0914")],
                          "experiments": [{"xml_id": 1, "publication": {"pubmed_id": "40075158"},
                              "detection_method": term("MI:0018"), "host_organisms": [{"taxid": 4932, "scientific_name": "yeast", "common_name": None}]}],
                          "participants": participants}}]
    return original, rows


class ControlsTests(unittest.TestCase):
    def test_inventory_is_original_six_plus_additive_three(self):
        value = validate.inventory()
        self.assertEqual(len(value["cases"]), 9)
        self.assertEqual(validate.sha(validate.CONTROLS), validate.EXPECTED_INVENTORY_SHA)
        self.assertEqual(validate.sha(validate.AMENDMENT), validate.EXPECTED_AMENDMENT_SHA)

    def test_unresolved_reference_is_quarantined_without_independence_inference(self):
        gate = validate.assess_xml_summary({"status": "completed_with_diagnostics", "error": None,
            "diagnostics": [{"callback": "onUnresolvedReference"}]}, 0)
        self.assertTrue(gate["quarantined"])
        self.assertEqual(gate["study_independence"], "not_determined")
        self.assertEqual(gate["study_reuse"], "not_determined")

    def test_transport_requires_terminal_count_and_no_unknown_records(self):
        fmt = "biograph-steward.intact-xml-evidence.v1"
        record = {"format": fmt, "record_kind": "evidence", "evidence_sequence": 1}
        summary = {"format": fmt, "record_kind": "file_summary", "evidence_count": 1}
        raw = lambda rows: "\n".join(json.dumps(row) for row in rows).encode()
        self.assertEqual(len(validate.parse_transport(raw([record, summary]))[0]), 1)
        for invalid in ([summary, record], [record, {**summary, "evidence_count": 0}], [record, {"format": fmt, "record_kind": "unknown"}, summary]):
            with self.assertRaises(ValueError):
                validate.parse_transport(raw(invalid))

    def test_generic_see_also_does_not_become_evidence_identity(self):
        evidence = {"identifiers": [xref("intact", "EBI-SYNTH")],
                    "xrefs": [xref("intact", "EBI-NOT-IDENTITY", "MI:0361", True),
                              xref("imex", "IM-SYNTH", "MI:0662", True)]}
        self.assertEqual(inspect.xml_evidence_ids(evidence), {("intact", "EBI-SYNTH"), ("imex", "IM-SYNTH")})

    def test_literal_identity_scope_excludes_primary_reference_and_secondary_ac(self):
        evidence = {"identifiers": [], "xrefs": [xref("intact", "EBI-PRIMARY-REF", "MI:0358"),
                    xref("intact", "EBI-SECONDARY-REF", "MI:0360", True)]}
        self.assertEqual(inspect.xml_evidence_ids(evidence), set())

    def test_development_version_gate_rejects_untested_version(self):
        summary = {"status": "completed", "error": None, "diagnostics": [], "xml_version": "v2_5_4"}
        record = {"xml_version": "v2_5_4"}
        self.assertFalse(inspect.assess_development_xml(summary, [record], 0)["quarantined"])
        self.assertTrue(inspect.assess_development_xml({**summary, "xml_version": "v3_0_0"}, [record], 0)["quarantined"])
        self.assertTrue(inspect.assess_development_xml(summary, [{"xml_version": "v2_5_3"}], 0)["quarantined"])
        self.assertTrue(inspect.assess_development_xml({**summary, "xml_version": None}, [], 0)["quarantined"])

    def test_source_guard_detects_mutation_and_symlink_without_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.xml"; path.write_bytes(b"opaque-one")
            receipt = {"bytes": path.stat().st_size, "sha256": validate.sha(path)}
            inspect.verify_source_bytes(path, receipt)
            path.write_bytes(b"opaque-two")
            with self.assertRaises(ValueError): inspect.verify_source_bytes(path, receipt)
            link = Path(temp) / "link.xml"; link.symlink_to(path)
            with self.assertRaises(ValueError): inspect.verify_source_bytes(link, {"bytes": path.stat().st_size, "sha256": validate.sha(path)})

    def test_external_entity_generic_dns_failure_cannot_pass(self):
        case = next(c for c in validate.inventory()["cases"] if c["id"] == "external_entity")
        raw = (validate.CONTROLS.parent / case["file"]).read_bytes()
        summary = {"format": "biograph-steward.intact-xml-evidence.v1", "record_kind": "file_summary", "status": "failed",
                   "evidence_count": 0, "input_sha256": hashlib.sha256(raw).hexdigest(), "input_bytes": len(raw),
                   "diagnostics": [], "error": {"class": "UnknownHostException", "message": "generic failure"},
                   "security": {"support_external_entities": False, "support_dtd": False, "external_resolver": "deny",
                                "schema_validation_invoked": False, "resolver_attempt_count": 1}}
        checks = validate.check_case(case, json.dumps(summary).encode(), 2, raw)
        self.assertFalse(all(c["passed"] for c in checks))
        names = {c["name"] for c in checks if not c["passed"]}
        self.assertIn("resolver_not_invoked", names)
        self.assertIn("entity_rejected_by_parser", names)

    def test_timeout_keeps_partial_official_streams_and_failed_report(self):
        bindings = {"dependency_jars": [], "java": {"executable": "/synthetic/java"}}
        with tempfile.TemporaryDirectory() as temp, patch.object(validate, "runtime_bindings", return_value=bindings), patch.object(validate.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 60, output=b"partial-jsonl", stderr=b"retained-error")):
            output = Path(temp) / "controls"
            report = validate.run_controls(Path(temp) / "classes", Path(temp) / "classpath", output)
            self.assertEqual(report["status"], "failed")
            self.assertEqual((output / "cases/typed_positive.jsonl").read_bytes(), b"partial-jsonl")
            self.assertEqual((output / "cases/typed_positive.stderr").read_bytes(), b"retained-error")
            self.assertTrue((output / "report.json").is_file())
            with self.assertRaises(FileExistsError):
                validate.run_controls(Path(temp) / "classes", Path(temp) / "classpath", output)


class PreaccessTests(unittest.TestCase):
    def receipt(self):
        return {"phase": "pre_access", "contract_sha256": inspect.CONTRACT_SHA,
                "allowlist": [{"publication_id": p, "url": inspect.DIRECTORY + p + ".xml"} for p in inspect.DEVELOPMENT],
                "maximum_source_bytes": inspect.MAX_BYTES, "selected_xml_bodies_accessed": False,
                "reserved_bodies_accessed": False, "code_bindings": {"synthetic-code": "bound"},
                "reference_bindings": {"consumed-only": "bound"}}

    def test_explicit_wrong_preaccess_sha_stops_before_contract_or_source_reads(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inspect, "contract") as read_contract:
            path = Path(temp) / "pre_access.json"; path.write_text("{}")
            with self.assertRaises(ValueError): inspect.verify_preaccess(path, "wrong")
            read_contract.assert_not_called()

    def test_altered_allowlist_and_code_binding_are_rejected_before_controls(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inspect, "contract", return_value={"release": {"allowlist": self.receipt()["allowlist"]}}), patch.object(inspect, "code_bindings", return_value={"synthetic-code": "bound"}), patch.object(inspect, "reference_bindings", return_value={"consumed-only": "bound"}), patch.object(inspect, "verify_controls") as verify:
            for altered in ("allowlist", "code_bindings"):
                receipt = self.receipt()
                receipt[altered] = [] if altered == "allowlist" else {"synthetic-code": "changed"}
                receipt["content_sha256"] = inspect.digest(receipt)
                path = Path(temp) / (altered + ".json"); path.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError): inspect.verify_preaccess(path, inspect.sha(path))
            verify.assert_not_called()


class ParityTests(unittest.TestCase):
    def test_reversed_xml_order_preserves_roles_by_identity(self):
        original, rows = sample()
        rows[0]["evidence"]["participants"].reverse()
        comparison = inspect.compare_study("40075158", original, rows)
        self.assertTrue(comparison["exact_evidence_id_bijection"])
        self.assertEqual(comparison["critical_field_counts"], {"equal": 17})
        self.assertEqual(comparison["rows"][0]["participant_alignment"][0]["xml_source_index"], 1)

    def test_extra_or_duplicate_xml_evidence_breaks_bijection(self):
        original, rows = sample()
        extra = deepcopy(rows[0]); extra["evidence_sequence"] = 2
        for same in (True, False):
            if not same:
                extra["evidence"]["identifiers"] = [xref("intact", "EBI-EXTRA")]
            comparison = inspect.compare_study("40075158", original, rows + [extra])
            self.assertFalse(comparison["exact_evidence_id_bijection"])

    def test_multiple_identity_accessions_in_same_database_remain_unresolved(self):
        original, rows = sample()
        interactor = rows[0]["evidence"]["participants"][0]["interactor"]
        interactor["identifiers"] = [xref("uniprotkb", "P99999"), xref("uniprotkb", "P12345-2", secondary=True)]
        result = inspect.compare_study("40075158", original, rows)
        self.assertIn("unresolved", result["critical_field_counts"])
        self.assertEqual(result["rows"][0]["checks"][7]["status"], "unresolved")

    def test_homomer_alignment_remains_unresolved(self):
        original, rows = sample()
        original[0]["reader_record"]["source_fields"]["primary_ids_b"] = deepcopy(original[0]["reader_record"]["source_fields"]["primary_ids_a"])
        result = inspect.compare_study("40075158", original, rows)
        unresolved = [c for c in result["rows"][0]["checks"] if c["status"] == "unresolved"]
        self.assertEqual(len(unresolved), 2)

    def test_wrong_role_is_difference_without_repair(self):
        original, rows = sample()
        rows[0]["evidence"]["participants"][0]["experimental_roles"] = [{"term": term("MI:0498")}]
        result = inspect.compare_study("40075158", original, rows)
        changes = [c["field"] for c in result["rows"][0]["checks"] if c["status"] == "different"]
        self.assertEqual(changes, ["participant_A.experimental_role_ids"])


class RetrievalTests(unittest.TestCase):
    def test_reserved_or_alternate_url_rejected_before_network(self):
        opener = unittest.mock.Mock()
        with tempfile.TemporaryDirectory() as temp:
            for pmid, url in [("39833857", inspect.DIRECTORY + "39833857.xml"),
                              ("40075158", inspect.DIRECTORY + "40075158.xml?alternate=1")]:
                with self.assertRaises(ValueError):
                    inspect.fetch_exact(pmid, url, temp, opener)
        opener.open.assert_not_called()

    def test_bounded_exact_request_saves_opaque_bytes_and_receipts(self):
        url = inspect.DIRECTORY + "40075158.xml"
        class Response(io.BytesIO):
            status = 200
            headers = {"Content-Length": "6"}
            def geturl(self): return url
        opener = unittest.mock.Mock(); opener.open.return_value = Response(b"opaque")
        with tempfile.TemporaryDirectory() as temp:
            receipt = inspect.fetch_exact("40075158", url, temp, opener)
            self.assertEqual((Path(temp) / "40075158.xml").read_bytes(), b"opaque")
            self.assertEqual(receipt["sha256"], hashlib.sha256(b"opaque").hexdigest())
            self.assertTrue((Path(temp) / "40075158_retrieval_started.json").is_file())
            self.assertEqual(json.loads((Path(temp) / "40075158_http_receipt.json").read_text())["outcome"], "opaque_bytes_saved_not_decoded")

    def test_oversize_content_length_fails_before_body_read_and_stays_recorded(self):
        url = inspect.DIRECTORY + "40075158.xml"
        class Response(io.BytesIO):
            status = 200
            headers = {"Content-Length": str(inspect.MAX_BYTES + 1)}
            def geturl(self): return url
            def read(self, *args): raise AssertionError("Oversized declared body must not be read")
        opener = unittest.mock.Mock(); opener.open.return_value = Response()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): inspect.fetch_exact("40075158", url, temp, opener)
            self.assertEqual(json.loads((Path(temp) / "40075158_http_receipt.json").read_text())["outcome"], "failed")
            self.assertFalse((Path(temp) / "40075158.xml").exists())

    def test_redirect_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect.NoRedirect().redirect_request(None, None, 302, "found", {}, "https://invalid.example/")


if __name__ == "__main__":
    unittest.main()
