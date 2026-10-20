"""Bounded Pharos context retrieval; raw source annotations are not new claims.

Offset pagination is checked against counts when available. A complete result
means observed API coverage for the requested family and cohort, not biological
completeness or a transactionally consistent upstream database snapshot.
"""
from collections import Counter
import re
from .client import PharosError, digest

DEFAULT_LIMITS = {"pathways": 2000, "go": 500, "ppis": 2000,
                  "drugs": 100, "expressions": 2000, "publications": 25}
MAX_LIMITS = {"pathways": 5000, "go": 2000, "ppis": 5000,
              "drugs": 500, "expressions": 5000, "publications": 200}
ROW_BUDGET = 200_000
BATCH_SIZE = 5
CONTEXT_PAGE_SIZE = 500
# PPI order is score-based without a unique tie-breaker. Fetch the whole bounded
# neighbor list in one call to avoid unstable offsets within score ties.
PPI_PAGE_SIZE = 5000
RECORD_IDS = {"pathways": "pwid", "ppis": "nid", "drugs": "ligid", "expressions": "expid", "publications": "pmid"}
FIELDS = {
    "pathways": "pwid name type sourceID url",
    "go": "goid type term evidence goeco assigned_by",
    "ppis": "nid type props { name value } target { uniprot sym name }",
    "drugs": "ligid name isdrug",
    "expressions": "expid type tissue value qual evidence conf zscore btoid uberon { uid name } pub { pmid } url",
    "publications": "pmid title date journal",
}
COUNTS = {"pathways": "pathwayCounts { name value }", "go": "goCounts { name value }",
          "ppis": "ppiCounts(filter: {ppiConfidence: 400}) { name value }",
          "drugs": "ligandCounts { name value }", "expressions": "expressionCounts { name value }",
          "publications": "publicationCount"}
METADATA_FIELDS = """uniprot dataSources affiliate_links { sourceName description url }
pathwayCounts { name value } goCounts { name value }
ppiCounts(filter: {ppiConfidence: 400}) { name value }
ligandCounts { name value } expressionCounts { name value } publicationCount"""
NOT_REQUESTED = {
    "non_drug_ligands": "Drug-listed ligands only; the full bioactivity collection is outside this profile.",
    "ligand_activities": "Drug listing does not establish binding, mechanism, indication or resistance.",
    "gtex": "Separate GTEx measurements are not included in the expressions endpoint.",
    "gwas": "No phenotype scope has been selected.",
    "lincs": "No perturbation or cell-line scope has been selected.",
    "generifs_and_full_text": "Publication discovery uses metadata only; no claim-level text retrieval.",
    "community_api_data": "Affiliate links are pointers, not retrieved external datasets.",
}


def settings(limits=None, tissue_term=""):
    result = dict(DEFAULT_LIMITS)
    if limits is not None:
        if not isinstance(limits, dict) or set(limits) - set(result):
            raise ValueError("Unknown context family in retrieval limits.")
        result.update(limits)
    for key, value in result.items():
        if type(value) is not int or not 0 <= value <= MAX_LIMITS[key]:
            raise ValueError(f"{key} limit must be 0-{MAX_LIMITS[key]}.")
    if not isinstance(tissue_term, str) or len(tissue_term) > 100:
        raise ValueError("Tissue search must be at most 100 characters.")
    # Match whole tissue words locally; the deployed full-text API is broken.
    if tissue_term and (not tissue_term.strip() or any(not (c.isalnum() or c.isspace()) for c in tissue_term)):
        raise ValueError("Use plain tissue search words, separated by spaces.")
    return result, " ".join(tissue_term.split())


def reported_count(raw, family):
    if family == "publications":
        return raw if type(raw) is int and raw >= 0 else None
    if not isinstance(raw, list):
        return None
    if any(not isinstance(r, dict) or type(r.get("value")) is not int or r["value"] < 0 for r in raw):
        return None
    if family in {"ppis", "drugs"}:
        key = "Total" if family == "ppis" else "drug"
        return next((r["value"] for r in raw if r.get("name") == key), None)
    return sum(r["value"] for r in raw)


def metadata_query(ids):
    definitions = ", ".join(f"$id{i}: String!" for i in range(len(ids)))
    selections = "\n".join(f"t{i}: target(q: {{uniprot: $id{i}}}) {{ {METADATA_FIELDS} }}" for i in range(len(ids)))
    return f"query ScopedMetadata({definitions}) {{ {selections} }}", {f"id{i}": uid for i, uid in enumerate(ids)}


