"""Official-package controls on invented annotations, never biological gold."""
from collections import Counter
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_official_qc as wrapper
from biograph_steward import gold_packet, go_qualification
from biograph_steward.client import digest
from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from biograph_steward.graph import save_run
from test_normalization import fixture
from test_go_native_qualification import record


# Public GO evidence-code/ECO mapping facts. The fixtures use only IDA/IEA;
# other codes initialize the official package's complete rule catalogue.
MAPPINGS = [
    ("EXP", "0000269"), ("HDA", "0007005"), ("HEP", "0007007"),
    ("HGI", "0007003"), ("HMP", "0007001"), ("HTP", "0006056"),
    ("IBA", "0000318"), ("IBD", "0000319"), ("IC", "0000305"),
    ("IDA", "0000314"), ("IEA", "0000501"), ("IEP", "0000270"),
    ("IGC", "0000317"), ("IGI", "0000316"), ("IKR", "0000320"),
    ("IMP", "0000315"), ("IPI", "0000353"), ("IRD", "0000321"),
    ("ISA", "0000247"), ("ISM", "0000255"), ("ISO", "0000266"),
    ("ISS", "0000250"), ("NAS", "0000303"), ("ND", "0000307"),
    ("RCA", "0000245"), ("TAS", "0000304")]


def ontology_fixture():
    iri = "http://purl.obolibrary.org/obo/GO_"
    namespace = "http://www.geneontology.org/formats/oboInOwl#hasOBONamespace"
    def node(num, branch="molecular_function", **meta):
        return {"id": iri + f"{num:07d}", "type": "CLASS", "lbl": "Invented test term",
                "meta": {"basicPropertyValues": [{"pred": namespace, "val": branch}], **meta}}
    nodes = [node(1), node(2, deprecated=True, basicPropertyValues=[
        {"pred": namespace, "val": "molecular_function"},
        {"pred": "http://purl.obolibrary.org/obo/IAO_0100001", "val": iri + "0000001"}]),
        node(3, deprecated=True), node(3674), node(5575, "cellular_component"), node(8150, "biological_process")]
    return {"graphs": [{"id": "http://purl.obolibrary.org/obo/go.owl",
        "meta": {"version": "http://purl.obolibrary.org/obo/go/releases/2026-01-01/go.owl"},
        "nodes": nodes, "edges": [{"sub": iri + "0000001", "pred": "is_a", "obj": iri + "0003674"}]}]}


