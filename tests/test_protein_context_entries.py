"""Invented native entry extension; no network, models or biological truth cases."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.protein_context import load_publication
from biograph_steward.protein_context_entries import extend_entries
from biograph_steward.protein_context_source import ENTRY_URL
from tests.protein_context_fixtures import write_packet


class EntryExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runs = Path(self.temp.name).resolve() / "runs"
        self.runs.mkdir()
        self.base = write_packet(self.runs / "parent")
        self.output = self.runs / "child"
        self.prefix = "entry_extension/" + self.base.pin
        self.calls = []
        self.responses = {
            "IPR111111": (200, {"metadata": {"accession": "IPR111111", "name": {"name": "INVENTED"},
                "is_llm": True, "is_reviewed_llm": False, "is_updated_llm": False, "go_terms": None}}),
            "IPR222222": (410, {"accession": "ipr222222", "source_database": "interpro",
                "deletion_date": "2022-08-25T00:00:00.000Z", "history": {"names": ["INVENTED"]}})}

    def transport(self, url, payload):
        self.calls.append((url, payload))
        self.assertIsNone(payload)
        entry = next(x for x in self.responses if ENTRY_URL.format(x) == url)
        status, body = self.responses[entry]
        return status, {"Set-Cookie": "not-retained"}, body if isinstance(body, bytes) else json.dumps(body).encode()

    def extend(self, entries=None, **kwargs):
        return extend_entries(self.base.folder, self.base.pin, entries or list(self.responses),
            self.output, runs_dir=self.runs, http_transport=self.transport, **kwargs)

    def test_preserves_all_parent_source_bytes_code_times_and_manifest_with_append_only_ledger(self):
        before = {name: (self.base.folder / name).read_bytes() for name in self.base.manifest["files"]}
        parent_manifest_bytes = (self.base.folder / "protein_context.json").read_bytes()
        with patch("biograph_steward.client.PharosClient.execute", side_effect=AssertionError("No repeated Pharos requests")):
            child = self.extend(register=True)
        self.assertEqual(len(self.calls), 2)
        for name, raw in before.items():
            self.assertEqual((self.output / name).read_bytes(), raw)
            self.assertEqual((self.base.folder / name).read_bytes(), raw)
        self.assertEqual((self.output / child["derived_from"]["manifest_file"]).read_bytes(), parent_manifest_bytes)
        self.assertEqual(child["derived_from"]["manifest_sha256"], self.base.pin)
        self.assertEqual(child["source_code"], self.base.manifest["source_code"])
        self.assertEqual(child["proteins"], self.base.manifest["proteins"])
        self.assertEqual(child["info_before_file"], self.base.manifest["info_before_file"])
        self.assertNotEqual(child["requests_file"], self.base.manifest["requests_file"])
        self.assertEqual(child["entry_extension"]["new_pharos_requests"], 0)
        self.assertEqual(child["entry_extension"]["new_mcp_requests"], 0)
        old = json.loads((self.base.folder / self.base.manifest["requests_file"]).read_text())["requests"]
        new = json.loads((self.output / child["requests_file"]).read_text())["requests"]
        self.assertEqual(new[:len(old)], old)
        self.assertEqual([r["http_status"] for r in new[len(old):]], [200, 410])
        self.assertNotIn("not-retained", json.dumps(new))
        replay = load_publication(self.output, sha(self.output / "protein_context.json"))
        self.assertEqual(set(replay["entry_metadata"]), set(self.responses))
        index = json.loads((self.runs / "protein_context_index.json").read_text())
        self.assertEqual(index["contexts"][0]["id"], "child")

    def test_wrong_required_pin_and_corrupted_parent_fail_before_new_calls_or_output(self):
        with self.assertRaises(ValueError):
            extend_entries(self.base.folder, "0" * 64, ["IPR111111"], self.output,
                           runs_dir=self.runs, http_transport=self.transport)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())
        path = self.base.folder / "interpro/matches_000.raw"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaises(ValueError):
            self.extend()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.calls, [])

    def test_http_failure_is_retained_without_manifest_or_registration(self):
        self.responses["IPR111111"] = 503, {"error": "INVENTED outage"}
        before_index = (self.runs / "protein_context_index.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "lookup failed"):
            self.extend(["IPR111111"], register=True)
        self.assertEqual((self.runs / "protein_context_index.json").read_bytes(), before_index)
        self.assertFalse((self.output / "protein_context.json").exists())
        self.assertIn(b"INVENTED outage", (self.output / (self.prefix + "/entries/IPR111111.raw")).read_bytes())
        self.assertTrue((self.output / "failure.json").exists())

    def test_transport_failure_is_unknown_with_attempt_metadata(self):
        def failed(url, payload):
            raise TimeoutError("INVENTED timeout")
        with self.assertRaises(TimeoutError):
            extend_entries(self.base.folder, self.base.pin, ["IPR111111"], self.output,
                           runs_dir=self.runs, http_transport=failed)
        ledger = json.loads((self.output / (self.prefix + "/source_requests.json")).read_text())["requests"]
        self.assertEqual(ledger[-1]["outcome"], "transport_failed")
        self.assertIsNone(ledger[-1]["http_status"])
        self.assertFalse(json.loads((self.output / "failure.json").read_text())["biological_negative_inferred"])

    def test_native_entry_identity_and_retirement_metadata_cannot_be_guessed(self):
        for index, (status, body) in enumerate(((200, {"metadata": {"accession": "IPR333333"}}),
                (410, {"accession": "ipr111111", "source_database": "interpro"}),
                (200, {"metadata": {"accession": "IPR111111", "is_llm": "true"}}))):
            self.output = self.runs / ("failure_" + str(index))
            self.responses["IPR111111"] = status, body
            with self.assertRaises(ValueError):
                self.extend(["IPR111111"])
            self.assertFalse((self.output / "protein_context.json").exists())
            self.assertEqual(json.loads((self.output / (self.prefix + "/entries/IPR111111.json")).read_text()), body)

    def test_reader_must_pass_before_registration(self):
        before_index = (self.runs / "protein_context_index.json").read_bytes()
        from biograph_steward import protein_context_entries as module
        original = module.load_publication
        def replay(folder, pin):
            if Path(folder) == self.output:
                raise ValueError("INVENTED child replay failure")
            return original(folder, pin)
        with patch.object(module, "load_publication", side_effect=replay):
            with self.assertRaisesRegex(ValueError, "child replay failure"):
                self.extend(register=True)
        self.assertFalse((self.output / "protein_context.json").exists())
        self.assertTrue((self.output / "unadmitted_protein_context.json").exists())
        self.assertEqual((self.runs / "protein_context_index.json").read_bytes(), before_index)

    def test_new_extension_preserves_nested_parent_manifest_and_previous_entry_bytes(self):
        first = self.extend(["IPR111111"])
        first_folder = self.output
        self.output = self.runs / "grandchild"
        child = extend_entries(first_folder, sha(first_folder / "protein_context.json"), ["IPR222222"],
            self.output, runs_dir=self.runs, http_transport=self.transport)
        self.assertEqual(set(child["entry_files"]), {"IPR111111", "IPR222222"})
        self.assertNotEqual(child["derived_from"]["manifest_file"], first["derived_from"]["manifest_file"])
        for name in first["files"]:
            self.assertEqual((self.output / name).read_bytes(), (first_folder / name).read_bytes())
        load_publication(self.output, sha(self.output / "protein_context.json"))

    def test_invalid_or_duplicate_entry_scope_is_rejected_without_calls(self):
        for entries in ([], ["IPR111111", "IPR111111"], ["../IPR111111"], ["ipr111111"]):
            with self.assertRaises(ValueError):
                extend_entries(self.base.folder, self.base.pin, entries, self.output,
                               runs_dir=self.runs, http_transport=self.transport)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.calls, [])

    def test_explicit_refresh_namespaces_new_entry_and_preserves_old_entry_bytes(self):
        first = self.extend(["IPR111111"])
        first_folder = self.output
        first_entry = first["entry_files"]["IPR111111"]
        previous = (first_folder / first_entry).read_bytes()
        self.responses["IPR111111"][1]["metadata"]["is_reviewed_llm"] = True
        self.output = self.runs / "refreshed"
        child = extend_entries(first_folder, sha(first_folder / "protein_context.json"), ["IPR111111"],
            self.output, runs_dir=self.runs, http_transport=self.transport)
        self.assertNotEqual(child["entry_files"]["IPR111111"], first_entry)
        self.assertEqual((self.output / first_entry).read_bytes(), previous)
        native = load_publication(self.output, sha(self.output / "protein_context.json"))
        self.assertTrue(native["entry_metadata"]["IPR111111"]["native_record"]["metadata"]["is_reviewed_llm"])

    def test_empty204_is_explicit_unavailable_not_a_fabricated_retirement(self):
        self.responses["IPR111111"] = 204, b""
        child = self.extend(["IPR111111"])
        self.assertEqual(child["entry_files"], {})
        relative = child["entry_unavailable"]["IPR111111"]
        self.assertEqual((self.output / relative).read_bytes(), b"")
        self.assertFalse((self.output / relative.replace(".raw", ".json")).exists())
        ledger = json.loads((self.output / child["requests_file"]).read_text())["requests"]
        self.assertEqual(ledger[-1]["http_status"], 204)
        self.assertNotIn("response_file", ledger[-1])
        self.assertNotIn("IPR111111", load_publication(self.output, sha(self.output / "protein_context.json"))["entry_metadata"])

    def test_nonempty204_retains_failure_and_does_not_register(self):
        self.responses["IPR111111"] = 204, b"contradictory body"
        before = (self.runs / "protein_context_index.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "empty body"):
            self.extend(["IPR111111"], register=True)
        self.assertFalse((self.output / "protein_context.json").exists())
        self.assertEqual((self.runs / "protein_context_index.json").read_bytes(), before)

    def test_refresh_200_to_204_then_200_switches_active_pointer_and_keeps_every_old_byte(self):
        first = self.extend(["IPR111111"])
        first_folder = self.output
        old_native = first["entry_files"]["IPR111111"]
        old_raw = (first_folder / old_native).read_bytes()
        self.output = self.runs / "now_unknown"
        self.responses["IPR111111"] = 204, b""
        second = extend_entries(first_folder, sha(first_folder / "protein_context.json"), ["IPR111111"],
            self.output, runs_dir=self.runs, http_transport=self.transport)
        self.assertNotIn("IPR111111", second["entry_files"])
        self.assertIn("IPR111111", second["entry_unavailable"])
        self.assertEqual((self.output / old_native).read_bytes(), old_raw)
        second_folder = self.output
        self.output = self.runs / "now_available"
        self.responses["IPR111111"] = 200, {"metadata": {"accession": "IPR111111", "is_llm": False}}
        third = extend_entries(second_folder, sha(second_folder / "protein_context.json"), ["IPR111111"],
            self.output, runs_dir=self.runs, http_transport=self.transport)
        self.assertIn("IPR111111", third["entry_files"])
        self.assertNotIn("IPR111111", third["entry_unavailable"])
        for name in second["files"]:
            self.assertEqual((self.output / name).read_bytes(), (second_folder / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
