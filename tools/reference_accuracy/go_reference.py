"""Source-backed experimental GO annotation compatibility, not biological truth.

Reuse the project's native Biopython producer and complete GAF sidecar reader.
No identifier aliases, term ancestors, historical qualifiers or negative labels
are inferred. The reference can support a narrowly declared annotation claim;
it cannot prove the original Pharos record or an independent experiment.
"""
from collections import Counter
from pathlib import Path
import argparse
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet, go_qualification
from biograph_steward.go_context_inspection import load_go_context, REPORT as CONTEXT_REPORT
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha, new_output
from tools.reference_accuracy.design import need, read_rows, write_jsonl

FORMAT = "biograph-steward.go-experimental-curation-reference.v1"
AXIS = "pinned_GO_experimental_annotation_compatibility"
EXPERIMENTAL = ("EXP", "IDA", "IPI", "IMP", "IGI", "IEP", "HTP", "HDA", "HMP", "HGI", "HEP")
POLICY = {"strict_projection_fields": ["subject", "GO_ID", "evidence_code", "assigned_by", "aspect"],
    "experimental_codes": list(EXPERIMENTAL), "positive_only": True,
    "single_human_taxon_only": True, "no_isoform_or_other_product_form": True,
    "no_annotation_extensions": True, "with_from_empty_for_unqualified_scope": True,
    "opposing_strict_NOT_candidate_kept_unknown": True}
LIMITATIONS = [
    "External GO curator annotations are not labels assigned by this project's AI.",
    "Annotation and evidence reuse is possible; independent studies or experimental replication are not established.",
    "Exact current-source projection compatibility does not identify the historical Pharos record.",
    "The original relation, polarity, extensions and source references remain unknown; none is backfilled.",
    "A positive-only reference cannot identify all erroneous edges; absence, NOT and ambiguity remain unknown.",
    "Reference agreement is not whole-graph scientific accuracy, clinical accuracy or prediction benefit.",
]


def exclusion_reasons(row):
    """All context gates are literal; canonical column17 repetition is not an isoform."""
    reasons = []
    if row["evidence_code"] not in EXPERIMENTAL:
        reasons.append("not_experimental_evidence_code")
    if row["taxon_ids"] != ["taxon:9606"]:
        reasons.append("not_single_human_taxon")
    if row["gene_product_form_id"] not in (None, "", row["subject"]):
        reasons.append("distinct_product_form_not_collapsed")
    if row["annotation_extension_raw"]:
        reasons.append("native_annotation_extension_not_in_original_claim")
    if row["with_from_raw"]:
        reasons.append("native_with_from_context_not_in_original_claim")
    return reasons


def classify(graph, native, compatibility):
    """One complete verdict per original assertion; omitted families stay unknown."""
    by_native = {row["id"]: row for row in native}
    need(len(by_native) == len(native), "duplicate native GO row identity.")
    expected = go_qualification.project_compatibilities(graph, native)
    need(compatibility == expected, "native candidates differ from the actual original graph.")
    by_edge = {}
    for link in expected:
        candidates = [by_native[rid] for rid in link["native_record_ids"]]
        eligibility = [{"native_record_id": row["id"], "excluded_because": exclusion_reasons(row)} for row in candidates]
        eligible = [row for row, gate in zip(candidates, eligibility) if not gate["excluded_because"]]
        positive = [r["id"] for r in eligible if not r["negated"]]
        negative = [r["id"] for r in eligible if r["negated"]]
        verdict = "agree" if positive and not negative else "unknown"
        by_edge[link["edge_id"]] = {"edge_id": link["edge_id"], "compatibility_key": link["compatibility_key"],
            "verdict": verdict, "all_native_candidate_ids": link["native_record_ids"],
            "candidate_eligibility": eligibility, "eligible_positive_record_ids": positive,
            "eligible_NOT_record_ids": negative,
            "reason": ("exact_projection_has_unqualified_positive_experimental_curation" if verdict == "agree" else
                       "opposing_unqualified_NOT_preserved" if negative else
                       "candidate_context_or_evidence_outside_fixed_scope" if candidates else "no_exact_native_projection"),
            "historical_record_identity_established": False, "native_qualifiers_backfilled": False}
    labels = []
    for assertion in sorted(graph["assertions"], key=lambda row: row["id"]):
        edges = [by_edge[e] for e in assertion["evidence_edge_ids"] if e in by_edge]
        in_scope = assertion["kind"] == "go_annotation"
        need(not in_scope or len(edges) == len(assertion["evidence_edge_ids"]), "GO assertion has missing edge candidates.")
        # The claim is annotation existence. One eligible compatible row can
        # support that scope; any strict opposing NOT on its other evidence
        # projection leaves the whole assertion unresolved conservatively.
        opposite = any(row["eligible_NOT_record_ids"] for row in edges)
        agree = in_scope and any(row["verdict"] == "agree" for row in edges) and not opposite
        labels.append({"assertion_id": assertion["id"], "assertion_sha256": digest(assertion),
            "family": assertion["kind"], "axis": AXIS, "verdict": "agree" if agree else "unknown",
            "evidence_edge_ids": list(assertion["evidence_edge_ids"]), "edge_assessments": edges,
            "reason": "compatible_external_experimental_annotation" if agree else
                      "reference_does_not_cover_this_family" if not in_scope else "no_eligible_unopposed_reference",
            "independent_scientific_correctness": "unreviewed"})
    return labels


