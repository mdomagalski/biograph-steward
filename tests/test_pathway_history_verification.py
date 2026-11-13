"""Invented archive/identifier fixtures: integrity controls, no biology labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biograph_steward.client import digest, write_json
from biograph_steward.cohort_mapping import collect_registry
from biograph_steward.file_utils import sha
from biograph_steward.wiki_history import load_history_packet, query_history
from tools.pathway_history import verify
from test_cohort_mapping import gene, protein, tsv
from test_pathway_history_models import model_xml


def seal(path, value):
    value = deepcopy(value)
    value["content_sha256"] = digest(value)
    write_json(path, value)
    return value


class HistoryVerificationTests(unittest.TestCase):
    def fixture(self, root, *, conflict=False):
        root = Path(root)
        (root / "source").mkdir()
        (root / "archives").mkdir()
        graph = {"edges": []}
        resources = []
        for number, (source_id, decision) in enumerate([("WP1_r99", "keep"), ("WP2_r100", "prune"), ("WP3_r101", "abstain")], 1):
            rows = []
            # Repeated source records remain separate evidence identities.
            for suffix in range(2 if number == 1 else 1):
                edge = {"id": f"edge:{number}-{suffix}", "subject": "UniProtKB:P04637", "assertion_id": f"assertion:{number}",
                    "object": "pharos.pathway:" + str(number), "record_kind": "pathway_membership",
                    "record_locators": [{"file": "invented", "row": number}],
                    "evidence_record": {"type": "WikiPathways", "sourceID": source_id, "pwid": number}}
                graph["edges"].append(edge)
                rows.append({"edge_id": edge["id"], "subject": edge["subject"], "assertion_id": edge["assertion_id"],
                    "local_object": edge["object"], "native_pwid": number,
                    "source_locators": edge["record_locators"], "raw_record_sha256": digest(edge["evidence_record"]),
                    "current_membership_decision": decision})
            wpid, revision = source_id.split("_r")
            resources.append({"provider": "WikiPathways", "full_source_id": source_id,
                "canonical_wpid": wpid, "requested_revision": revision, "evidence_edges": rows})
        write_json(root / "graph.json", graph)
        current = seal(root / "current.json", {"format": "biograph-steward.current-wikipathways-view.v1",
            "source_decisions": [{"edge_id": r["edge_id"], "decision": r["current_membership_decision"]}
                                 for resource in resources for r in resource["evidence_edges"]]})
        inventory = seal(root / "inventory.json", {"format": verify.INVENTORY_FORMAT,
            "source_graph_path": str(root / "graph.json"), "source_graph_file_sha256": sha(root / "graph.json"),
            "current_source_view_report_path": str(root / "current.json"),
            "current_source_view_report_file_sha256": sha(root / "current.json"),
            "current_source_view_content_sha256": current["content_sha256"], "versions": resources,
            "distinct_version_count": 3, "native_edge_count": 4})
        documents = {}
        for key in ("archive_exporter", "monthly_release_producer", "gpml2013a_schema",
                    "bridgedb_datasources", "bridgedb_datasource_columns", "bridgedb_system_codes"):
            path = root / "source" / (key + ".txt")
            path.write_text("Invented software fixture " + key)
            documents[key] = {"file": path.relative_to(root).as_posix(), "sha256": sha(path)}
        rows = []
        for code in ("S", "L", "H", "Hac", "En"):
            row = [""] * 14
            row[0], row[1] = "Invented", code
            row[5] = "protein" if code == "S" else "gene"
            row[8] = {"H": "urn:miriam:hgnc.symbol", "Hac": "urn:miriam:hgnc"}.get(code, "invented")
            rows.append("\t".join(row))
        datasource = root / documents["bridgedb_datasources"]["file"]
        datasource.write_text("\n".join(rows) + "\n")
        documents["bridgedb_datasources"]["sha256"] = sha(datasource)
        archive_specs, records = [], []
        for index in range(2 if conflict else 1):
            path = root / "archives" / (f"invented-{index}.zip")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("Hs_Invented_WP1_99.gpml", model_xml(identifier="2" if index else "1"))
                z.writestr("Hs_Invented_WP2_100.gpml", model_xml(database="UniProtKB", identifier="P04637"))
                # A modern date suffix never supplies a legacy revision.
                z.writestr("Hs_Invented_WP3_20251203.gpml", model_xml())
            checksum = "md5:" + hashlib.md5(path.read_bytes()).hexdigest()
            url = "https://zenodo.org/api/records/1/files/" + path.name + "/content"
            doi = f"10.5281/zenodo.{index+1}"
            records.append({"doi": doi, "metadata": {"license": {"id": "cc-zero"}},
                "files": [{"key": path.name, "checksum": checksum, "size": path.stat().st_size, "links": {"self": url}}]})
            archive_specs.append({"file": path.relative_to(root).as_posix(), "sha256": sha(path), "url": url,
                "publisher_checksum": checksum, "record_DOI": doi, "license": {"id": "cc-zero"},
                "archive_release": "20190110"})
        write_json(root / "source" / "metadata.json", {"hits": {"hits": records}})
        seal(root / "sources.json", {"format": verify.SOURCES_FORMAT, "source_documents": documents,
            "archives": archive_specs, "metadata_pages": [{"file": "source/metadata.json", "sha256": sha(root / "source" / "metadata.json")}]})
        raw = {"hgnc_complete_set.txt": tsv([gene("HGNC:1", "INVENTED", products="P04637")]),
               "uniprot_reviewed_human_symbols.tsv": tsv([protein("P04637", "HGNC:1", "INVENTED")])}
        registry = collect_registry(root / "registry", transport=lambda url: (next(v for k, v in raw.items()
            if ("storage.googleapis.com" in url) == (k == "hgnc_complete_set.txt")), {}))
        return {"inventory_path": root / "inventory.json", "sources_path": root / "sources.json",
            "registry_directory": root / "registry", "inventory_sha256": sha(root / "inventory.json"),
            "sources_sha256": sha(root / "sources.json"), "registry_sha256": registry["registry_sha256"]}, documents

    def run_fixture(self, args, documents, out, validator=None):
        pins = {key: documents[key]["sha256"] for key in verify.REVIEWED_PINS}
        validator = validator or (lambda raw: {"executed": True, "passed": True, "synthetic_mock": True})
        with patch.object(verify, "REVIEWED_PINS", pins), patch.object(verify, "official_schema_validator", return_value=validator):
            return verify.verify_history(output=out, **args)

    def test_full_denominators_literal_scope_and_offline_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, documents = self.fixture(root)
            original = (root / "graph.json").read_bytes()
            report = self.run_fixture(args, documents, root / "out")
            self.assertEqual((root / "graph.json").read_bytes(), original)
            self.assertEqual(report["counts"]["original_rows"], 4)
            self.assertEqual(report["counts"]["original_unique_subject_version_connections"], 3)
            self.assertEqual(report["counts"]["exact_publisher_bound_versions"], 2)
            self.assertEqual(report["counts"]["original_row_statuses"], {
                "compatible_gene_level_xref": 2, "explicitly_encoded_protein_xref": 1, "unresolved": 1})
            packet = load_history_packet(root / "out", expected_content_sha256=report["content_sha256"])
            result = query_history(packet, "UniProtKB:P04637", "WP1_r99")
            self.assertEqual(result["status"], "compatible_gene_level_xref")
            self.assertFalse(result["model"]["author_schema_validation"]["executed"])
            self.assertFalse(result["schema_reexecuted_in_consumer"])
            self.assertEqual(query_history(packet, "UniProtKB:P04637", "WP3_r101")["status"], "unresolved")
            # Source/native/current-view labels are separate; source-positive
            # WP2 remains reported even where the invented current view prunes.
            self.assertEqual(query_history(packet, "UniProtKB:P04637", "WP2_r100")["status"], "explicitly_encoded_protein_xref")

    def test_conflicting_exact_publisher_content_abstains_without_cherry_pick(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, docs = self.fixture(root, conflict=True)
            report = self.run_fixture(args, docs, root / "out")
            self.assertEqual(report["counts"]["models_with_conflicting_byte_hashes"], 1)
            packet = load_history_packet(root / "out", expected_content_sha256=report["content_sha256"])
            self.assertEqual(query_history(packet, "UniProtKB:P04637", "WP1_r99")["status"], "unresolved")

    def test_source_mutation_during_execution_leaves_no_success_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, docs = self.fixture(root)
            def mutate(raw):
                (root / docs["bridgedb_system_codes"]["file"]).write_text("changed during validation")
                return {"executed": True, "passed": True, "synthetic_mock": True}
            with self.assertRaisesRegex(ValueError, "changed"):
                self.run_fixture(args, docs, root / "out", validator=mutate)
            self.assertFalse((root / "out" / "historical_verification.json").exists())

    def test_publisher_checksum_mismatch_fails_before_materialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, docs = self.fixture(root)
            source = json.loads((root / "sources.json").read_text())
            source.pop("content_sha256")
            source["archives"][0]["publisher_checksum"] = "md5:" + "0" * 32
            seal(root / "sources.json", source)
            args["sources_sha256"] = sha(root / "sources.json")
            with self.assertRaisesRegex(ValueError, "publisher metadata"):
                self.run_fixture(args, docs, root / "out")
            self.assertFalse((root / "out").exists())

    def test_portable_proof_tampering_and_wrong_expected_seal_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, docs = self.fixture(root)
            report = self.run_fixture(args, docs, root / "out")
            with self.assertRaisesRegex(ValueError, "seal or format"):
                load_history_packet(root / "out", expected_content_sha256="0" * 64)
            path = root / "out" / "archives" / "invented-0.zip"
            path.write_bytes(path.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "proof missing or changed"):
                load_history_packet(root / "out", expected_content_sha256=report["content_sha256"])


if __name__ == "__main__":
    unittest.main()
