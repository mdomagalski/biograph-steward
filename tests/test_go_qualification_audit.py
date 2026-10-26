"""Invented annotations test preservation, identity boundaries and provenance."""
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biograph_steward.client import PharosClient, write_json
from test_pharos_inventory import GENES, InventoryAPI, inventory_fixture, retrieval

SPEC = importlib.util.spec_from_file_location("go_audit", Path(__file__).resolve().parents[1] / "scripts/audit_go_qualification.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def record(**changes):
    fields = ["UniProtKB", "P00001", "G", "NOT|enables", "GO:0000001", "PMID:36949045", "IPI", "UniProtKB:P00002,UniProtKB:P00003|UniProtKB:P00004", "F", "name", "", "protein", "taxon:9606", "20260101", "UniProt", "occurs_in(CL:0000001),part_of(GO:0000002)|occurs_in(CL:0000003)", "P00001-2"]
    for key, value in changes.items():
        fields[int(key)] = value
    parsed = {"Qualifier": fields[3].split("|"), "DB:Reference": fields[5].split("|"), "Evidence": fields[6]}
    return audit.stage_record(9, "\t".join(fields), fields, parsed, {"P00001", "P00002", "P00003"})


class QualificationAuditTests(unittest.TestCase):
    def test_negation_reference_and_grouping_preserved(self):
        row = record()
        self.assertTrue(row["negated"])
        self.assertTrue(row["blocked_reference_present"])
        self.assertEqual(row["raw_fields"][7], "UniProtKB:P00002,UniProtKB:P00003|UniProtKB:P00004")
        self.assertIn(",", row["raw_fields"][15])
        self.assertEqual(row["raw_fields"][16], "P00001-2")
        self.assertEqual(row["with_from_inventory_ids"], ["UniProtKB:P00002", "UniProtKB:P00003"])
        self.assertFalse(row["feature_use_approved"])

    def test_reference_match_is_exact(self):
        self.assertFalse(record(**{"5": "PMID:369490450"})["blocked_reference_present"])

    def test_first_taxon_controls_subject(self):
        self.assertIsNone(record(**{"12": "taxon:10090|taxon:9606"}))
        self.assertIsNotNone(record(**{"12": "taxon:9606|taxon:10090"}))

    def test_no_namespace_or_isoform_collapse(self):
        self.assertIsNone(record(**{"0": "OtherDB"}))
        self.assertIsNone(record(**{"1": "P00001-2"}))

    def test_projected_match_is_not_record_identity(self):
        row = record()
        key = tuple(row["projection_key"])
        self.assertEqual(audit.group_comparison([row], {key: 1}), {"one_to_one_projection": 1})
        self.assertEqual(audit.group_comparison([row, row], {key: 1}), {"multiple_records_projection": 1})
        self.assertFalse(row["record_identity_with_pharos_established"])

    def test_one_sided_groups_stay_separate(self):
        row = record()
        other = ("P00002", "GO:0000009", "IDA", "Other")
        self.assertEqual(audit.group_comparison([row], {other: 1}), {"goa_only_projection": 1, "pharos_only_projection": 1})

    def test_negation_and_exposure_counts_are_stratified_by_projection(self):
        unique = record()
        multiple = record(**{"4": "GO:0000002"})
        unmatched = record(**{"4": "GO:0000003"})
        for row in (unique, multiple, unmatched):
            row["reserved_pair_exposure"] = audit.exposure_diagnostics(row, {("P00001", "P00002"): ["candidate:1"]})
        details = audit.group_details([unique, multiple, multiple, unmatched],
            {tuple(unique["projection_key"]): 1, tuple(multiple["projection_key"]): 1}, True)
        self.assertEqual(details["one_to_one_projection"]["negated_goa_rows"], 1)
        self.assertEqual(details["multiple_records_projection"]["negated_goa_rows"], 2)
        self.assertEqual(details["goa_only_projection"]["with_from_reserved_pair_goa_rows"], 1)
        no_mask = audit.group_details([unique], {tuple(unique["projection_key"]): 1})
        self.assertIsNone(no_mask["one_to_one_projection"]["with_from_reserved_pair_goa_rows"])

    def test_malformed_column_count_cannot_be_silently_zipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.gaf.gz"
            with gzip.open(path, "wt") as handle:
                handle.write("!gaf-version: 2.2\nshort\trow\n")
            with self.assertRaisesRegex(ValueError, "expected 17"):
                list(audit.source_rows(path))

    def test_duplicate_source_records_are_not_erased(self):
        raw = record()["raw_line"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "same.gaf.gz"
            with gzip.open(path, "wt") as handle:
                handle.write("!gaf-version: 2.2\n" + raw + "\n" + raw + "\n")
            self.assertEqual([r[0] for r in audit.source_rows(path)], [2, 3])

    def test_reserved_pairs_include_reverse_and_self(self):
        row = record(**{"7": "UniProtKB:P00002,UniProtKB:P00001"})
        pairs = {("P00001", "P00002"): ["candidate:1"], ("P00001", "P00001"): ["candidate:2"]}
        hits = audit.exposure_diagnostics(row, pairs)["with_from"]
        self.assertEqual({tuple(r["unordered_product_pair"]) for r in hits}, set(pairs))
        reverse = record(**{"1": "P00002", "7": "UniProtKB:P00001"})
        self.assertEqual(audit.exposure_diagnostics(reverse, pairs)["with_from"][0]["candidate_ids"], ["candidate:1"])

    def test_extension_scan_does_not_claim_semantics_or_collapse_isoforms(self):
        extension = "has_input(UniProtKB:P00002),occurs_in(CL:0000001)|has_input(UniProtKB:P00002-2)"
        row = record(**{"15": extension})
        hits = audit.exposure_diagnostics(row, {("P00001", "P00002"): ["candidate:1"]})
        self.assertEqual(len(hits["extension"]), 1)
        self.assertEqual(row["raw_fields"][15], extension)
        self.assertEqual(row["extension_unresolved_identifiers"], ["CL:0000001", "UniProtKB:P00002-2"])
        self.assertFalse(row["extension_identifier_scan_is_semantic_validation"])

    def test_mask_and_inventory_hashes_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlaps.json"
            mask = {"format": "biograph-steward.pharos-pair-mask-inventory.v1",
                    "equivalent_product_pairs": [{"products": ["P00002", "P00001"], "candidate_ids": ["candidate:1"]}]}
            path.write_text(json.dumps(mask))
            report = {"format": "biograph-steward.pharos-inventory-audit.v1",
                      "inventory_sha256": "inventory", "overlaps_sha256": audit.digest(mask)}
            receipt = {"retrieval_plan_sha256": "plan", "retrieval_summary_sha256": "summary",
                       "db_version": "synthetic", "input_files": {}, "chunk_files": {}}
            report.update(receipt)
            report["content_sha256"] = audit.digest(report)
            path.with_name("report.json").write_text(json.dumps(report))
            pairs, _ = audit.load_pair_mask(path, "inventory", {"P00001", "P00002"}, receipt)
            self.assertEqual(pairs, {("P00001", "P00002"): ["candidate:1"]})
            with self.assertRaisesRegex(ValueError, "different accession inventory"):
                audit.load_pair_mask(path, "other", {"P00001", "P00002"}, receipt)
            mask["equivalent_product_pairs"][0]["products"] = ["P00001", "P00001"]
            path.write_text(json.dumps(mask))
            with self.assertRaisesRegex(ValueError, "differs from its sealed report"):
                audit.load_pair_mask(path, "inventory", {"P00001", "P00002"}, receipt)
            report["inventory_sha256"] = "tampered"
            path.with_name("report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "report digest mismatch"):
                audit.load_pair_mask(path, "tampered", {"P00001", "P00002"}, receipt)


class RetrievalBindingTests(unittest.TestCase):
    """Resealed counterexamples must fail population/source binding, not just hashes."""

    def setUp(self):
        import audit_pharos_inventory as inventory_audit
        from audit_inmc_inputs import PANEL_HEADER
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.archive = self.root / "synthetic.zip"
        # Deliberately undecodable outcome fields prove the real producer only
        # decodes the two identity columns when making this integration fixture.
        panel = PANEL_HEADER + b"\n" + b"".join(
            f"{a}\t{b}\t".encode("ascii") + b"\xff\t\xff\t\xff\t\xff\n"
            for a, b in zip(GENES[::2], GENES[1::2]))
        with zipfile.ZipFile(self.archive, "w") as bundle:
            bundle.writestr(inventory_audit.PANEL_MEMBER, panel)
        archive_hash = audit.sha(self.archive)
        pin = patch.object(inventory_audit, "ARCHIVE_SHA256", archive_hash)
        pin.start()
        self.addCleanup(pin.stop)
        inventory = inventory_fixture()
        inventory["archive_sha256"] = archive_hash
        self.inventory = self.root / "inventory.json"
        write_json(self.inventory, inventory)
        self.accessions = {r["uniprot_id"].removeprefix("UniProtKB:") for r in inventory["targets"]}
        self.inventory_hash = audit.sha(self.inventory)
        self.folder = self.root / "retrieval"
        self.api = InventoryAPI()
        retrieval.retrieve_inventory(self.inventory, self.folder, chunk_size=1, progress=None,
                                     client_factory=lambda: PharosClient(transport=self.api))
        self.paths = sorted((self.folder / "chunks").glob("*.json"))

    def groups(self, paths=None, inventory_hash=None, accessions=None):
        return audit.pharos_groups(self.paths if paths is None else paths,
                                   inventory_hash or self.inventory_hash,
                                   self.accessions if accessions is None else accessions)

    def replace_sealed(self, path, transform):
        value = retrieval.read_json(path)
        value.pop("content_sha256")
        transform(value)
        write_json(path, retrieval.seal(value))

    def replace_chunk(self, transform):
        path = self.paths[0]
        self.replace_sealed(path, transform)
        self.replace_sealed(self.folder / "summary.json",
                            lambda value: value["files"].update({"chunks/00000.json": audit.sha(path)}))

    def mask(self, receipt, **changes):
        path = self.root / "mask" / "overlaps.json"
        mask = {"format": "biograph-steward.pharos-pair-mask-inventory.v1",
                "equivalent_product_pairs": [{"products": ["P00533", "P04637"],
                                               "candidate_ids": ["candidate:1"]}]}
        write_json(path, mask)
        report = {"format": "biograph-steward.pharos-inventory-audit.v1",
                  "inventory_sha256": self.inventory_hash, "overlaps_sha256": audit.digest(mask),
                  **{key: receipt[key] for key in ("retrieval_plan_sha256", "retrieval_summary_sha256",
                                                  "db_version", "input_files", "chunk_files")}, **changes}
        write_json(path.with_name("report.json"), retrieval.seal(report))
        return path

    def test_completed_inventory_bound_retrieval_is_accepted(self):
        groups, targets, files, receipt = self.groups()
        self.assertEqual(targets, {"P00533", "P04637"})
        self.assertEqual(sum(groups.values()), 1)
        self.assertEqual(len(files), 4)
        self.assertEqual(receipt["inventory_sha256"], self.inventory_hash)
        path = self.mask(receipt)
        pairs, bound = audit.load_pair_mask(path, self.inventory_hash, self.accessions, receipt)
        self.assertEqual(pairs, {("P00533", "P04637"): ["candidate:1"]})
        self.assertEqual(bound["retrieval_plan_sha256"], receipt["retrieval_plan_sha256"])

    def test_resealed_chunk_from_another_plan_is_rejected(self):
        self.replace_chunk(lambda value: value.update(plan_sha256="another-plan"))
        with self.assertRaisesRegex(ValueError, "plan binding"):
            self.groups()

    def test_resealed_chunk_with_another_source_version_is_rejected(self):
        self.replace_chunk(lambda value: value.update(db_version_before="pharos-other", db_version_after="pharos-other"))
        with self.assertRaisesRegex(ValueError, "version, or plan binding"):
            self.groups()

    def test_summary_source_version_must_agree(self):
        self.replace_sealed(self.folder / "summary.json", lambda value: value.update(db_versions=["pharos-other"]))
        with self.assertRaisesRegex(ValueError, "source versions"):
            self.groups()

    def test_unrelated_inventory_or_population_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "different accession inventory"):
            self.groups(inventory_hash="another-inventory")
        with self.assertRaisesRegex(ValueError, "different accession inventory"):
            self.groups(accessions=self.accessions | {"P00001"})

    def test_unrelated_target_and_requested_accessions_are_rejected(self):
        self.replace_chunk(lambda value: value["targets"][0].update(uniprot="P00001"))
        with self.assertRaisesRegex(ValueError, "targets differ from resolved"):
            self.groups()
        self.replace_chunk(lambda value: value.update(requested_uniprots=["P00001"]))
        with self.assertRaisesRegex(ValueError, "identity, version, or plan binding"):
            self.groups()

    def test_subset_or_mixed_directory_cannot_be_joined(self):
        with self.assertRaisesRegex(ValueError, "manifest chunks"):
            self.groups(paths=self.paths[:-1])
        other = self.root / "other" / "chunks" / self.paths[0].name
        other.parent.mkdir(parents=True)
        other.write_bytes(self.paths[0].read_bytes())
        with self.assertRaisesRegex(ValueError, "one completed retrieval"):
            self.groups(paths=[other, *self.paths[1:]])

    def test_unfinished_retrieval_is_rejected(self):
        self.replace_sealed(self.folder / "summary.json", lambda value: value.update(retrieval_finished=False))
        with self.assertRaisesRegex(ValueError, "completed explicit-accession"):
            self.groups()

    def test_mask_cannot_come_from_another_retrieval(self):
        *_, receipt = self.groups()
        for field in ("retrieval_plan_sha256", "retrieval_summary_sha256", "db_version"):
            with self.subTest(field=field):
                path = self.mask(receipt, **{field: "another-retrieval"})
                with self.assertRaisesRegex(ValueError, "different retrieval"):
                    audit.load_pair_mask(path, self.inventory_hash, self.accessions, receipt)
        for field in ("input_files", "chunk_files"):
            with self.subTest(field=field):
                path = self.mask(receipt, **{field: {}})
                with self.assertRaisesRegex(ValueError, "different saved retrieval files"):
                    audit.load_pair_mask(path, self.inventory_hash, self.accessions, receipt)
        with self.assertRaisesRegex(ValueError, "requires the same completed"):
            audit.load_pair_mask(path, self.inventory_hash, self.accessions, None)

    def test_actual_inventory_audit_report_is_accepted(self):
        import audit_pharos_inventory as inventory_audit
        report, overlaps = inventory_audit.audit(self.folder, self.archive)
        path = self.root / "actual-audit" / "overlaps.json"
        write_json(path, overlaps)
        write_json(path.with_name("report.json"), report)
        *_, receipt = self.groups()
        pairs, bound = audit.load_pair_mask(path, self.inventory_hash, self.accessions, receipt)
        expected = {tuple(sorted(row["products"])): sorted(row["candidate_ids"])
                    for row in overlaps["equivalent_product_pairs"]}
        self.assertEqual(pairs, expected)
        self.assertEqual(bound["retrieval_summary_sha256"], report["retrieval_summary_sha256"])
        self.assertIn("input_files", report)
        self.assertNotIn("files", report)
        wrong_schema = dict(report)
        wrong_schema.pop("content_sha256")
        wrong_schema["files"] = wrong_schema.pop("input_files")
        write_json(path.with_name("report.json"), retrieval.seal(wrong_schema))
        with self.assertRaisesRegex(ValueError, "different saved retrieval files"):
            audit.load_pair_mask(path, self.inventory_hash, self.accessions, receipt)

    def test_source_only_and_completed_join_parser_paths(self):
        # The parser is intentionally isolated from the core app environment.
        # All identity/provenance tests above run without this optional package.
        try:
            import Bio
        except ModuleNotFoundError as exc:
            if exc.name != "Bio":
                raise
            self.skipTest("Optional parser integration requires isolated Biopython 1.88.")
        if Bio.__version__ != "1.88":
            self.skipTest("Optional parser integration requires pinned Biopython 1.88.")
        gaf = self.root / "synthetic.gaf.gz"
        fields = record()["raw_fields"]
        fields[1], fields[7] = "P00533", "UniProtKB:P04637"
        with gzip.open(gaf, "wt") as handle:
            handle.write("!gaf-version: 2.2\n" + "\t".join(fields) + "\n")
        source = audit.audit(gaf, self.inventory, self.root / "source-only")
        self.assertIsNone(source["inputs"]["pharos_retrieval"])
        self.assertFalse(source["pair_overlap_evaluated"])
        self.assertIn("Reserved-pair overlap was not evaluated", source["interpretation"])
        *_, receipt = self.groups()
        joined = audit.audit(gaf, self.inventory, self.root / "joined", self.paths, self.mask(receipt))
        self.assertEqual(joined["pharos_compared_accessions"], 2)
        self.assertEqual(joined["pair_exposure_counts"]["with_from_rows"], 1)
        self.assertEqual(joined["inputs"]["pharos_retrieval"], receipt)
        self.assertIn("identify exact literal accession matches", joined["interpretation"])
        self.assertNotIn("overlap was not evaluated", joined["interpretation"])
