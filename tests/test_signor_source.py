"""Synthetic stable-schema sources; no model, network or saved research labels.

Publication tests patch the official release digest to their invented fixture.
Production accepts only the pinned complete official release bytes.
"""
from copy import deepcopy
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward import signor_source as signor


def sealed(value):
    value = {key: item for key, item in value.items() if key != "content_sha256"}
    return {**value, "content_sha256": digest(value)}


def source_row(number, a="P00533", b="P01116", **changes):
    row = {key: "" for key in signor.COLUMNS}
    row.update(ENTITYA="invented regulator", TYPEA="protein", IDA=a, DATABASEA="UNIPROT",
        ENTITYB="invented target", TYPEB="protein", IDB=b, DATABASEB="UNIPROT",
        EFFECT="up-regulates activity", MECHANISM="phosphorylation", RESIDUE="Ser1", SEQUENCE="invented",
        TAX_ID="9606", PMID=str(100 + number), DIRECT="t", ANNOTATOR="invented",
        SENTENCE="Invented fixture, not a biological assertion.", SIGNOR_ID="SIGNOR-" + str(number))
    row.update(changes)
    return row


def source_bytes(rows, columns=None):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns or signor.COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def source_fixture():
    return [source_row(1, CELL_DATA="BTO:0000567"),
        source_row(2, a="P01116", b="P00533", EFFECT="down-regulates activity", MECHANISM="binding", DIRECT="f",
            CELL_DATA="BTO:0000007;BTO:0000093", TISSUE_DATA="BTO:0000150",
            SENTENCE='Invented sentence with "quotes"\nand a second physical line.'),
        source_row(3, a="P01116", b="P01116", EFFECT="unknown", RESIDUE="Thr2"),
        source_row(4, b="P15056"), source_row(5, b="P15056", RESIDUE="Tyr3"),
        source_row(6, b="P04637"), source_row(7, b="P04637", TAX_ID="10090"),
        source_row(8, TYPEA="proteinfamily"), source_row(9, DATABASEA="SIGNOR"),
        source_row(10, a="P00533;P01116")]


def baseline():
    accessions = ["P00533", "P01116", "P15056"]
    snapshot = sealed({"data_kind": "live_pharos", "targets": [{"uniprot": uid} for uid in accessions]})
    graph = {"snapshot_sha256": snapshot["content_sha256"],
        "nodes": [{"id": "UniProtKB:" + uid, "category": "biolink:Protein"} for uid in accessions],
        "edges": [{"id": "existing", "subject": "UniProtKB:P01116", "object": "UniProtKB:P00533",
            "record_kind": "protein_interaction", "symmetric": True, "original_score": 0.8}],
        "targets": [{"id": "UniProtKB:" + uid} for uid in accessions],
        "review_events": [{"original": "illustrative prior review"}]}
    return snapshot, graph


def pubmed_xml(pmids=range(101, 106)):
    """Invented PubMed metadata: missing Review type must not mean primary."""
    articles = []
    for pmid in pmids:
        types = "<PublicationType>Review</PublicationType>" if pmid == 101 else "<PublicationType>Journal Article</PublicationType>"
        correction = '<CommentsCorrectionsList><CommentsCorrections RefType="ErratumIn"><PMID>999</PMID></CommentsCorrections></CommentsCorrectionsList>' if pmid == 102 else ""
        articles.append(f'<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>Invented title {pmid}</ArticleTitle><Abstract><AbstractText>In this review, an invented fixture.</AbstractText></Abstract><PublicationTypeList>{types}</PublicationTypeList></Article>{correction}</MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="pubmed">{pmid}</ArticleId></ArticleIdList></PubmedData></PubmedArticle>')
    return ("<PubmedArticleSet>" + "".join(articles) + "</PubmedArticleSet>").encode()


class SignorSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "invented.tsv"
        self.publication = self.root / "publication"
        self.raw = source_bytes(source_fixture())
        self.source.write_bytes(self.raw)
        fixture_digest = patch.object(signor, "RELEASE_SHA256", signor._sha(self.raw))
        fixture_digest.start()
        self.addCleanup(fixture_digest.stop)

    def publish(self):
        snapshot, graph = baseline()
        signor.publish_release(self.source, snapshot, self.publication)
        manifest, projection, files = signor.load_publication(self.publication)
        return snapshot, graph, manifest, projection, files

    def test_full_raw_replay_and_every_selected_field_preserved(self):
        snapshot, graph, manifest, projection, files = self.publish()
        self.assertEqual(files[signor.RAW_FILE], self.raw)
        self.assertEqual(projection["summary"]["source_rows"], 10)
        self.assertEqual(projection["summary"]["qualified_regulatory_observations"], 5)
        self.assertEqual(sum(projection["summary"]["source_row_states"].values()), 10)
        self.assertEqual([r["source_row"] for r in projection["observations"]], source_fixture()[:5])
        self.assertEqual(projection["observations"][1]["source_data_record_ordinal"], 2)
        self.assertEqual(projection["observations"][2]["source_data_record_ordinal"], 3)
        self.assertEqual(projection["observations"][1]["source_row"]["SENTENCE"], source_fixture()[1]["SENTENCE"])
        self.assertEqual(manifest["source_license"]["license"], "CC-BY-4.0")
        self.assertEqual(manifest["citations"][0]["role"], "resource_publication")
        result = signor.prepare(snapshot, graph, manifest, projection)
        for edge in result["edges"]:
            original = next(row for row in source_fixture() if row["SIGNOR_ID"] == edge["observation"]["source_record_id"])
            self.assertEqual(edge["evidence_record"]["source_row"], original)
            self.assertEqual(edge["subject"], "UniProtKB:" + original["IDA"])
            self.assertEqual(edge["object"], "UniProtKB:" + original["IDB"])
            self.assertEqual(edge["qualifiers"]["regulatory_effect"], original["EFFECT"] or None)
            self.assertEqual(edge["qualifiers"]["regulatory_mechanism"], original["MECHANISM"] or None)
            self.assertEqual(edge["qualifiers"]["cell_line"], original["CELL_DATA"] or None)
            self.assertEqual(edge["qualifiers"]["tissue"], original["TISSUE_DATA"] or None)
            self.assertEqual(edge["publications"], ["PMID:" + original["PMID"]])
            self.assertFalse(edge["symmetric"])
            self.assertFalse(edge["biologically_validated"])
            self.assertEqual(edge["lifecycle_state"], "candidate")
            self.assertEqual(edge["data_kind"], "published_database_annotations")
            self.assertEqual(edge["record_kind"], "source_regulatory_observation")
            self.assertTrue(edge["record_locators"][0].startswith("extension_sources/signor/source/Oct2026_release.txt#data-record="))

    def test_overlap_counts_pairs_separately_from_records_and_self_regulation(self):
        snapshot, graph, manifest, projection, _ = self.publish()
        before = deepcopy((snapshot, graph, manifest, projection))
        result = signor.prepare(snapshot, graph, manifest, projection)
        self.assertEqual((snapshot, graph, manifest, projection), before)
        self.assertEqual(result["nodes"], [])
        summary = result["summary"]
        self.assertEqual(summary["additional_source_records"], 5)
        self.assertEqual(summary["new_workspace_pairs"], 1)
        self.assertEqual(summary["new_pair_source_records"], 2)
        self.assertEqual(summary["existing_workspace_pairs_with_new_source_record"], 1)
        self.assertEqual(summary["existing_pair_source_records"], 2)
        self.assertEqual(summary["self_regulatory_records"], 1)
        self.assertEqual(summary["self_regulatory_participants"], 1)
        self.assertEqual(summary["integrated_self_regulatory_records"], 1)
        self.assertIsNone(summary["independent_evidence_count"])
        self.assertFalse(summary["biological_validation_performed"])
        self.assertFalse(summary["automatic_acceptance_performed"])

    def test_tf_directness_and_missing_context_are_not_inferred(self):
        snapshot, graph, manifest, projection, _ = self.publish()
        result = signor.prepare(snapshot, graph, manifest, projection)
        by_id = {row["source_record_id"]: row for row in result["observations"]}
        self.assertIs(by_id["SIGNOR-1"]["source_reported_direct"], True)
        self.assertIs(by_id["SIGNOR-2"]["source_reported_direct"], False)
        self.assertEqual(by_id["SIGNOR-2"]["direct_literal"], "f")
        self.assertEqual(by_id["SIGNOR-2"]["cell_context_raw"], "BTO:0000007;BTO:0000093")
        self.assertEqual(by_id["SIGNOR-3"]["cell_context_raw"], "")
        self.assertEqual(by_id["SIGNOR-3"]["cell_context_reporting"], "unreported")
        self.assertEqual(by_id["SIGNOR-3"]["effect_literal"], "unknown")
        self.assertEqual(by_id["SIGNOR-3"]["mechanism_literal"], "phosphorylation")
        self.assertTrue(by_id["SIGNOR-3"]["self_regulation"])
        self.assertNotIn("confidence", by_id["SIGNOR-1"])

    def test_unknown_directness_is_rejected_not_converted_to_false(self):
        for value in ("", "unknown", "YES", "TRUE"):
            row = source_row(11, DIRECT=value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "unknown directness"):
                signor.parse_release(source_bytes([row]), ["P00533", "P01116"])

    def test_exact_27_header_and_record_shape_are_required(self):
        for columns in (signor.COLUMNS[:-1], (*signor.COLUMNS, "SCORE"), tuple(reversed(signor.COLUMNS))):
            raw = ("\t".join(columns) + "\n").encode()
            with self.subTest(columns=columns), self.assertRaisesRegex(ValueError, "27-column"):
                signor.parse_release(raw, ["P00533"])
        with self.assertRaisesRegex(ValueError, "malformed"):
            signor.parse_release(("\t".join(signor.COLUMNS) + "\nP00533\tbroken\n").encode(), ["P00533"])

    def test_no_family_expansion_alias_matching_or_isoform_collapse(self):
        rows = [source_row(1, a="P00533-2"), source_row(2, a="EGFR"),
            source_row(3, TYPEB="complex"), source_row(4, TAX_ID="-1")]
        parsed = signor.parse_release(source_bytes(rows), ["P00533", "P01116"])
        self.assertEqual(len(parsed["records"]), 1)
        self.assertEqual(parsed["records"][0]["source_experimental_organism_raw"], "-1")
        self.assertEqual(parsed["records"][0]["source_experimental_organism_reporting_state"], "source_reported_in_vitro")
        self.assertEqual(parsed["row_states"], {"outside_primary_cohort": 1, "nonexact_accession": 1,
            "nonprotein_participant": 1, "selected_primary_cohort_protein_regulation": 1})
        exact = signor.parse_release(source_bytes([rows[0]]), ["P00533-2", "P01116"])
        self.assertEqual(exact["records"][0]["products"][0], "UniProtKB:P00533-2")

    def test_all_source_organisms_are_retained_separate_from_human_participants(self):
        organisms = ["9606", "10090", "-1", "", "-99", "0", "001", "unknown"]
        raw = source_bytes([source_row(i + 20, TAX_ID=organism) for i, organism in enumerate(organisms)])
        self.source.write_bytes(raw)
        snapshot, graph = baseline()
        with patch.object(signor, "RELEASE_SHA256", signor._sha(raw)):
            signor.publish_release(self.source, snapshot, self.publication)
            manifest, projection, _ = signor.load_publication(self.publication)
            result = signor.prepare(snapshot, graph, manifest, projection)
        self.assertEqual(len(result["edges"]), len(organisms))
        self.assertFalse(result["summary"]["source_experimental_organisms_used_for_selection"])
        self.assertFalse(result["summary"]["assay_host_taxon_inferred"])
        self.assertEqual(result["summary"]["source_experimental_organism_raw_counts"], {organism: 1 for organism in organisms})
        by_organism = {row["source_experimental_organism_raw"]: row for row in result["observations"]}
        for raw_organism, row in by_organism.items():
            self.assertEqual(row["participant_taxon"], "NCBITaxon:9606")
            self.assertIn("primary Pharos human-protein cohort", row["participant_taxon_basis"])
            self.assertIsNone(row["assay_host_taxon"])
            self.assertEqual(row["source_row"]["TAX_ID"], raw_organism)
        self.assertEqual(by_organism["10090"]["source_experimental_taxon"], "NCBITaxon:10090")
        self.assertEqual(by_organism["9606"]["source_experimental_taxon"], "NCBITaxon:9606")
        self.assertEqual(by_organism["-1"]["source_experimental_organism_reporting_state"], "source_reported_in_vitro")
        self.assertIsNone(by_organism["-1"]["source_experimental_taxon"])
        self.assertEqual(by_organism[""]["source_experimental_organism_reporting_state"], "unreported")
        for organism in ("-99", "0", "001", "unknown"):
            self.assertEqual(by_organism[organism]["source_experimental_organism_reporting_state"], "raw_unresolved")
            self.assertIsNone(by_organism[organism]["source_experimental_taxon"])
        self.assertTrue(all(edge["qualifiers"]["species"] == "NCBITaxon:9606" for edge in result["edges"]))

    def test_v2_contract_does_not_silently_load_archived_human_only_v1(self):
        self.publish()
        path = self.publication / "publication.json"
        manifest = json.loads(path.read_text())
        manifest["format"] = "biograph-steward.signor-source-publication.v1"
        write_json(path, sealed(manifest))
        with self.assertRaisesRegex(ValueError, "unsupported source publication contract"):
            signor.load_publication(self.publication)

    def test_source_record_identity_and_publication_must_be_exact(self):
        for row in (source_row(1, PMID="PMID:101"), source_row(1, SIGNOR_ID="")):
            with self.subTest(row=row), self.assertRaises(ValueError):
                signor.parse_release(source_bytes([row]), ["P00533", "P01116"])
        with self.assertRaisesRegex(ValueError, "repeated"):
            signor.parse_release(source_bytes([source_row(1), source_row(1)]), ["P00533", "P01116"])

    def test_missing_graph_node_does_not_add_a_participant(self):
        snapshot, graph, manifest, projection, _ = self.publish()
        graph["nodes"] = [node for node in graph["nodes"] if node["id"] != "UniProtKB:P15056"]
        result = signor.prepare(snapshot, graph, manifest, projection)
        self.assertEqual(result["nodes"], [])
        self.assertEqual(len(result["edges"]), 3)
        self.assertEqual(result["summary"]["integration_state_counts"]["endpoint_outside_resolved_cohort"], 2)

    def test_snapshot_cohort_and_seal_changes_are_rejected(self):
        snapshot, graph, manifest, projection, _ = self.publish()
        snapshot["targets"].pop()
        with self.assertRaisesRegex(ValueError, "sealed"):
            signor.prepare(snapshot, graph, manifest, projection)
        snapshot = sealed(snapshot)
        graph["snapshot_sha256"] = snapshot["content_sha256"]
        with self.assertRaisesRegex(ValueError, "exactly this primary"):
            signor.prepare(snapshot, graph, manifest, projection)

    def test_wrong_raw_bytes_and_raw_tampering_are_rejected(self):
        snapshot, _ = baseline()
        self.source.write_bytes(self.raw + b"unexpected")
        with self.assertRaisesRegex(ValueError, "pinned complete official"):
            signor.publish_release(self.source, snapshot, self.publication)
        self.source.write_bytes(self.raw)
        self.publish()
        path = self.publication / signor.RAW_FILE
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.assertRaises(ValueError):
            signor.load_publication(self.publication)

    def test_even_resealed_projection_does_not_replace_source_values(self):
        self.publish()
        path = self.publication / "projection.json"
        projection = json.loads(path.read_text())
        projection["observations"][0]["effect_literal"] = "invented opposite effect"
        projection = sealed(projection)
        write_json(path, projection)
        mpath = self.publication / "publication.json"
        manifest = json.loads(mpath.read_text())
        manifest["files"]["projection.json"] = signor._sha(path.read_bytes())
        manifest["projection_content_sha256"] = projection["content_sha256"]
        write_json(mpath, sealed(manifest))
        with self.assertRaisesRegex(ValueError, "source parser replay"):
            signor.load_publication(self.publication)

    def test_immutable_publication_and_symlink_source_rejected(self):
        snapshot, _, _, _, _ = self.publish()
        with self.assertRaisesRegex(ValueError, "immutable output"):
            signor.publish_release(self.source, snapshot, self.publication)
        link = self.root / "source-link.tsv"
        link.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "ordinary files"):
            signor.publish_release(link, snapshot, self.root / "second")

    def test_optional_pubmed_xml_reuses_parser_and_does_not_select_evidence(self):
        xml = self.root / "pubmed.xml"
        xml.write_bytes(pubmed_xml())
        snapshot, graph = baseline()
        signor.publish_release(self.source, snapshot, self.publication, pubmed_xml=xml)
        manifest, projection, files = signor.load_publication(self.publication)
        self.assertEqual(files[signor.PUBMED_FILE], xml.read_bytes())
        self.assertEqual(projection["summary"]["publication_metadata_available_pmids"], 5)
        self.assertEqual(projection["summary"]["publication_metadata_marked_review_pmids"], 1)
        self.assertEqual(projection["summary"]["publication_metadata_with_linked_notices_pmids"], 1)
        self.assertEqual(projection["summary"]["publication_metadata_with_erratum_in_pmids"], 1)
        self.assertEqual(projection["summary"]["publication_metadata_with_retraction_notice_pmids"], 0)
        self.assertFalse(projection["summary"]["primary_experimental_evidence_assessed"])
        self.assertEqual(projection["publication_metadata"]["101"]["publication_types"], ["Review"])
        self.assertEqual(projection["publication_metadata"]["102"]["correction_types"], ["ErratumIn"])
        self.assertEqual(projection["publication_metadata"]["102"]["primary_experimental_evidence"], "not_assessed")
        result = signor.prepare(snapshot, graph, manifest, projection)
        self.assertEqual(len(result["edges"]), 5)
        self.assertTrue(all(row["primary_experimental_evidence"] == "not_assessed" for row in result["observations"]))
        for row in result["observations"]:
            self.assertTrue(row["publication_metadata"][0]["source_locator"].startswith("extension_sources/signor/source/pubmed.xml#"))

    def test_optional_pubmed_metadata_must_cover_selected_pmids_and_cannot_be_tampered(self):
        xml = self.root / "pubmed.xml"
        xml.write_bytes(pubmed_xml(range(101, 105)))
        snapshot, _ = baseline()
        with self.assertRaisesRegex(ValueError, "every selected source PMID"):
            signor.publish_release(self.source, snapshot, self.publication, pubmed_xml=xml)
        xml.write_bytes(pubmed_xml())
        signor.publish_release(self.source, snapshot, self.publication, pubmed_xml=xml)
        path = self.publication / signor.PUBMED_FILE
        path.write_bytes(path.read_bytes().replace(b"ErratumIn", b"InventedNotice"))
        with self.assertRaises(ValueError):
            signor.load_publication(self.publication)


if __name__ == "__main__":
    unittest.main()
