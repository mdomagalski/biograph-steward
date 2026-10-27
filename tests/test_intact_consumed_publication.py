"""Invented interaction rows and metadata; no local run artifacts required."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.assay_attachment import attach_assay, load_publication
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.graph import save_run
from biograph_steward.intact_final_publication import (
    CONSUMED_FORMAT, FORMAT, load_projection, publish_material,
)
from test_assay_attachment import cohort_snapshot
from test_intact_final_publication import encode, seal, sha
from test_intact_consumed_flow import consumed_material as invented_material


def consumed_material():
    return invented_material()[:4]


class ConsumedPublicationTests(unittest.TestCase):
    def setUp(self):
        # Replace only the known historical metadata fingerprint for invented
        # fixtures. Production validation and the fixed study allowlist run intact.
        origin = consumed_material()[2]["origin_reserved_freeze_sha256"]
        patcher = patch("biograph_steward.intact_final_publication.ORIGIN_RESERVED_SHA", origin)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_label_survives_normal_dispatch_attachment_and_export(self):
        files, catalog, bindings, inspection = consumed_material()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            manifest = publish_material(files, catalog, bindings, inspection, root / "publication")
            self.assertEqual(manifest["format"], CONSUMED_FORMAT)
            _, evidence, reopened_files = load_publication(root / "publication")
            self.assertTrue(evidence["summary"]["consumed_input_replay"])
            self.assertFalse(evidence["summary"]["fresh_validation_performed"])
            self.assertIn("Consumed-data development replay", reopened_files["index.html"].decode())
            save_run(cohort_snapshot(), root / "cohort")
            graph = attach_assay(root / "cohort", root / "publication", root / "attached")
            self.assertEqual(graph["assay_evidence"]["source_bindings"], bindings)
            export_packet(root / "attached", root / "packet")
            load_packet(root / "packet")
            packet = json.loads((root / "packet/packet_manifest.json").read_text())
            self.assertIn("intact_final_publication", packet["implementation_sha256"])
            source_manifests = list((root / "packet").rglob("publication.json"))
            self.assertTrue(source_manifests)
            self.assertTrue(any(json.loads(p.read_text()).get("format") == CONSUMED_FORMAT
                                for p in source_manifests))

    def test_consumed_cannot_use_old_envelope_or_false_accuracy_claim(self):
        files, catalog, bindings, inspection = consumed_material()
        with tempfile.TemporaryDirectory() as tmp:
            manifest = publish_material(files, catalog, bindings, inspection, Path(tmp).resolve() / "pub")
            _, _, complete_files = load_publication(Path(tmp).resolve() / "pub")
            with self.assertRaises(ValueError):
                load_projection({**manifest, "format": FORMAT}, complete_files)
            changed = dict(complete_files)
            freeze = json.loads(changed["execution_freeze.json"])
            freeze.pop("content_sha256")
            freeze["scientific_accuracy_measured"] = True
            changed["execution_freeze.json"] = encode(seal(freeze))
            altered = deepcopy(manifest)
            altered["bindings"]["execution_freeze_sha256"] = sha(changed["execution_freeze.json"])
            with self.assertRaises(ValueError):
                load_projection(altered, changed)

    def test_origin_and_archive_are_required_and_bound(self):
        files, catalog, bindings, inspection = consumed_material()
        for name in ("origin_execution_freeze.json", "historical_code_archive_receipt.json"):
            changed = dict(files)
            changed.pop(name)
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp).resolve() / "invalid"
                with self.assertRaises(ValueError):
                    publish_material(changed, catalog, bindings, inspection, out)
                self.assertFalse(out.exists())
        changed = dict(files)
        archive = json.loads(changed["historical_code_archive_receipt.json"])
        archive.pop("content_sha256")
        archive["files"][0]["sha256"] = "0" * 64
        changed["historical_code_archive_receipt.json"] = encode(seal(archive))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            publish_material(changed, catalog, bindings, inspection, Path(tmp).resolve() / "invalid")


if __name__ == "__main__":
    unittest.main()
