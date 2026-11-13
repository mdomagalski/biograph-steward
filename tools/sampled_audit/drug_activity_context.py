#!/usr/bin/env python3
"""Inspect existing Pharos drug activity context without changing an assertion.

The public Ligand/LigandActivity API already supplies identifiers and references
omitted from a thin drug-listing projection. This adapter preserves those rows;
it does not infer activity units, assay conditions, clinical utility or truth.
The API has no activity pagination, so live reads require a bounded size check.
"""
from copy import deepcopy
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import PharosClient, digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha

FORMAT = "biograph-steward.drug-activity-context.v1"
SIZE_QUERY = "query DrugActivitySize($id:String!){dbVersion ligand(ligid:$id){ligid name isdrug actcnt}}"
QUERY = "query SampleDrugActivity($id:String!){dbVersion ligand(ligid:$id){ligid name isdrug synonyms{name value} smiles actcnt targetCount activities(all:true){actid type value moa reference target{uniprot sym tcrdid name} pubs{pmid}}}}"


def need(condition, message):
    if not condition:
        raise ValueError("Drug activity context: " + message)


def identity(dossier):
    need(gold_packet._sealed(dossier)
         and dossier.get("format") == "biograph-steward.sampled-assertion-dossier.v1",
         "provide an intact frozen assertion dossier.")
    assertion = dossier.get("assertion", {})
    need(assertion.get("kind") == "drug_listing"
         and assertion.get("predicate") == "biograph:has_drug_listing",
         "only the stored target-linked drug-listing predicate is supported.")
    subject, obj = assertion.get("subject", ""), assertion.get("object", "")
    need(subject.startswith("UniProtKB:") and obj.startswith("pharos.ligand:"),
         "the original target accession and local ligand identifier are required.")
    uniprot, ligid = subject.split(":", 1)[1], obj.split(":", 1)[1]
    need(bool(uniprot) and re.fullmatch(r"[A-Z0-9]{12}", ligid),
         "the original ligand must be an explicit LyCHI layer-4 identifier.")
    need(dossier.get("assertion_id") == assertion.get("id")
         and dossier.get("assertion_content_sha256") == digest(assertion),
         "assertion identity or content binding differs.")
    edges = dossier.get("source_edges")
    need(isinstance(edges, list) and bool(edges)
         and {e.get("id") for e in edges} == set(assertion.get("evidence_edge_ids", []))
         and all(e.get("subject") == subject and e.get("object") == obj
                 and e.get("predicate") == assertion["predicate"]
                 and e.get("evidence_record", {}).get("ligid") == ligid
                 and dossier.get("source_edge_content_sha256", {}).get(e["id"]) == digest(e)
                 for e in edges), "original source edge/ligand bindings differ.")
    return uniprot, ligid


