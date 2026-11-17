"""Invented typed-API captures; no saved research run or network required."""
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from biograph_steward.client import digest, write_json
from biograph_steward.string_component import MAPPING_COLUMNS, NETWORK_COLUMNS, parse_mapping, parse_network
from biograph_steward import string_source_update as update


def sealed(value):
    return {**value, "content_sha256": digest(value)}


def fixture_capture(folder, *, alias=False, score=None):
    """Source metadata are invented; scores are unrelated to biological facts."""
    folder.mkdir()
    accessions = ["P00533", "P01116", "P04637", "P15056"]
    ids = {a: "9606.TEST" + a for a in accessions if a != "P04637"}
    if alias:
        ids["P01116"] = ids["P00533"]
    map_rows = [dict(zip(MAPPING_COLUMNS, (i, a, ids[a], "9606", "Homo sapiens", a, "invented")))
                for i, a in enumerate(accessions) if a in ids]
    raw_mapping = ("\t".join(MAPPING_COLUMNS) + "\n" + "".join(
        "\t".join(str(r[k]) for k in MAPPING_COLUMNS) + "\n" for r in map_rows)).encode()
    mappings = parse_mapping(raw_mapping, accessions)
    reps = sorted(set(ids.values()))
    raw_rows = []
    for n, (a, b) in enumerate(combinations(reps, 2)):
        default = {k: "0" for k in NETWORK_COLUMNS}
        default.update({k: "-" for k in NETWORK_COLUMNS if k.startswith(("physical_", "regulatory_"))})
        default.update(stringId_A=a, stringId_B=b, preferredName_A=a, preferredName_B=b,
            ncbiTaxonId="9606", sign="n/a", functional_combined_score=str(score if score is not None else [0.8, 0.4, 0.39][n]),
            physical_combined_score="0")
        raw_rows.extend([default, {**default, "stringId_A": b, "stringId_B": a,
                                  "preferredName_A": b, "preferredName_B": a}])
    raw_network = ("\t".join(NETWORK_COLUMNS) + "\n" + "".join(
        "\t".join(str(r[k]) for k in NETWORK_COLUMNS) + "\n" for r in raw_rows)).encode()
    network = parse_network(raw_network, reps)
    mapping_params = {"identifiers": "\r".join(accessions), "species": "9606", "echo_query": "1",
                      "caller_identity": "biograph-steward"}
    protocol = sealed({"format": update.CAPTURE_FORMAT, "accessions": accessions,
        "rules": {**update.PROFILE, "release": "12.5", "species": "9606", "mapping_echo_query": "1",
                  "max_requests": 2, "assay_outcomes_loaded": False, "inference_calls": 0},
        "implementation_sha256": {"historical_version.py": "a" * 64},
        "source_files_sha256": {n: "b" * 64 for n in ("graph.json", "snapshot.json", "targets.tsv", "run_manifest.json")},
        "mapping_request": {"method": "get_string_ids", "parameters": mapping_params}})
    write_json(folder / "protocol.json", protocol)
    network_params = {"identifiers": "\r".join(reps), "species": "9606",
                      "caller_identity": "biograph-steward", **update.PROFILE}
    write_json(folder / "resolved_network_request.json", sealed({"protocol_sha256": protocol["content_sha256"],
        "string_ids": reps, "parameters": network_params, "declared_before_network_request": True}))
    for method, params, raw in (("get_string_ids", mapping_params, raw_mapping), ("network", network_params, raw_network)):
        (folder / (method + ".tsv")).write_bytes(raw)
        url = update.BASE + method + "?" + urlencode(params)
        write_json(folder / (method + ".receipt.json"), sealed({"parameters": params,
            "url": url, "final_url": url, "status": 200, "body_file": method + ".tsv",
            "body_bytes": len(raw), "body_sha256": update._sha(raw),
            "headers": {"Content-Type": "text/tab-separated-values", "string-api-version": "2",
                        "Content-Length": str(len(raw))}, "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00"}))
    write_json(folder / "mappings.json", mappings)
    write_json(folder / "parsed_network.json", [{"pair": list(k), **v} for k, v in sorted(network.items())])
    return accessions


def baseline(accessions):
    snapshot = sealed({"data_kind": "live_pharos", "targets": [{"uniprot": a} for a in accessions]})
    graph = {"snapshot_sha256": snapshot["content_sha256"],
        "nodes": [{"id": "UniProtKB:" + a, "category": "biolink:Protein"} for a in accessions],
        "edges": [{"id": "old-edge", "subject": "UniProtKB:P00533", "object": "UniProtKB:P01116",
                   "record_kind": "protein_interaction", "original_score": 0.6}],
        "review_events": [{"unchanged": "illustrative existing review"}]}
    return snapshot, graph


class StringSourceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.capture, self.publication = self.root / "capture", self.root / "publication"

    def publish(self, **kwargs):
        accessions = fixture_capture(self.capture, **kwargs)
        update.publish_capture(self.capture, self.publication)
        manifest, projection, files = update.load_publication(self.publication)
        return accessions, manifest, projection, files

    def test_raw_replay_all_pair_accounting_and_provenance_preserves_inputs(self):
        accessions, manifest, projection, files = self.publish()
        snapshot, graph = baseline(accessions)
        before = deepcopy((snapshot, graph, manifest, projection))
        result = update.prepare(snapshot, graph, manifest, projection)
        self.assertEqual((snapshot, graph, manifest, projection), before)
        self.assertEqual(projection["summary"]["possible_unordered_pairs"], 6)
        self.assertEqual(projection["summary"]["pair_states"], {"functional_score_below400": 1,
            "qualifying_functional_association": 2, "unresolved_endpoint": 3})
        self.assertEqual(len(result["observations"]), 6)
        self.assertEqual(result["summary"]["new_workspace_pairs"], 1)
        self.assertEqual(result["summary"]["existing_workspace_pairs_with_new_source_record"], 1)
        self.assertIsNone(result["summary"]["independent_evidence_count"])
        self.assertFalse(result["summary"]["biological_validation_performed"])
        self.assertEqual(result["nodes"], [])
        for e in result["edges"]:
            self.assertEqual(e["extension_source_kind"], "string")
            self.assertEqual(e["extension_publication_sha256"], manifest["content_sha256"])
            self.assertEqual(e["qualifiers"], {"evidence_type": "STRING12.5functional_association"})
            self.assertEqual(e["publications"], [])
            self.assertEqual(e["source_record_count"], 1)
            self.assertEqual(len(e["record_locators"]), 2)
            self.assertTrue(all(p.startswith("extension_sources/string/capture/network.tsv#row=") for p in e["record_locators"]))
            self.assertEqual(e["source_scores_raw"]["physical_combined_score"], 0)
        self.assertEqual(manifest["source_license"]["license"], "CC-BY-4.0")
        self.assertIn("capture/network.tsv", files)

    def test_threshold_is_inclusive_and_missing_is_not_zero(self):
        accessions, manifest, projection, _ = self.publish(score=0)
        snapshot, graph = baseline(accessions)
        result = update.prepare(snapshot, graph, manifest, projection)
        self.assertEqual(result["edges"], [])
        numeric = [r for r in projection["pair_ledger"] if r["state"] == "functional_score_below400"]
        self.assertEqual(len(numeric), 3)
        self.assertTrue(all(r["functional_score"] == 0 for r in numeric))
        self.assertTrue(all(r["functional_score"] is None for r in projection["pair_ledger"] if r["state"] == "unresolved_endpoint"))

    def test_alias_representative_is_not_chosen_for_multiple_proteins(self):
        accessions, manifest, projection, _ = self.publish(alias=True)
        snapshot, graph = baseline(accessions)
        result = update.prepare(snapshot, graph, manifest, projection)
        self.assertEqual(result["edges"], [])
        self.assertEqual(projection["summary"]["pair_states"], {"ambiguous_locus_correspondence": 2,
            "collapsed_pair": 1, "unresolved_endpoint": 3})

    def test_no_node_expansion_or_capture_scope_change(self):
        accessions, manifest, projection, _ = self.publish()
        snapshot, graph = baseline(accessions)
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] != "UniProtKB:P15056"]
        result = update.prepare(snapshot, graph, manifest, projection)
        self.assertEqual(len(result["edges"]), 1)
        self.assertTrue(any(o["integration_state"] == "endpoint_outside_resolved_cohort" for o in result["observations"]))
        snapshot["targets"].pop()
        snapshot["content_sha256"] = digest({k: v for k, v in snapshot.items() if k != "content_sha256"})
        graph["snapshot_sha256"] = snapshot["content_sha256"]
        with self.assertRaisesRegex(ValueError, "exactly this source cohort"):
            update.prepare(snapshot, graph, manifest, projection)

    def test_captured_bytes_and_parser_output_tampering_are_rejected(self):
        self.publish()
        path = self.publication / "capture/network.tsv"
        path.write_bytes(path.read_bytes() + b"tamper")
        with self.assertRaises(ValueError):
            update.load_publication(self.publication)

    def test_even_resealed_projection_cannot_override_source_replay(self):
        self.publish()
        path = self.publication / "projection.json"
        value = json.loads(path.read_text()); value["pair_ledger"][0]["functional_score"] = 1
        write_json(path, sealed({k: v for k, v in value.items() if k != "content_sha256"}))
        mpath = self.publication / "publication.json"
        manifest = json.loads(mpath.read_text())
        manifest["files"]["projection.json"] = update._sha(path.read_bytes())
        manifest = sealed({k: v for k, v in manifest.items() if k != "content_sha256"})
        write_json(mpath, manifest)
        with self.assertRaisesRegex(ValueError, "parser replay"):
            update.load_publication(self.publication)

    def test_publication_is_immutable_and_candidate_capture_is_not_full_scope(self):
        self.publish()
        with self.assertRaisesRegex(ValueError, "immutable output"):
            update.publish_capture(self.capture, self.publication)
        protocol = json.loads((self.capture / "protocol.json").read_text())
        protocol["format"] = "biograph-steward.string-component-protocol.v1"
        write_json(self.capture / "protocol.json", sealed({k: v for k, v in protocol.items() if k != "content_sha256"}))
        with self.assertRaisesRegex(ValueError, "candidate-only"):
            update.publish_capture(self.capture, self.root / "second-publication")

    def test_added_labels_or_outcomes_do_not_select_associations(self):
        accessions, manifest, projection, _ = self.publish()
        snapshot, graph = baseline(accessions)
        before = update.prepare(snapshot, graph, manifest, projection)
        (self.capture / "irrelevant_assay_labels.json").write_text('{"all_outcomes":"opposite invented values"}')
        update.publish_capture(self.capture, self.root / "different-label-publication")
        m, p, _ = update.load_publication(self.root / "different-label-publication")
        after = update.prepare(snapshot, graph, m, p)
        fields = lambda result: [(e["subject"], e["object"], e["source_scores_raw"]) for e in result["edges"]]
        self.assertEqual(fields(before), fields(after))
        self.assertEqual(before["summary"]["new_workspace_pairs"], after["summary"]["new_workspace_pairs"])


if __name__ == "__main__":
    unittest.main()
