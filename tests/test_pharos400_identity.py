"""Invented CSV rows test source-identity boundaries, not biological accuracy."""
from copy import deepcopy
import csv
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from biograph_steward.evidence_mapping import build_mapping_set
from biograph_steward.pharos400_identity import (
    SOURCE_URL, SOURCE_VERSION, capture_intake, select_rows, verify_intake, build_endpoints,
)


HEADER = ["id", "uniprot_id", "tdl", "canonical_isoform_status", "uniprot_isoform",
          "xref", "name", "protein_group_anchor"]


def row(uid="P00001", **changes):
    value = {"id": "INTERNAL-1", "uniprot_id": uid, "tdl": "Tbio",
             "canonical_isoform_status": "canonical", "uniprot_isoform": "",
             "xref": "UniProtKB:P00002", "name": "Invented protein",
             "protein_group_anchor": "True"}
    value.update(changes)
    return value


def csv_bytes(rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HEADER, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def selected(rows, requested=None):
    raw = csv_bytes(rows)
    return select_rows(StringIO(raw.decode(), newline=""), requested or ["P00001"],
                       source_sha256=hashlib.sha256(raw).hexdigest(), source_bytes=len(raw))


class FakeResponse(BytesIO):
    def __init__(self, body, *, status=200, url=SOURCE_URL, headers=None):
        super().__init__(body)
        self.status, self.url = status, url
        self.headers = headers if headers is not None else {"Content-Length": str(len(body))}

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, output, response=None, error=None):
        self.output, self.response, self.error, self.calls = output, response, error, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if not (self.output / "request_contract.json").is_file():
            raise AssertionError("Network attempted before immutable request contract.")
        if self.error is not None:
            raise self.error
        return self.response


def write_intake(path, subset):
    def write(name, value):
        raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        (path / name).write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()
    contract = {"url": SOURCE_URL, "method": "GET", "source_version": SOURCE_VERSION,
                "allowed_exact_identifiers": subset["requested_identifiers"],
                "selection_fields": ["uniprot_id", "uniprot_isoform"],
                "network": {"retries": 0, "follow_redirects": False}}
    contract_sha = write("request_contract.json", contract)
    selected_sha = write("selected_rows.json", subset)
    receipt = {"status": "complete", "http_status": 200, "url": SOURCE_URL,
               "final_url": SOURCE_URL, "request_contract_sha256": contract_sha,
               "selected_rows_sha256": selected_sha,
               "source_sha256": subset["source_sha256"], "source_bytes": subset["source_bytes"],
               "source_data_row_count": subset["source_data_row_count"],
               "csv_header": subset["csv_header"], "selected_row_count": len(subset["selected_rows"]),
               "selected_ids": subset["requested_identifiers"],
               "http_headers": {"Content-Length": str(subset["source_bytes"]),
                                "ETag": '"invented-only"', "Last-Modified": "invented"}}
    write("http_receipt.json", receipt)


