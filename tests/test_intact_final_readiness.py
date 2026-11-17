"""Metadata-only final preflight gates; no selected interaction body is opened."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_intact_final_readiness as checker


class FinalReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in {checker.RULES, *checker.ORIGINAL_PINS, *checker.REQUIRED_METADATA}:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checker.ROOT / relative, target)
        self.rules = json.loads((self.root / checker.RULES).read_text())

    def save_rules(self):
        (self.root / checker.RULES).write_text(json.dumps(self.rules))

    def add_execution_metadata(self):
        """Invented declarations test the gate, never claim a real runner exists."""
        fields = {
            "full_flow_runner": "scripts/run_intact_final_evaluation.py",
            "synthetic_checks": "docs/evaluations/intact_final_synthetic_20261026_summary.json",
            "development_checks": "docs/evaluations/intact_final_development_20261026_summary.json",
        }
        metadata = {"format": "biograph-steward.intact-final-execution-readiness.v1",
                    "full_flow_runner_declared": True, "immutable_bindings_declared": True}
        for key, relative in fields.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# synthetic runner declaration\n" if key == "full_flow_runner" else '{"synthetic_fixture":true}\n')
            metadata[key] = {"path": relative, "sha256": checker.sha(target)}
            if key != "full_flow_runner":
                metadata[key]["status"] = "passed"
        relative = "docs/evaluations/intact_final_execution_readiness_20261026.json"
        target = self.root / relative
        target.write_text(json.dumps(metadata))
        self.rules["execution_readiness"]["metadata"] = {"path": relative, "sha256": checker.sha(target)}
        self.save_rules()
        return target, metadata

    def test_current_rules_verify_but_remain_blocked_without_full_flow(self):
        opened = []
        original_open = Path.open

        def guarded_open(path, *args, **kwargs):
            relative = path.relative_to(self.root).as_posix()
            self.assertIn(relative, checker.ALLOWED)
            self.assertNotIn("opaque_sources", relative)
            opened.append(relative)
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", guarded_open):
            result = checker.check(self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["rules_metadata_verified"])
        self.assertFalse(result["reserved_reference_bodies_accessed"])
        self.assertFalse(result["authorizes_reference_access"])
        self.assertFalse(result["evaluation_executed"])
        self.assertTrue(any("full-flow" in item for item in result["remaining_checks"]))
        self.assertEqual(set(opened), {checker.RULES, *checker.ORIGINAL_PINS, *checker.REQUIRED_METADATA})

    def test_original_bytes_and_declared_seals_cannot_be_changed(self):
        protocol = self.root / checker.PROTOCOL
        protocol.write_bytes(protocol.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "changed or missing"):
            checker.check(self.root)
        self.rules["original_protocol"]["sha256"] = checker.sha(protocol)
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "seals may not change"):
            checker.check(self.root)

    def test_reserved_list_and_prepare_only_boundary_are_exact(self):
        self.rules["reserved_publication_ids"].reverse()
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "exact frozen reserved"):
            checker.check(self.root)
        self.rules["reserved_publication_ids"] = list(checker.RESERVED)
        self.rules["prepare_only_checker_authorizes_reserved_access"] = True
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "prepare-only"):
            checker.check(self.root)

    def test_unknown_lineage_and_overlap_cannot_shrink_source_eligibility(self):
        original = deepcopy(self.rules)
        for key, value in [("unknown_lineage_is_independent", True),
                           ("overlap_exclusions_change_source_eligibility", True),
                           ("source_eligibility_denominator", "successfully_resolved_cohort")]:
            with self.subTest(rule=key):
                self.rules = deepcopy(original)
                self.rules["rules"][key] = value
                self.save_rules()
                with self.assertRaisesRegex(ValueError, "denominator rule is unsafe"):
                    checker.check(self.root)

    def test_missing_metadata_seal_and_malformed_readiness_fail_closed(self):
        original = deepcopy(self.rules)
        self.rules["metadata_bindings"].pop()
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "five explicit"):
            checker.check(self.root)
        self.rules = original
        self.rules["execution_readiness"] = []
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "metadata object"):
            checker.check(self.root)

    def test_forbidden_binding_is_rejected_before_any_hash_or_open(self):
        bindings = [{"path": checker.PROTOCOL, "sha256": checker.ORIGINAL_PINS[checker.PROTOCOL]},
                    {"path": "runs/intact_fidelity_preparation_20261026/opaque_sources/39833857.txt", "sha256": "a" * 64}]
        with patch.object(checker, "sha", side_effect=AssertionError("No file may be hashed")), \
                patch.object(Path, "open", side_effect=AssertionError("No file may be opened")):
            with self.assertRaisesRegex(ValueError, "Unapproved metadata/code path"):
                checker.verify_bindings(self.root, bindings)

    def test_symlink_into_opaque_directory_is_rejected_before_hashing(self):
        relative = sorted(checker.REQUIRED_METADATA)[0]
        target = self.root / relative
        target.unlink()
        target.symlink_to(self.root / "opaque_sources" / "39833857.txt")
        with patch.object(checker, "sha", side_effect=AssertionError("No file may be hashed")):
            with self.assertRaisesRegex(ValueError, "Symlink metadata/code"):
                checker.check(self.root)

    def test_missing_full_flow_components_cannot_be_declared_ready(self):
        self.rules["execution_readiness"]["status"] = "ready"
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "separate sealed full-flow"):
            checker.check(self.root)
        metadata_path, metadata = self.add_execution_metadata()
        del metadata["development_checks"]
        metadata_path.write_text(json.dumps(metadata))
        self.rules["execution_readiness"]["metadata"]["sha256"] = checker.sha(metadata_path)
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "all required"):
            checker.check(self.root)

    def test_separate_synthetic_declarations_still_never_authorize_execution(self):
        metadata_path, metadata = self.add_execution_metadata()
        result = checker.check(self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["authorizes_reference_access"])
        self.assertTrue(any("declarations checked only" in item for item in result["remaining_checks"]))
        metadata["synthetic_checks"]["status"] = "failed"
        metadata_path.write_text(json.dumps(metadata))
        self.rules["execution_readiness"]["metadata"]["sha256"] = checker.sha(metadata_path)
        self.save_rules()
        with self.assertRaisesRegex(ValueError, "checks must pass"):
            checker.check(self.root)


if __name__ == "__main__":
    unittest.main()
