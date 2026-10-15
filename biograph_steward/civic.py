"""Bounded read-only CIViC retrieval and source-qualified response annotations.

This first adapter has one declared scope. A molecular profile and a therapy
set remain whole; they are never expanded into single-variant/drug claims.
"""
from collections import Counter
from copy import deepcopy
import json
import os
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .client import canonical, digest, utcnow

ENDPOINT = "https://civicdb.org/api/graphql"
FORMAT = "biograph-steward.civic.v1"
POLICY = "civic-kras-crc-predictive.v1"
THERAPIES = {"cetuximab": "C1723", "panitumumab": "C1857"}
LICENSE = {"dataSource": "CIViC", "license": "CC0-1.0",
           "licenseURL": "https://creativecommons.org/publicdomain/zero/1.0/",
           "source": "https://docs.civicdb.org/en/latest/about/faq.html"}
RESOLVE = """query StewardCivicScope {
  genes(entrezIds:[3845],first:2) { nodes {id name entrezId deprecated myGeneInfoDetails} }
  diseases(doid:"9256",first:10) { nodes {id name doid deprecated link} pageInfo {hasNextPage} }
  cetuximab:therapies(ncitId:"C1723",first:10) {nodes{id name ncitId deprecated link} pageInfo{hasNextPage}}
  panitumumab:therapies(ncitId:"C1857",first:10) {nodes{id name ncitId deprecated link} pageInfo{hasNextPage}}
}"""
EVIDENCE = """query StewardCivicEvidence($disease:Int!,$therapy:Int!,$first:Int!,$after:String) {
  evidenceItems(diseaseId:$disease,therapyId:$therapy,molecularProfileName:"KRAS",
    evidenceType:PREDICTIVE,status:ACCEPTED,first:$first,after:$after,sortBy:{column:ID,direction:ASC}) {
    totalCount pageInfo {hasNextPage endCursor}
    nodes {id description evidenceType evidenceDirection significance evidenceLevel evidenceRating
      status flagged openRevisionCount variantOrigin therapyInteractionType link
      molecularProfile {id name rawName isComplex isMultiVariant deprecated flagged link
        variants {id name deprecated flagged link feature {id name deprecated
          featureInstance {__typename ... on Gene {entrezId}}}}}
      disease {id name doid deprecated link}
      therapies {id name ncitId deprecated link}
      source {id sourceType citationId citation title publicationYear sourceUrl link deprecated retracted}
    }
  }
}"""


class CivicError(ValueError):
    pass


