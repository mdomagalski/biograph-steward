#!/usr/bin/env python3
"""Offline execution of official ontobio rules on preserved native GAF rows.

This optional adapter supplies pinned inputs, records official calls and keeps
before/after rows. It contains no replacement GO rule or biological truth model.
"""
from collections import Counter
from collections.abc import Mapping
from contextlib import ExitStack
from copy import deepcopy
import gzip
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.go_ontology_qualification import load_ontology
from biograph_steward import gold_packet

FORMAT = "biograph-steward.official-native-go-qc.v1"
ONTOBIO_VERSION = "2.9.12"
PREFIXCOMMONS_VERSION = "0.1.12"
SELECTED_RULES = ("0000022", "0000061")
ECO_URLS = {
    "http://purl.obolibrary.org/obo/eco/gaf-eco-mapping.txt": "eco",
    "https://purl.obolibrary.org/obo/eco/gaf-eco-mapping.txt": "eco",
    "http://purl.obolibrary.org/obo/eco/gaf-eco-mapping-derived.txt": "eco_derived",
    "https://purl.obolibrary.org/obo/eco/gaf-eco-mapping-derived.txt": "eco_derived",
}
GAFERENCER_ARCHIVE_SHA256 = "d15dba87343ebc1564602365cfa06ae6bcc943a3b2712cf2e422ebcb4796fbf3"


def need(condition, message):
    if not condition:
        raise ValueError("Official GO QC: " + message)


def pinned_file(path, expected):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), "inputs must be ordinary files.")
    need(isinstance(expected, str) and re.fullmatch(r"[a-f0-9]{64}", expected), "an explicit SHA256 is required.")
    need(sha(path) == expected, "input bytes differ from SHA256: " + str(path))
    return path


def serialize_gaf(annotation):
    """Use the official writer on a copy of its mutable model.

    In ontobio2.9.12, to_gaf_2_2_tsv changes object.taxon.namespace to
    'taxon'. Serializing the working annotation before GAFeRence lookup would
    therefore change its URI key. Preserve the official parsed model for QC.
    """
    return "\t".join(map(str, deepcopy(annotation).to_gaf_2_2_tsv()))


def _execution(path, expected_format="biograph-steward.gaferencer-execution.v1"):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), "execution proof must be an ordinary file.")
    value = gold_packet._read(path)
    need(gold_packet._sealed(value) and value.get("format") == expected_format
         and value.get("status") == "completed" and type(value.get("exit_code")) is int
         and value["exit_code"] == 0, "a sealed successful GAFeRence execution is required.")
    need(value.get("binary_archive_sha256") == GAFERENCER_ARCHIVE_SHA256,
         "execution does not bind the reviewed GAFeRence v0.5 release.")
    return path, value


def _coverage_key(raw, gaference):
    need(isinstance(raw, dict) and set(raw) == {"annotation", "taxon", "extension"},
         "invalid released parser key.")
    link = raw["annotation"]
    need(isinstance(link, dict) and set(link) == {"relation", "term"}
         and all(isinstance(v, str) and v for v in link.values())
         and isinstance(raw["taxon"], str) and bool(raw["taxon"])
         and isinstance(raw["extension"], list), "released parser key is incomplete.")
    need(all(isinstance(x, dict) and set(x) == {"relation", "term"}
         and all(isinstance(v, str) and v for v in x.values()) for x in raw["extension"]),
         "released parser extension key is incomplete.")
    return gaference.AnnotationKey(gaference.RelationTo(link["relation"], link["term"]),
                                  raw["taxon"], gaference.make_conjunctions(raw["extension"]))


