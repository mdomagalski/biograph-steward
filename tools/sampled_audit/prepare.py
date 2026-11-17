#!/usr/bin/env python3
"""Prepare a frozen stratified SRSWOR evidence audit from a verified Gold packet.

The design is ordinary probability sampling, not a correctness classifier.
Existing assertion identities and source inspection supply every dossier.
Nothing here labels biological truth, retrieves evidence or changes a graph.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import load_packet
from biograph_steward.inspection import inspect_selection

FORMAT = "biograph-steward.stratified-assertion-audit.v1"
STATUS_FIELDS = ("source_relative_support", "primary_evidence_support")
METHOD = {
    "name": "Fixed stratified simple random sampling without replacement",
    "stratum": "exact assertion kind",
    "unit": "complete qualified assertion, including all source evidence edges",
    "within_stratum": "Python Random.sample on sorted exact assertion IDs",
    "selection_is_label_independent": True,
    "foundation": "https://www.vldb.org/pvldb/vol12/p1679-gao.pdf",
    "variance_reference": "https://ccsg.isr.umich.edu/chapters/sample-design/appendix-c/",
    "not_a_reproduction_of": "SIGMOD 2025 replacement-sampling simulator or VLDB 2026 LLM stratification",
}
CRITERIA = {
    "source_relative_support": {
        "supported": "The preserved source supports the exact stored qualified assertion; this can establish listing/annotation existence without experimental truth.",
        "contradicted": "The exact preserved source contradicts the stored assertion or a source/identifier/qualifier transformation is demonstrably wrong.",
        "unresolved": "Source binding, missing context or unavailable evidence prevents a defensible source-relative decision.",
    },
    "primary_evidence_support": {
        "supported": "Examined primary article, source dataset or curation record supports the exact qualified claim; name its evidence type and shared lineage explicitly.",
        "contradicted": "Examined primary evidence contradicts the exact qualified claim, including its direction and conditions.",
        "unresolved": "No sufficient primary evidence was examined, or it does not resolve the exact qualified claim. Missing evidence is not a negative.",
    },
    "independent_scientific_correctness": "unreviewed: these AI-assisted audits are not qualified independent biological truth judgments",
    "general": [
        "Assess the predicate as stored; do not replace annotation existence, a drug listing, proximity or functional association with direct binding or causation.",
        "Keep NOT, evidence direction, species, form, variants, therapy combinations, cell/tissue and assay qualifiers attached.",
        "An obsolete identifier can be a currency defect while the historical source assertion remains faithful.",
        "Source presence, primary support and independent scientific correctness are distinct outcomes.",
        "A second database name or shared citation is not independent replication.",
        "Retain unresolved judgments in the sampled population and preserve the original inclusion probabilities.",
    ],
}


def need(condition, message):
    if not condition:
        raise ValueError("Sampled assertion audit: " + message)


def draw_sample(assertions, allocation, seed):
    """Return exact selected identities and first-order inclusion probabilities."""
    need(type(seed) is int and seed >= 0, "provide a nonnegative integer random seed.")
    need(isinstance(allocation, dict) and allocation, "provide an explicit nonempty stratum allocation.")
    groups = defaultdict(list)
    ids = set()
    for assertion in assertions:
        uid, kind = assertion.get("id"), assertion.get("kind")
        need(isinstance(uid, str) and uid and uid not in ids and isinstance(kind, str) and kind,
             "assertion IDs must be unique and kinds explicit.")
        ids.add(uid)
        groups[kind].append(uid)
    need(set(allocation) == set(groups), "allocation must cover every assertion kind exactly.")
    rng, strata, rows = random.Random(seed), {}, []
    for kind in sorted(groups):
        population = sorted(groups[kind])
        n, total = allocation[kind], len(population)
        need(type(n) is int and 1 <= n <= total, "sample allocation must be positive and no larger than its population: " + kind)
        strata[kind] = {"population_size": total, "sample_size": n,
                        "inclusion_probability": {"numerator": n, "denominator": total},
                        "population_weight": total / len(assertions)}
        for uid in sorted(rng.sample(population, n)):
            rows.append({"case_id": "case_%03d" % (len(rows) + 1),
                         "assertion_id": uid, "stratum": kind,
                         "inclusion_probability": {"numerator": n, "denominator": total},
                         "inverse_inclusion_weight": total / n})
    return strata, rows


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def prepare(packet, allocation, seed, output):
    """Freeze the design before drawing and materialize source-bound dossiers."""
    implementation_pin = sha(__file__)
    manifest, graph = load_packet(packet)
    manifest_pin = sha(Path(packet) / "packet_manifest.json")
    # Freeze an outcome-independent contract before selecting or inspecting cases.
    population = Counter(a["kind"] for a in graph["assertions"])
    need(isinstance(allocation, dict) and set(allocation) == set(population),
         "allocation must cover every assertion kind exactly.")
    need(all(type(n) is int and 1 <= n <= population[k] for k, n in allocation.items()),
         "every allocation must be within its positive population size.")
    need(type(seed) is int and seed >= 0, "provide a nonnegative integer random seed.")
    folder = new_output(output, packet)
    protocol = {"format": FORMAT, "created_at": utcnow(),
        "packet_id": manifest["packet_id"], "baseline_graph_sha256": manifest["graph_sha256"],
        "packet_manifest_file_sha256": manifest_pin,
        "population_unit": "assertion", "population_size": len(graph["assertions"]),
        "evidence_edge_count": len(graph["edges"]), "population_by_stratum": dict(sorted(population.items())),
        "sample_allocation": dict(sorted(allocation.items())), "seed": seed,
        "method": METHOD, "review_criteria": CRITERIA,
        "intervention": {"policy": "existing separate active-primary-GO-ID view",
            "policy_code": "biograph_steward/go_ontology_qualification.py",
            "policy_implementation_sha256": sha(ROOT / "biograph_steward/go_ontology_qualification.py"),
            "scope": "ontology currentness, not a false-biological-relationship classifier",
            "paired_metrics": ["source-supported assertions removed", "source-contradicted assertions removed",
                               "unresolved assertions removed/retained", "exact ontology-currency defect census"],
            "review_dossiers_hide_intervention_dispositions": True},
        "evaluation_boundary": {"review_kind": "AI-assisted source/primary-evidence audit",
            "biological_accuracy_estimated": False, "independent_scientific_labels_generated": False,
            "population_accuracy_confidence_interval_planned": False,
            "unresolved_cases_dropped": False, "source_graph_changed": False,
            "new_model_inference_calls": 0, "primary_evidence_fetched_by_preparation": False}}
    protocol["content_sha256"] = digest(protocol)
    write_json(folder / "protocol.json", protocol)
    strata, sample = draw_sample(graph["assertions"], allocation, seed)
    sample_id = "audit:" + digest({"protocol": protocol["content_sha256"], "sample": sample})
    by_id = {a["id"]: a for a in graph["assertions"]}
    edges = {e["id"]: e for e in graph["edges"]}
    nodes = {n["id"]: n for n in graph["nodes"]}
    (folder / "cases").mkdir()
    templates = []
    for item in sample:
        assertion = by_id[item["assertion_id"]]
        selected_edges = [deepcopy(edges[uid]) for uid in assertion["evidence_edge_ids"]]
        inspected = inspect_selection(graph, assertion["id"])
        dossier = {"format": "biograph-steward.sampled-assertion-dossier.v1",
            "sample_id": sample_id, "protocol_content_sha256": protocol["content_sha256"],
            **item, "assertion": deepcopy(assertion), "assertion_content_sha256": digest(assertion),
            "source_edges": selected_edges,
            "source_edge_content_sha256": {e["id"]: digest(e) for e in selected_edges},
            "endpoint_nodes": [deepcopy(nodes[uid]) for uid in sorted({assertion["subject"], assertion["object"]})],
            "source_inspection": inspected, "intervention_disposition_exposed": False,
            "scientific_judgment": "not assigned by preparation"}
        dossier["content_sha256"] = digest(dossier)
        path = "cases/" + item["case_id"] + ".json"
        write_json(folder / path, dossier)
        item["dossier_path"] = path
        item["dossier_content_sha256"] = dossier["content_sha256"]
        templates.append({"case_id": item["case_id"], "assertion_id": item["assertion_id"],
            "stratum": item["stratum"], "sample_id": sample_id,
            "dossier_content_sha256": dossier["content_sha256"],
            **{field: None for field in STATUS_FIELDS},
            "independent_scientific_correctness": "unreviewed", "review_actor": None,
            "source_relative_reason": None, "primary_evidence_reason": None,
            "evidence_basis": [], "reference_independence": "not established"})
    write_jsonl(folder / "sample.jsonl", sample)
    write_jsonl(folder / "reviews.template.jsonl", templates)
    # A completed sample must still bind the verified source it started with.
    # Replaying at scoring time is an additional check, not a substitute for
    # refusing a source change before publishing this preparation's seal.
    need(load_packet(packet)[0] == manifest
         and sha(Path(packet) / "packet_manifest.json") == manifest_pin,
         "source packet changed during sample preparation.")
    need(sha(__file__) == implementation_pin
         and sha(ROOT / "biograph_steward/go_ontology_qualification.py")
             == protocol["intervention"]["policy_implementation_sha256"],
         "preparation or bound policy implementation changed.")
    report = {"format": FORMAT, "sample_id": sample_id,
        "protocol_content_sha256": protocol["content_sha256"], "packet_id": manifest["packet_id"],
        "baseline_graph_sha256": manifest["graph_sha256"], "strata": strata,
        "population_size": len(graph["assertions"]), "sample_size": len(sample),
        "scientific_accuracy_measured": False, "review_judgments_generated": False,
        "files": {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*")) if p.is_file()},
        "implementation_sha256": implementation_pin}
    report["content_sha256"] = digest(report)
    write_json(folder / "sample_manifest.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", required=True, type=Path)
    p.add_argument("--allocation", required=True, type=Path, help="JSON object of exact assertion kind to sample size")
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    report = prepare(args.packet, json.loads(args.allocation.read_text()), args.seed, args.out)
    print(json.dumps({key: report[key] for key in ("sample_id", "population_size", "sample_size", "content_sha256")}, indent=2))


if __name__ == "__main__":
    main()
