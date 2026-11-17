"""Invented records only; reserved PMIDs are filenames, never real source access."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.assay_attachment import attach_assay, load_publication
from biograph_steward.assay_questions import answer_assay_question
from biograph_steward.client import digest
from biograph_steward.gold_packet import export_packet, load_packet
from biograph_steward.graph import save_run
from biograph_steward.intact_final_publication import (
    RESERVED, DEVELOPMENT, build_evidence, records_from_material, publish_material,
)
from biograph_steward.intact_evidence import build_evidence as old_build
from biograph_steward.questions import save_answer
from scripts.evaluate_intact_evidence_fidelity import evaluate_rows
from test_assay_attachment import cohort_snapshot
from test_intact_evidence import fixture, identifier

ROOT = Path(__file__).resolve().parents[1]
sha = lambda raw: hashlib.sha256(raw).hexdigest()
encode = lambda obj: (json.dumps(obj, indent=2) + "\n").encode()


def seal(obj):
    return {**obj, "content_sha256": digest(obj)}


def material(split="reserved_final", *, empty=False):
    """No public data copied: all four synthetic rows reuse the invented fixture."""
    ids = RESERVED if split == "reserved_final" else DEVELOPMENT
    files = {"LICENSE.md": b"Invented records for engineering tests only.\n"}
    records, ledger, catalog, source_hashes, reader_hashes = [], [], [], {}, {}
    for index, pmid in enumerate(ids):
        row = deepcopy(fixture()[0][0]["reader_record"])
        row["line_number"] = 1
        pub = row["source_fields"]["publication_ids"]
        pub.update(raw="pubmed:" + pmid, values=[identifier("pubmed", pmid)])
        row["raw_cells"][8] = pub["raw"]
        row["raw_cells"][35] = ["true", "false", "-", "false"][index]
        row["interaction"]["negative"] = row["raw_cells"][35] == "true"
        row["raw_line"] = "\t".join(row["raw_cells"])
        source_name, reader_name = "source/" + pmid + ".txt", "reader/" + pmid + ".jsonl"
        files[source_name] = (row["raw_line"] + "\n").encode()
        files[reader_name] = (json.dumps(row) + "\n").encode()
        source_hashes[pmid], reader_hashes[pmid] = sha(files[source_name]), sha(files[reader_name])
        wrapper = {"publication_id": "pubmed:" + pmid, "artifact_sha256": source_hashes[pmid],
                   "source_file": source_name, "reader_file": reader_name, "reader_record": row}
        records.append(wrapper)
        catalog.append({k: wrapper[k] for k in ("publication_id", "artifact_sha256", "source_file", "reader_file")})
        catalog[-1]["reader_sha256"] = reader_hashes[pmid]
        ledger.append({"publication_id": "pubmed:" + pmid, "artifact_sha256": source_hashes[pmid],
                       "release": "2026-10-17", "source_line": 1, "raw_row_sha256": sha(row["raw_line"].encode()),
                       "kind": "evidence", "eligible": not empty,
                       "exclusion_reasons": ["invented_outside_scope"] if empty else []})
    runtime = {"invented_runtime": True}
    xml_runtime = {"invented_xml_runtime": True}
    for name, fmt, rt in (("controls_report.json", "biograph-steward.intact-reader-controls-result.v1", runtime),
                          ("xml_controls_report.json", "biograph-steward.intact-xml-controls-result.v1", xml_runtime)):
        access_key = "reference_rows_accessed" if name == "controls_report.json" else "selected_xml_bodies_accessed"
        files[name] = encode(seal({"format": fmt, "status": "passed", "all_checks_passed": True,
                                  "synthetic_only": True, access_key: False,
                                  "runtime_bindings": rt, "invented_test_fixture": True}))
    files["execution_freeze.json"] = encode(seal({
        "format": "biograph-steward.intact-final-execution-freeze.v1", "publication_ids": list(ids),
        "assessment_split": split, "pre_access": True, "invented_test_fixture": True}))
    files["protocol.json"] = (ROOT / "docs/evaluations/intact_fidelity_20261026_protocol.json").read_bytes()
    files["semantic_amendment.json"] = (ROOT / "docs/evaluations/intact_fidelity_20261026_semantic_amendment.json").read_bytes()
    files["row_ledger.jsonl"] = b"".join((json.dumps(x) + "\n").encode() for x in ledger)
    inspection = {"status": "final_inspected_not_fidelity_scored" if split == "reserved_final"
                  else "development_full_flow_replay_not_final_score", "publication_ids": list(ids),
                  "bindings": {"runtime_bindings": runtime, "controls_report_sha256": sha(files["controls_report.json"]),
                               "execution_freeze_sha256": sha(files["execution_freeze.json"])}}
    files["inspection_report.json"] = encode(inspection)
    bindings = {"assessment_split": split, "publication_ids": list(ids),
                "source_sha256": source_hashes, "reader_sha256": reader_hashes,
                "reader_runtime": runtime, "xml_reader_runtime": xml_runtime}
    for filename, key in (("protocol.json", "protocol_sha256"), ("semantic_amendment.json", "amendment_sha256"),
                          ("row_ledger.jsonl", "ledger_sha256"), ("inspection_report.json", "result_sha256"),
                          ("execution_freeze.json", "execution_freeze_sha256"),
                          ("controls_report.json", "controls_report_sha256"),
                          ("xml_controls_report.json", "xml_controls_report_sha256")):
        bindings[key] = sha(files[filename])
    return files, catalog, bindings, inspection, records, ledger


class FinalPublicationTests(unittest.TestCase):
    def test_scope_does_not_relax_development_guard(self):
        files, catalog, bindings, _, records, ledger = material()
        with self.assertRaises(ValueError):
            old_build(records, ledger, bindings)
        for mutation in ({"assessment_split": "arbitrary"}, {"publication_ids": list(reversed(RESERVED))},
                         {"execution_freeze_sha256": None}, {"source_sha256": {}}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                build_evidence(records, ledger, {**bindings, **mutation})
        self.assertEqual(records_from_material(files, catalog, bindings), records)

    def test_zero_eligible_is_preserved_not_success_or_missing_source(self):
        files, catalog, bindings, inspection, _, _ = material(empty=True)
        with tempfile.TemporaryDirectory() as t:
            out = Path(t).resolve() / "pub"
            publish_material(files, catalog, bindings, inspection, out)
            _, evidence, _ = load_publication(out)
            self.assertEqual(evidence["summary"]["primary_eligible"], 0)
            self.assertEqual(evidence["summary"]["source_evidence_rows"], 4)
            self.assertEqual(evidence["summary"]["excluded_evidence"], 4)
            self.assertEqual(len(evidence["row_ledger"]), 4)

    def test_complete_readable_answer_export_and_reopen(self):
        for split in ("reserved_final", "development_replay"):
            files, catalog, bindings, inspection, records, ledger = material(split)
            with self.subTest(split=split), tempfile.TemporaryDirectory() as t:
                root = Path(t).resolve(); pub = root / "pub"
                before = deepcopy((files, catalog, bindings, inspection))
                publish_material(files, catalog, bindings, inspection, pub)
                self.assertEqual((files, catalog, bindings, inspection), before)
                _, evidence, _ = load_publication(pub)
                self.assertEqual(len(evidence["observations"]), 4)
                save_run(cohort_snapshot(), root / "cohort")
                graph = attach_assay(root / "cohort", pub, root / "attached")
                answer = answer_assay_question(graph, source_run="attached")
                save_answer(answer, root / "answer")
                export_packet(root / "attached", root / "packet")
                load_packet(root / "packet")
                packet_manifest = json.loads((root / "packet/packet_manifest.json").read_text())
                self.assertIn("intact_final_publication", packet_manifest["implementation_sha256"])
                exported = [json.loads(x) for x in (root / "packet/assay_observations.jsonl").read_text().splitlines()]
                answer_export = [json.loads(x) for x in (root / "answer/assay_evidence.jsonl").read_text().splitlines()]
                references = [{"ledger": a, "reader_record": b["reader_record"]} for a, b in zip(ledger, records)]
                evaluated = evaluate_rows(references, graph["assay_observations"], answer["results"], exported,
                    answer_export, (root / "answer/report.html").read_text(), graph_edges=graph["edges"])
                self.assertEqual(len(evaluated["rows"]), 4)
                self.assertTrue(all(r["strict_fidelity"] for r in evaluated["rows"]))
                self.assertFalse(evaluated["unexpected_observation_locators"])

    def test_uncatalogued_path_tamper_and_missing_freeze_are_rejected(self):
        files, catalog, bindings, inspection, _, _ = material()
        with self.assertRaises(ValueError):
            records_from_material({**files, "source/unapproved.txt": b""}, catalog, bindings)
        with tempfile.TemporaryDirectory() as t:
            for label, missing in (("freeze", "execution_freeze.json"), ("xml_controls", "xml_controls_report.json")):
                changed = dict(files); changed.pop(missing)
                with self.subTest(label=label), self.assertRaises((ValueError, KeyError)):
                    publish_material(changed, catalog, bindings, inspection, Path(t).resolve() / label)
                self.assertFalse((Path(t).resolve() / label).exists())


if __name__ == "__main__":
    unittest.main()
