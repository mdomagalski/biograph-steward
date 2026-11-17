"""Engineering controls for metadata selection and opaque retrieval preparation.

All filenames/content here are synthetic; no public reference row is opened.
"""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts.prepare_intact_fidelity_reference import (
    BASE, NoRedirect, metadata_selection, verify_freeze,
)
from scripts.verify_intact_fidelity_preparation import amended_contract
from scripts import verify_intact_fidelity_preparation as semantic_guard

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/evaluations/intact_fidelity_20261026_protocol.json"
AMENDMENT = ROOT / "docs/evaluations/intact_fidelity_20261026_semantic_amendment.json"
AMENDMENT_SHA = "2cd2cb485836228ce71dd9d62201c61dd5de45d18563894ac883f188f245e98c"


def directory(names):
    return ("<html>" + "".join(
        '<tr><td><a href="' + name + '">' + name + '</a></td>'
        '<td align="right">2026-10-23 20:50</td>'
        '<td align="right">8.0K</td></tr>' for name in names) + "</html>").encode()


class IntactPreparationTests(unittest.TestCase):
    def test_selection_is_order_independent_and_study_grouped(self):
        names = [str(number) + ".txt" for number in range(100001, 100021)]
        selected = metadata_selection(directory(names))
        reverse = metadata_selection(directory(reversed(names)))
        self.assertEqual(selected, reverse)
        self.assertEqual(selected["directory_publication_files"], 20)
        self.assertEqual(len(selected["selected"]), 8)
        self.assertEqual([row["split"] for row in selected["selected"]],
                         ["development"] * 4 + ["reserved_final"] * 4)
        self.assertEqual(len({row["publication_id"] for row in selected["selected"]}), 8)
        self.assertTrue(all(row["url"] == BASE + row["filename"]
                            for row in selected["selected"]))

    def test_missing_panel_does_not_trigger_replacement(self):
        with self.assertRaisesRegex(ValueError, "Fewer than eight"):
            metadata_selection(directory(["100001.txt"]))

    def test_duplicate_filename_rejected_instead_of_cross_split_repeat(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            metadata_selection(directory(["100001.txt"] * 9))

    def test_tampered_panel_rejected_before_any_other_input_or_network_access(self):
        with tempfile.TemporaryDirectory() as temp:
            panel = Path(temp) / "panel.json"
            panel.write_text("{}")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_freeze(panel, "0" * 64)

    def test_redirect_cannot_change_frozen_source(self):
        with self.assertRaisesRegex(ValueError, "exact frozen official URL"):
            NoRedirect().redirect_request(None, None, 302, "Moved", {},
                                          "https://example.invalid/other.txt")


class IntactSemanticAmendmentTests(unittest.TestCase):
    def test_acknowledged_amendment_corrects_only_rule_without_rewriting_history(self):
        before = PROTOCOL.read_bytes()
        original = json.loads(before)
        # Test the replay contract without requiring historical, ignored source
        # captures. The synthetic amendment binds invented evidence bytes while
        # retaining the tracked protocol's exact field replacement and code pin.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            evidence = root / 'invented_format_metadata.txt'
            evidence.write_text('Invented format metadata; no reference rows.')
            amendment = json.loads(AMENDMENT.read_text())
            amendment['evidence'] = [{'local_path': evidence.name,
                                      'sha256': semantic_guard.sha(evidence)}]
            path = root / 'amendment.json'
            path.write_text(json.dumps(amendment))
            acknowledgement = semantic_guard.sha(path)
            with patch.object(semantic_guard, 'ROOT', root):
                corrected = amended_contract(PROTOCOL, path, acknowledgement)
                evidence.write_text('Changed invented metadata.')
                with self.assertRaisesRegex(ValueError, 'Pinned semantic evidence changed'):
                    amended_contract(PROTOCOL, path, acknowledgement)
        self.assertEqual(PROTOCOL.read_bytes(), before)
        self.assertEqual(corrected.pop("effective_contract_amendment_sha256"), acknowledgement)
        corrected.pop("original_protocol_sha256")
        changed = corrected["field_contract"][4]["rule"]
        self.assertIn("no expansion annotation was supplied", changed)
        self.assertIn("does not establish true-binary experimental origin", changed)
        corrected["field_contract"][4]["rule"] = original["field_contract"][4]["rule"]
        self.assertEqual(corrected, original)

    def test_missing_acknowledgement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "acknowledgement is required"):
            amended_contract(PROTOCOL, AMENDMENT, "")

    def test_changed_amendment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / "amendment.json"
            changed.write_bytes(AMENDMENT.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "acknowledgement is required"):
                amended_contract(PROTOCOL, changed, AMENDMENT_SHA)

    def test_changed_original_protocol_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / "protocol.json"
            changed.write_bytes(PROTOCOL.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "Original frozen protocol changed"):
                amended_contract(changed, AMENDMENT, AMENDMENT_SHA)


if __name__ == "__main__":
    unittest.main()