def canonical_query_key(key, gaference):
    """Bridge typed model extension units to the published full-IRI key form.

    ontobio2.9.12 expands the main fields but leaves extension Curie objects
    unexpanded in make_keys_from_gaf. Its JSON loader instead stores IRI strings.
    Existing official relation/prefix APIs provide the exact conversion; no
    namespace aliases, identifier replacements or passing entries are added.
    """
    from ontobio.model.association import Curie
    from ontobio.rdfgen import relations
    from prefixcommons import curie_util
    registered_relations = set(relations.label_relation_lookup().values())
    units = []
    for unit in key.extension.elements:
        relation = unit.relation
        if isinstance(relation, Curie):
            relation = relations.curie_to_obo_uri(relation)
            need(relation in registered_relations, "extension relation is not in the official relation registry.")
        filler = unit.term
        if isinstance(filler, Curie):
            try:
                filler = curie_util.expand_uri(str(filler), cmaps=[gaference.prefix_context], strict=True)
            except Exception as exc:
                raise ValueError("Official GO QC: extension filler has no verified prefix expansion.") from exc
        need(all(isinstance(value, str) and value.startswith(("http://", "https://")) for value in (relation, filler)),
             "extension key has no full-IRI representation.")
        units.append({"relation": relation, "term": filler})
    return gaference.AnnotationKey(key.relation_to, key.taxon, gaference.make_conjunctions(units))


class OfficialIriQueryMapping(Mapping):
    """Read-only query adapter; published inference entries stay unmodified."""
    def __init__(self, values, gaference, current_record):
        self._values = values
        self.gaference = gaference
        self.current_record = current_record
        self.calls = []

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, key):
        canonical = canonical_query_key(key, self.gaference)
        value = self._values.get(canonical)
        self.calls.append({"native_record_id": self.current_record["value"],
            "typed_extension_key_converted": canonical != key, "explicit_sparse_delta_match": value is not None,
            "satisfiable": value.satisfiable if value is not None else None,
            "taxon_problem": value.taxon_problem if value is not None else None,
            "additional_inferences": len(value.inferences) if value is not None else None})
        if value is None:
            raise KeyError(key)
        return value


def _ordered_contexts(proof, parser=False):
    argv, files = proof.get("argv"), proof.get("context_files")
    need(isinstance(argv, list) and all(isinstance(x, str) for x in argv)
         and isinstance(files, dict), "execution context arguments are unavailable.")
    if parser:
        need(argv.count("ReleasedParserCoverage") == 1, "coverage bridge invocation is ambiguous.")
        args = argv[argv.index("ReleasedParserCoverage") + 1:]
        need(len(args) == 5, "coverage bridge arguments differ from the reviewed API.")
        names = [Path(path).name for path in args[2:4]]
    else:
        positions = [i for i, value in enumerate(argv) if value == "--contexts"]
        need(len(positions) == 2 and all(i + 1 < len(argv) for i in positions),
             "producer must declare the two separate ordered prefix contexts.")
        names = [Path(argv[i + 1]).name for i in positions]
    need(len(set(names)) == 2 and all(name in files for name in names), "context arguments do not match their file pins.")
    return [files[name] for name in names]