def page_query(family, tasks, tissue_term):
    definitions, selections, variables = [], [], {}
    for i, (uid, skip, top) in enumerate(tasks):
        definitions.extend([f"$id{i}: String!", f"$skip{i}: Int!", f"$top{i}: Int!"])
        variables.update({f"id{i}": uid, f"skip{i}": skip, f"top{i}": top})
        args = f"skip: $skip{i}, top: $top{i}"
        if family == "ppis":
            args += ", filter: {ppiConfidence: 400}"
        elif family == "drugs":
            args += ", isdrug: true"
        field = "ligands" if family == "drugs" else family
        selections.append(f"t{i}: target(q: {{uniprot: $id{i}}}) {{ uniprot reported: {COUNTS[family]} rows: {field}({args}) {{ {FIELDS[family]} }} }}")
    return f"query Scoped_{family}({', '.join(definitions)}) {{ {' '.join(selections)} }}", variables


def _target(data, alias, uid):
    row = data.get(alias)
    if not isinstance(row, dict) or row.get("uniprot") != uid:
        raise PharosError(f"Pharos did not return the requested target {uid}; partial context rejected.")
    return row


def retrieve_context(client, targets, limits, tissue_term="", progress=None, *, row_budget=ROW_BUDGET, batch_sizes=None):
    """Attach context to seed targets, retaining out-of-cohort PPIs only in raw responses."""
    limits, tissue_term = settings(limits, tissue_term)
    batch_sizes = batch_sizes or {}
    if (set(batch_sizes) - set(limits) or any(type(v) is not int or not 1 <= v <= BATCH_SIZE for v in batch_sizes.values())):
        raise ValueError("Family batch sizes must be between 1 and the normal request batch size.")
    ids = [t.get("uniprot") for t in targets]
    if any(not isinstance(uid, str) or not uid for uid in ids) or len(set(ids)) != len(ids):
        raise PharosError("Scoped retrieval requires distinct, nonempty seed UniProt identifiers.")
    cohort = set(ids)
    metadata = {}
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start:start + BATCH_SIZE]
        data = client.execute(*metadata_query(batch))
        for i, uid in enumerate(batch):
            metadata[uid] = _target(data, f"t{i}", uid)
        if progress:
            progress(f"Context inventory: {min(start + BATCH_SIZE, len(ids))}/{len(ids)} proteins")
    rows, used = [], 0
    for target in targets:
        target["pathways"] = []
        target["pharos_context"] = {"metadata": metadata[target["uniprot"]]}
    for family, limit in limits.items():
        states = []
        for target in targets:
            uid = target["uniprot"]
            count_key = COUNTS[family].split("(")[0].split()[0]
            total = reported_count(metadata[uid].get(count_key), family)
            expected = total
            state = {"uniprot": uid, "symbol": target.get("sym"), "family": family,
                     "available": expected, "available_before_scope": total,
                     "retrieved": 0, "retained": 0, "excluded_by_scope": 0,
                     "limit": limit, "status": "not_requested" if not limit else "pending",
                     "pages": [], "issues": [], "observed_counts": [total]}
            if family == "expressions" and not tissue_term:
                state["status"] = "not_requested"
                state["issues"].append("A tissue search is required; no disease-to-tissue mapping was inferred.")
            if state["status"] == "pending" and expected == 0:
                state["status"] = "complete"
            states.append({"coverage": state, "target": target, "page_hashes": set(), "record_ids": set()})
            if family != "pathways":
                target["pharos_context"][family] = []
        while pending := [s for s in states if s["coverage"]["status"] == "pending"]:
            batch, tasks = [], []
            remaining = row_budget - used
            if remaining <= 0:
                for s in pending:
                    s["coverage"]["status"] = "budget_limited"
                break
            for s in pending[:batch_sizes.get(family, BATCH_SIZE)]:
                if remaining <= 0:
                    break  # Reserved for this batch; short pages may release budget.
                c = s["coverage"]
                top = min(PPI_PAGE_SIZE if family == "ppis" else CONTEXT_PAGE_SIZE, limit - c["retrieved"], remaining)
                if c["available"] is not None:
                    top = min(top, max(1, c["available"] - c["retrieved"]))
                if top <= 0:
                    c["status"] = "capped"
                    continue
                remaining -= top
                batch.append(s)
                tasks.append((c["uniprot"], c["retrieved"], top))
            if not tasks:
                continue
            request_index = len(client.records)
            data = client.execute(*page_query(family, tasks, tissue_term))
            for i, (s, (uid, skip, top)) in enumerate(zip(batch, tasks)):
                c = s["coverage"]
                result = _target(data, f"t{i}", uid)
                page = result.get("rows")
                if not isinstance(page, list) or any(not isinstance(r, dict) for r in page) or len(page) > top:
                    raise PharosError(f"Malformed {family} page for {uid}; partial context rejected.")
                total = reported_count(result.get("reported"), family)
                if total not in c["observed_counts"]:
                    c["observed_counts"].append(total)
                    c["issues"].append("Reported count changed during retrieval.")
                fingerprint = digest(page)
                if page and fingerprint in s["page_hashes"]:
                    raise PharosError(f"Repeated {family} page for {uid}; pagination stopped.")
                s["page_hashes"].add(fingerprint)
                if family in RECORD_IDS:
                    identifiers = {str(r[RECORD_IDS[family]]) for r in page if r.get(RECORD_IDS[family]) is not None}
                    if identifiers & s["record_ids"]:
                        c["issues"].append("Record identifiers overlapped across pages; completeness is unverified.")
                    s["record_ids"].update(identifiers)
                c["pages"].append({"skip": skip, "requested": top, "returned": len(page),
                                   "request_index": request_index, "response_pointer": f"/data/t{i}/rows"})
                c["retrieved"] += len(page)
                used += len(page)
                retained = page
                if family == "ppis":
                    if any(not isinstance(r.get("target"), dict) or not r["target"].get("uniprot") for r in page):
                        raise PharosError(f"Missing interaction partner for {uid}.")
                    retained = [r for r in page if r["target"]["uniprot"] in cohort]
                if family == "expressions":
                    if any(not isinstance(r.get("tissue"), str) for r in page):
                        raise PharosError(f"Missing expression tissue for {uid}.")
                    retained = [r for r in page if any(re.search(r"\b" + re.escape(word) + r"\b", r["tissue"], re.I)
                                                     for word in tissue_term.split())]
                c["retained"] += len(retained)
                c["excluded_by_scope"] += len(page) - len(retained)
                destination = s["target"] if family == "pathways" else s["target"]["pharos_context"]
                destination.setdefault(family, []).extend(retained)
                expected = c["available"]
                if len(page) < top or (expected is not None and c["retrieved"] >= expected):
                    c["status"] = "complete" if expected is not None else "exhausted"
                    if expected is not None and c["retrieved"] != expected:
                        c["issues"].append("Retrieved row count does not match the inventory.")
                elif c["retrieved"] >= limit:
                    c["status"] = "capped"
                if c["issues"] and c["status"] != "pending":
                    c["status"] = "inconsistent"
            if progress:
                done = sum(s["coverage"]["status"] != "pending" for s in states)
                progress(f"{family}: {done}/{len(ids)} proteins; {used:,} context rows retrieved")
        rows.extend(s["coverage"] for s in states)
    # Make envelope indexes local to the eventual snapshot request list in client.py.
    summary = {}
    for family in limits:
        selected = [r for r in rows if r["family"] == family]
        summary[family] = {"retrieved": sum(r["retrieved"] for r in selected),
                           "retained": sum(r["retained"] for r in selected),
                           "excluded_by_scope": sum(r["excluded_by_scope"] for r in selected),
                           "available": sum(r["available"] for r in selected) if all(r["available"] is not None for r in selected) else None,
                           "target_statuses": dict(Counter(r["status"] for r in selected))}
    result = {"profile": "scoped.v1", "limits_per_target": limits, "row_budget": row_budget,
            "rows_retrieved": used, "scope": {"seed_uniprots": ids, "ppi_partners": "selected_cohort_only",
            "ppi_confidence": 400, "tissue_search": tissue_term or None,
            "expression_search_semantics": "Local case-insensitive whole-word OR matching of tissue labels after a bounded scan; not an ontology mapping. Pharos tissue full-text search failed in live validation (missing index).",
            "publications": "Target-linked discovery metadata in API order; not disease-specific supporting citations."},
            "not_requested": NOT_REQUESTED, "summary": summary, "targets": rows,
            "completeness_note": "Complete means fetched rows match reported counts for these seed targets and filters. Exhausted means a short page was observed without a matching count endpoint. Offset pagination is not an atomic upstream snapshot."}
    if batch_sizes: result['transport_batch_sizes'] = batch_sizes
    return result
