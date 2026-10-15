"""Deterministic molecular-profile/therapy evidence questions, not advice."""
from collections import defaultdict
from copy import deepcopy

from .client import digest
from .questions import graph_basis, INSPECTABLE

TEMPLATE = "civic_variant_therapy.v1"


def answer_civic_question(graph, *, profile="all", therapy="both", view="accepted", max_results=8,
                          max_paths=3, template=TEMPLATE, source_run=None):
    if template != TEMPLATE or not graph.get("civic"):
        raise ValueError("This question requires a saved scoped CIViC source. Retrieve it first.")
    if view not in {"accepted","candidates"} or therapy not in {"both","cetuximab","panitumumab"}:
        raise ValueError("Select a supported therapy and accepted or candidates view.")
    if type(max_results) is not int or not 1 <= max_results <= 30 or type(max_paths) is not int or not 1 <= max_paths <= 10:
        raise ValueError("Use 1–30 molecular profiles and 1–10 assertions per profile.")
    nodes = {n["id"]:n for n in graph["nodes"]}
    edges = {e["id"]:e for e in graph["edges"]}
    report=graph["civic"]
    therapy_ids={t["id"] for t in report["scope"]["therapies"] if therapy == "both" or t["name"].casefold() == therapy}
    all_profiles={a["subject"] for a in graph["assertions"] if a["kind"] == "variant_therapy_response"}
    if not isinstance(profile,str) or profile != "all" and profile not in all_profiles:
        raise ValueError("Choose an exact molecular profile from this scoped source.")
    eligible=[]
    for a in graph["assertions"]:
        if a["kind"] != "variant_therapy_response" or a["lifecycle_state"] not in INSPECTABLE:
            continue
        if profile != "all" and a["subject"] != profile:
            continue
        evidence=[edges[eid] for eid in a["structurally_usable_evidence_ids"] if eid in edges and edges[eid]["status"] == "passed_structural_checks"]
        if evidence and therapy_ids.intersection(t["id"] for t in nodes[a["object"]]["members"]):
            eligible.append((a,evidence))
    eligible.sort(key=lambda ae:(nodes[ae[0]["subject"]]["name"].casefold(),nodes[ae[0]["object"]]["name"].casefold(),
                                 ae[0]["qualifiers"]["evidence_direction"],ae[0]["qualifiers"]["response"],ae[0]["id"]))
    accepted=sum(a["lifecycle_state"] == "accepted" for a,_ in eligible)
    visible=[ae for ae in eligible if view == "candidates" or ae[0]["lifecycle_state"] == "accepted"]
    grouped=defaultdict(list)
    for a,e in visible:grouped[a["subject"]].append((a,e))
    results,citations,summary=[],[],[]
    overlap={r["evidence_id"]:r for r in report["overlap"]["rows"]}
    for mid,records in list(grouped.items())[:max_results]:
        paths=[]
        for a,evidence in records[:max_paths]:
            cid=f"E{len(citations)+1:03d}"
            citation={"id":cid,"assertion_id":a["id"],"revision":a["revision"],"kind":a["kind"],
                      "subject":a["subject"],"predicate":a["predicate"],"object":a["object"],
                      "qualifiers":deepcopy(a["qualifiers"]),"review_state":a["lifecycle_state"],
                      "source_names":deepcopy(a["source_names"]),"normalization_notes":deepcopy(a["normalization_notes"]),
                      "used_evidence_edge_ids":[e["id"] for e in evidence],"source_record_count":len(evidence),
                      "evidence_records":deepcopy(evidence),"publications":deepcopy(a["publications"]),
                      "overlap":[deepcopy(overlap[e["evidence_record"]["id"]]) for e in evidence]}
            citations.append(citation)
            did=a["qualifiers"]["disease"]
            path={"id":"path:"+digest({"assertion":a["id"],"revision":a["revision"]})[:20],"kind":a["kind"],
                  "node_ids":[mid,a["object"],did],"assertion_ids":[a["id"]],"citation_ids":[cid],
                  "review_status":"accepted" if a["lifecycle_state"] == "accepted" else "candidate_evidence"}
            paths.append(path)
            conditions=a["qualifiers"]
            levels=", ".join(sorted({e["source_context"]["evidence_level"] for e in evidence}))
            origin=conditions["variant_origin"].replace("_"," ").lower()
            effect=conditions["response"].replace("SENSITIVITYRESPONSE","sensitivity/response").replace("_"," ").lower()
            direction="supports" if conditions["evidence_direction"] == "SUPPORTS" else "does not support"
            interaction=conditions.get("therapy_interaction")
            therapy_label=nodes[a["object"]]["name"] + (f" ({interaction.lower()})" if interaction else "")
            prefix="Accepted locally" if a["lifecycle_state"] == "accepted" else "Candidate — local review required"
            statement=(f"{prefix}: CIViC {direction} {effect} for the complete molecular profile {nodes[mid]['name']} "
                       f"with {therapy_label} in {nodes[did]['name']} ({did}); variant origin {origin}, evidence level(s) {levels}.")
            summary.append({"path_id":path["id"],"profile_id":mid,"review_status":path["review_status"],"text":statement,"citation_ids":[cid]})
        results.append({"profile":deepcopy(nodes[mid]),"paths":paths,"eligible_path_count":len(records),"omitted_paths":len(records)-len(paths)})
    # Alert only on comparable source qualifications. Study/assay context is
    # still in the record text, so differing annotations are not adjudicated contradictions.
    comparison=defaultdict(list)
    for a,_ in visible:
        key=(a["subject"],a["object"],a["qualifiers"]["disease"],a["qualifiers"]["variant_origin"])
        comparison[key].append(a)
    alerts=[]
    for key,assertions in comparison.items():
        directions=defaultdict(set)
        for a in assertions:directions[a["qualifiers"]["response"]].add(a["qualifiers"]["evidence_direction"])
        divergent=("RESISTANCE" in directions and "SENSITIVITYRESPONSE" in directions
                   and "SUPPORTS" in directions["RESISTANCE"] and "SUPPORTS" in directions["SENSITIVITYRESPONSE"])
        if divergent or any(len(d)>1 for d in directions.values()):
            alerts.append({"profile_id":key[0],"therapy_set_id":key[1],"disease_id":key[2],"variant_origin":key[3],
                           "assertion_ids":[a["id"] for a in assertions],
                           "note":"Different response annotations or evidence directions for the same profile and therapy set. Review original study/assay conditions; this is not an adjudicated contradiction."})
    used_nodes={n for r in results for p in r["paths"] for n in p["node_ids"]}
    name=nodes[profile]["name"] if profile != "all" else "KRAS-containing molecular profiles"
    answer={"question_format":"biograph-steward.guided-question.v1","template":TEMPLATE,
            "source_run":source_run,"data_kind":graph["data_kind"],"snapshot_sha256":graph["snapshot_sha256"],
            "snapshot_created_at":graph["snapshot_created_at"],"database_version":graph.get("db_version"),
            "civic_snapshot_sha256":graph["civic_snapshot_sha256"],"civic_created_at":report["created_at"],
            "graph_basis_sha256":graph_basis(graph),"review_events_sha256":digest(graph.get("review_events",[])),
            "question":f"What CIViC evidence reports therapy response for {name} in Colorectal Cancer (DOID:9256)?",
            "plan":{"profile":profile,"therapy":therapy,"view":view,"max_results":max_results,"max_paths_per_profile":max_paths,
                    "source_scope":deepcopy(report["scope"]),"coverage":deepcopy(report["coverage"]),
                    "pharos_disease":deepcopy(graph["disease"]),"mapping":deepcopy(report["mapping"])},
            "availability":{"inspectable_assertions":len(eligible),"accepted_assertions":accepted,
                            "inspectable_profiles":len({a["subject"] for a,_ in eligible})},
            "overview":f"Showing {len(results)} of {len(grouped)} molecular profiles using " + ("locally accepted evidence only." if view == "accepted" else "candidate and accepted evidence for inspection."),
            "matching_profiles":len(grouped),"returned_profiles":len(results),"omitted_profiles":len(grouped)-len(results),
            "results":results,"summary":summary,"citations":citations,"nodes":[deepcopy(nodes[n]) for n in sorted(used_nodes)],
            "discordant_annotations":alerts,"overlap_summary":{k:deepcopy(v) for k,v in report["overlap"].items() if k != "rows"},
            "limitations":["CIViC Colorectal Cancer (DOID:9256) remains separate from the Pharos disease. No disease equivalence or subtype transfer is inferred.",
                "Complete molecular profiles, raw profile expressions, variant origin and therapy sets are retained. Combination/sequential/substitute evidence does not establish a single-drug effect.",
                "SUPPORTS and DOES_NOT_SUPPORT qualify the stated significance separately. Not supporting sensitivity is not automatically resistance.",
                "CIViC ACCEPTED is an editorial source status, not local acceptance. Only explicit local review produces an accepted answer.",
                "Evidence levels and source descriptions retain mixed clinical and preclinical conditions. No automated source-paper entailment or patient-specific treatment recommendation is performed.",
                "Flagged, deprecated/retracted, pending-revision, unsupported and unmapped items are excluded with reasons in civic_report.json.",
                "Coverage describes the exact gene-name search, DOID, source status and ingredient therapy IDs. Other diseases, named regimen entities and submitted items were not searched.",
                "No matching Pharos reference does not prove new or independent evidence. Shared PMID references are reported without counting them as independent experiments.",
                "Ordering is by profile/therapy name and direction/significance; it is not a clinical or confidence ranking. Display caps do not change source totals.",
                "The live API supplies no release identifier here. Snapshot/response hashes and retrieval times pin this pull; genomic allele normalization is not implemented."],
            "interpretation":"Cited source annotations for research inspection; local acceptance is not clinical truth or an experimental label.",
            "engine":"deterministic_graph_query","llm_used":False}
    if graph["data_kind"] == "synthetic_demo":
        answer["limitations"].insert(0,"SYNTHETIC SOFTWARE DEMONSTRATION — not biomedical evidence.")
    answer["answer_sha256"]=digest(answer)
    return answer