def checked_source(packet, context, context_sha256, plan, plan_sha256):
    packet, context, plan = map(lambda p: Path(p).absolute(), (packet, context, plan))
    need(plan.is_file() and not plan.is_symlink()
         and sha(context / CONTEXT_REPORT) == context_sha256 and sha(plan) == plan_sha256,
         "explicit GO context/source-plan pins differ.")
    source_plan = gold_packet._read(plan)
    need(gold_packet._sealed(source_plan) and source_plan.get("qualifier_policy") == POLICY,
         "reviewed fixed GO reference policy differs.")
    manifest, graph = gold_packet.load_packet(packet)
    report, native, compatibility = load_go_context(context)
    need(report["packet_id"] == manifest["packet_id"] and report["graph_sha256"] == manifest["graph_sha256"]
         and source_plan.get("context_report_sha256") == context_sha256
         and source_plan.get("context_report_content_sha256") == report["content_sha256"]
         and source_plan.get("native_GAF_sha256") == report["source"]["gaf_sha256"]
         and source_plan.get("source_url") == report["source"]["provided_source_url"], "GO source/graph bindings differ.")
    pins = {str(packet / "packet_manifest.json"): sha(packet / "packet_manifest.json"),
            **{str(packet / name): value for name, value in manifest["files"].items()},
            str(context / CONTEXT_REPORT): context_sha256,
            **{str(context / name): value for name, value in report["files"].items()}, str(plan): plan_sha256}
    return manifest, graph, report, native, compatibility, source_plan, pins


def publisher_proof(path, pin, source):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and sha(path) == pin, "publisher receipt pin differs.")
    value = gold_packet._read(path)
    need(gold_packet._sealed(value) and value.get("status") == 200
         and value.get("url") == value.get("response_url") == source["provided_source_url"]
         and value.get("expected_sha256") == value.get("actual_sha256") == source["gaf_sha256"]
         and value.get("matches_pinned_reference") is True,
         "publisher receipt does not bind the same successful official source response.")
    return value