class CivicClient:
    def __init__(self, *, timeout=30, transport=None):
        self.timeout, self.transport = timeout, transport
        self.records, self.last_request = [], 0

    def execute(self, query, variables=None):
        payload = {"query": query, "variables": variables or {}}
        if self.transport:
            response = self.transport(payload)
        else:
            # Stay below the documented anonymous 3 requests/second limit.
            delay = .4 - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
            req = Request(ENDPOINT, data=canonical(payload).encode(), method="POST",
                          headers={"Content-Type": "application/json", "Accept": "application/json",
                                   "User-Agent": "BioGraphSteward/0.5 read-only evidence retrieval"})
            context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
            self.last_request = time.monotonic()
            try:
                with urlopen(req, timeout=self.timeout, context=context) as r:
                    raw = r.read(10_000_001)
                if len(raw) > 10_000_000:
                    raise CivicError("CIViC response exceeds 10 MB; reduce the retrieval scope.")
                response = json.loads(raw)
            except (HTTPError, URLError, OSError, ValueError) as exc:
                raise CivicError(f"CIViC retrieval failed: {exc}. No demonstration fallback was used.") from exc
        if not isinstance(response, dict) or response.get("errors") or not isinstance(response.get("data"), dict):
            messages = "; ".join(str(e.get("message", "GraphQL error")) for e in response.get("errors", []) if isinstance(e,dict)) if isinstance(response,dict) else ""
            raise CivicError("CIViC GraphQL error or unexpected response; partial data was rejected. " + messages[:500])
        self.records.append({"endpoint": ENDPOINT, "request": payload, "retrieved_at": utcnow(),
                             "response": deepcopy(response), "response_sha256": digest(response)})
        return response["data"]

    def retrieve(self, max_items=100):
        if type(max_items) is not int or not 1 <= max_items <= 200:
            raise ValueError("Use 1–200 evidence items per therapy.")
        try:
            return self._retrieve(max_items)
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            raise CivicError("CIViC response schema changed; no partial run was published.") from exc

    def _retrieve(self, max_items):
        self.records = []
        resolved = self.execute(RESOLVE)
        genes = resolved["genes"]["nodes"]
        if len(genes) != 1 or genes[0].get("entrezId") != 3845 or genes[0].get("deprecated") is not False:
            raise CivicError("CIViC KRAS gene resolution is missing or ambiguous.")
        gene = genes[0]
        disease = resolve_exact(resolved["diseases"], "doid", "9256")
        therapies = [resolve_exact(resolved[name], "ncitId", ncit) for name, ncit in THERAPIES.items()]
        items, coverage = {}, []
        for therapy in therapies:
            cursor, seen_cursors, seen_ids, total, issues = None, set(), set(), None, []
            has_next = True
            while len(seen_ids) < max_items and has_next:
                page_size = min(50, max_items - len(seen_ids))
                variables = {"disease": disease["id"], "therapy": therapy["id"], "first": page_size, "after": cursor}
                page = self.execute(EVIDENCE, variables)["evidenceItems"]
                rows, info, reported = page.get("nodes"), page.get("pageInfo"), page.get("totalCount")
                if (not isinstance(rows, list) or len(rows) > page_size or not isinstance(info, dict)
                        or type(info.get("hasNextPage")) is not bool or type(reported) is not int or reported < 0):
                    raise CivicError("CIViC pagination schema changed; no partial run was published.")
                if total is None:
                    total = reported
                elif total != reported:
                    issues.append("reported_count_changed_during_retrieval")
                new_ids = 0
                for i, row in enumerate(rows):
                    if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0:
                        raise CivicError("CIViC evidence item lacks a stable integer identifier.")
                    eid = row["id"]
                    locator = {"request_index": len(self.records)-1, "response_pointer": f"/data/evidenceItems/nodes/{i}"}
                    if eid in seen_ids:
                        issues.append("repeated_evidence_id")
                    else:
                        new_ids += 1
                    seen_ids.add(eid)
                    if eid in items and items[eid]["record"] != row:
                        raise CivicError("CIViC returned different versions of one evidence item during this pull; retry.")
                    items.setdefault(eid, {"record": deepcopy(row), "provenance": []})["provenance"].append(locator)
                has_next, cursor = info["hasNextPage"], info.get("endCursor")
                if has_next and (not rows or not new_ids or not cursor or cursor in seen_cursors):
                    raise CivicError("CIViC pagination did not advance; no partial run was published.")
                seen_cursors.add(cursor)
            if not has_next and len(seen_ids) != total:
                issues.append("retrieved_count_differs_from_reported")
            coverage.append({"therapy": deepcopy(therapy), "reported": total, "retrieved": len(seen_ids),
                             "limit": max_items, "has_next_page": has_next,
                             "status": "inconsistent" if issues else "capped" if has_next else "complete",
                             "issues": sorted(set(issues))})
        snapshot = {"snapshot_format": FORMAT, "data_kind": "live_civic", "created_at": utcnow(),
                    "endpoint": ENDPOINT, "policy": POLICY, "source_version": None,
                    "version_note": "Live API has no release identifier in this adapter; response and snapshot hashes pin the retrieved content.",
                    "scope": {"gene": gene, "disease": disease, "therapies": therapies,
                              "evidence_type": "PREDICTIVE", "source_status": "ACCEPTED", "max_items_per_therapy": max_items,
                              "profile_search": "KRAS", "disease_policy": "Exact DOID:9256; no parent/child disease equivalence.",
                              "therapy_policy": "Exact ingredient therapy IDs. Multi-therapy records are retained as complete sets; named regimen entities not containing those IDs are outside scope."},
                    "items": [items[k] for k in sorted(items)], "coverage": coverage,
                    "requests": deepcopy(self.records), "source_license": LICENSE}
        snapshot["content_sha256"] = digest(snapshot)
        return snapshot


def resolve_exact(connection, key, value):
    if connection.get("pageInfo", {}).get("hasNextPage") is not False:
        raise CivicError("CIViC identifier resolution was truncated.")
    matches = [r for r in connection["nodes"] if str(r.get(key)) == value and r.get("deprecated") is False]
    if len(matches) != 1:
        raise CivicError("CIViC identifier resolution is missing or ambiguous: " + key + "=" + value)
    return matches[0]


def verify_civic(snapshot):
    try:
        _verify_civic(snapshot)
    except (KeyError,TypeError,IndexError,AttributeError) as exc:
        raise ValueError("CIViC snapshot structure is invalid.") from exc


