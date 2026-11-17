"""Invented SIGNOR source records exercise a pure, directed answer contract."""
from copy import deepcopy
import csv
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.assertions import build_assertions
from biograph_steward.client import digest
from biograph_steward.regulatory_questions import answer_regulatory_question, ANCHOR
from biograph_steward import signor_source as signor

KRAS = "UniProtKB:P01116"
BRAF = "UniProtKB:P15056"
TP53 = "UniProtKB:P04637"


def fixture():
    """Use the actual local source adapter, with its release pin patched to invented bytes."""
    accessions = sorted([ANCHOR.split(":")[1], KRAS.split(":")[1], BRAF.split(":")[1], TP53.split(":")[1]])
    snapshot = {"data_kind": "live_pharos", "targets": [{"uniprot": p} for p in accessions]}
    snapshot["content_sha256"] = digest(snapshot)
    graph = {"graph_format": "invented-regulatory-fixture", "data_kind": "synthetic_demo",
        "snapshot_sha256": snapshot["content_sha256"], "snapshot_created_at": "2026-01-01T00:00:00Z",
        "targets": [{"id": "UniProtKB:" + p} for p in accessions], "edges": [], "review_events": [],
        "nodes": [{"id": p, "category": "biolink:Protein", "sym": label}
                  for p, label in [(ANCHOR, "EGFR"), (KRAS, "KRAS"), (BRAF, "BRAF"), (TP53, "TP53")]]}
    pairs = [(ANCHOR, KRAS), (BRAF, ANCHOR), (ANCHOR, ANCHOR), (TP53, KRAS), (ANCHOR, BRAF)]
    rows = []
    for n, (a, b) in enumerate(pairs, 1):
        row = {k: "" for k in signor.COLUMNS}
        row.update(ENTITYA="invented regulator", TYPEA="protein", IDA=a.split(":")[1], DATABASEA="UNIPROT",
            ENTITYB="invented target", TYPEB="protein", IDB=b.split(":")[1], DATABASEB="UNIPROT",
            EFFECT="up-regulates activity", MECHANISM="phosphorylation", RESIDUE="Ser" + str(n),
            SEQUENCE="invented sequence", TAX_ID="9606", PMID=str(100 + n), DIRECT="t",
            ANNOTATOR="invented", SENTENCE="Invented source sentence " + str(n), SIGNOR_ID="SIGNOR-" + str(n))
        rows.append(row)
    rows[1].update(EFFECT="down-regulates activity", DIRECT="f", CELL_DATA="BTO:0000007", TISSUE_DATA="liver")
    rows[2].update(MECHANISM="autophosphorylation", CELL_DATA="invented cell")
    rows[4].update(SENTENCE='Invented sentence with "quotes"\nand a second physical line.')
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=signor.COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    raw = stream.getvalue().encode()
    xml = '<PubmedArticleSet>' + ''.join(
        '<PubmedArticle><MedlineCitation><PMID>' + str(100 + n) + '</PMID><Article><ArticleTitle>Invented paper '
        + str(n) + '</ArticleTitle><PublicationTypeList><PublicationType>'
        + ('Review' if n == 1 else 'Journal Article')
        + '</PublicationType></PublicationTypeList></Article></MedlineCitation></PubmedArticle>'
        for n in range(1, 6)) + '</PubmedArticleSet>'
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder).resolve()
        source, pubmed, publication = folder / "source.tsv", folder / "pubmed.xml", folder / "publication"
        source.write_bytes(raw); pubmed.write_text(xml)
        with patch.object(signor, "RELEASE_SHA256", signor._sha(raw)):
            signor.publish_release(source, snapshot, publication, pubmed_xml=pubmed)
            manifest, projection, _ = signor.load_publication(publication)
            prepared = signor.prepare(snapshot, graph, manifest, projection)
    graph.update(edges=prepared["edges"], extension_observations=prepared["observations"],
        evidence_extension={"sources": {"signor": prepared["summary"]}},
        evidence_extension_sha256=digest({"invented_extension_publication": manifest["content_sha256"]}))
    graph["assertions"] = build_assertions(graph)
    return graph


def observation(graph, record="SIGNOR-1"):
    return next(r for r in graph["extension_observations"] if r["source_record_id"] == record)


def edge_for(graph, record="SIGNOR-1"):
    eid = observation(graph, record)["graph_edge_id"]
    return next(e for e in graph["edges"] if e["id"] == eid)