def verify_sparse_proof(prepared, base_lines, headers, table, producer, coverage_execution,
                        coverage_path, inference_sha256, base_gaf_sha256, ontology_binding,
                        gaference, prefix_context_sha256):
    """Validate actual released-parser coverage for the published sparse delta.

    No passing entries are inserted. Absence has the official rule13 meaning
    only after successful, same-input producer and exact parser-key coverage.
    """
    for proof in (producer, coverage_execution):
        need(proof.get("input_gaf_sha256") == base_gaf_sha256,
             "execution proof uses a different prepared GAF.")
        version = re.search(r"/go/releases/([0-9]{4}-[0-9]{2}-[0-9]{2})/", str(proof.get("ontology_version")))
        current = re.search(r"/go/releases/([0-9]{4}-[0-9]{2}-[0-9]{2})/", ontology_binding["ontology_version"])
        need(version is not None and current is not None and version.group(1) == current.group(1),
             "reasoning ontology and native GO release differ.")
        need(isinstance(proof.get("ontology_sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", proof["ontology_sha256"]),
             "reasoning ontology byte pin is unavailable.")
        need(isinstance(proof.get("context_files"), dict)
             and sorted(proof["context_files"].values()) == sorted(prefix_context_sha256),
             "reasoner prefix contexts differ from the official QC runtime.")
    need(_ordered_contexts(producer) == _ordered_contexts(coverage_execution, parser=True)
         == prefix_context_sha256, "producer and coverage prefix context order differs from the verified contract.")
    need(producer.get("output_sha256") == inference_sha256,
         "sparse output differs from its successful producer receipt.")
    need(coverage_execution.get("ontology_sha256") == producer["ontology_sha256"],
         "coverage and producer use different reasoning ontologies.")
    need(isinstance(producer.get("runtime_files"), dict) and bool(producer["runtime_files"])
         and coverage_execution.get("runtime_files") == producer["runtime_files"],
         "coverage and producer do not bind the same released runtime files.")
    need(coverage_execution.get("output_sha256") == sha(coverage_path),
         "released parser coverage differs from its execution receipt.")
    need(coverage_execution.get("coverage_source_sha256") == sha(Path(__file__).with_name("ReleasedParserCoverage.java")),
         "released-parser bridge source differs from its execution receipt.")
    need(isinstance(coverage_execution.get("coverage_class_sha256"), str)
         and re.fullmatch(r"[a-f0-9]{64}", coverage_execution["coverage_class_sha256"]),
         "compiled released-parser bridge is unbound.")
    records = [gold_packet._decode(line) for line in Path(coverage_path).read_bytes().splitlines()]
    need(len(records) == len(prepared) and coverage_execution.get("output_rows") == len(records),
         "released parser coverage row count differs from prepared GAF.")
    all_keys, matched, exempt = set(), 0, 0
    for index, ((rid, annotation), source_line, row) in enumerate(zip(prepared, base_lines, records, strict=True)):
        need(isinstance(row, dict) and set(row) == {"gaf_line", "raw_line_sha256", "released_parser_keys"}
             and row["gaf_line"] == len(headers) + index + 1
             and row["raw_line_sha256"] == hashlib.sha256(source_line.encode("utf-8")).hexdigest()
             and isinstance(row["released_parser_keys"], list),
             "released parser coverage does not bind the exact prepared row.")
        keys = {_coverage_key(key, gaference) for key in row["released_parser_keys"]}
        expected = {canonical_query_key(key, gaference) for key in gaference.make_keys_from_gaf(annotation)}
        if annotation.negated:
            exempt += 1
        else:
            need(bool(keys) and keys == expected,
                 "released parser dropped or changed a non-NOT annotation key: " + rid)
            matched += 1
        all_keys.update(keys)
    need(set(table) <= all_keys, "sparse delta includes a key outside released-parser coverage.")
    return {"producer_execution_sha256": producer["content_sha256"],
            "coverage_execution_sha256": coverage_execution["content_sha256"],
            "coverage_file_sha256": sha(coverage_path), "covered_non_not_associations": matched,
            "negated_exempt_associations": exempt, "constructed_unique_keys": len(all_keys),
            "explicit_sparse_delta_keys": len(table),
            "ordered_prefix_context_sha256": prefix_context_sha256,
            "typed_extension_query_normalization": "Official registered-relation curie_to_obo_uri plus strict prefixcommons filler expansion.",
            "normal_absent_keys_materialized_as_pass_entries": False,
            "interpretation": "Official sparse delta after verified successful processing: no reported taxon problem is not experimental truth."}


def offline_requests(pinned_sources, calls):
    """Replay only exact pinned ECO responses; prohibit every other request.

    ontobio fetches these maps during import. Standard Requests transport
    interception supplies preserved source bytes without editing its parsers,
    mapping implementation or GO rule bodies.
    """
    import requests

    def request(session, method, url, **kwargs):
        need(str(method).upper() == "GET" and url in ECO_URLS,
             "unrecorded network request prohibited: " + str(url))
        data = pinned_sources[ECO_URLS[url]]
        calls.append({"url": url, "source": ECO_URLS[url], "response_sha256": hashlib.sha256(data).hexdigest()})
        response = requests.Response()
        response.status_code = 200
        response._content = data
        response.url = url
        response.encoding = "utf-8"
        return response

    return patch.object(requests.sessions.Session, "request", new=request)


def run(qualification, ontology, retracted_refs, eco_mapping, eco_derived_mapping, output, *,
        ontology_sha256, retracted_sha256, eco_sha256, eco_derived_sha256,
        inferences=None, inferences_sha256=None, inferences_source_gaf_sha256=None,
        inferences_ontology_version=None, inference_mode="complete_keys",
        inference_execution=None, parser_coverage=None, parser_execution=None):
    """Run native source QC; never mutate the source or the saved app graph."""
    from biograph_steward import go_context_inspection
    load_go_context = go_context_inspection.load_go_context

    need(importlib.metadata.version("ontobio") == ONTOBIO_VERSION,
         "use the inspected official ontobio==" + ONTOBIO_VERSION)
    need(importlib.metadata.version("prefixcommons") == PREFIXCOMMONS_VERSION,
         "use the inspected prefixcommons==" + PREFIXCOMMONS_VERSION)
    source_report, native_rows, _ = load_go_context(qualification)
    need(inference_mode in {"complete_keys", "published_sparse_delta"}, "unsupported inference mode.")
    paths = {"ontology": pinned_file(ontology, ontology_sha256),
             "retracted": pinned_file(retracted_refs, retracted_sha256),
             "eco": pinned_file(eco_mapping, eco_sha256),
             "eco_derived": pinned_file(eco_derived_mapping, eco_derived_sha256)}
    nodes, ontology_binding, ontology_bytes = load_ontology(paths["ontology"], ontology_sha256)
    del nodes
    go_headers = [line.removeprefix("!go-version:").strip() for line in source_report["source"]["headers"]
                  if line.startswith("!go-version:")]
    header_dates = [re.search(r"/go/releases/([0-9]{4}-[0-9]{2}-[0-9]{2})/", value) for value in go_headers]
    ontology_date = re.search(r"/go/releases/([0-9]{4}-[0-9]{2}-[0-9]{2})/", ontology_binding["ontology_version"])
    need(len(header_dates) == 1 and header_dates[0] is not None and ontology_date is not None
         and header_dates[0].group(1) == ontology_date.group(1),
         "native GAF and ontology must declare the same dated GO release.")
    if inferences is not None:
        paths["inferences"] = pinned_file(inferences, inferences_sha256)
        inference_source = json.loads(paths["inferences"].read_text())
        need(isinstance(inference_source, list) and (bool(inference_source) or inference_mode == "published_sparse_delta"),
             "a real, nonempty inference table or proven published sparse delta is required for rule13.")
        need(all(isinstance(row, dict) and set(row) == {"annotation", "inferences", "satisfiable", "taxonProblem"}
             and type(row["satisfiable"]) is bool and type(row["taxonProblem"]) is bool
             and isinstance(row["inferences"], list)
             and all(isinstance(link, dict) and set(link) == {"relation", "term"}
                 and all(isinstance(v, str) and v for v in link.values()) for link in row["inferences"])
             for row in inference_source), "inference output does not match the reviewed GAFeRence schema.")
        if inference_mode == "published_sparse_delta":
            need(all(row["inferences"] or not row["satisfiable"] for row in inference_source),
                 "published GAFeRence output contains a normal non-delta entry.")
        need(isinstance(inferences_source_gaf_sha256, str)
             and re.fullmatch(r"[a-f0-9]{64}", inferences_source_gaf_sha256),
             "GAFeRence requires the declared exact input GAF SHA256.")
        need(inferences_ontology_version == ontology_binding["ontology_version"],
             "GAFeRence must use the same declared native GO ontology version.")
        if inference_mode == "published_sparse_delta":
            need(all(path is not None for path in (inference_execution, parser_coverage, parser_execution)),
                 "published sparse delta requires successful producer and actual parser-coverage proof.")
            paths["inference_execution"], producer_proof = _execution(inference_execution)
            paths["parser_execution"], parser_proof = _execution(parser_execution,
                "biograph-steward.gaferencer-parser-coverage.v1")
            paths["parser_coverage"] = pinned_file(parser_coverage, parser_proof.get("output_sha256"))
        else:
            need(all(path is None for path in (inference_execution, parser_coverage, parser_execution)),
                 "parser proof is supported only for published sparse-delta mode.")
    else:
        need(all(x is None for x in (inferences_sha256, inferences_source_gaf_sha256, inferences_ontology_version)),
             "inference provenance without a table is invalid.")
        need(inference_mode == "complete_keys" and all(x is None for x in
             (inference_execution, parser_coverage, parser_execution)), "inference proof without a table is invalid.")
        inference_source = None
    pins = {name: sha(path) for name, path in paths.items()}
    folder = new_output(output, qualification, *paths.values())
    transport_calls = []
    all_traces, lifecycle_calls, prepared = [], [], []
    active_id = {"value": None}
    rule_calls = []
    try:
        with offline_requests({name: paths[name].read_bytes() for name in ("eco", "eco_derived")}, transport_calls):
            from ontobio.io import assocparser, gafparser, qc, gaference
            from ontobio.ontol_factory import OntologyFactory
            from ontobio.validation import metadata
            from ontobio.ecomap import EcoMap
            from ontobio.model import association

            expected_mappings = EcoMap().parse_ecomap_str(paths["eco"].read_text())
            expected_derived = EcoMap().parse_derived_ecomap_str(paths["eco_derived"].read_text())
            need(all(mapper.mappings() == expected_mappings and mapper.derived_mappings() == expected_derived
                     for mapper in (gafparser.ecomap, qc.ecomapping, association.ecomap)),
                 "the official runtime's cached ECO mapping differs from the supplied source.")

            with tempfile.TemporaryDirectory(dir=folder) as temp:
                ont_path = Path(temp) / "ontology.json"
                ont_path.write_bytes(gzip.decompress(ontology_bytes) if ontology_bytes.startswith(b"\x1f\x8b") else ontology_bytes)
                ont = OntologyFactory().create(str(ont_path), ignore_cache=True)
            retractions = metadata.retracted_pub_set(str(paths["retracted"]))
            need(bool(retractions), "the retracted-reference set is empty or unavailable.")
            config = assocparser.AssocParserConfig(ontology=ont, repair_obsoletes=True, ecomap=gafparser.ecomap,
                retracted_pub_set=retractions, rule_set=list(SELECTED_RULES))
            need(all(config.rule_set.should_run_rule(rule) for rule in SELECTED_RULES),
                 "the official rule-set selector did not enable the requested rules.")
            parser = gafparser.GafParser(config=config, dataset="preserved-native-go-context")
            for header in source_report["source"]["headers"]:
                parser.parse_line(header + "\n")
            need(parser.gaf_version() == "2.2", "official parser did not recognize native GAF2.2.")

            def record_test(original, rule, fresh_instance):
                def invoke(instance, annotation, config, group=None):
                    # The upstream global enum keeps a rule61 closure cache.
                    # A fresh public rule instance prevents reuse of an older
                    # ontology's closure when this API runs twice in a process.
                    result = original(fresh_instance, annotation, config, group=group)
                    rule_calls.append({"native_record_id": active_id["value"], "rule": rule,
                        "result_type": result.result_type.name, "message": result.message})
                    return result
                return invoke

            lifecycle = assocparser.AssocParser._validate_ontology_class_id

            def record_lifecycle(instance, term, *args, **kwargs):
                result = lifecycle(instance, term, *args, **kwargs)
                lifecycle_calls.append({"native_record_id": active_id["value"],
                                        "input_term": term, "output_term": result})
                return result

            with ExitStack() as stack:
                stack.enter_context(patch.object(qc.GoRule22, "test", new=record_test(qc.GoRule22.test, "GORULE:0000022", qc.GoRule22())))
                stack.enter_context(patch.object(qc.GoRule61, "test", new=record_test(qc.GoRule61.test, "GORULE:0000061", qc.GoRule61())))
                stack.enter_context(patch.object(assocparser.AssocParser, "_validate_ontology_class_id", new=record_lifecycle))
                for row in native_rows:
                    active_id["value"] = row["id"]
                    associations = list(parser.association_generator(io.StringIO(row["raw_line"] + "\n"), skipheader=True))
                    after = [serialize_gaf(a) for a in associations]
                    before_fields = row["raw_line"].split("\t")
                    changed_columns = sorted({i + 1 for output_line in after for i, (old, new) in
                                              enumerate(zip(before_fields, output_line.split("\t"), strict=True))
                                              if old != new})
                    all_traces.append({"native_record_id": row["id"], "source_line": row["source_line"],
                        "before": row["raw_line"], "after_base_rules": after,
                        "base_rule_filtered": not bool(after),
                        "base_literal_output_changed": bool(after) and after != [row["raw_line"]],
                        "changed_gaf_columns": changed_columns})
                    prepared.extend((row["id"], association) for association in associations)
            official_report = parser.report.to_report_json()
            taxon = {"requested": inference_source is not None, "status": "not_run_missing_inferences",
                     "non_not_associations": sum(not a.negated for _, a in prepared),
                     "negated_exempt_associations": sum(a.negated for _, a in prepared),
                     "missing_key_associations": None, "results": []}
            final = prepared
            headers = source_report["source"]["headers"]
            base_lines = [serialize_gaf(a) for _, a in prepared]
            base_gaf = "\n".join(headers + base_lines) + "\n"
            base_gaf_sha256 = hashlib.sha256(base_gaf.encode("utf-8")).hexdigest()
            if inference_source is not None:
                need(base_gaf_sha256 == inferences_source_gaf_sha256,
                     "GAFeRence input GAF differs from the exact prepared native annotations.")
                table = gaference.build_annotation_inferences(inference_source)
                need(len(table) == len(inference_source), "inference data repeat or overwrite a semantic key.")
                if inference_mode == "published_sparse_delta":
                    from prefixcommons import curie_util
                    context_root = Path(curie_util.__file__).parent / "registry"
                    taxon["sparse_proof"] = verify_sparse_proof(prepared, base_lines, headers, table,
                        producer_proof, parser_proof, paths["parser_coverage"], pins["inferences"],
                        base_gaf_sha256, ontology_binding, gaference,
                        [sha(context_root / name) for name in ("go_context.jsonld", "obo_context.jsonld")])
                    taxon["missing_key_associations"] = 0
                else:
                    need(bool(table), "the official inference loader produced no keys.")
                    missing = [(rid, a) for rid, a in prepared if not a.negated and
                               (not gaference.make_keys_from_gaf(a) or any(
                                   canonical_query_key(k, gaference) not in table
                                   for k in gaference.make_keys_from_gaf(a)))]
                    taxon["missing_key_associations"] = len(missing)
                    need(not missing, "inference key coverage is incomplete; rule13 was not run.")
                lookup = OfficialIriQueryMapping(table, gaference, active_id)
                config.annotation_inferences = lookup
                config.rule_set = assocparser.RuleSet(["0000013"])
                rule13, final = qc.GoRule13(), []
                for rid, annotation in prepared:
                    active_id["value"] = rid
                    result = rule13.run_test(annotation, config)
                    taxon["results"].append({"native_record_id": rid, "negated_annotation_exempt": annotation.negated,
                        "result_type": result.result_type.name, "message": result.message})
                    if result.result_type != qc.ResultType.ERROR:
                        final.append((rid, annotation))
                taxon["status"] = ("executed_with_proven_sparse_delta_parser_coverage" if inference_mode == "published_sparse_delta"
                                   else "executed_with_complete_non_not_key_coverage")
                taxon["inference_keys"] = len(table)
                taxon["actual_lookup_calls"] = lookup.calls
                taxon["published_inference_entries_modified"] = False
            final_lines = [serialize_gaf(a) for _, a in final]
            (folder / "base_validated_native.gaf").write_text(base_gaf)
            (folder / "validated_native.gaf").write_text("\n".join(headers + final_lines) + "\n")
            for name, values in (("native_row_changes.jsonl", all_traces), ("official_rule_calls.jsonl", rule_calls),
                                 ("official_lifecycle_calls.jsonl", lifecycle_calls)):
                (folder / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))
            write_json(folder / "official_report.json", official_report)
            write_json(folder / "taxon_rule.json", taxon)
            code = {name: sha(module.__file__) for name, module in
                    (("assocparser", assocparser), ("gafparser", gafparser), ("qc", qc), ("gaference", gaference))}
        need(all(sha(path) == pins[name] for name, path in paths.items()), "a source changed during execution.")
        need(load_go_context(qualification)[0]["content_sha256"] == source_report["content_sha256"],
             "native source context changed during execution.")
        counts = {"native_input_records": len(native_rows), "base_output_associations": len(prepared),
                  "final_output_associations": len(final),
                  "base_filtered_native_records": sum(r["base_rule_filtered"] for r in all_traces),
                  "base_literal_changed_native_records": sum(r["base_literal_output_changed"] for r in all_traces),
                  "field_change_records": {name: sum(number in r["changed_gaf_columns"] for r in all_traces)
                      for number, name in ((4, "relation"), (5, "GO_ID"), (6, "reference"),
                                           (8, "with_from"), (16, "extensions"), (17, "product_form"))},
                  "rule_invocations": {rule: dict(Counter(x["result_type"] for x in rule_calls if x["rule"] == rule))
                                       for rule in ("GORULE:0000022", "GORULE:0000061")}}
        report = {"format": FORMAT, "created_at": utcnow(), "status": "completed",
            "source_context_report_sha256": source_report["content_sha256"], "packet_id": source_report["packet_id"],
            "input_files": {name: {"sha256": pins[name], "path": str(path)} for name, path in paths.items()},
            "ontology": ontology_binding, "ontobio_version": ONTOBIO_VERSION,
            "prefixcommons_version": PREFIXCOMMONS_VERSION, "official_code_sha256": code,
            "native_gaf_go_version": go_headers[0], "native_gaf_and_ontology_release_match": True,
            "retracted_reference_headers": [line for line in paths["retracted"].read_text().splitlines() if line.startswith("!")],
            "runtime_dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
            "explicit_qc_rule_selectors": list(SELECTED_RULES),
            "lifecycle_validation": "Official GafParser obsolete/alternative-ID validation, repair enabled, including With/From and extensions.",
            "taxon_rule_status": taxon["status"], "counts": counts,
            "inference_mode": inference_mode,
            "base_validated_native_gaf_sha256": base_gaf_sha256,
            "inference_provenance": None if inference_source is None else {
                "declared_source_gaf_sha256": inferences_source_gaf_sha256,
                "declared_native_go_ontology_version": inferences_ontology_version,
                "publisher_or_execution_authentication_performed": False},
            "pinned_transport_calls": transport_calls, "unrecorded_network_allowed": False,
            "official_methods_recorded_without_rule_body_changes": True,
            "scientific_accuracy_measured": False, "independent_biological_validation": False,
            "source_graph_changed": False, "historical_pharos_qualifiers_backfilled": False,
            "implementation_sha256": sha(__file__),
            "native_loader_implementation_sha256": sha(go_context_inspection.__file__),
            "limits": ["GO quality-control agreement is not experimental biological truth.",
                       "Retraction metadata has its own capture date and does not certify current completeness.",
                       "GAF serialization can change representation without changing biological meaning.",
                       "Official parser messages can include auto-pass entries for unselected rules; actual invocations are recorded separately.",
                       "Native GOA source QC does not identify the historical Pharos source record or establish independent evidence."]}
        report["files"] = {p.name: sha(p) for p in folder.iterdir() if p.is_file()}
        report["content_sha256"] = digest(report)
        write_json(folder / "report.json", report)
        return report
    except Exception as exc:
        write_json(folder / "failure.json", {"status": "failed_unsealed", "error": type(exc).__name__ + ": " + str(exc),
                                             "source_graph_changed": False})
        raise


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("qualification", "ontology", "retracted-refs", "eco-mapping", "eco-derived-mapping", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    for name in ("ontology-sha256", "retracted-sha256", "eco-sha256", "eco-derived-sha256"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--inferences", type=Path)
    p.add_argument("--inferences-sha256")
    p.add_argument("--inferences-source-gaf-sha256")
    p.add_argument("--inferences-ontology-version")
    p.add_argument("--inference-mode", choices=("complete_keys", "published_sparse_delta"), default="complete_keys")
    p.add_argument("--inference-execution", type=Path)
    p.add_argument("--parser-coverage", type=Path)
    p.add_argument("--parser-execution", type=Path)
    args = vars(p.parse_args())
    args["output"] = args.pop("out")
    print(json.dumps({"report_sha256": run(**args)["content_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