def _verify_civic(snapshot):
    if snapshot.get("snapshot_format") != FORMAT or snapshot.get("policy") != POLICY:
        raise ValueError("Unsupported CIViC snapshot format or policy.")
    if snapshot.get("data_kind") not in {"live_civic", "synthetic_demo"}:
        raise ValueError("CIViC snapshot must declare its data kind.")
    if snapshot.get("content_sha256") != digest({k:v for k,v in snapshot.items() if k != "content_sha256"}):
        raise ValueError("CIViC snapshot integrity check failed.")
    scope=snapshot["scope"]
    if (scope["gene"].get("entrezId") != 3845 or str(scope["disease"].get("doid")) != "9256"
            or {t.get("ncitId") for t in scope["therapies"]} != set(THERAPIES.values())
            or len(scope["therapies"]) != 2 or len({t["id"] for t in scope["therapies"]}) != 2
            or scope.get("evidence_type") != "PREDICTIVE" or scope.get("source_status") != "ACCEPTED"
            or scope.get("profile_search") != "KRAS" or type(scope.get("max_items_per_therapy")) is not int
            or not 1 <= scope["max_items_per_therapy"] <= 200):
        raise ValueError("CIViC snapshot is outside the supported fixed retrieval scope.")
    requests = snapshot["requests"]
    for request in requests:
        if request.get("response_sha256") != digest(request.get("response")) or request.get("response", {}).get("errors"):
            raise ValueError("CIViC source response integrity check failed.")
    ids = set()
    for item in snapshot["items"]:
        record = item["record"]
        if record["id"] in ids or not item["provenance"]:
            raise ValueError("CIViC snapshot contains duplicate or untraceable evidence items.")
        ids.add(record["id"])
        for location in item["provenance"]:
            index=location["request_index"]
            if (type(index) is not int or not 0 <= index < len(requests)
                    or not isinstance(location["response_pointer"],str)
                    or not re.fullmatch(r"/data/evidenceItems/nodes/[0-9]+",location["response_pointer"])):
                raise ValueError("CIViC response locator is invalid.")
            try:
                value = requests[index]["response"]
                for part in location["response_pointer"].strip("/").split("/"):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                if value != record:
                    raise ValueError("CIViC evidence differs from its raw response.")
            except (IndexError, KeyError, TypeError) as exc:
                raise ValueError("CIViC response locator is invalid.") from exc


def mapped_proteins(civic, nodes):
    """Use source-provided, human Swiss-Prot mappings; never join on symbols."""
    gene = civic["scope"]["gene"]
    details = gene.get("myGeneInfoDetails")
    try:
        details = json.loads(details) if isinstance(details, str) else details
        if (gene.get("entrezId") != 3845 or str(details.get("entrezgene", details.get("_id"))) != "3845"
                or details.get("taxid") not in {None, 9606}):
            return []
        refs = details.get("uniprot", {}).get("Swiss-Prot", [])
        refs = [refs] if isinstance(refs, str) else refs
        return sorted({"UniProtKB:"+r for r in refs if isinstance(r,str) and "UniProtKB:"+r in nodes
                       and nodes["UniProtKB:"+r].get("identifier_mapped")})
    except (ValueError, TypeError, AttributeError):
        return []