def assertion_for(graph, record="SIGNOR-1"):
    aid = edge_for(graph, record)["assertion_id"]
    return next(a for a in graph["assertions"] if a["id"] == aid)


class RegulatoryQuestionTests(unittest.TestCase):
    def setUp(self):
        self.graph = fixture()

    def test_direction_and_self_records_are_counted_once(self):
        outgoing = answer_regulatory_question(self.graph)
        incoming = answer_regulatory_question(self.graph, direction="incoming")
        both = answer_regulatory_question(self.graph, direction="both")
        self.assertEqual(outgoing["summary"]["source_observations"], 5)
        self.assertEqual(outgoing["summary"]["anchored_observations"], 4)
        self.assertEqual(outgoing["summary"]["direction_observations"], 3)
        self.assertEqual(incoming["summary"]["direction_observations"], 2)
        self.assertEqual(both["summary"]["direction_observations"], 4)
        self.assertEqual([r["source_record_id"] for r in incoming["records"]], ["SIGNOR-2", "SIGNOR-3"])
        for result in (outgoing, incoming, both):
            self.assertEqual(result["summary"]["self_regulatory_observations"], 1)
            self.assertEqual(sum(r["relative_direction"] == "self" for r in result["records"]), 1)
        self.assertEqual(next(r for r in incoming["records"] if r["source_record_id"] == "SIGNOR-2")["products"],
                         [BRAF, ANCHOR])

    def test_pages_and_literal_search_have_clear_counts(self):
        first = answer_regulatory_question(self.graph, direction="both", limit=2)
        second = answer_regulatory_question(self.graph, direction="both", limit=2, offset=2)
        self.assertEqual(first["summary"]["next_offset"], 2)
        self.assertIsNone(second["summary"]["next_offset"])
        self.assertEqual(first["summary"]["matching_observations"], 4)
        self.assertEqual(len({r["id"] for r in first["records"] + second["records"]}), 4)
        self.assertEqual(answer_regulatory_question(self.graph, direction="both", search="braf")["summary"]["matching_observations"], 2)
        result = answer_regulatory_question(self.graph, direction="both", search="BTO:0000007")
        self.assertEqual([r["source_record_id"] for r in result["records"]], ["SIGNOR-2"])
        self.assertEqual(answer_regulatory_question(self.graph, search="second physical line")["summary"]["matching_observations"], 1)
        # Generic limitations mention colorectal cancer; it is not source context.
        for query in ("colorectal", "CRC", "not present"):
            self.assertEqual(answer_regulatory_question(self.graph, direction="both", search=query)["records"], [])
        self.assertEqual(answer_regulatory_question(self.graph, offset=99)["records"], [])

    def test_missing_context_and_publication_types_are_preserved_without_inference(self):
        result = answer_regulatory_question(self.graph, direction="both")
        row = next(r for r in result["records"] if r["source_record_id"] == "SIGNOR-1")
        self.assertEqual(row["cell_context_raw"], "")
        self.assertEqual(row["tissue_context_raw"], "")
        self.assertEqual(row["cell_context_reporting"], "unreported")
        self.assertEqual(row["tissue_context_reporting"], "unreported")
        self.assertEqual(row["publication_metadata"][0]["publication_types"], ["Review"])
        self.assertEqual(row["primary_experimental_evidence"], "not_assessed")
        other = next(r for r in result["records"] if r["source_record_id"] == "SIGNOR-5")
        self.assertEqual(other["publication_metadata"][0]["publication_types"], ["Journal Article"])
        self.assertEqual(other["primary_experimental_evidence"], "not_assessed")
        self.assertEqual(result["summary"]["cell_context_reported_observations"], 2)
        self.assertEqual(result["summary"]["cell_context_unreported_observations"], 2)
        self.assertEqual(result["summary"]["tissue_context_reported_observations"], 1)
        self.assertEqual(result["summary"]["tissue_context_unreported_observations"], 3)

    def test_complete_source_copies_seal_and_no_mutation_or_fetch(self):
        before = deepcopy(self.graph)
        with patch("urllib.request.urlopen", side_effect=AssertionError("No source fetch allowed")):
            result = answer_regulatory_question(self.graph, direction="both", source_run="invented_run")
        source = {r["id"]: r for r in self.graph["extension_observations"]}
        for row in result["records"]:
            self.assertEqual(row["source_observation"], source[row["observation_id"]])
            self.assertEqual(row["supporting_sentence_raw"], source[row["observation_id"]]["source_row"]["SENTENCE"])
            self.assertTrue(any(c["url"].startswith("https://pubmed.ncbi.nlm.nih.gov/") for c in row["citations"]))
        self.assertEqual(result["source_run"], "invented_run")
        self.assertEqual((result["read_only"], result["model_calls"], result["source_fetches"]), (True, 0, 0))
        self.assertEqual(result["content_sha256"], digest({k: v for k, v in result.items() if k != "content_sha256"}))
        result["records"][0]["source_observation"]["source_row"]["EFFECT"] = "changed"
        result["records"][0]["publication_metadata"][0]["title"] = "changed"
        self.assertEqual(self.graph, before)

    def test_local_review_is_separate_from_preserved_source(self):
        assertion = assertion_for(self.graph)
        assertion["lifecycle_state"] = "rejected"
        answer = answer_regulatory_question(self.graph)
        row = next(r for r in answer["records"] if r["source_record_id"] == "SIGNOR-1")
        self.assertEqual(row["local_review_state"], "rejected")
        self.assertEqual(row["source_observation"]["local_review_state"], "candidate")
        self.assertEqual(answer["summary"]["local_review_states"]["rejected"], 1)

    def test_primary_identifier_bounds_and_invalid_parameters(self):
        for kw in ({"protein": "EGFR"}, {"protein": "P00533"}, {"protein": " UniProtKB:P00533"},
                   {"protein": "UniProtKB:missing"}, {"direction": "sideways"}, {"direction": []},
                   {"search": None}, {"search": "x" * 201}, {"offset": -1}, {"offset": True},
                   {"limit": 0}, {"limit": 26}, {"limit": True}, {"source_run": "../other"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                answer_regulatory_question(self.graph, **kw)
        self.graph["nodes"].append({"id": "UniProtKB:extension_only", "category": "biolink:Protein"})
        with self.assertRaisesRegex(ValueError, "primary graph targets"):
            answer_regulatory_question(self.graph, "UniProtKB:extension_only")

    def test_empty_valid_scope_is_an_explicit_empty_answer(self):
        self.graph["extension_observations"] = []
        answer = answer_regulatory_question(self.graph)
        self.assertEqual(answer["records"], [])
        self.assertEqual(answer["summary"]["source_observations"], 0)
        self.assertIsNone(answer["summary"]["next_offset"])

    def test_ordered_edge_and_assertion_or_source_tampering_fails(self):
        mutations = [
            lambda g: edge_for(g).update(subject=KRAS, object=ANCHOR),
            lambda g: edge_for(g).update(record_kind="protein_interaction"),
            lambda g: edge_for(g).update(extension_source_kind="string"),
            lambda g: edge_for(g).update(symmetric=True),
            lambda g: edge_for(g).update(snapshot_sha256="0" * 64),
            lambda g: edge_for(g).update(extension_publication_sha256="0" * 64),
            lambda g: observation(g).update(effect_literal="invented replacement"),
            lambda g: g["extension_observations"].append(deepcopy(g["extension_observations"][0])),
            lambda g: edge_for(g).update(assertion_id="missing"),
            lambda g: assertion_for(g).update(evidence_extension_sha256="0" * 64),
            lambda g: assertion_for(g).update(revision="changed"),
            lambda g: edge_for(g).update(qualifiers=[]),
            lambda g: edge_for(g).pop("predicate"),
            lambda g: assertion_for(g).update(evidence_edge_ids=None),
            lambda g: assertion_for(g).update(lifecycle_state=[]),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                graph = deepcopy(self.graph); mutate(graph)
                answer_regulatory_question(graph, direction="both")

    def test_context_and_unsafe_citation_changes_fail_even_with_matching_edge_copies(self):
        for field, value in [("cell_context_reporting", "reported"),
                             ("citations", [{"id": "PMID:101", "url": "javascript:alert(1)"}])]:
            graph = deepcopy(self.graph); row = observation(graph)
            row[field] = value
            edge_for(graph)["evidence_record"] = deepcopy(row)
            edge_for(graph)["observation"] = deepcopy(row)
            with self.subTest(field=field), self.assertRaises(ValueError):
                answer_regulatory_question(graph)

    def test_search_cannot_hide_a_selected_tampered_record(self):
        edge_for(self.graph)["object"] = ANCHOR
        with self.assertRaises(ValueError):
            answer_regulatory_question(self.graph, search="no matching record", offset=100)


if __name__ == "__main__":
    unittest.main()
