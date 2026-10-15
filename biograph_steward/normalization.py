"""Conservative Pharos annotation assertions with source-preserving normalization.

Local predicates describe the annotation actually returned. They do not infer
positive GO relations, physical binding, drug response, or positive expression.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import re
from urllib.parse import quote

from .client import canonical, digest

POLICY = "biograph-steward.context-normalization.v1"
PREDICATES = {
    "go_annotation": "biograph:has_go_annotation",
    "protein_interaction": "biograph:has_interaction_annotation",
    "drug_listing": "biograph:has_drug_listing",
    "expression_observation": "biograph:has_expression_observation",
}
GO_CATEGORIES = {"P": "biolink:BiologicalProcess", "F": "biolink:MolecularActivity",
                 "C": "biolink:CellularComponent"}


def value_text(value):
    return value.strip() if isinstance(value, str) else ""


def normalize_context(records, nodes, quarantine, emit, snapshot):
    """Normalize source context; emit evidence edges before assertion grouping.

    Only existing seed proteins may be endpoints. PPI endpoints are ordered for
    identity, with original directions and all scores retained as source views.
    """
    cohort = {uid for uid, n in nodes.items() if n["category"] == "biolink:Protein"}
    report = {"policy": POLICY, "families": {}, "predicates": PREDICATES,
              "limitations": ["GO relation, negation and extensions are not exposed by the retrieved fields.",
                              "Interaction annotations include functional associations; physical binding is not inferred.",
                              "Drug listings contain no activity, disease indication or response assertion.",
                              "Expression units are not supplied; source values and scales are not combined.",
                              "Publication discovery records are not claim-specific evidence."]}
    ppi_groups = defaultdict(list)
    # A GO identifier with conflicting aspects cannot safely receive a category.
    aspects = defaultdict(set)
    for entry in records:
        r = entry["record"]
        if entry["family"] == "go" and isinstance(r, dict):
            aspects[value_text(r.get("goid"))].add(value_text(r.get("type")))

    def node(uid, name, category, mapped=True, **extra):
        if uid not in nodes:
            nodes[uid] = {"id": uid, "name": name, "category": category, "identifier_mapped": mapped,
                          "sym": None, "tdl": None, "url": None, "data_kind": snapshot["data_kind"], **extra}
        elif nodes[uid]["name"] != name:
            nodes[uid]["aliases"] = sorted(set(nodes[uid].get("aliases", [])) | {name})

    def reject(entry, reason):
        entry["normalization_status"] = "quarantined_context"
        entry["normalization_issues"] = [reason]
        quarantine.append({"reason": reason, "locator": entry["record_locators"][0],
                           "record_locators": list(entry["record_locators"]),
                           "subject": entry["subject"], "record": deepcopy(entry["record"])})

    def publish(entries, subject, obj, kind, source, *, qualifiers=None, reasons=None,
                notes=None, record=None, reference=None, **extra):
        locators = sorted({p for e in entries for p in e["record_locators"]})
        source_rows = sum(len(e["record_locators"]) for e in entries)
        r = deepcopy(entries[0]["record"] if record is None else record)
        eid = emit(subject, PREDICATES[kind], obj, r, locators[0], reasons or [], kind, source, reference,
                   qualifiers=qualifiers or {}, record_locators=locators,
                   context_record_ids=sorted(e["id"] for e in entries),
                   source_record_count=source_rows, normalization_notes=notes or [],
                   normalization_policy=POLICY,
                   retrieval_provenance={"aggregator": "Pharos", "database_version": snapshot.get("db_version"),
                       "source_responses": sorted({canonical(p): p for e in entries for p in e.get("source_response_locators", [])}.values(), key=canonical)}, **extra)
        for entry in entries:
            entry["normalization_status"] = "normalized_candidate"
            entry["normalized_evidence_edge_ids"].append(eid)

    for entry in records:
        entry["normalized_evidence_edge_ids"] = []
        entry["assertion_ids"] = []
        family, subject, r = entry["family"], entry["subject"], entry["record"]
        if family == "publications":
            entry["normalization_status"] = "discovery_only"
            continue
        if subject not in cohort:
            reject(entry, "context_subject_not_a_valid_seed_protein")
            continue
        if not isinstance(r, dict):
            reject(entry, "malformed_context_record")
            continue
        if family == "go":
            uid, aspect, term = value_text(r.get("goid")), value_text(r.get("type")), value_text(r.get("term"))
            if not re.fullmatch(r"GO:[0-9]{7}", uid) or aspect not in GO_CATEGORIES or not term:
                reject(entry, "invalid_go_identifier_aspect_or_term")
                continue
            if len(aspects[uid]) != 1:
                reject(entry, "conflicting_go_aspects")
                continue
            node(uid, term, GO_CATEGORIES[aspect], source_identifier=uid, go_aspect=aspect)
            reasons = []
            if not value_text(r.get("assigned_by")):
                reasons.append("go_assigning_source_missing")
            if not value_text(r.get("evidence")):
                reasons.append("go_evidence_code_missing")
            publish([entry], subject, uid, "go_annotation", r.get("assigned_by"),
                    qualifiers={"go_aspect": aspect}, reasons=reasons,
                    annotation_context={"aspect": aspect, "relation": None, "negated": None, "extensions": None,
                                        "evidence_code": r.get("evidence"), "eco_code": r.get("goeco")},
                    notes=["Annotation existence only: GO relation, polarity and annotation extensions were not retrieved."])
        elif family == "ppis":
            partner = r.get("target")
            partner = "UniProtKB:" + value_text(partner.get("uniprot")) if isinstance(partner, dict) else None
            if partner not in cohort:
                reject(entry, "interaction_partner_outside_selected_cohort")
                continue
            sources = tuple(sorted({s.strip() for s in value_text(r.get("type")).split(",") if s.strip()}))
            pair = tuple(sorted((subject, partner)))
            ppi_groups[(pair, sources)].append(entry)
        elif family == "drugs":
            uid, name = value_text(r.get("ligid")), value_text(r.get("name"))
            if not uid or not name or r.get("isdrug") is not True:
                reject(entry, "invalid_or_unconfirmed_drug_listing")
                continue
            uid = "pharos.ligand:" + quote(uid, safe="")
            node(uid, name, "biolink:ChemicalEntity", mapped=False, source_identifier=r["ligid"], pharos_isdrug=True)
            publish([entry], subject, uid, "drug_listing", "Pharos",
                    reasons=["local_ligand_identifier_needs_mapping"],
                    notes=["Target-linked drug listing only; no activity, mechanism, indication or treatment response was retrieved."])
        elif family == "expressions":
            expid, tissue, assay = r.get("expid"), value_text(r.get("tissue")), value_text(r.get("type"))
            if (isinstance(expid, bool) or not re.fullmatch(r"[1-9][0-9]*", str(expid)) or not tissue or not assay):
                reject(entry, "expression_identifier_tissue_or_assay_missing")
                continue
            measurement, qualitative = r.get("value"), r.get("qual")
            if (measurement is None or isinstance(measurement, str) and not measurement.strip()) and not value_text(qualitative):
                reject(entry, "expression_measurement_missing")
                continue
            if isinstance(measurement, (dict, list, bool)) or isinstance(qualitative, (dict, list, bool)):
                reject(entry, "malformed_expression_measurement")
                continue
            uberon = r.get("uberon")
            uid = value_text(uberon.get("uid")) if isinstance(uberon, dict) else ""
            mapped = bool(re.fullmatch(r"UBERON:[0-9]{7}", uid))
            uid = uid if mapped else "biograph.tissue:" + digest(tissue)[:20]
            name = value_text(uberon.get("name")) if mapped else tissue
            node(uid, name or tissue, "biolink:AnatomicalEntity", mapped=mapped, source_identifier=uid if mapped else None)
            observation = {"id": "pharos.expression:" + str(expid), "assay": assay,
                           "tissue_id": uid, "tissue_label": tissue, "value_raw": measurement,
                           "qualitative_raw": qualitative, "unit": None,
                           "evidence_raw": r.get("evidence"), "conf_raw": r.get("conf"), "zscore_raw": r.get("zscore")}
            qualifiers = {"tissue": uid, "tissue_label": tissue, "assay": assay,
                          "observation_id": observation["id"],
                          "measurement_value": str(measurement) if measurement is not None else None,
                          "measurement_qualifier": value_text(qualitative) or None}
            pub = r.get("pub")
            pmid = pub.get("pmid") if isinstance(pub, dict) else None
            reference = "PMID:" + str(pmid) if re.fullmatch(r"[1-9][0-9]*", str(pmid)) else None
            publish([entry], subject, uid, "expression_observation", assay, qualifiers=qualifiers,
                    reasons=[] if mapped else ["unresolved_tissue_identifier"], observation=observation,
                    reference=reference, notes=["An observation is retained even when not detected; numeric values remain on their original source scale and units are unknown."])

    for (pair, sources), entries in sorted(ppi_groups.items()):
        # Incoming and outgoing views are views of one annotation, not two experiments.
        views = [{"reported_subject": e["subject"], "record": deepcopy(e["record"])} for e in entries]
        views.sort(key=canonical)
        props = [{"reported_subject": e["subject"], "properties": deepcopy(e["record"].get("props", []))}
                 for e in entries]
        props.sort(key=canonical)
        orientations = {e["subject"] for e in entries}
        publish(entries, pair[0], pair[1], "protein_interaction", ",".join(sources) or None,
                record={"source_bundle": list(sources), "source_views": views},
                reasons=[] if sources else ["interaction_source_missing"],
                evidence_sources=list(sources), symmetric=True,
                reciprocal_views_collapsed=max(0, len(orientations) - 1),
                source_scores_raw={"properties_by_view": props},
                notes=["Undirected database interaction annotation; endpoint order is canonical for identity. Source bundle and every original property are preserved without score combination or a physical-binding inference."])

    for family in sorted({r["family"] for r in records}):
        selected = [r for r in records if r["family"] == family]
        report["families"][family] = {
            "input_source_rows": sum(len(r["record_locators"]) for r in selected),
            "distinct_context_records": len(selected),
            "exact_duplicate_rows_grouped": sum(len(r["record_locators"]) - 1 for r in selected),
            "statuses": dict(sorted(Counter(r["normalization_status"] for r in selected).items())),
            "normalized_evidence_records": len({eid for r in selected for eid in r["normalized_evidence_edge_ids"]}),
        }
    report["reciprocal_views_collapsed"] = sum(max(0, len({r["subject"] for r in group}) - 1) for group in ppi_groups.values())
    return report
