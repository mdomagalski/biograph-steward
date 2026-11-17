"""Synthetic end-to-end registry/transport and prediction-boundary checks."""
from contextlib import redirect_stdout
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import platform
import tempfile
import unittest

import numpy
import scipy

from biograph_steward.client import digest
from run_source_comparison import main, macro
from test_pilot_methods import encoded, fixture, gene, protein


def save(path, value):
    path.write_text(json.dumps(value) + "\n")


class SourceComparisonRunnerTests(unittest.TestCase):
    def make_plan(self, root, *, bad_ids=False):
        genes = [gene(i, name) for i, name in enumerate(["ALPHA", "BETA", "GAMMA"], 1)]
        for i, row in enumerate(genes, 1):
            row["ensembl_gene_id"] = f"ENSG{i:011d}"
        proteins = [protein(i, name) for i, name in enumerate(["ALPHA", "BETA", "GAMMA"], 1)]
        registry = root / "registry"; registry.mkdir()
        (registry / "hgnc_complete_set.txt").write_bytes(encoded(genes))
        (registry / "uniprot_reviewed_human_symbols.tsv").write_bytes(encoded(proteins))
        manifest = {"taxon_id": 9606, "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in registry.iterdir()}}
        manifest["registry_sha256"] = digest(manifest)
        save(registry / "manifest.json", manifest)
        _, capture = fixture(genes, proteins)
        sequence = root / "sequences.tsv"; sequence.write_bytes(encoded(list(capture.values())))
        signatures = {"ALPHA": ["UniProtKB:P00002|S2", "UniProtKB:P00002|T3"],
                      "GAMMA": ["UniProtKB:P00002|Y4", "UniProtKB:P00002|S5"]}
        profiles = {name: str(root / (name + ".json")) for name in ["first", "second"]}
        for path in profiles.values(): save(Path(path), signatures)
        measurement = root / "values.csv"
        with measurement.open("w", newline="") as f:
            writer = csv.writer(f); writer.writerow(["ID", "a", "b", "c"])
            for i, site in enumerate(["S2", "T3", "Y4", "S5"]):
                identity = f"BETA|{site}|ENSG00000000002|ENSP00000000002"
                writer.writerow(["wrong_three|field|id" if bad_ids else identity, i + 1, 4 - i, i - 2])
        reference = root / "reference.csv"
        with reference.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "Description", "Control", "Time_min", "PMID", "target", "sign"])
            for condition, target, sign, parent in [("a", "ALPHA", 1, "11"), ("b", "GAMMA", -1, "11"), ("c", "ALPHA", -1, "22")]:
                writer.writerow([condition, "invented", "invented", "NA", parent, target, sign])
        files = [p for p in root.rglob("*") if p.is_file()]
        plan = {"runtime": {"python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__},
                "files_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                "registry_directory": str(registry), "sequence_reference": str(sequence),
                "measurement_csv": str(measurement), "reference_csv": str(reference),
                "signature_paths": profiles, "candidate_genes": ["ALPHA", "GAMMA"],
                "selected_conditions": ["a", "b", "c"], "selected_parents": ["11", "22"],
                "measurement_header": ["ID", "a", "b", "c"], "minimum_sites": 2,
                "limitations": ["Invented software fixture, not biological evidence."]}
        plan["content_sha256"] = digest(plan)
        path = root / "plan.json"; save(path, plan)
        return path

    def test_actual_registry_loader_and_four_field_ids_reach_sealed_predictions_before_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); plan = self.make_plan(root); output = root / "out"
            with redirect_stdout(StringIO()): main(plan, output)
            prediction = json.loads((output / "predictions_sealed.private.json").read_text())
            access = json.loads((output / "reference_access_started.json").read_text())
            result = json.loads((output / "results.private.json").read_text())
            self.assertEqual(prediction["measurement_mapping"], {"qualified": 4})
            self.assertFalse(prediction["reference_target_signs_accessed"])
            self.assertLess(prediction["created_at"], access["created_at"])
            self.assertEqual(access["prediction_content_sha256"], prediction["content_sha256"])
            self.assertEqual(result["parent_macros"]["first"]["case_count"], 3)
            self.assertEqual(result["parent_macros"]["first"]["parent_count"], 2)
            self.assertEqual(result["parent_macros"]["first"], result["parent_macros"]["second"])

    def test_zero_qualified_sites_stops_before_inference_or_label_access(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); plan = self.make_plan(root, bad_ids=True); output = root / "out"
            with self.assertRaisesRegex(AssertionError, "No qualified measurement sites"):
                main(plan, output)
            self.assertFalse((output / "predictions_sealed.private.json").exists())
            self.assertFalse((output / "reference_access_started.json").exists())

    def test_changed_input_stops_before_creating_access_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); plan = self.make_plan(root); output = root / "out"
            (root / "values.csv").write_text("changed")
            with self.assertRaises(AssertionError): main(plan, output)
            self.assertFalse(output.exists())

    def test_study_weighting_and_missing_scores_do_not_become_case_weighting(self):
        def row(parent, condition, rank, missing=False):
            return dict(parent=parent, condition=condition, normalized_rank=rank,
                        direction_agreement=not missing, signed_top5=False, abstained=missing)
        result = macro([row("one", "a", .1), row("one", "a", .3), row("one", "b", .4), row("two", "c", 1, True)])
        self.assertAlmostEqual(result["macro"]["normalized_rank"], .65)
        self.assertEqual(result["macro"]["target_score_coverage"], .5)


if __name__ == "__main__":
    unittest.main()