def normalize_civic(civic, snapshot, nodes, edges, quarantine, add_edge):
    verify_civic(civic)
    if (civic["data_kind"] == "synthetic_demo") != (snapshot["data_kind"] == "synthetic_demo"):
        raise ValueError("Do not mix synthetic and live source snapshots.")
    baseline_edges = deepcopy(list(edges.values()))
    proteins = mapped_proteins(civic, nodes)
    selected = civic["scope"]
    if selected["gene"].get("entrezId") != 3845 or str(selected["disease"].get("doid")) != "9256":
        raise ValueError("CIViC snapshot is outside the supported KRAS/DOID:9256 scope.")
    selected_therapies = {t["id"] for t in selected["therapies"]}
    entities = {}
    for item in civic["items"]:
        r = item["record"]
        mp = r.get("molecularProfile") or {}
        records = [("profile",mp),("disease",r.get("disease") or {}),("source",r.get("source") or {})]
        records += [("therapy",t) for t in r.get("therapies") or []]
        records += [("variant",v) for v in mp.get("variants") or []]
        for family, record in records:
            if record.get("id") is None:
                continue
            key=(family,record["id"])
            if key in entities and entities[key] != record:
                raise ValueError("Inconsistent CIViC "+family+" records within one snapshot; retrieve a new consistent source.")
            entities[key]=record
    normalized, excluded = [], []
    for i, item in enumerate(civic["items"]):
        r = item["record"]
        mp, disease, therapies, source = r.get("molecularProfile") or {}, r.get("disease") or {}, r.get("therapies") or [], r.get("source") or {}
        variants = mp.get("variants") or []
        locus = f"civic_snapshot.json#/items/{i}/record"
        reasons = []
        if r.get("evidenceType") != "PREDICTIVE" or r.get("status") != "ACCEPTED":
            reasons.append("outside_predictive_accepted_source_scope")
        if disease.get("id") != selected["disease"]["id"] or str(disease.get("doid")) != "9256":
            reasons.append("outside_exact_civic_disease_scope")
        if not selected_therapies.intersection(t.get("id") for t in therapies):
            reasons.append("outside_selected_therapy_scope")
        if not any(v.get("feature", {}).get("featureInstance", {}).get("entrezId") == 3845 for v in variants):
            reasons.append("profile_without_verified_kras_gene")
        if not proteins:
            reasons.append("unresolved_gene_to_cohort_protein_mapping")
        required = [mp, disease, source, *therapies, *variants]
        if not variants or not therapies or any(type(x.get("id")) is not int or not x.get("name", x.get("title")) for x in required):
            reasons.append("missing_source_identifier_or_label")
        if any(x.get("deprecated") is not False for x in required) or source.get("retracted") is not False:
            reasons.append("deprecated_or_retracted_or_unknown_source_state")
        if (r.get("flagged") is not False or mp.get("flagged") is not False
                or any(v.get("flagged") is not False or v.get("feature", {}).get("deprecated") is not False for v in variants)):
            reasons.append("flagged_or_unknown_source_state")
        if r.get("openRevisionCount") != 0:
            reasons.append("pending_or_unknown_source_revisions")
        if r.get("evidenceDirection") not in {"SUPPORTS", "DOES_NOT_SUPPORT"} or r.get("significance") not in {"RESISTANCE", "SENSITIVITYRESPONSE", "REDUCED_SENSITIVITY", "ADVERSE_RESPONSE"}:
            reasons.append("unsupported_or_missing_response_semantics")
        if not r.get("description") or not r.get("evidenceLevel") or not r.get("variantOrigin"):
            reasons.append("missing_evidence_conditions")
        if len(therapies) > 1 and r.get("therapyInteractionType") not in {"COMBINATION", "SEQUENTIAL", "SUBSTITUTES"}:
            reasons.append("unresolved_multi_therapy_interaction")
        if reasons:
            entry = {"reason": ";".join(sorted(set(reasons))), "locator": locus, "record": deepcopy(r)}
            excluded.append({"evidence_id": r["id"], **entry})
            quarantine.append(entry)
            continue
        mid, did = "CIViC.molecularprofile:"+str(mp["id"]), "DOID:"+str(disease["doid"])
        therapy_ids = sorted("CIViC.therapy:"+str(t["id"]) for t in therapies)
        tid = "biograph:therapyset:"+digest({"members":therapy_ids,"interaction":r.get("therapyInteractionType")})[:20]
        interaction=r.get("therapyInteractionType")
        separator=" or " if interaction == "SUBSTITUTES" else " / " if interaction == "SEQUENTIAL" else " + "
        therapy_label=separator.join(t["name"] for t in sorted(therapies,key=lambda t:t["id"]))
        if interaction == "SEQUENTIAL":
            therapy_label += " (sequential; order not specified)"
        for uid, name, category, raw in [(mid, mp["name"], "biograph:MolecularProfile", mp),
                                          (did, disease["name"], "biolink:Disease", disease),
                                          (tid, therapy_label, "biograph:TherapySet", {})]:
            nodes.setdefault(uid,{"id":uid,"name":name,"sym":None,"tdl":None,"category":category,
                                  "identifier_mapped":True,"data_kind":civic["data_kind"],
                                  "url":"https://civicdb.org"+raw["link"] if raw.get("link","").startswith("/") else None})
        nodes[mid].update({"variants":deepcopy(variants),"profile_expression":mp.get("rawName"),"protein_ids":proteins})
        nodes[tid].update({"members":deepcopy(therapies),"interaction_type":r.get("therapyInteractionType")})
        pmids = ["PMID:"+str(source["citationId"])] if source.get("sourceType") == "PUBMED" and str(source.get("citationId","")).isdigit() else []
        qualifiers = {"disease":did,"variant":mid,"therapy":tid,"response":r["significance"],
                      "evidence_direction":r["evidenceDirection"],"variant_origin":r["variantOrigin"],
                      "therapy_interaction":r.get("therapyInteractionType"),"evidence_type":r["evidenceType"]}
        edge_id = add_edge(mid,"biograph:has_reported_therapy_response",tid,deepcopy(r),locus,[],"variant_therapy_response","CIViC",
                           reference="; ".join(pmids) or source.get("sourceUrl"), qualifiers=qualifiers,
                           aggregator="CIViC",publications=pmids,evidence_raw=r["description"],
                           snapshot_sha256=civic["content_sha256"],source_record_count=1,
                           retrieval_provenance=[{**p,"endpoint":civic["endpoint"],"retrieved_at":civic["requests"][p["request_index"]]["retrieved_at"],
                                                  "response_sha256":civic["requests"][p["request_index"]]["response_sha256"]} for p in item["provenance"]],
                           normalization_notes=["Complete CIViC molecular profile and therapy set retained; no single-variant or single-drug extrapolation.",
                                                "CIViC ACCEPTED is a source editorial status; local human review begins as candidate.",
                                                "DOID:9256 is kept separate from the selected Pharos disease; no equivalence has been inferred."],
                           source_context={"evidence_level":r["evidenceLevel"],"evidence_rating":r.get("evidenceRating"),
                                           "source_status":r["status"],"protein_ids":proteins,"civic_evidence_id":r["id"],
                                           "source_url":"https://civicdb.org/evidence/"+str(r["id"])})
        normalized.append(edge_id)
    overlap = overlap_report([edges[eid] for eid in normalized],baseline_edges,snapshot)
    return {"policy":POLICY,"source_snapshot_sha256":civic["content_sha256"],"created_at":civic["created_at"],
            "source_version":civic.get("source_version"),"scope":deepcopy(selected),"coverage":deepcopy(civic["coverage"]),
            "mapping":{"source":"CIViC NCBIGene:3845 → myGeneInfoDetails Swiss-Prot → exact cohort identifier", "protein_ids":proteins,
                       "taxon_policy":"The supported gene NCBIGene:3845 is human KRAS. Missing taxid in the cached cross-reference is not experimental species information.",
                       "status":"mapped" if proteins else "unresolved", "mapping_locator":"civic_snapshot.json#/scope/gene/myGeneInfoDetails"},
            "retrieved_items":len(civic["items"]),"normalized_items":len(normalized),"excluded_items":excluded,
            "overlap":overlap,"source_license":deepcopy(civic["source_license"])}


