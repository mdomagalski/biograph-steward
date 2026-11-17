"""Publish expert CIViC Assertions separately from reported Evidence Items.

The API's full molecular profile, disease and therapy combination are preserved.
Exact structured context overlap is diagnostic only: an Assertion conclusion
does not falsify a historical reported observation, and free-text clinical
conditions are not automatically validated by matching scalar fields.
"""
from pathlib import Path
import argparse
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json, utcnow
from biograph_steward.file_utils import sha, new_output
from tools.reference_accuracy.design import need, write_jsonl


def context_key(record):
    """Exact native IDs only; no gene-to-variant or combination-to-drug inference."""
    try:
        mp, disease, therapies = (record[key] for key in ("molecularProfile", "disease", "therapies"))
        if (record["status"] != "ACCEPTED" or record["flagged"] is not False or record["openRevisionCount"] != 0
                or mp["deprecated"] is not False or mp["flagged"] is not False or disease["deprecated"] is not False
                or not therapies or any(t["deprecated"] is not False for t in therapies)):
            return None
        variants = []
        for v in mp["variants"]:
            f = v["feature"]
            if v["deprecated"] is not False or v["flagged"] is not False or f["deprecated"] is not False:
                return None
            variants.append((v["id"], f["id"], f["featureInstance"]["__typename"], f["featureInstance"].get("entrezId")))
        if not variants or len(set(variants)) != len(variants):
            return None
        therapy_ids = [(t["id"], t["ncitId"]) for t in therapies]
        if len(set(therapy_ids)) != len(therapy_ids):
            return None
        kind = record.get("assertionType", record.get("evidenceType"))
        if kind != "PREDICTIVE" or record["variantOrigin"] not in {"SOMATIC", "GERMLINE"}:
            return None
        if (any(type(x) is not int or x < 1 for x in [mp["id"], disease["id"],
                *[v[0] for v in variants], *[v[1] for v in variants], *[t[0] for t in therapy_ids]])
                or type(mp["isComplex"]) is not bool or type(mp["isMultiVariant"]) is not bool
                or not isinstance(disease["doid"], str) or not disease["doid"]):
            return None
        return (mp["id"], mp["isComplex"], mp["isMultiVariant"], tuple(sorted(variants)),
                disease["id"], disease["doid"], tuple(sorted(therapy_ids)),
                record["therapyInteractionType"], record["variantOrigin"], kind)
    except (KeyError, TypeError):
        return None


def checked(path, pin):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and sha(path) == pin, "CIViC proof file/pin differs.")
    value = gold_packet._read(path)
    need(gold_packet._sealed(value), "CIViC proof content seal differs.")
    return value


def native_response_rows(capture):
    rows = []
    for request in capture["request_records"]:
        need(request["endpoint"] == "https://civicdb.org/api/graphql"
             and digest(request["response"]) == request["response_sha256"], "CIViC response source/seal differs.")
        result = request["response"]["data"]["assertions"]
        rows.extend(result["nodes"])
    need(capture["request_records"] and result["pageInfo"]["hasNextPage"] is False
         and result["totalCount"] == len(rows), "CIViC captured native pagination is incomplete.")
    need(rows == capture["assertions"] and len({r["id"] for r in rows}) == len(rows), "CIViC records differ from preserved API responses.")
    return rows


