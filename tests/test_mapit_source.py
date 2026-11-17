"""Invented source fixtures exercise source preservation and proximity semantics."""
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from biograph_steward import mapit_source as m
from biograph_steward.assertions import assertion_identity


def sealed(value):
    value["content_sha256"] = digest({k: v for k, v in value.items() if k != "content_sha256"})
    return value


def raw_json(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def tsv(columns, rows):
    stream = StringIO()
    writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return stream.getvalue().encode()


def material_fixture():
    """Simulated completed-source receipts; no real measurements or R execution."""
    samples = ["S" + str(n) for n in range(168)]
    annotations, identities, stats = [], [], []
    for n in range(1, 6477):
        accession = "P" + str(n).zfill(5)
        group = "P00220;Q00001" if n == 220 else accession
        exact = n != 220
        annotations.append([group, "Protein" + str(n), "G" + str(n), "Invented source protein", *(["1"] * 168)])
        identities.append([n + 1, "G" + str(n), group, "G" + str(n), group if exact else "NA",
                           "exact_single_source_accession" if exact else "unresolved_group_or_accession"])
        if n <= 5378:
            positive = n <= 120 or n in (220, 533)
            stats.append(["G" + str(n), "G" + str(n), -1 if positive else 1,
                          .001 if positive else .8, .01 if positive else .9, "not_imputed", *(["0"] * 168)])
    meta = tsv(["Col", "Block", "Tissue", "Ab", "Sample"],
               [[n + 5, "B" + str(n // 12), "Tumor" if n % 24 < 12 else "Healthy",
                 "Primary" if n % 2 else "Isotype", sample] for n, sample in enumerate(samples)])
    files = {
        "source/raw/EGFR_colon_report.pg_matrix.tsv": tsv(
            ["Protein.Group", "Protein.Names", "Genes", "First.Protein.Description", *["Raw" + s for s in samples]], annotations),
        "source/raw/EGFR_colon_report.pr_matrix.tsv": b"Invented precursor data, no model run\n",
        "source/pg_annotation_only.tsv": b"Invented annotation capture\n",
        "source/identity_sidecar.R": b"# Invented identity source\n",
        "source/run_author_variant.R": b"# Invented guard: expected_q <- p.adjust(fit$p.value\n",
        "source/EGFR_Aggregated_model.released.R": b"# Invented released variant\n",
        "source/EGFR_Aggregated_model.source_key_corrected.R": b"# Invented corrected variant\n",
        "source/sample_metadata_audit.json": b"{}\n", "source/patient7_metadata_only.patch": b"Invented patch\n",
    }
    for label in ("primary", "released"):
        for name in m._MODEL_FILES:
            files["source/" + label + "/" + name] = b"Invented completed-model artifact\n"
        files["source/" + label + "/sample_metadata.tsv"] = meta
        files["source/" + label + "/author_full_stats.tsv"] = tsv(
            ["Protein", "Genes", "Beta_Ab", "P_Ab", "Q_Ab", "ImputeStatus", *samples], stats)
        files["source/" + label + "/identity_sidecar.tsv"] = tsv(
            ["Source.Matrix.Row", "Model.Protein", "Protein.Group", "Genes", "Exact.UniProt", "Identity.Status"], identities)
    for name in ("linux-64.mirror.sha256.explicit.txt", "linux-64.package-manifest.json",
                 "runtime_acceptance.json", "runtime_probe.container.txt"):
        files["runtime/" + name] = b"Invented runtime\n"
    mapping = {
        "EGFR_colon_report.pg_matrix.tsv": "source/raw/EGFR_colon_report.pg_matrix.tsv",
        "EGFR_colon_report.pr_matrix.tsv": "source/raw/EGFR_colon_report.pr_matrix.tsv",
        **{n: "source/" + n for n in ("pg_annotation_only.tsv", "identity_sidecar.R", "run_author_variant.R",
                 "EGFR_Aggregated_model.released.R", "EGFR_Aggregated_model.source_key_corrected.R")}}
    evidence = {
        **{"reference_runtime/" + n: m._sha(files["runtime/" + n]) for n in
           ("linux-64.mirror.sha256.explicit.txt", "linux-64.package-manifest.json",
            "runtime_acceptance.json", "runtime_probe.container.txt")},
        **{"reference_rules/author_runtime/" + n: m._sha(files["source/" + n]) for n in
           ("sample_metadata_audit.json", "patient7_metadata_only.patch")}}
    protocol = sealed({"run_bundle_files": {n: m._sha(files[p]) for n, p in mapping.items()}, "evidence_bindings": evidence})
    files["source/protocol.json"] = raw_json(protocol)
    protocol_hash = m._sha(files["source/protocol.json"])
    files["source/final_freeze_receipt.json"] = raw_json({"protocol_file_sha256": protocol_hash})
    execution = {"complete": True, "protocol_file_sha256": protocol_hash, "variants": [
        {"name": variant, "returncode": 0, "files": {n: m._sha(files["source/" + label + "/" + n]) for n in m._MODEL_FILES}}
        for variant, label in (("source_key_corrected", "primary"), ("released_metadata", "released"))]}
    files["source/execution_receipt.json"] = raw_json(execution)
    files["source/assessment_report.json"] = raw_json(sealed({"invented": True}))
    files["archive/archive_receipt.json"] = raw_json({"sha256": "a" * 64, "gzip_full_crc_and_eof_verified": True})
    files["archive/extraction_receipt.json"] = raw_json(sealed({"historical_archive_sha256": "a" * 64}))
    partners = ["P" + str(n).zfill(5) for n in range(1, 121)]
    proteins = [{"uniprot": uid, "protein_id": n, "symbol": uid, "target_count": 1}
                for n, uid in enumerate(["P00533", *partners])]
    raw_pairs = []
    for n, score in ((1, 900), (2, 399)):
        uid = partners[n - 1]
        for left, right in (("P00533", uid), (uid, "P00533")):
            raw_pairs.append({"id": len(raw_pairs) + 1, "subject_uniprot": left,
                              "object_uniprot": right, "ppitypes": "STRINGDB", "score": score})
    files["archive/proteins.json"] = raw_json(proteins)
    files["archive/pairs.json"] = raw_json(raw_pairs)
    queries = m.archive_queries(partners)
    for n, sql in queries.items():
        files["archive/" + n + ".sql"] = sql.encode()
    files["archive/query_receipt.json"] = raw_json({"archive_sha256": "a" * 64,
        "schema": "ncats_ppi exact accession lookup; nonmock raw and resolver profile",
        "public_profile": "exclude mock; exclude exact STRINGDB score<400",
        "queries_sha256": {n: m._sha(files["archive/" + n + ".sql"]) for n in queries},
        "outputs_sha256": {n: m._sha(files["archive/" + n + ".json"]) for n in queries}})
    files["source/licensing_contract.json"] = raw_json(sealed({"study_doi": m.DOI,
        "figshare": {"id": 31820131, "license": {"name": "CC BY 4.0"}},
        "author_code": {"license": "cc-by-4.0"}}))
    files["LICENSE.md"] = b"Invented licensing fixture\n"
    return files


def manifest_fixture(files):
    projection = m.project_material(files)
    files = {**files, "projection.json": raw_json(projection)}
    manifest = sealed({"format": m.FORMAT, "source_kind": "mapit", "baseline_modified": False,
        "independent_validation_performed": False, "summary": projection["summary"],
        "projection_content_sha256": projection["content_sha256"],
        "source_license": {"license": "Invented test source"},
        "files": {n: m._sha(raw) for n, raw in files.items()}})
    return manifest, projection, files


class MapitSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = material_fixture()

    def test_complete_family_preserved_and_only_exact_enriched_partners_projected(self):
        value = m.project_material(self.material)
        self.assertEqual(value["summary"]["full_modeled_groups"], 5378)
        self.assertEqual(value["summary"]["full_family_enriched_groups"], 122)
        self.assertEqual(value["summary"]["enriched_unresolved_identity_groups"], 1)
        self.assertEqual(len(value["observations"]), 120)
        self.assertTrue(any(r["state"] == "not_called_not_a_negative" for r in value["full_model_ledger"]))
        self.assertTrue(all(r["partner"] != m.BAIT for r in value["observations"]))
        self.assertEqual(value["observations"][0]["interaction_type"]["id"], "MI:2364")
        self.assertIsNone(value["observations"][0]["independent_evidence_count"])

    def test_archive_raw_subthreshold_and_absent_states_remain_distinct(self):
        value = m.project_material(self.material)
        rows = {r["partner"]: r for r in value["observations"]}
        self.assertEqual(rows["UniProtKB:P00001"]["archive_lookup"]["status"], "present_in_archived_public_PPI_profile")
        self.assertEqual(rows["UniProtKB:P00002"]["archive_lookup"]["status"], "raw_archived_pair_below_public_profile")
        self.assertEqual(rows["UniProtKB:P00003"]["archive_lookup"]["status"], "no_nonmock_archived_PPI_pair")
        self.assertFalse(rows["UniProtKB:P00003"]["archive_lookup"]["current_Pharos_absence_established"])

    def test_changed_model_bytes_and_missing_original_variant_fail(self):
        changed = dict(self.material)
        changed["source/primary/author_full_stats.tsv"] += b"changed\n"
        with self.assertRaises(ValueError):
            m.project_material(changed)
        changed = dict(self.material)
        del changed["source/released/author_fit_MArrayLM.rds"]
        with self.assertRaises((ValueError, KeyError)):
            m.project_material(changed)

    def test_ambiguous_group_is_not_first_accession_and_positive_boundary_is_strict(self):
        ledger, selected = m._model_rows(self.material)
        row = next(r for r in ledger if r["model_protein"] == "G220")
        self.assertIsNone(row["exact_node_id"])
        self.assertEqual(row["state"], "enriched_identity_unresolved")
        self.assertNotIn("UniProtKB:P00220", {r["exact_node_id"] for r in selected})
        self.assertEqual(m._number("0", "Q_Ab"), 0)
        with self.assertRaises(ValueError):
            m._number("Inf", "Q_Ab")
        with self.assertRaises(ValueError):
            m._number("-0.1", "Q_Ab")

    def test_preparation_preserves_primary_targets_and_binds_candidate_edges_to_publication(self):
        manifest, projection, _ = manifest_fixture(self.material)
        snapshot = {"data_kind": "live_pharos", "content_sha256": "b" * 64}
        baseline = {"snapshot_sha256": "b" * 64, "targets": [{"id": m.BAIT}],
                    "nodes": [{"id": m.BAIT}, {"id": "UniProtKB:P00001"}], "edges": []}
        before = deepcopy(baseline)
        prepared = m.prepare(snapshot, baseline, manifest, projection)
        self.assertEqual(baseline, before)
        self.assertEqual(len(prepared["nodes"]), 119)
        self.assertEqual(len(prepared["edges"]), 120)
        self.assertTrue(all(e["record_kind"] == "tissue_proximity_observation" for e in prepared["edges"]))
        self.assertTrue(all(e["extension_source_kind"] == "mapit" for e in prepared["edges"]))
        self.assertTrue(all(e["extension_publication_sha256"] == manifest["content_sha256"] for e in prepared["edges"]))
        self.assertTrue(all(r["local_review_state"] == "candidate" for r in prepared["observations"]))
        for edge in prepared["edges"]:
            assertion_identity(edge["subject"], edge["predicate"], edge["object"], edge["record_kind"], edge["qualifiers"])
            self.assertTrue(all(n.startswith(m.PREFIX) for n in edge["record_locators"]))
        changed = sealed({**manifest, "new_packaging_note": "another source publication"})
        different = m.prepare(snapshot, baseline, changed, projection)
        self.assertNotEqual(prepared["edges"][0]["id"], different["edges"][0]["id"])
        self.assertNotEqual(prepared["edges"][0]["qualifiers"], different["edges"][0]["qualifiers"])

    def test_anchor_must_be_a_primary_target_not_only_an_incidental_node(self):
        manifest, projection, _ = manifest_fixture(self.material)
        with self.assertRaises(ValueError):
            m.prepare({"data_kind": "live_pharos", "content_sha256": "b" * 64},
                      {"snapshot_sha256": "b" * 64, "targets": [], "nodes": [{"id": m.BAIT}], "edges": []},
                      manifest, projection)

    def test_saved_publication_replays_and_rejects_changed_source_inventory(self):
        manifest, projection, files = manifest_fixture(self.material)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            for name, raw in files.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            (folder / "publication.json").write_bytes(raw_json(manifest))
            loaded, reproduced, _ = m.load_publication(folder)
            self.assertEqual(loaded, manifest)
            self.assertEqual(reproduced, projection)
            (folder / "source/primary/author_full_stats.tsv").write_bytes(b"changed\n")
            with self.assertRaises(ValueError):
                m.load_publication(folder)


if __name__ == "__main__":
    unittest.main()