class OfficialQCControls(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.context = self.root / "context"
        headers = ["!gaf-version: 2.2", "!generated-by: INVENTED", "!date-generated: 2026-01-01",
                   "!go-version: http://purl.obolibrary.org/obo/go/releases/2026-01-01/go.owl"]
        variants = [
            {}, {"3": "located_in"}, {"3": "NOT|located_in"},
            {"5": "PMID:99999991"}, {"4": "GO:0000002"}, {"4": "GO:0000003"},
            {"6": "IEA", "7": "UniProtKB:P00533", "5": "GO_REF:0000002"}]
        self.native = [record(i + 5, **{"1": "P04637", "3": "enables", "4": "GO:0000001",
            "5": "PMID:11111111", "6": "IDA", "7": "", "12": "taxon:9606",
            "14": "INVENTED", "15": "", "16": "UniProtKB:P04637", **change})
            for i, change in enumerate(variants)]
        self.gaf = self.root / "invented.gaf.gz"
        self.gaf.write_bytes(gzip.compress(("\n".join(headers + [r["raw_line"] for r in self.native]) + "\n").encode(), mtime=0))
        gaf_pin = sha(self.gaf)
        self.native = [go_qualification.native_record(r["source_line"], r["raw_line"], r["raw_fields"], r["parsed"], gaf_pin)
                       for r in self.native]
        snapshot = fixture()
        source = self.root / "source"
        save_run(snapshot, source)
        packet = self.root / "packet"
        gold_packet.export_packet(source, packet)
        with patch.object(go_qualification, "read_native_gaf", return_value=(self.native, {
                "headers": headers, "gaf_sha256": gaf_pin, "total_source_rows": len(self.native),
                "parser": {"package": "biopython", "version": "1.88", "function": "Bio.UniProt.GOA.gafiterator"}})):
            go_qualification.qualify_go_context(packet, self.gaf, self.context, expected_gaf_sha256=gaf_pin)
        self.ontology = self.root / "ontology.json.gz"
        self.ontology.write_bytes(gzip.compress(json.dumps(ontology_fixture()).encode(), mtime=0))
        self.retractions = self.root / "retracted.txt"
        self.retractions.write_text("!Invented test set\nPMID:99999991\n")
        self.eco = self.root / "eco.txt"
        self.eco.write_text("".join(code + "\tDefault\tECO:" + number + "\n" for code, number in MAPPINGS))
        self.derived = self.root / "derived.txt"
        self.derived.write_text("# Invented empty derived map; default mapping is sufficient for these controls\n")
        self.kwargs = {"ontology_sha256": sha(self.ontology), "retracted_sha256": sha(self.retractions),
                       "eco_sha256": sha(self.eco), "eco_derived_sha256": sha(self.derived)}

    def run_qc(self, name="result", **changes):
        return wrapper.run(self.context, self.ontology, self.retractions, self.eco, self.derived,
                           self.root / name, **{**self.kwargs, **changes})

    def test_actual_official_rules_repair_filter_and_preserve_native_originals(self):
        original = {p.relative_to(self.context).as_posix(): sha(p) for p in self.context.rglob("*") if p.is_file()}
        report = self.run_qc()
        self.assertEqual(report["counts"]["native_input_records"], 7)
        self.assertEqual(report["counts"]["base_filtered_native_records"], 2)
        self.assertEqual(report["counts"]["base_output_associations"], 5)
        self.assertEqual(report["counts"]["rule_invocations"]["GORULE:0000022"], {"PASS": 5, "ERROR": 1})
        self.assertEqual(report["counts"]["rule_invocations"]["GORULE:0000061"], {"PASS": 4, "WARNING": 2})
        traces = [json.loads(line) for line in (self.root / "result/native_row_changes.jsonl").read_text().splitlines()]
        self.assertEqual(traces[1]["after_base_rules"][0].split("\t")[3], "enables")
        self.assertEqual(traces[2]["after_base_rules"][0].split("\t")[3], "NOT|enables")
        self.assertEqual(traces[4]["after_base_rules"][0].split("\t")[4], "GO:0000001")
        self.assertEqual(traces[3]["after_base_rules"], [])
        self.assertEqual(traces[5]["after_base_rules"], [])
        self.assertEqual(report["taxon_rule_status"], "not_run_missing_inferences")
        self.assertEqual(original, {p.relative_to(self.context).as_posix(): sha(p) for p in self.context.rglob("*") if p.is_file()})
        self.assertFalse(report["scientific_accuracy_measured"])
        self.assertFalse(report["source_graph_changed"])

    def test_rule_set_integer_example_does_not_run_but_exact_padded_string_runs(self):
        with wrapper.offline_requests({"eco": self.eco.read_bytes(), "eco_derived": self.derived.read_bytes()}, []):
            from ontobio.io import assocparser, gafparser, qc
            parser = gafparser.GafParser(config=assocparser.AssocParserConfig())
            parser.parse_line("!gaf-version: 2.2\n")
            annotation = parser.parse_line(self.native[3]["raw_line"] + "\n").associations[0]
            for selector, expected in (([22], qc.ResultType.PASS), (["0000022"], qc.ResultType.ERROR)):
                config = assocparser.AssocParserConfig(rule_set=selector, retracted_pub_set={"PMID:99999991"})
                self.assertEqual(qc.GoRule22().run_test(annotation, config).result_type, expected)

    def test_official_serialization_does_not_mutate_working_taxon_lookup_keys(self):
        with wrapper.offline_requests({"eco": self.eco.read_bytes(), "eco_derived": self.derived.read_bytes()}, []):
            from ontobio.io import assocparser, gafparser, gaference
            parser = gafparser.GafParser(config=assocparser.AssocParserConfig())
            parser.parse_line("!gaf-version: 2.2\n")
            annotation = parser.parse_line(self.native[0]["raw_line"] + "\n").associations[0]
            keys = gaference.make_keys_from_gaf(annotation)
            wrapper.serialize_gaf(annotation)
            self.assertEqual(str(annotation.object.taxon), "NCBITaxon:9606")
            self.assertEqual(gaference.make_keys_from_gaf(annotation), keys)

    def test_source_pin_tampering_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, "differ from SHA256"):
            self.run_qc(ontology_sha256="0" * 64)
        self.assertFalse((self.root / "result").exists())

    def test_different_native_ontology_vintage_fails_before_output(self):
        value = ontology_fixture()
        value["graphs"][0]["meta"]["version"] = "http://purl.obolibrary.org/obo/go/releases/2025-01-01/go.owl"
        self.ontology.write_bytes(gzip.compress(json.dumps(value).encode(), mtime=0))
        with self.assertRaisesRegex(ValueError, "same dated GO release"):
            self.run_qc(ontology_sha256=sha(self.ontology))
        self.assertFalse((self.root / "result").exists())

    def test_unrecorded_network_is_blocked(self):
        import requests
        with wrapper.offline_requests({"eco": self.eco.read_bytes(), "eco_derived": self.derived.read_bytes()}, []):
            with self.assertRaisesRegex(ValueError, "unrecorded network"):
                requests.get("https://example.invalid/unpinned")

    def test_empty_inference_table_cannot_be_reported_as_taxon_validation(self):
        path = self.root / "inferences.json"
        path.write_text("[]")
        with self.assertRaisesRegex(ValueError, "nonempty"):
            self.run_qc(inferences=path, inferences_sha256=sha(path))
        self.assertFalse((self.root / "result").exists())

    def inference_file(self, term="0000001"):
        path = self.root / "inferences.json"
        path.write_text(json.dumps([{"annotation": {"annotation": {
            "relation": "http://purl.obolibrary.org/obo/RO_0002327",
            "term": "http://purl.obolibrary.org/obo/GO_" + term},
            "taxon": "http://purl.obolibrary.org/obo/NCBITaxon_9606", "extension": []},
            "satisfiable": False, "taxonProblem": True, "inferences": []}]))
        return path

    def test_nonempty_but_unmatched_inferences_fail_instead_of_silent_pass(self):
        base = self.run_qc("base")
        path = self.inference_file("9999999")
        with self.assertRaisesRegex(ValueError, "key coverage is incomplete"):
            self.run_qc("bad_inferences", inferences=path, inferences_sha256=sha(path),
                inferences_source_gaf_sha256=base["base_validated_native_gaf_sha256"],
                inferences_ontology_version=base["ontology"]["ontology_version"])
        self.assertFalse((self.root / "bad_inferences/report.json").exists())

    def test_official_taxon_rule_distinguishes_not_experimental_and_nonexperimental(self):
        base = self.run_qc("base")
        path = self.inference_file()
        report = self.run_qc("taxon", inferences=path, inferences_sha256=sha(path),
            inferences_source_gaf_sha256=base["base_validated_native_gaf_sha256"],
            inferences_ontology_version=base["ontology"]["ontology_version"])
        self.assertEqual(report["taxon_rule_status"], "executed_with_complete_non_not_key_coverage")
        taxon = json.loads((self.root / "taxon/taxon_rule.json").read_text())
        self.assertEqual(Counter(r["result_type"] for r in taxon["results"]), {"PASS": 1, "WARNING": 3, "ERROR": 1})
        self.assertEqual(taxon["negated_exempt_associations"], 1)
        self.assertEqual(report["counts"]["final_output_associations"], 4)

    def test_complete_mode_extension_coverage_and_actual_rule_lookup_use_same_official_key(self):
        headers = [line for line in gzip.decompress(self.gaf.read_bytes()).decode().splitlines() if line.startswith("!")]
        extended = list(self.native)
        fields = {str(i): value for i, value in enumerate(extended[0]["raw_fields"])}
        fields["15"] = "has_input(UniProtKB:P00533)"
        extended[0] = record(extended[0]["source_line"], **fields)
        source = self.root / "extended.gaf.gz"
        source.write_bytes(gzip.compress(("\n".join(headers + [r["raw_line"] for r in extended]) + "\n").encode(), mtime=0))
        pin = sha(source)
        extended = [go_qualification.native_record(r["source_line"], r["raw_line"], r["raw_fields"], r["parsed"], pin)
                    for r in extended]
        self.context = self.root / "extended_context"
        with patch.object(go_qualification, "read_native_gaf", return_value=(extended, {
                "headers": headers, "gaf_sha256": pin, "total_source_rows": len(extended),
                "parser": {"package": "biopython", "version": "1.88", "function": "Bio.UniProt.GOA.gafiterator"}})):
            go_qualification.qualify_go_context(self.root / "packet", source, self.context, expected_gaf_sha256=pin)
        base = self.run_qc("extension_base")
        path = self.inference_file()
        values = json.loads(path.read_text())
        extension = json.loads(json.dumps(values[0]))
        extension["annotation"]["extension"] = [{"relation": "http://purl.obolibrary.org/obo/RO_0002233",
            "term": "http://identifiers.org/uniprot/P00533"}]
        values.append(extension)
        path.write_text(json.dumps(values))
        provenance = {"inferences": path, "inferences_sha256": sha(path),
            "inferences_source_gaf_sha256": base["base_validated_native_gaf_sha256"],
            "inferences_ontology_version": base["ontology"]["ontology_version"]}
        report = self.run_qc("complete_extension", **provenance)
        self.assertEqual(report["taxon_rule_status"], "executed_with_complete_non_not_key_coverage")
        taxon = json.loads((self.root / "complete_extension/taxon_rule.json").read_text())
        first = next(x for x in taxon["results"] if x["native_record_id"] == extended[0]["id"])
        self.assertEqual(first["result_type"], "WARNING")
        lookup = next(x for x in taxon["actual_lookup_calls"] if x["native_record_id"] == extended[0]["id"])
        self.assertTrue(lookup["typed_extension_key_converted"])
        self.assertTrue(lookup["explicit_sparse_delta_match"])
        path.write_text(json.dumps(values[:1]))
        with self.assertRaisesRegex(ValueError, "key coverage is incomplete"):
            self.run_qc("missing_complete_extension", **{**provenance, "inferences_sha256": sha(path)})

    def sparse_proof(self, base, *, delta=None):
        """Invented execution/coverage receipts exercise the contract, not truth."""
        import hashlib
        from prefixcommons import curie_util
        context_root = Path(curie_util.__file__).parent / "registry"
        lines = (self.root / "base/base_validated_native.gaf").read_text().splitlines()
        coverage = []
        for index, line in enumerate(lines, 1):
            if line.startswith("!"): continue
            coverage.append({"gaf_line": index, "raw_line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                "released_parser_keys": [{"annotation": {"relation": "http://purl.obolibrary.org/obo/RO_0002327",
                    "term": "http://purl.obolibrary.org/obo/GO_0000001"},
                    "taxon": "http://purl.obolibrary.org/obo/NCBITaxon_9606", "extension": []}]})
        coverage_path = self.root / "coverage.jsonl"
        coverage_path.write_text("".join(json.dumps(x) + "\n" for x in coverage))
        delta_path = self.root / "delta.json"
        delta_path.write_text(json.dumps(delta or []))
        common = {"format": "biograph-steward.gaferencer-execution.v1", "status": "completed", "exit_code": 0,
            "phase": "synthetic_software_control", "input_gaf_sha256": base["base_validated_native_gaf_sha256"],
            "ontology_sha256": "f" * 64,
            "ontology_version": "http://purl.obolibrary.org/obo/go/releases/2026-01-01/extensions/go-gaf.owl",
            "binary_archive_sha256": wrapper.GAFERENCER_ARCHIVE_SHA256,
            "context_files": {name: sha(context_root / name) for name in ("go_context.jsonld", "obo_context.jsonld")},
            "runtime_files": {"synthetic_fixture_only": "e" * 64},
            "argv": ["gaferencer", "gaf", "--contexts", "/fake/go_context.jsonld", "--contexts", "/fake/obo_context.jsonld"],
            "synthetic_fixture_not_authenticated_execution": True}
        producer = {**common, "output_sha256": sha(delta_path)}
        producer["content_sha256"] = digest(producer)
        producer_path = self.root / "producer.json"; write_json(producer_path, producer)
        parser = {**common, "format": "biograph-steward.gaferencer-parser-coverage.v1",
            "output_sha256": sha(coverage_path), "output_rows": len(coverage),
            "coverage_source_sha256": sha(Path(wrapper.__file__).with_name("ReleasedParserCoverage.java")),
            "coverage_class_sha256": "c" * 64,
            "argv": ["java", "-cp", "test", "ReleasedParserCoverage", "/fake/go.owl", "/fake/input.gaf",
                     "/fake/go_context.jsonld", "/fake/obo_context.jsonld", "/fake/coverage.jsonl"]}
        parser["content_sha256"] = digest(parser)
        parser_path = self.root / "parser.json"; write_json(parser_path, parser)
        return {"inferences": delta_path, "inferences_sha256": sha(delta_path),
            "inferences_source_gaf_sha256": base["base_validated_native_gaf_sha256"],
            "inferences_ontology_version": base["ontology"]["ontology_version"],
            "inference_mode": "published_sparse_delta", "inference_execution": producer_path,
            "parser_coverage": coverage_path, "parser_execution": parser_path}

    def test_empty_published_delta_requires_matching_success_and_complete_parser_coverage(self):
        base = self.run_qc("base")
        proof = self.sparse_proof(base)
        report = self.run_qc("sparse", **proof)
        self.assertEqual(report["taxon_rule_status"], "executed_with_proven_sparse_delta_parser_coverage")
        taxon = json.loads((self.root / "sparse/taxon_rule.json").read_text())
        self.assertEqual(taxon["sparse_proof"]["explicit_sparse_delta_keys"], 0)
        self.assertEqual(taxon["sparse_proof"]["covered_non_not_associations"], 4)
        self.assertFalse(taxon["sparse_proof"]["normal_absent_keys_materialized_as_pass_entries"])

    def test_arbitrary_empty_sparse_delta_without_proof_is_not_validation(self):
        base = self.run_qc("base")
        proof = self.sparse_proof(base)
        proof.pop("parser_execution")
        with self.assertRaisesRegex(ValueError, "requires successful producer"):
            self.run_qc("unproven", **proof)
        self.assertFalse((self.root / "unproven/report.json").exists())

    def test_sparse_coverage_row_keys_must_match_the_actual_official_qc_keys(self):
        base = self.run_qc("base")
        proof = self.sparse_proof(base)
        rows = [json.loads(x) for x in proof["parser_coverage"].read_text().splitlines()]
        rows[0]["released_parser_keys"][0]["taxon"] = "taxon:9606"
        proof["parser_coverage"].write_text("".join(json.dumps(x) + "\n" for x in rows))
        receipt = json.loads(proof["parser_execution"].read_text())
        receipt["output_sha256"] = sha(proof["parser_coverage"])
        receipt.pop("content_sha256"); receipt["content_sha256"] = digest(receipt)
        write_json(proof["parser_execution"], receipt)
        with self.assertRaisesRegex(ValueError, "dropped or changed"):
            self.run_qc("incomplete", **proof)
        self.assertFalse((self.root / "incomplete/report.json").exists())

    def test_sparse_producer_failure_or_different_input_never_becomes_a_pass(self):
        base = self.run_qc("base")
        proof = self.sparse_proof(base)
        receipt = json.loads(proof["inference_execution"].read_text())
        receipt["exit_code"] = 1
        receipt.pop("content_sha256");receipt["content_sha256"] = digest(receipt)
        write_json(proof["inference_execution"], receipt)
        with self.assertRaisesRegex(ValueError, "successful GAFeRence execution"):
            self.run_qc("failed_producer", **proof)

    def test_different_context_precedence_cannot_be_accepted_with_same_file_set(self):
        base = self.run_qc("base")
        proof = self.sparse_proof(base)
        receipt = json.loads(proof["inference_execution"].read_text())
        receipt["argv"][3], receipt["argv"][5] = receipt["argv"][5], receipt["argv"][3]
        receipt.pop("content_sha256");receipt["content_sha256"] = digest(receipt)
        write_json(proof["inference_execution"], receipt)
        with self.assertRaisesRegex(ValueError, "context order differs"):
            self.run_qc("wrong_precedence", **proof)

    def test_typed_ro_gorel_and_filler_keys_use_official_api_for_actual_rule_lookup(self):
        with wrapper.offline_requests({"eco": self.eco.read_bytes(), "eco_derived": self.derived.read_bytes()}, []):
            from ontobio.io import assocparser, gafparser, gaference, qc
            parser = gafparser.GafParser(config=assocparser.AssocParserConfig())
            parser.parse_line("!gaf-version: 2.2\n")
            row = record(**{"1": "P04637", "3": "enables", "4": "GO:0000001", "5": "PMID:11111111",
                "6": "IDA", "7": "", "12": "taxon:9606",
                "15": "has_input(UniProtKB:P00533),exists_during(GO:0071383),results_in_division_of(CL:0002591)"})
            annotation = parser.parse_line(row["raw_line"] + "\n").associations[0]
            raw_key = gaference.make_keys_from_gaf(annotation)[0]
            expected = wrapper._coverage_key({"annotation": {"relation": "http://purl.obolibrary.org/obo/RO_0002327",
                "term": "http://purl.obolibrary.org/obo/GO_0000001"}, "taxon": "http://purl.obolibrary.org/obo/NCBITaxon_9606",
                "extension": [{"relation": "http://purl.obolibrary.org/obo/RO_0002233", "term": "http://identifiers.org/uniprot/P00533"},
                    {"relation": "http://purl.obolibrary.org/obo/GOREL_0000032", "term": "http://purl.obolibrary.org/obo/GO_0071383"},
                    {"relation": "http://purl.obolibrary.org/obo/GOREL_0001019", "term": "http://purl.obolibrary.org/obo/CL_0002591"}]}, gaference)
            self.assertNotEqual(raw_key, expected)  # Verified installed-package interoperation gap.
            self.assertEqual(wrapper.canonical_query_key(raw_key, gaference), expected)
            table = {expected: gaference.InferenceValue(False, True, [])}
            proxy = wrapper.OfficialIriQueryMapping(table, gaference, {"value": "invented"})
            config = assocparser.AssocParserConfig(rule_set=["0000013"], annotation_inferences=proxy)
            self.assertEqual(qc.GoRule13().run_test(annotation, config).result_type, qc.ResultType.WARNING)
            self.assertEqual(len(table), 1)
            self.assertTrue(proxy.calls[0]["typed_extension_key_converted"])

    def test_unknown_relation_namespaces_are_not_guessed(self):
        with wrapper.offline_requests({"eco": self.eco.read_bytes(), "eco_derived": self.derived.read_bytes()}, []):
            from ontobio.io import gaference
            from ontobio.model import association
            key = gaference.AnnotationKey(gaference.RelationTo("http://purl.obolibrary.org/obo/RO_0002327",
                "http://purl.obolibrary.org/obo/GO_0000001"), "http://purl.obolibrary.org/obo/NCBITaxon_9606",
                association.ConjunctiveSet(frozenset([association.ExtensionUnit(
                    association.Curie("INVENTED", "123"), association.Curie("GO", "0000001"))])))
            with self.assertRaisesRegex(ValueError, "official relation registry"):
                wrapper.canonical_query_key(key, gaference)


if __name__ == "__main__":
    unittest.main()
