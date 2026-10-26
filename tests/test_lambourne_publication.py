"""Publication integrity checks using invented, already-assessed observations."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publish_lambourne_evidence as publication

assessment = publication.assessment


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.options = {}
        self.select = None
        self.payload = []
        self.in_payload = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids[attrs["id"]] = (tag, attrs)
        if tag == "select":
            self.select = attrs.get("id")
            self.options[self.select] = []
        if tag == "option" and self.select:
            self.options[self.select].append(attrs.get("value"))
        if tag == "script" and attrs.get("id") == "records":
            self.in_payload = True

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None
        if tag == "script":
            self.in_payload = False

    def handle_data(self, data):
        if self.in_payload:
            self.payload.append(data)


def fixture_records():
    lookup, assays = [], []
    states = [assessment.STATES[0], assessment.STATES[1], assessment.STATES[2]]
    for index, (state, status) in enumerate(zip(states, ("not_detected", "detected", "test_failed"))):
        products = [f"P{index * 2:05d}", f"P{index * 2 + 1:05d}"]
        identity = {"source_row": index + 2, "uniprot_a": products[0], "uniprot_b": products[1],
                    "ad_orf_id": str(index * 2 + 1), "db_orf_id": str(index * 2 + 2)}
        lookup.append({"products": products, "source_row": index + 2, "identity": identity,
                       "pharos_status": state, "resolved_endpoint_count": 1 if index == 2 else 2,
                       "pharos_matches": {"raw": [{"record": {"type": "STRINGDB"}}] if index == 0 else []},
                       "previous_pharos_status": "unassessed", **{key: False for key in assessment.FLAGS}})
        eligible = status != "test_failed"
        assays.append({"products": products, "source_row": index + 2, "assay_status": status,
                       "evaluable": eligible, "detected": status == "detected" if eligible else None,
                       "ad_orf_id": identity["ad_orf_id"], "db_orf_id": identity["db_orf_id"],
                       "construct_match": True, "issues": [], "raw_source_rows": [index + 2],
                       "published_result": status, "required_confirmation": "3at", "confirmation_3at": True,
                       "confirmation_lw": None})
    return lookup, assessment.join_assay(assessment.make_comparator(lookup), assays)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.freeze = self.base / "freeze"
        self.results = self.base / "results"
        self.output = self.base / "publication"
        (self.freeze / "lookup").mkdir(parents=True)
        (self.freeze / "source").mkdir()
        self.results.mkdir()
        lookup, rows = fixture_records()
        assessment.write_json(self.freeze / "lookup/pair_lookup.json", lookup)
        source_hashes = {}
        for key, name in (("panel", "panel.tsv"), ("raw", "raw_human.tsv"), ("orf_map", "orf_map.tsv")):
            path = self.freeze / "source" / name
            path.write_text("INVENTED " + key + "\n", encoding="utf-8")
            source_hashes[key] = publication.sha(path)
        assessment.write_json(self.freeze / "protocol.json", assessment.seal({
            "format": "synthetic.frozen.assessment", "files": assessment.file_inventory(self.freeze, "protocol.json")}))
        assessment.write_json(self.results / "rows.json", rows)
        assessment.write_json(self.results / "assay_audit.json", {"source_sha256": source_hashes})
        (self.results / "report.html").write_text("<!doctype html><p>Invented assessment</p>", encoding="utf-8")
        assessment.write_json(self.results / "report.json", assessment.seal({
            "format": "synthetic.assessment.result", "files": assessment.file_inventory(self.results, "report.json")}))
        # Source decoding and assay classification are covered by the unchanged
        # upstream runner. Publication capture/hashes and projection stay real.
        patcher = mock.patch.object(assessment, "verify", side_effect=lambda freeze, results: assessment.read(Path(results) / "report.json"))
        self.semantic_verifier = patcher.start()
        self.addCleanup(patcher.stop)

    def publish(self):
        return publication.publish(self.freeze, self.results, self.output)

    def reseal_publication(self, mutate=None):
        manifest = assessment.read(self.output / publication.MANIFEST)
        if mutate:
            mutate(manifest)
        manifest["files"] = assessment.file_inventory(self.output, publication.MANIFEST)
        assessment.write_json(self.output / publication.MANIFEST, assessment.seal(manifest))

    def test_round_trip_copies_original_bytes_and_preserves_all_statuses(self):
        originals = {str(path.relative_to(self.base)): path.read_bytes()
                     for folder in (self.freeze, self.results) for path in folder.rglob("*") if path.is_file()}
        manifest = self.publish()
        self.assertEqual(publication.verify(self.output), manifest)
        for rel, content in originals.items():
            self.assertEqual((self.output / "source" / rel).read_bytes(), content)
            self.assertEqual((self.base / rel).read_bytes(), content)
        evidence = assessment.read(self.output / "evidence.json")
        self.assertEqual(evidence["summary"]["observations"], 3)
        self.assertEqual(evidence["summary"]["assay_evaluable"], 2)
        self.assertEqual(evidence["summary"]["assay_excluded"], 1)
        self.assertEqual(evidence["summary"]["detected_without_bounded_pharos_match"], 1)
        self.assertEqual(evidence["graph"], assessment.read(self.output / "graph.json"))
        self.assertFalse(manifest["baseline_modified"])
        self.assertFalse(manifest["independent_validation_performed"])

    def test_published_bundle_replays_after_original_inputs_are_removed(self):
        expected = self.publish()
        shutil.rmtree(self.freeze)
        shutil.rmtree(self.results)
        self.assertEqual(publication.verify(self.output), expected)
        self.assertEqual(self.semantic_verifier.call_args.args,
                         (self.output / "source/freeze", self.output / "source/results"))

    def test_existing_output_and_input_descendant_are_rejected_before_verification(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep")
        for output in (self.output, self.freeze / "new", self.results / "new", self.base):
            with self.subTest(output=output), self.assertRaises(ValueError):
                publication.publish(self.freeze, self.results, output)
        self.semantic_verifier.assert_not_called()
        self.assertEqual(sentinel.read_text(), "keep")

    def test_second_publication_cannot_replace_a_completed_bundle(self):
        self.publish()
        before = {p.relative_to(self.output).as_posix(): publication.sha(p)
                  for p in self.output.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError):
            self.publish()
        after = {p.relative_to(self.output).as_posix(): publication.sha(p)
                 for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_input_tamper_and_extra_file_are_rejected_without_publication(self):
        for path in (self.freeze / "source/panel.tsv", self.results / "rows.json"):
            content = path.read_bytes()
            path.write_bytes(content + b"ALTERED")
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.publish()
            self.assertFalse(self.output.exists())
            path.write_bytes(content)
        (self.freeze / "extra.txt").write_text("unlisted")
        with self.assertRaises(ValueError):
            self.publish()

    def test_source_and_output_symlinks_are_rejected(self):
        target = self.freeze / "source/panel.tsv"
        target.rename(target.with_suffix(".saved"))
        target.symlink_to(target.with_suffix(".saved"))
        with self.assertRaises(ValueError):
            self.publish()
        target.unlink()
        target.with_suffix(".saved").rename(target)
        self.output.symlink_to(self.freeze, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.publish()
        self.assertTrue(self.output.is_symlink())

    def test_output_under_symlink_parent_is_not_published(self):
        real = self.base / "real"
        real.mkdir()
        alias = self.base / "alias"
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError):
            publication.publish(self.freeze, self.results, alias / "publication")
        self.assertEqual(list(real.iterdir()), [])

    def test_failed_assessment_verification_creates_no_output(self):
        self.semantic_verifier.side_effect = ValueError("invented invalid assessment")
        with self.assertRaisesRegex(ValueError, "invalid assessment"):
            self.publish()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.base.glob(".assay-evidence-*")), [])

    def test_plain_artifact_tamper_and_symlink_are_rejected(self):
        self.publish()
        graph = self.output / "graph.json"
        original = graph.read_bytes()
        graph.write_bytes(original + b" ")
        with self.assertRaises(ValueError):
            publication.verify(self.output)
        graph.write_bytes(original)
        graph.rename(self.base / "graph.json")
        graph.symlink_to(self.base / "graph.json")
        with self.assertRaises(ValueError):
            publication.verify(self.output)

    def test_resealed_graph_evidence_and_html_changes_do_not_replay(self):
        self.publish()
        for name in ("evidence.json", "graph.json", "index.html"):
            path = self.output / name
            original = path.read_bytes()
            if name.endswith(".json"):
                value = assessment.read(path)
                value["unverified_change"] = True
                assessment.write_json(path, value)
            else:
                path.write_bytes(original + b"<p>Unverified claim</p>")
            self.reseal_publication()
            with self.subTest(name=name), self.assertRaises(ValueError):
                publication.verify(self.output)
            path.write_bytes(original)
            self.reseal_publication()

    def test_resealed_copied_source_tamper_fails_its_inner_receipt(self):
        self.publish()
        path = self.output / "source/freeze/source/raw_human.tsv"
        path.write_bytes(path.read_bytes() + b"changed")
        self.reseal_publication()
        with self.assertRaises(ValueError):
            publication.verify(self.output)

    def test_resealed_code_hash_or_interpretation_changes_are_rejected(self):
        self.publish()
        original = (self.output / publication.MANIFEST).read_bytes()
        changes = [lambda value: value["implementation_sha256"].update({publication.CODE[0]: "0" * 64}),
                   lambda value: value.update(baseline_modified=True),
                   lambda value: value.update(standard_conformance_claimed=True),
                   lambda value: value.update(automatic_pruning=True),
                   lambda value: value.update(independent_validation_performed=True),
                   lambda value: value.update(summary={"observations": 99}),
                   lambda value: value["bindings"].update(result_sha256="0" * 64)]
        for index, mutate in enumerate(changes):
            self.reseal_publication(mutate)
            with self.subTest(change=index), self.assertRaises(ValueError):
                publication.verify(self.output)
            (self.output / publication.MANIFEST).write_bytes(original)

    def test_html_preserves_payload_without_script_or_markup_injection(self):
        self.publish()
        evidence = assessment.read(self.output / "evidence.json")
        malicious = '</script><script>alert("injected")</script><img src=x onerror=alert(1)>'
        changed = copy.deepcopy(evidence)
        changed["summary"]["untrusted"] = malicious
        observation = changed["observations"][0]
        observation["original"]["assay"]["published_result"] = malicious
        html = publication.render_evidence_html(changed)
        self.assertNotIn(malicious, html)
        self.assertNotIn('<script>alert("injected")', html)
        self.assertIn("&lt;/script&gt;", html)
        parser = PageParser()
        parser.feed(html)
        records = json.loads("".join(parser.payload))
        self.assertEqual(records[0]["assay"]["published_result"], malicious)
        self.assertEqual(len(records), 3)

    def test_html_filter_controls_retain_failed_and_unresolved_observations(self):
        self.publish()
        parser = PageParser()
        parser.feed((self.output / "index.html").read_text())
        self.assertEqual(parser.options["outcome"], ["all", "detected", "not_detected", "excluded"])
        self.assertEqual(parser.options["lookup"], ["all", *assessment.STATES])
        self.assertEqual(parser.ids["protein"][0], "input")
        for key in ("missing", "prev", "next"):
            self.assertEqual(parser.ids[key][0], "button")
        records = json.loads("".join(parser.payload))
        self.assertEqual({row["assay"]["assay_status"] for row in records},
                         {"detected", "not_detected", "test_failed"})
        self.assertEqual({row["comparator"]["pharos_status"] for row in records}, set(assessment.STATES))


if __name__ == "__main__":
    unittest.main()