def prepare(packet, expert, inventory, plan, output, *, expert_sha256, inventory_sha256, plan_sha256):
    packet, expert, inventory, plan = map(lambda p: Path(p).absolute(), (packet, expert, inventory, plan))
    manifest, graph = gold_packet.load_packet(packet)
    e, context, source_plan = checked(expert, expert_sha256), checked(inventory, inventory_sha256), checked(plan, plan_sha256)
    need(source_plan.get("baseline_packet_id") == manifest["packet_id"]
         and source_plan.get("baseline_graph_sha256") == manifest["graph_sha256"]
         and source_plan.get("baseline_packet_manifest_sha256") == sha(packet / "packet_manifest.json")
         and source_plan.get("selection_uses_conclusion_labels") is False
         and source_plan.get("reference_conclusion_fields_opened") is False,
         "CIViC reviewed source plan belongs to another graph or outcome-selected scope.")
    rows, context_rows = native_response_rows(e), native_response_rows(context)
    need(e["source_plan_sha256"] == context["source_plan_sha256"] == plan_sha256
         and e["context_inventory_file_sha256"] == inventory_sha256
         and e["context_inventory_content_sha256"] == context["content_sha256"]
         and context["conclusion_labels_retrieved"] is False, "CIViC context-before-conclusion binding differs.")
    need({r["id"] for r in rows} == {r["id"] for r in context_rows}
         and len(rows) == context["total_count"], "CIViC selected native Assertion inventory differs.")
    prior = {r["id"]: r for r in context_rows}
    need(all(context_key(r) is not None and context_key(r) == context_key(prior[r["id"]]) for r in rows),
         "CIViC native context changed or source eligibility differs.")
    need(all(r["disease"]["id"] == source_plan["source"]["disease_id"]
             and r["disease"]["doid"] == source_plan["source"]["disease_doid"]
             and r["assertionType"] == source_plan["source"]["assertion_type"]
             and r["status"] == source_plan["source"]["status"] for r in rows), "CIViC exact reviewed reference scope differs.")
    ref_by_key = {}
    claims = []
    for row in rows:
        ref_by_key.setdefault(context_key(row), []).append(row["id"])
        claims.append({"id": "CIViC.assertion:" + str(row["id"]), "source_url": "https://civicdb.org/assertions/" + str(row["id"]),
            "claim_kind": "expert_curated_clinical_interpretation", "native_record": row,
            "context_key": context_key(row), "free_text_clinical_qualifiers_preserved": True,
            "gene_or_drug_generalization_performed": False, "original_graph_assertion_replaced": False,
            "label_producer": "CIViC accepted expert editorial curation, not project AI",
            "independent_experimental_replication_established": False})
    overlap = []
    for edge in graph["edges"]:
        if edge.get("record_kind") != "variant_therapy_response":
            continue
        matches = ref_by_key.get(context_key(edge["evidence_record"]), [])
        overlap.append({"edge_id": edge["id"], "assertion_id": edge["assertion_id"],
            "native_evidence_id": edge["evidence_record"]["id"], "exact_context_Assertion_ids": matches,
            "clinical_accuracy_verdict": "unknown", "predicate_scope_mismatch": True,
            "reason": "Reported study observation is not an aggregate clinical conclusion; scalar context overlap alone is insufficient."})
    pins = {str(expert): expert_sha256, str(inventory): inventory_sha256, str(plan): plan_sha256,
        str(packet / "packet_manifest.json"): sha(packet / "packet_manifest.json"),
        **{str(packet / name): pin for name, pin in manifest["files"].items()}}
    code_pin = sha(__file__)
    out = new_output(output, packet, expert, inventory, plan)
    for source, name in ((expert, "expert_reference.json"), (inventory, "context_inventory.json"), (plan, "source_plan.json")):
        shutil.copyfile(source, out / name)
        need(sha(source) == sha(out / name) == pins[str(source)], "CIViC copied proof differs.")
    write_jsonl(out / "expert_clinical_claims.jsonl", claims)
    write_jsonl(out / "original_graph_context_coverage.jsonl", overlap)
    need(all(sha(path) == pin for path, pin in pins.items()) and sha(__file__) == code_pin,
         "CIViC source or implementation changed during export.")
    report = {"format": "biograph-steward.civic-expert-Assertion-layer.v1", "created_at": utcnow(),
        "packet_id": manifest["packet_id"], "graph_sha256": manifest["graph_sha256"],
        "expert_Assertions": len(claims), "original_civic_evidence_edges": len(overlap),
        "original_civic_assertions": len({r["assertion_id"] for r in overlap}),
        "exact_context_matched_edges": sum(bool(r["exact_context_Assertion_ids"]) for r in overlap),
        "clinical_accuracy_resolved": 0, "source_graph_changed": False, "original_audits_changed": False,
        "expert_labels_independent_of_project_AI": True, "independent_primary_studies_established": False,
        "label_selection": "Outcome-free exact native accepted predictive disease context inventory, then preserved expert conclusions.",
        "data_license": {"identifier": "CC0-1.0", "url": "https://docs.civicdb.org/en/latest/about/faq.html"},
        "input_files_sha256": pins, "implementation_sha256": code_pin,
        "limitations": ["Expert Assertions can include disagreeing Evidence Items; linked membership does not establish agreement.",
            "Molecular profiles and whole therapy sets remain exact; subsets, aliases and disease ancestors are not inferred.",
            "Structured context agreement cannot validate omitted stage, treatment-line or guideline conditions in the clinical text.",
            "These clinical interpretations remain separate from the graph's reported-study-observation predicate."],
        "files": {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    report["content_sha256"] = digest(report); write_json(out / "report.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("packet", "expert", "inventory", "plan", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    for key in ("expert-sha256", "inventory-sha256", "plan-sha256"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    print(prepare(a.packet, a.expert, a.inventory, a.plan, a.out, expert_sha256=a.expert_sha256,
        inventory_sha256=a.inventory_sha256, plan_sha256=a.plan_sha256)["content_sha256"])


if __name__ == "__main__":
    main()