def prepare(packet, context, plan, output, *, context_sha256, plan_sha256,
            publisher_receipt=None, publisher_receipt_sha256=None):
    values = checked_source(packet, context, context_sha256, plan, plan_sha256)
    manifest, graph, source, native, compatibility, source_plan, pins = values
    code_pin = sha(__file__)
    need((publisher_receipt is None) == (publisher_receipt_sha256 is None), "publisher receipt and pin must be paired.")
    if publisher_receipt is not None:
        publisher_proof(publisher_receipt, publisher_receipt_sha256, source["source"])
        pins[str(Path(publisher_receipt).absolute())] = publisher_receipt_sha256
    accessions = {r["compatibility_key"][0].removeprefix("UniProtKB:") for r in compatibility}
    replay, parser = go_qualification.read_native_gaf(Path(context) / "source/annotations.gaf.gz",
        accessions, source["source"]["gaf_sha256"])
    need(replay == native and all(source["source"][k] == v for k, v in parser.items()),
         "actual author-parser replay differs from the complete native sidecar.")
    labels = classify(graph, native, compatibility)
    folder = new_output(output, packet, context, plan)
    shutil.copytree(context, folder / "native_context")
    shutil.copyfile(plan, folder / "source_plan.json")
    if publisher_receipt is not None:
        shutil.copyfile(publisher_receipt, folder / "publisher_receipt.json")
        publisher_proof(folder / "publisher_receipt.json", publisher_receipt_sha256, source["source"])
    write_jsonl(folder / "reference_labels.jsonl", labels)
    copied = checked_source(packet, folder / "native_context", context_sha256,
                            folder / "source_plan.json", plan_sha256)
    need(copied[3:6] == values[3:6] and all(sha(path) == pin for path, pin in pins.items())
         and sha(__file__) == code_pin, "original/copied reference input or code changed during build.")
    report = {"format": FORMAT, "created_at": utcnow(), "packet_id": manifest["packet_id"],
        "graph_sha256": manifest["graph_sha256"], "axis": AXIS, "policy": POLICY,
        "product_form_rule": "empty or literal equality with the full subject CURIE; no isoform normalization",
        "source_plan_file_sha256": plan_sha256, "context_report_file_sha256": context_sha256,
        "publisher_receipt_file_sha256": publisher_receipt_sha256,
        "publisher_receipt_scope": "Captured ordinary HTTPS source-byte match; not experimental truth or cryptographic source attestation.",
        "source": source["source"], "author_parser_executed": parser["parser"],
        "license": {"identifier": "CC-BY-4.0", "url": "https://geneontology.org/docs/go-citation-policy/"},
        "label_producer": "external GO experimental curator annotation; deterministic exact-context compatibility",
        "counts": dict(Counter(row["verdict"] for row in labels)),
        "family_counts": dict(Counter(row["family"] for row in labels)),
        "source_graph_changed": False, "old_audits_changed": False,
        "independent_experimental_replication": False, "scientific_truth_accuracy_measured": False,
        "implementation_sha256": code_pin, "input_files_sha256": pins,
        "limitations": LIMITATIONS, "files": inventory(folder)}
    report["content_sha256"] = digest(report)
    write_json(folder / "report.json", report)
    return report


def inventory(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and p != folder / "report.json"}


def load_reference(folder, packet, *, report_sha256):
    folder = Path(folder).absolute()
    need(not any(p.is_symlink() for p in [folder, *folder.rglob("*")])
         and sha(folder / "report.json") == report_sha256, "reference directory or explicit pin differs.")
    report = gold_packet._read(folder / "report.json")
    need(gold_packet._sealed(report) and report.get("format") == FORMAT and report.get("axis") == AXIS
         and report.get("policy") == POLICY, "reference identity/policy differs.")
    need(all(report.get(k) is False for k in ("source_graph_changed", "old_audits_changed",
         "independent_experimental_replication", "scientific_truth_accuracy_measured")), "reference scope differs.")
    need(report["files"] == inventory(folder), "reference proof inventory differs.")
    values = checked_source(packet, folder / "native_context", report["context_report_file_sha256"],
                            folder / "source_plan.json", report["source_plan_file_sha256"])
    manifest, graph, source, native, links, _, pins = values
    if report.get("publisher_receipt_file_sha256") is not None:
        publisher_proof(folder / "publisher_receipt.json", report["publisher_receipt_file_sha256"], source["source"])
    need(report["packet_id"] == manifest["packet_id"] and report["graph_sha256"] == manifest["graph_sha256"]
         and report["source"] == source["source"] and report["author_parser_executed"] == source["source"]["parser"],
         "reference source/version identity differs.")
    expected = classify(graph, native, links)
    need(read_rows(folder / "reference_labels.jsonl") == expected
         and report["counts"] == dict(Counter(r["verdict"] for r in expected))
         and report["family_counts"] == dict(Counter(r["family"] for r in expected)), "reference labels do not replay.")
    need(all(sha(path) == pin for path, pin in pins.items()) and sha(folder / "report.json") == report_sha256
         and report["files"] == inventory(folder), "source/reference changed during validation.")
    return report, expected


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("packet", "context", "plan", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    for key in ("context-sha256", "plan-sha256"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--publisher-receipt", type=Path)
    p.add_argument("--publisher-receipt-sha256")
    a = p.parse_args()
    print(prepare(a.packet, a.context, a.plan, a.out, context_sha256=a.context_sha256,
                  plan_sha256=a.plan_sha256, publisher_receipt=a.publisher_receipt,
                  publisher_receipt_sha256=a.publisher_receipt_sha256)["content_sha256"])


if __name__ == "__main__":
    main()
