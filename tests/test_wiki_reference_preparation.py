"""Offline reference-packet transport tests; native-reader execution is separate."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from tools.sampled_audit import prepare_wiki_reference as builder


class WikiReferencePreparationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.metadata, self.output = self.root / "metadata.json", self.root / "packet"
        self.files = {}
        for key in builder.FILE_KEYS:
            path = self.inputs / (key + ".txt")
            path.write_text("INVENTED TRANSPORT CONTROL " + key + "\n")
            self.files[key] = {"path": str(path.relative_to(self.root)), "sha256": sha(path)}
        # This suite checks contract/copy behavior without a pandas dependency
        # or vendored author code. Actual pinned readers are executed in the
        # real-source replay; these explicit patches are transport fixtures.
        p1 = patch.object(builder, "AUTHOR_PINS", {k: self.files[k]["sha256"] for k in ("read_gmt", "read_pathway_gmt")})
        p2 = patch.object(builder, "AUTHOR_DOCUMENTATION_PINS", {
            "pywp_LICENSE": self.files["reader_license"]["sha256"],
            "rWikiPathways_LICENSE": self.files["r_reader_license"]["sha256"],
            "rWikiPathways_readPathwayGMT.R": self.files["r_reader_documentation"]["sha256"]})
        p1.start(); p2.start()
        self.addCleanup(p1.stop); self.addCleanup(p2.stop)
        self.config = {"format": builder.INPUT_FORMAT, "source_release": "20261110",
            "source_url": "https://data.wikipathways.org/current/gmt/wikipathways-20261110-gmt-Homo_sapiens.gmt",
            "files": deepcopy(self.files), "version_proof": {"Version": "WP1_r2", "canonical_WPID": "WP1"}}
        self.write_config()

    def write_config(self):
        write_json(self.metadata, self.config)

    def native_replay_fixture(self, path, pin):
        self.assertEqual(sha(path), pin)
        data = gold_packet._read(path)
        self.assertTrue(gold_packet._sealed(data))
        self.assertEqual(data["format"], builder.REFERENCE_FORMAT)
        self.assertEqual(data["species"], "Homo sapiens")
        self.assertNotIn("cohort", data)
        self.assertFalse((self.output / "reference.json").exists())
        self.assertFalse((self.output / "reference_manifest.json").exists())
        native = path.parent / "wikipathways-20261110-gmt-Homo_sapiens.gmt"
        self.assertEqual(sha(native), self.files["gmt"]["sha256"])
        self.assertEqual(len([p for p in path.parent.iterdir() if p.is_file()]), 9)
        return {"WP1": {"genes": {"1"}}}, {"pathways": 1, "native_membership_rows": 1,
            "unique_memberships": 1, "author_reader_executed": True,
            "reference_content_sha256": data["content_sha256"]}

    def build(self, replay=None):
        with patch.object(builder, "load_reference", side_effect=replay or self.native_replay_fixture):
            return builder.prepare_reference(self.metadata, self.output)

    def test_minimal_packet_is_replayed_before_publication_and_has_complete_pins(self):
        before = {p: sha(p) for p in self.inputs.iterdir()}
        report = self.build()
        self.assertEqual(report["status"], "native_reference_replayed")
        self.assertEqual(report["pathways"], 1)
        self.assertFalse(report["cohort_specific_outcomes_included"])
        self.assertFalse(report["scientific_accuracy_measured"])
        reference = gold_packet._read(self.output / "reference.json")
        self.assertNotIn("cohort", reference)
        self.assertNotIn("RAD21", json.dumps(reference))
        self.assertEqual(reference["native_author_parser"]["r_reader_license_sha256"], self.files["r_reader_license"]["sha256"])
        self.assertEqual(sha(self.output / "rWikiPathways_LICENSE"), self.files["r_reader_license"]["sha256"])
        self.assertEqual(report["reference_content_sha256"], reference["content_sha256"])
        self.assertEqual(report["reference_file_sha256"], sha(self.output / "reference.json"))
        self.assertEqual(report["content_sha256"], digest({k: v for k, v in report.items() if k != "content_sha256"}))
        self.assertEqual(set(report["files"]), {p.name for p in self.output.iterdir() if p.is_file()} - {"reference_manifest.json"})
        for name, pin in report["files"].items():
            self.assertEqual(sha(self.output / name), pin)
        self.assertEqual({p: sha(p) for p in before}, before)

    def test_partial_extra_cohort_or_mismatched_version_metadata_fails_before_output(self):
        original = deepcopy(self.config)
        variants = []
        for edit in (lambda c: c.update(cohort=[]), lambda c: c["files"].pop("gmt"),
                     lambda c: c["files"].pop("r_reader_license"),
                     lambda c: c["files"]["gmt"].update(label="supported"),
                     lambda c: c["version_proof"].update(canonical_WPID="WP99"),
                     lambda c: c.update(source_url="https://example.invalid/data.gmt")):
            value = deepcopy(original); edit(value); variants.append(value)
        for value in variants:
            self.config = value; self.write_config()
            with self.subTest(value=value), patch.object(builder, "load_reference") as replay:
                with self.assertRaises(ValueError):
                    builder.prepare_reference(self.metadata, self.output)
                replay.assert_not_called()
            self.assertFalse(self.output.exists())

    def test_mutated_source_bytes_or_unreviewed_author_code_fail_before_execution(self):
        self.config["files"]["gmt"]["sha256"] = "0" * 64
        self.write_config()
        with patch.object(builder, "load_reference") as replay, self.assertRaises(ValueError):
            builder.prepare_reference(self.metadata, self.output)
        replay.assert_not_called()
        self.config["files"]["gmt"] = deepcopy(self.files["gmt"])
        code = self.inputs / "read_gmt.txt"
        code.write_text("UNREVIEWED REPLACEMENT")
        self.config["files"]["read_gmt"]["sha256"] = sha(code)
        self.write_config()
        with patch.object(builder, "load_reference") as replay, self.assertRaisesRegex(ValueError, "reviewed code"):
            builder.prepare_reference(self.metadata, self.output)
        replay.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_failed_native_replay_never_publishes_a_reference_or_success_manifest(self):
        with self.assertRaisesRegex(ValueError, "invalid native GMT"):
            self.build(lambda *_: (_ for _ in ()).throw(ValueError("invalid native GMT")))
        self.assertFalse((self.output / "reference.json").exists())
        self.assertFalse((self.output / "reference_manifest.json").exists())
        self.assertEqual(list(self.output.iterdir()), [])

    def test_source_change_during_native_replay_never_publishes_success(self):
        def mutate(path, pin):
            result = self.native_replay_fixture(path, pin)
            source = self.inputs / "gmt.txt"
            source.write_bytes(source.read_bytes() + b"CHANGED")
            return result
        with self.assertRaises(ValueError):
            self.build(mutate)
        self.assertFalse((self.output / "reference.json").exists())
        self.assertFalse((self.output / "reference_manifest.json").exists())

    def test_symlinked_inputs_and_existing_outputs_are_rejected(self):
        link = self.inputs / "linked.txt"
        link.symlink_to(self.inputs / "gmt.txt")
        self.config["files"]["gmt"]["path"] = str(link)
        self.write_config()
        with self.assertRaises(ValueError):
            self.build()
        self.config["files"]["gmt"] = deepcopy(self.files["gmt"]); self.write_config()
        self.build()
        before = {p: sha(p) for p in self.output.iterdir() if p.is_file()}
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual({p: sha(p) for p in before}, before)


if __name__ == "__main__":
    unittest.main()