class Pharos400IdentityTests(unittest.TestCase):
    def test_exact_selection_preserves_all_columns_raw_bytes_and_absolute_locators(self):
        rows = [row("P00002", id="OTHER"), row(name="Invented, quoted\nprotein"),
                row("P00001-2", id="ISOFORM", canonical_isoform_status="isoform")]
        subset = selected(rows)
        self.assertEqual(subset["source_data_row_count"], 3)
        self.assertEqual(len(subset["selected_rows"]), 1)
        chosen = subset["selected_rows"][0]
        self.assertEqual(chosen["row"], rows[1])
        self.assertEqual((chosen["logical_data_row"], chosen["source_csv_row"]), (2, 3))
        self.assertEqual((chosen["physical_line_start"], chosen["physical_line_end"]), (3, 4))
        self.assertIn('"Invented, quoted\nprotein"', chosen["original_csv_record"])
        self.assertTrue(chosen["original_csv_record"].endswith("\r\n"))

    def test_xrefs_symbols_and_ifx_ids_never_select_a_row(self):
        subset = selected([row("P00002", id="P00001", xref="UniProtKB:P00001", name="P00001")])
        result = build_endpoints(subset)
        self.assertEqual(result["endpoints"], [])
        self.assertEqual(result["summary"]["requested_ids_without_selected_rows"], ["P00001"])

    def test_unique_canonical_row_maps_only_its_exact_public_identity(self):
        subset = selected([row()])
        original = deepcopy(subset)
        endpoint = build_endpoints(subset)["endpoints"][0]
        self.assertEqual(subset, original)
        self.assertEqual(endpoint["primary_ids"], ["UniProtKB:P00001"])
        self.assertEqual(endpoint["identity_role"], "source_primary")
        self.assertFalse(endpoint["source_internal_id_is_public_protein_identifier"])
        self.assertEqual(endpoint["unavailable_grouping_columns"],
                         ["canonical_isoform_status_source", "is_canonical"])
        baseline = {**endpoint, "endpoint_id": "baseline:1", "role": "baseline",
                    "resource_version": "pharos319"}
        maps = build_mapping_set([baseline, endpoint], mapping_set_id="urn:test:mappings",
                                 mapping_set_version="INVENTED-1", mapping_date="2026-10-27",
                                 license_url="https://opensource.org/license/mit/")
        self.assertEqual(len(maps["mappings"]), 1)
        self.assertEqual(maps["mappings"][0]["object_source_version"], "pharos400")

    def test_repeated_base_is_not_exact_product_identity_even_on_canonical_anchor(self):
        subset = selected([row(), row(id="OTHER-PRODUCT", canonical_isoform_status="alternate_product")])
        result = build_endpoints(subset)
        self.assertEqual(len(result["endpoints"]), 2)
        self.assertEqual(result["summary"]["source_primary_endpoints"], 0)
        self.assertTrue(all(not e["primary_ids"] for e in result["endpoints"]))
        self.assertIn("shared_base_accession_does_not_identify_product", result["unresolved"][0]["reasons"])

    def test_explicit_isoform_keeps_suffix_and_never_uses_bare_base(self):
        subset = selected([row(canonical_isoform_status="isoform", uniprot_isoform="P00001-2")],
                          ["P00001-2"])
        endpoint = build_endpoints(subset)["endpoints"][0]
        self.assertEqual(endpoint["primary_ids"], ["UniProtKB:P00001-2"])
        self.assertNotEqual(endpoint["primary_ids"], ["UniProtKB:P00001"])
        self.assertEqual(subset["selected_rows"][0]["matched_identifiers"],
                         [{"field": "uniprot_isoform", "identifier": "P00001-2"}])

    def test_noncanonical_anchor_and_conflicting_or_missing_isoform_stay_unresolved(self):
        cases = [row(canonical_isoform_status="alternate_product"),
                 row(canonical_isoform_status="isoform"),
                 row(canonical_isoform_status="isoform", uniprot_isoform="P00002-2"),
                 row(uniprot_isoform="P00001-1"),
                 row(canonical_isoform_status="UNKNOWN")]
        for source in cases:
            with self.subTest(source=source):
                result = build_endpoints(selected([source]))
                self.assertEqual(result["summary"]["source_primary_endpoints"], 0)
                self.assertEqual(len(result["unresolved"]), 1)

    def test_duplicate_explicit_isoform_or_source_row_id_does_not_merge(self):
        for source_rows in [
            [row(canonical_isoform_status="isoform", uniprot_isoform="P00001-2"),
             row(id="PRODUCT2", canonical_isoform_status="isoform", uniprot_isoform="P00001-2")],
            [row(), row("P00002")],
        ]:
            with self.subTest(source_rows=source_rows):
                result = build_endpoints(selected(source_rows, ["P00001", "P00002"]))
                self.assertEqual(result["summary"]["source_primary_endpoints"], 0)
                self.assertEqual(len(result["endpoints"]), 2)

    def test_receipt_verification_is_offline_and_states_missing_full_source_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve()
            write_intake(path, selected([row()]))
            verified = verify_intake(path)
            self.assertEqual(verified["requested_accessions"], ["P00001"])
            self.assertTrue(verified["integrity"]["preserved_selected_records_verified"])
            self.assertFalse(verified["integrity"]["selection_completeness_replayed_offline"])
            self.assertEqual(build_endpoints(verified)["summary"]["selected_rows"], 1)
            raw = path / "selected_rows.json"
            raw.write_bytes(raw.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "bindings"):
                verify_intake(path)

    def test_resealed_parsed_row_or_out_of_scope_raw_record_is_rejected(self):
        for mutate in (lambda s: s["selected_rows"][0]["row"].update(tdl="Tclin"),
                       lambda s: s.update(requested_identifiers=["P00002"]),
                       lambda s: s["selected_rows"][0].update(physical_line_end=9)):
            with tempfile.TemporaryDirectory() as tmp:
                subset = selected([row()])
                mutate(subset)
                write_intake(Path(tmp).resolve(), subset)
                with self.assertRaises(ValueError):
                    verify_intake(Path(tmp).resolve())

    def test_redirect_incomplete_download_symlink_and_malformed_csv_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve()
            write_intake(path, selected([row()]))
            receipt_path = path / "http_receipt.json"
            original = json.loads(receipt_path.read_text())
            for changes in ({"final_url": "https://example.org/redirect"},
                            {"http_status": 206},
                            {"http_headers": {"Content-Length": "1"}}):
                receipt_path.write_text(json.dumps({**original, **changes}))
                with self.assertRaises(ValueError):
                    verify_intake(path)
            receipt_path.unlink()
            receipt_path.symlink_to(path / "selected_rows.json")
            with self.assertRaisesRegex(ValueError, "nonsymlink"):
                verify_intake(path)
        for text in ("id,uniprot_id\nA,P00001\n", ",".join(HEADER) + "\nA,P00001\n"):
            with self.assertRaises(ValueError):
                select_rows(StringIO(text), ["P00001"], source_sha256="a" * 64, source_bytes=len(text))

    def test_capture_one_fake_get_after_contract_preserves_only_selected_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve() / "intake"
            body = csv_bytes([row("P00002", id="OTHER"), row()])
            opener = FakeOpener(output, FakeResponse(body))
            result = capture_intake(["P00001"], output, opener=opener)
            self.assertEqual(len(opener.calls), 1)
            request, timeout = opener.calls[0]
            self.assertEqual((request.full_url, request.get_method(), timeout), (SOURCE_URL, "GET", 60))
            self.assertEqual(result["subset"]["source_sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(result["subset"]["source_data_row_count"], 2)
            self.assertEqual(len(result["subset"]["selected_rows"]), 1)
            self.assertEqual({p.name for p in output.iterdir()},
                             {"request_contract.json", "http_receipt.json", "selected_rows.json"})
            self.assertFalse(result["integrity"]["full_source_csv_retained"])

    def test_capture_failure_is_preserved_without_retry_or_output_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve() / "intake"
            opener = FakeOpener(output, error=urllib.error.URLError("invented offline DNS failure"))
            with self.assertRaisesRegex(ValueError, "immutable error receipt"):
                capture_intake(["P00001"], output, opener=opener)
            self.assertEqual(len(opener.calls), 1)
            saved = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertEqual(set(saved), {"request_contract.json", "http_receipt.json"})
            self.assertEqual(json.loads(saved["http_receipt.json"])["status"], "failed")
            with self.assertRaises(FileExistsError):
                capture_intake(["P00001"], output, opener=opener)
            self.assertEqual(len(opener.calls), 1)
            self.assertEqual(saved, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_capture_rejects_redirect_short_or_oversized_body_without_second_get(self):
        body = csv_bytes([row()])
        cases = [{"url": "https://example.org/redirect"}, {"status": 302},
                 {"headers": {"Content-Length": str(len(body) + 1)}},
                 {"headers": {"Content-Encoding": "gzip"}}]
        for changes in cases:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp).resolve() / "intake"
                opener = FakeOpener(output, FakeResponse(body, **changes))
                with self.assertRaises(ValueError):
                    capture_intake(["P00001"], output, opener=opener)
                self.assertEqual(len(opener.calls), 1)
                self.assertFalse((output / "selected_rows.json").exists())
        with tempfile.TemporaryDirectory() as tmp, patch("biograph_steward.pharos400_identity.MAX_BYTES", 16):
            output = Path(tmp).resolve() / "intake"
            opener = FakeOpener(output, FakeResponse(body))
            with self.assertRaises(ValueError):
                capture_intake(["P00001"], output, opener=opener)
            self.assertEqual(len(opener.calls), 1)

    def test_verify_and_capture_reject_ancestor_symlink_and_extra_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            real = root / "real"
            real.mkdir()
            intake = real / "intake"
            intake.mkdir()
            write_intake(intake, selected([row()]))
            alias = root / "alias"
            alias.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "ancestors"):
                verify_intake(alias / "intake")
            opener = FakeOpener(alias / "new", FakeResponse(csv_bytes([row()])))
            with self.assertRaisesRegex(ValueError, "ancestors"):
                capture_intake(["P00001"], alias / "new", opener=opener)
            self.assertEqual(opener.calls, [])
            (intake / ".hidden").write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "inventory"):
                verify_intake(intake)


if __name__ == "__main__":
    unittest.main()