def overlap_report(civic_edges, baseline_edges, snapshot):
    from .assertions import assertion_identity
    def identity(edge):
        return assertion_identity(edge['subject'],edge['predicate'],edge['object'],edge['record_kind'],edge.get('qualifiers',{}))
    supporting = {p for e in baseline_edges for p in e.get("publications",[])}
    discovery = set()
    for t in snapshot["targets"]:
        if not isinstance(t,dict):
            continue
        collection=t.get("pharos_context",{}).get("publications",[])
        for r in collection if isinstance(collection,list) else []:
            if str(r.get("pmid","")).isdigit():discovery.add("PMID:"+str(r["pmid"]))
    rows=[]
    for e in civic_edges:
        same = [b for b in baseline_edges if b["record_kind"] == e["record_kind"] and identity(b) == identity(e)]
        pmids=set(e["publications"])
        rows.append({"evidence_id":e["evidence_record"]["id"],"edge_id":e["id"],
                     "representation":"duplicate_qualified_assertion" if same else "additional_qualified_detail",
                     "matching_baseline_edge_ids":[b["id"] for b in same],
                     "shared_supporting_publications":sorted(pmids & supporting),
                     "shared_discovery_publications":sorted(pmids & discovery),
                     "publication_overlap":"shared_supporting_publication" if pmids & supporting else "shared_discovery_publication" if pmids & discovery else "no_matching_explicit_reference" if pmids else "unresolved_reference",
                     "independence":"unresolved"})
    return {"policy":"qualified-identity-and-explicit-pmid.v1","rows":rows,
            "representation_counts":dict(Counter(r["representation"] for r in rows)),
            "publication_counts":dict(Counter(r["publication_overlap"] for r in rows)),
            "verified_independent_evidence":0,
            "limitations":["Comparison covers only the retrieved Pharos baseline, not all upstream database content.",
                           "A shared PMID does not establish an identical claim; a different PMID does not establish an independent experiment.",
                           "Missing Pharos citations and capped publication discovery leave underlying-study overlap unresolved."]}
