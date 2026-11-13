"""Synthetic source eligibility, not invented biological correctness labels."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.cohort_mapping import SOURCES, collect_registry
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from biograph_steward.reviews import review_run
from tools.sampled_audit import wiki_current_view as view
from test_cohort_mapping import gene, protein, registry, tsv
from test_normalization import fixture, resign


def membership(gene_ids):
    return {"genes": set(gene_ids), "source_line": 1, "raw_line_sha256": "a" * 64}


class WikiEligibilityUnitTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry([gene("HGNC:1", "TEST", products="P04637")],
                                 [protein("P04637", "HGNC:1", "TEST")])
        self.relation = view.gene_relationship("UniProtKB:P04637", self.registry)

    def test_presence_absence_and_unknown_have_different_meanings(self):
        rows = {"WP1": membership(["1"]), "WP2": membership(["2"])}
        present = view.classify_membership("WP1_r99", self.relation, rows)
        absent = view.classify_membership("WP2", self.relation, rows)
        missing = view.classify_membership("WP999", self.relation, rows)
        self.assertEqual((present["decision"], absent["decision"], missing["decision"]), ("keep", "prune", "abstain"))
        self.assertEqual(present["source_version_relation"], {"subject": "WP1_r99", "predicate": view.RELATION,
            "object": "WP1", "content_equivalence": False})
        self.assertFalse(absent["encoded_membership_present"])
        self.assertIsNone(absent["source_version_relation"])
        self.assertIsNone(missing["encoded_membership_present"])

    def test_no_fuzzy_names_version_guessing_or_isoform_stripping(self):
        rows = {"WP1": membership(["1"])}
        for source_id in [None, "WP1_r0", "WP01", "wp1", "WP1_r2_extra", "Some pathway", "WP1_r2 " ]:
            with self.subTest(source_id=source_id):
                self.assertEqual(view.classify_membership(source_id, self.relation, rows)["decision"], "abstain")
        for subject in ["P04637", "UniProtKB:P04637-2", "NCBIGene:1", "UniProtKB:P00001", "uniprotkb:P04637"]:
            with self.subTest(subject=subject):
                relation = view.gene_relationship(subject, self.registry)
                self.assertFalse(relation["qualified"])
                self.assertEqual(view.classify_membership("WP1", relation, rows)["decision"], "abstain")

    def test_gene_relation_is_explicit_agreement_not_identity(self):
        self.assertTrue(self.relation["qualified"])
        self.assertEqual(self.relation["ncbi_gene_id"], "1")
        self.assertEqual(self.relation["relation"], "gene_to_protein_relationship_not_identity")
        scenarios = [
            ([gene("HGNC:1", "TEST", products="P04637")], [protein("P04637", "HGNC:1", "TEST", ncbi="1;2")]),
            ([gene("HGNC:1", "TEST", products="P04637")], [protein("P04637", "HGNC:1;HGNC:2", "TEST")]),
            ([gene("HGNC:1", "TEST", products="P00533")], [protein("P04637", "HGNC:1", "TEST")]),
            ([gene("HGNC:1", "TEST", products="P04637", status="Entry Withdrawn")], [protein("P04637", "HGNC:1", "TEST")]),
            ([gene("HGNC:1", "TEST", products="P04637")], [protein("P04637", "HGNC:1", "TEST", ncbi="2")]),
        ]
        for genes, proteins in scenarios:
            with self.subTest(genes=genes, proteins=proteins):
                self.assertFalse(view.gene_relationship("UniProtKB:P04637", registry(genes, proteins))["qualified"])

    def test_unreviewed_author_code_is_never_executed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "EXECUTED"
            (root / "pywp_pywikipathways_read_gmt.py").write_text("raise RuntimeError('must not run')")
            with self.assertRaisesRegex(ValueError, "input missing, symlinked or changed"):
                view.author_memberships(root / "irrelevant.gmt", root)
            self.assertFalse(marker.exists())

    def test_report_pin_and_seal_fail_before_any_optional_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            write_json(path, {"format": view.REFERENCE_FORMAT, "content_sha256": "b" * 64})
            with patch.object(view, "author_memberships", side_effect=AssertionError("must not parse")):
                with self.assertRaisesRegex(ValueError, "input missing, symlinked or changed"):
                    view.load_reference(path, "0" * 64)
                with self.assertRaisesRegex(ValueError, "format or content seal"):
                    view.load_reference(path, sha(path))

    def test_wrong_declared_R_license_pin_fails_before_reader_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            report = {"format": view.REFERENCE_FORMAT, "source_release": "20261110", "species": "Homo sapiens",
                "native_author_parser": {"repository": view.AUTHOR_REPOSITORY, "commit": view.AUTHOR_COMMIT,
                    "function": "read_pathway_gmt", "source_sha256": view.AUTHOR_PINS,
                    "r_reader_license_sha256": "0" * 64}}
            report["content_sha256"] = digest(report)
            write_json(path, report)
            with patch.object(view, "author_memberships", side_effect=AssertionError("must not parse")):
                with self.assertRaisesRegex(ValueError, "documentation license differs"):
                    view.load_reference(path, sha(path))


class WikiEligibilityGoldTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run, self.packet, self.output = [self.root / name for name in ("run", "packet", "output")]
        snapshot = fixture()
        for target in snapshot["targets"]:
            target["pathways"] = []
        snapshot["targets"][0]["pathways"] = [
            {"pwid": 101, "name": "Invented encoded membership", "type": "WikiPathways", "sourceID": "WP1_r10"},
            {"pwid": 102, "name": "Same source with separate native local ID", "type": "WikiPathways", "sourceID": "WP1_r10"},
            {"pwid": 103, "name": "Separate historical version", "type": "WikiPathways", "sourceID": "WP1_r11"},
            {"pwid": 104, "name": "Invented absent encoded gene", "type": "WikiPathways", "sourceID": "WP2"},
            {"pwid": 105, "name": "Invented unknown current pathway", "type": "WikiPathways", "sourceID": "WP3"},
            {"pwid": 106, "name": "Invented unrecognized source ID", "type": "WikiPathways", "sourceID": "WP1_r0"},
            {"pwid": 107, "name": "Outside current Wiki profile", "type": "Reactome", "sourceID": "R-HSA-1"},
        ]
        graph = save_run(resign(snapshot), self.run)
        reviewed_edge = next(e for e in graph["edges"] if e["record_kind"] == "pathway_membership" and e["evidence_record"]["pwid"] == 101)
        reviewed_run = self.root / "reviewed"
        self.graph = review_run(self.run, reviewed_run, reviewed_edge["assertion_id"], "rejected", "Invented reviewer", "Test review retained independently of source currency")
        self.manifest = gold_packet.export_packet(reviewed_run, self.packet)
        self.source_inventory = self.inventory(self.packet)
        self.registry_directory = self.root / "registry"
        hgnc = tsv([gene("HGNC:1", "TEST", products="P04637")])
        uniprot = tsv([protein("P04637", "HGNC:1", "TEST")])
        self.registry_manifest = collect_registry(self.registry_directory, transport=lambda url:
            (hgnc if url == SOURCES["hgnc_complete_set.txt"] else uniprot, {}))
        self.reference = self.root / "reference/report.json"
        self.reference.parent.mkdir()
        write_json(self.reference, {"synthetic_mocked_reference": True})
        (self.reference.parent / "proof.txt").write_text("Synthetic source binding, not biological evidence")
        self.binding = {"proof_files": {"proof.txt": sha(self.reference.parent / "proof.txt")},
                        "source_sha256": "a" * 64}
        self.memberships = {"WP1": membership(["1"]), "WP2": membership(["2"])}

    @staticmethod
    def inventory(folder):
        return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*") if p.is_file()}

    def qualify(self, **kwargs):
        with patch.object(view, "load_reference", return_value=(self.memberships, self.binding)), \
                patch("urllib.request.urlopen", side_effect=AssertionError("no retrieval")):
            return view.qualify_current_wikipathways(self.packet, self.reference, self.registry_directory, self.output,
                reference_sha256=sha(self.reference), registry_sha256=self.registry_manifest["registry_sha256"], **kwargs)

    def test_complete_reversible_gold_view_preserves_unknown_and_reviews(self):
        report = self.qualify()
        disposition, retained = gold_packet.load_decisions(self.output / "retained")
        self.assertEqual(report["counts"]["WikiPathways"], {"keep": 3, "prune": 1, "abstain": 2})
        self.assertEqual(report["counts"]["exact_subject_type_full_sourceID_groups"], 5)
        self.assertEqual(disposition["counts"]["prune"], 1)
        self.assertEqual(len(retained["edges"]), len(self.graph["edges"]) - 1)
        pruned = next(e["id"] for e in self.graph["edges"] if e.get("evidence_record", {}).get("pwid") == 104)
        self.assertEqual({e["id"] for e in self.graph["edges"]} - {e["id"] for e in retained["edges"]}, {pruned})
        self.assertEqual(retained["nodes"], self.graph["nodes"])
        self.assertEqual(self.inventory(self.packet), self.source_inventory)
        self.assertEqual(gold_packet.load_packet(self.output / "retained/baseline_packet")[1], self.graph)
        edge = next(e for e in retained["edges"] if e.get("evidence_record", {}).get("pwid") == 101)
        assertion = next(a for a in retained["assertions"] if a["id"] == edge["assertion_id"])
        self.assertEqual(assertion["lifecycle_state"], "rejected")
        decisions = json.loads((self.output / "decisions.json").read_text())["decisions"]
        self.assertEqual({d["edge_id"] for d in decisions}, {e["id"] for e in self.graph["edges"]})
        self.assertTrue(all(d["confidence"] is None for d in decisions))
        for field in ["biological_truth_assessed", "independent_biological_accuracy", "historical_claims_refuted", "protein_form_identity_inferred"]:
            self.assertFalse(report[field])
        self.assertTrue(report["exploratory_post_sample_development"])

    def test_exact_full_source_groups_do_not_merge_local_rows_or_revisions(self):
        self.qualify()
        groups = json.loads((self.output / "source_groups.json").read_text())["groups"]
        first = next(g for g in groups if g["full_source_id"] == "WP1_r10")
        other = next(g for g in groups if g["full_source_id"] == "WP1_r11")
        self.assertEqual(set(first["native_pwids"]), {101, 102})
        self.assertEqual(first["raw_edge_count"], 2)
        self.assertEqual(len(first["edge_ids"]), 2)
        self.assertNotEqual(first["group_id"], other["group_id"])
        self.assertFalse(first["native_rows_merged"])
        self.assertIsNone(first["independent_evidence_count"])

    def test_registry_pin_mismatch_fails_before_output(self):
        changed = deepcopy(self.registry_manifest)
        wrong_pin = "0" * 64
        with patch.object(view, "load_reference", return_value=(self.memberships, self.binding)):
            with self.assertRaisesRegex(ValueError, "registry seal differs"):
                view.qualify_current_wikipathways(self.packet, self.reference, self.registry_directory, self.output,
                    reference_sha256=sha(self.reference), registry_sha256=wrong_pin)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.registry_manifest, changed)

    def test_actor_and_output_require_explicit_immutable_choices(self):
        for actor in ["", "unassigned", None]:
            with self.subTest(actor=actor), patch.object(view, "load_reference", side_effect=AssertionError("no parse")):
                with self.assertRaisesRegex(ValueError, "explicit actor"):
                    view.qualify_current_wikipathways(self.packet, self.reference, self.registry_directory, self.output,
                        reference_sha256=sha(self.reference), registry_sha256=self.registry_manifest["registry_sha256"], actor=actor)
        self.qualify()
        before = self.inventory(self.output)
        with self.assertRaisesRegex(ValueError, "immutable output"):
            self.qualify()
        self.assertEqual(before, self.inventory(self.output))

    def test_concurrent_reference_change_cannot_leave_a_success_report(self):
        save = gold_packet.save_decisions

        def changed_after_export(*args, **kwargs):
            result = save(*args, **kwargs)
            (self.reference.parent / "proof.txt").write_text("changed during materialization")
            return result

        with patch.object(view.gold_packet, "save_decisions", side_effect=changed_after_export):
            with self.assertRaisesRegex(ValueError, "input missing, symlinked or changed"):
                self.qualify()
        self.assertFalse((self.output / "wiki_current_qualification.json").exists())
        self.assertEqual(self.inventory(self.packet), self.source_inventory)

    def test_changed_copied_reference_cannot_be_sealed_when_source_is_unchanged(self):
        copy = view.shutil.copyfile
        reference_pin = sha(self.reference)
        tampered = []

        def changed_copy(source, target, *args, **kwargs):
            result = copy(source, target, *args, **kwargs)
            if Path(target).resolve() == (self.output / "reference/reviewed_reference_report.json").resolve():
                Path(target).write_bytes(Path(target).read_bytes() + b"\n")
                tampered.append(str(target))
            return result

        with patch.object(view.shutil, "copyfile", side_effect=changed_copy):
            with self.assertRaisesRegex(ValueError, "input missing, symlinked or changed"):
                self.qualify()
        self.assertEqual(sha(self.reference), reference_pin)
        self.assertEqual(len(tampered), 1)
        self.assertFalse((self.output / "wiki_current_qualification.json").exists())
        self.assertEqual(self.inventory(self.packet), self.source_inventory)

    def test_changed_copied_registry_cannot_be_sealed_when_source_is_unchanged(self):
        copy = view.shutil.copyfile
        registry_before = self.inventory(self.registry_directory)
        tampered = []

        def changed_copy(source, target, *args, **kwargs):
            result = copy(source, target, *args, **kwargs)
            if Path(target).resolve() == (self.output / "registry/hgnc_complete_set.txt").resolve():
                Path(target).write_bytes(Path(target).read_bytes() + b"\n")
                tampered.append(str(target))
            return result

        with patch.object(view.shutil, "copyfile", side_effect=changed_copy):
            with self.assertRaisesRegex(ValueError, "Registry bytes changed"):
                self.qualify()
        self.assertEqual(self.inventory(self.registry_directory), registry_before)
        self.assertEqual(len(tampered), 1)
        self.assertFalse((self.output / "wiki_current_qualification.json").exists())
        self.assertEqual(self.inventory(self.packet), self.source_inventory)


if __name__ == "__main__":
    unittest.main()