def inspect_record(dossier, record, *, max_activities=1000):
    """Bind a saved existing-client response to the exact frozen listing.

    A current record match is context enrichment, not a historical actid
    crosswalk, independent replication, biological verdict or graph update.
    """
    need(type(max_activities) is int and 1 <= max_activities <= 5000,
         "the activity bound must be an integer from 1 to 5000.")
    uniprot, ligid = identity(dossier)
    need(isinstance(record, dict) and record.get("request") == {
        "query": QUERY, "variables": {"id": "LYCHI:" + ligid}},
        "response must come from the fixed exact-LyCHI activity request.")
    response = record.get("response")
    PharosClient._validate_response(response)
    need(record.get("response_sha256") == digest(response), "response bytes/content changed.")
    data = response["data"]
    need(isinstance(data.get("dbVersion"), str) and bool(data["dbVersion"]),
         "current database version is missing.")
    ligand = data.get("ligand")
    need(isinstance(ligand, dict) and ligand.get("ligid") == ligid,
         "current response does not resolve the exact original ligand; no name substitution is permitted.")
    rows = ligand.get("activities")
    need(isinstance(rows, list) and len(rows) <= max_activities
         and type(ligand.get("actcnt")) is int and ligand["actcnt"] == len(rows),
         "activity list is absent, over its bound or inconsistent with its reported count.")
    seen, exact, other, unresolved = set(), [], [], []
    for i, row in enumerate(rows):
        need(isinstance(row, dict) and type(row.get("actid")) is int
             and row["actid"] not in seen, "activity IDs are absent or duplicated.")
        seen.add(row["actid"])
        target = row.get("target")
        accession = target.get("uniprot") if isinstance(target, dict) else None
        entry = {"pointer": "/response/data/ligand/activities/" + str(i),
                 "record": deepcopy(row)}
        if accession == uniprot:
            exact.append(entry)
        elif isinstance(accession, str) and accession:
            other.append(entry)
        else:
            unresolved.append(entry)
    result = {"format": FORMAT, "created_at": utcnow(),
        **{k: dossier[k] for k in ("case_id", "assertion_id", "sample_id")},
        "dossier_content_sha256": dossier["content_sha256"],
        "stored_predicate": "biograph:has_drug_listing", "uniprot": uniprot,
        "ligid": ligid, "database_version": data["dbVersion"],
        "source_response_sha256": record["response_sha256"],
        "source_request_sha256": digest({"endpoint": record.get("endpoint"), **record["request"]}),
        "source_ligand": {k: deepcopy(v) for k, v in ligand.items() if k != "activities"},
        "activity_counts": {"returned": len(rows), "exact_target": len(exact),
                            "other_target": len(other), "unresolved_target": len(unresolved)},
        "exact_target_activities": exact, "other_target_activities": other,
        "unresolved_target_activities": unresolved,
        "unit_or_scale": "not supplied by this API schema; raw values are not converted",
        "native_assay_context": "not supplied by this API; follow explicit native identifiers/references",
        "reference_independence": "not established; source rows and publications may be reused",
        "source_graph_changed": False, "assertion_qualifiers_backfilled": False,
        "review_labels_assigned": False, "scientific_accuracy_measured": False,
        "limits": ["Current activity context is not original historical record identity.",
            "No exact activity found is missing context, not a biological negative.",
            "Chemical synonyms remain source-provided identifiers; multiple IDs are not collapsed.",
            "No direct binding, efficacy, species, variant or potency consensus is inferred."]}
    result["content_sha256"] = digest(result)
    return result


def capture(dossier, client, *, max_activities=1000):
    """At most two existing-client calls; refuse a large unpaginated request."""
    uniprot, ligid = identity(dossier)
    need(type(max_activities) is int and 1 <= max_activities <= 5000,
         "the activity bound must be an integer from 1 to 5000.")
    variables = {"id": "LYCHI:" + ligid}
    data = client.execute(SIZE_QUERY, variables, cache=False)
    ligand = data.get("ligand")
    need(isinstance(ligand, dict) and ligand.get("ligid") == ligid
         and type(ligand.get("actcnt")) is int and 0 <= ligand["actcnt"] <= max_activities,
         "exact ligand is unresolved or the unpaginated activity count is unavailable/too large.")
    client.execute(QUERY, variables, cache=False)
    return inspect_record(dossier, client.records[-1], max_activities=max_activities)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossier", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--record", type=Path, help="Inspect a saved PharosClient response offline.")
    source.add_argument("--live", action="store_true", help="Make at most two explicit read-only API requests.")
    parser.add_argument("--max-activities", type=int, default=1000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    dossier = gold_packet._read(args.dossier)
    pins = {str(args.dossier.absolute()): sha(args.dossier)}
    if args.live:
        client = PharosClient(timeout=35, retries=0)
        result = capture(dossier, client, max_activities=args.max_activities)
        records = client.records
    else:
        result = inspect_record(dossier, gold_packet._read(args.record), max_activities=args.max_activities)
        records = None
        pins[str(args.record.absolute())] = sha(args.record)
    need(all(sha(name) == pin for name, pin in pins.items()), "an input changed while reading it.")
    output = new_output(args.out, args.dossier, *([args.record] if args.record else []))
    write_json(output / "context.json", result)
    if records is not None:
        write_json(output / "requests.json", records)
    write_json(output / "input_bindings.json", pins)
    print(result["content_sha256"])


if __name__ == "__main__":
    main()
