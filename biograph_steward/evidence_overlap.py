"""Read-only overlap of a saved Pharos workspace and qualified assay records.

Identifier correspondence, pair representation, curated records and experiments
are separate units. This audit never merges records or assigns independence.
PSI-MI identity qualifiers and the existing application source models supply the
semantics; no XML, identifier-history or biological inference engine is added.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from html import escape
import json
from pathlib import Path
import re

from .assertions import assertion_identity
from .client import digest, utcnow, write_json
from .file_utils import new_output, sha
from .graph import UNIPROT

FORMAT = "biograph-steward.evidence-overlap.v1"
POLICY = "exact-identifiers-and-source-qualified-evidence.v1"
LICENSE = "https://opensource.org/licenses/MIT"
LIMITATIONS = [
    "Same pair, claim, publication, curated record and experiment are different units; their flags are not additive.",
    "Pharos functional association is not an assay-specific physical interaction or a biological negative.",
    "A shared PMID can contain different experiments; distinct PMIDs, methods or accessions do not prove independence.",
    "IntAct/IMEx record identities and external structural identities are reported separately; shared structures do not prove shared experiments.",
    "Source context available in an added record is not proof of previously unknown biology or novel evidence.",
    "No pair match is scoped to the saved retrieval; incomplete coverage never establishes absence.",
    "SSSOM documents exact source-primary protein identifier correspondence, not gene/protein, sequence or construct equivalence.",
    "This report covers selected workspace assay observations, including excluded observations, not all records in their source publication or all Pharos.",
    "Independent study counts and scientific accuracy remain unverified. No record is accepted, merged or pruned automatically.",
]


def _pmids(values):
    return sorted({"PMID:" + m.group(1) for v in values if isinstance(v, str)
                   and (m := re.fullmatch(r"(?:pubmed|pmid):([1-9][0-9]*)", v, re.I))})


def _publications(values):
    result = set(_pmids(values))
    for value in values:
        if isinstance(value, str) and (match := re.fullmatch(r"(?:doi:|https://doi.org/)(10\.[0-9]{4,9}/\S+)", value, re.I)):
            result.add("doi:" + match.group(1).lower())
    return sorted(result)


def _identifier(ref):
    database = (ref.get("database") or {}).get("name", "").lower()
    accession = ref.get("id")
    return database + ":" + accession if database and isinstance(accession, str) and accession else None


def _qualified_identities(refs, *, record_only=False):
    result = set()
    for ref in refs:
        identifier = _identifier(ref)
        database = (ref.get("database") or {}).get("name", "").lower()
        qualifier = (ref.get("qualifier") or {}).get("mi_id")
        if identifier and (qualifier == "MI:0356" or database == "imex" and qualifier == "MI:0662"):
            if not record_only or database in {"intact", "imex"}:
                result.add(identifier)
    return sorted(result)


def _pair(products):
    if (not isinstance(products, list) or len(products) != 2
            or any(not isinstance(v, str) or not v.startswith("UniProtKB:")
                   or not UNIPROT.fullmatch(v[10:]) for v in products)):
        return None
    return tuple(sorted(products))


def _claim(edge):
    value = assertion_identity(edge["subject"], edge["predicate"], edge["object"],
                               edge["record_kind"], edge.get("qualifiers", {}))
    # Direction is not inferred from sorted endpoints or assay roles.
    return {**value, "symmetric": edge.get("symmetric", False)}


def _coverage(snapshot, pair):
    if pair is None:
        return {"complete": False, "reason": "unresolved_exact_primary_pair"}
    scope = snapshot.get("scope") or {}
    if scope.get("kind") != "protein_cohort":
        return {"complete": False, "reason": "not_an_explicit_exact_cohort"}
    resolutions = scope.get("resolutions", [])
    rows = (snapshot.get("retrieval", {}).get("context") or {}).get("targets", [])
    checks = []
    for protein in sorted(set(pair)):
        uid = protein[10:]
        resolved = [r for r in resolutions if r.get("requested_uniprot") == uid]
        evidence = [r for r in rows if r.get("uniprot") == uid and r.get("family") == "ppis"]
        complete = (len(resolved) == len(evidence) == 1
            and resolved[0].get("status") == "resolved" and resolved[0].get("returned_uniprot") == uid
            and evidence[0].get("status") == "complete" and not evidence[0].get("issues")
            and type(evidence[0].get("available")) is int
            and evidence[0].get("retrieved") == evidence[0]["available"]
            and evidence[0].get("retained", 0) + evidence[0].get("excluded_by_scope", 0) == evidence[0]["retrieved"])
        checks.append({"protein_id": protein, "complete": complete,
                       "resolution": deepcopy(resolved), "ppi_coverage": deepcopy(evidence)})
    return {"complete": all(r["complete"] for r in checks), "endpoints": checks,
            "scope": deepcopy((snapshot.get("retrieval", {}).get("context") or {}).get("scope")),
            "reason": "complete_bounded_ppi_retrieval" if all(r["complete"] for r in checks)
                      else "missing_or_incomplete_retrieval_or_identity"}


def _xml_companions(material):
    """Use captured official-reader JSON, never parse XML or infer experiments.

    Publication intake already verifies all preserved file hashes. Only the
    existing bridge's explicitly typed evidence objects are consumed here.
    """
    result = []
    for name, raw in sorted(material.items()):
        if not name.endswith(".jsonl"):
            continue
        for number, line in enumerate(raw.splitlines(), 1):
            row = json.loads(line)
            if row.get("format") != "biograph-steward.intact-xml-evidence.v1" or row.get("record_kind") != "evidence":
                continue
            evidence = row["evidence"]
            references = evidence.get("identifiers", []) + evidence.get("xrefs", [])
            result.append({"file": name, "file_sha256": hashlib.sha256(raw).hexdigest(),
                "line": number, "record": evidence,
                "record_ids": _qualified_identities(references, record_only=True),
                "qualified_aliases": _qualified_identities(references)})
    return result


def _source_facts(observation, companions):
    source_fields = observation.get("source_fields") or {}
    evidence_values = (source_fields.get("evidence_ids") or {}).get("values", [])
    # MITAB column 14 explicitly supplies interaction identifiers, not arbitrary xrefs.
    aliases = sorted({v for ref in evidence_values if (v := _identifier(ref))})
    narrow = [v for v in aliases if v.startswith(("intact:", "imex:"))]
    matches = [row for row in companions if set(row["record_ids"]) & set(narrow)]
    experiment_ids, local_experiments, experiment_rows = set(), set(), []
    if len(matches) == 1:
        xml = matches[0]
        aliases = sorted(set(aliases) | set(xml["qualified_aliases"]))
        for experiment in xml["record"].get("experiments", []):
            # IMEx-primary is a study registration, not an experiment identifier.
            global_ids = sorted({_identifier(ref) for ref in experiment.get("xrefs", [])
                if (ref.get("qualifier") or {}).get("mi_id") == "MI:0356"
                and (ref.get("database") or {}).get("name", "").lower() == "intact"
                and _identifier(ref)})
            local = {"reader_artifact_sha256": xml["file_sha256"], "xml_id": experiment.get("xml_id"),
                     "publication_id": observation.get("study"), "source_locator": deepcopy(experiment.get("source_locator"))}
            locator = local["source_locator"] or {}
            if (local["xml_id"] is not None and type(locator.get("line")) is int and locator["line"] > 0
                    and type(locator.get("column")) is int and locator["column"] > 0):
                local_experiments.add(digest(local))
            experiment_ids.update(global_ids)
            experiment_rows.append({"global_identity_qualified_ids": global_ids, "local_identity": local,
                "reader_locator": xml["file"] + "#line=" + str(xml["line"]),
                "source_locator": deepcopy(experiment.get("source_locator"))})
    narrow = [v for v in aliases if v.startswith(("intact:", "imex:"))]
    values = lambda key: (source_fields.get(key) or {}).get("values", [])
    raw = observation.get("raw_cells") or []
    context = {
        "publication": bool(_publications([observation.get("study", "")])),
        "curated_record_identity": bool(narrow),
        "assay_method": bool(values("detection_methods") or observation.get("assay")),
        "interaction_type": bool(values("interaction_types")),
        "experimental_host": bool(observation.get("assay_hosts")),
        "participant_roles": any(values(k) for k in ("biological_roles_a", "biological_roles_b", "experimental_roles_a", "experimental_roles_b"))
            or any((observation.get("constructs") or {}).get(k) for k in ("ad_experimental_role", "db_experimental_role")),
        "constructs_features_or_stoichiometry": bool(observation.get("constructs")) or any(v not in {"", "-"} for v in raw[36:40]),
        "source_outcome_or_negative_state": bool(observation.get("assay_status")),
        "scoped_experiment_identity": bool(experiment_rows),
    }
    return {"pmids": _pmids([observation.get("study", "")]),
        "publication_identifiers": _publications([observation.get("study", "")]), "record_identity_aliases": narrow,
        "external_identity_aliases": [v for v in aliases if v not in narrow],
        "experiment_ids": sorted(experiment_ids), "local_experiment_keys": sorted(local_experiments),
        "experiments": experiment_rows, "xml_join_status": "one_captured_evidence_record" if len(matches) == 1
        else "ambiguous_captured_record_join" if matches else "not_available",
        "context_availability": context}


def _baseline_facts(edge):
    # Do not scrape free-text props, provider names, target discovery citations,
    # or IMEx registrations into invented claim/experiment identifiers.
    pmids = _pmids(edge.get("publications", [])); publications = _publications(edge.get("publications", []))
    return {"edge_id": edge["id"], "record_kind": edge["record_kind"], "predicate": edge["predicate"],
        "pmids": pmids, "publication_identifiers": publications, "record_identity_aliases": [], "external_identity_aliases": [],
        "experiment_ids": [], "local_experiment_keys": [], "context_availability": {"publication": bool(publications)},
        "lineage_status": "claim_supporting_experiment_identifiers_not_exposed_by_current_baseline_projection",
        "source_bundle": deepcopy(edge.get("evidence_sources", [])),
        "source_record_count": edge.get("source_record_count"),
        "record_locators": deepcopy(edge.get("record_locators", [])),
        "source_response_provenance": deepcopy(edge.get("retrieval_provenance"))}


def analyze_overlap(snapshot, graph, attachment, material):
    """Analyze selected assay observations against the original Pharos edges."""
    observations = graph.get("assay_observations")
    if not isinstance(observations, list) or not isinstance(attachment, dict):
        raise ValueError("Choose a saved workspace with a qualified assay attachment.")
    if snapshot.get("content_sha256") != graph.get("snapshot_sha256"):
        raise ValueError("Overlap inputs must use the same saved Pharos snapshot.")
    baseline = [e for e in graph["edges"] if e["record_kind"] not in {"assay_observation", "variant_therapy_response"}]
    ppis = defaultdict(list)
    for edge in baseline:
        if edge["record_kind"] == "protein_interaction" and (pair := _pair([edge["subject"], edge["object"]])):
            ppis[pair].append(edge)
    edges = {e["id"]: e for e in graph["edges"]}
    companions = _xml_companions(material)
    records = []
    for observation in observations:
        pair = _pair(observation.get("products")); matches = ppis.get(pair, [])
        added = _source_facts(observation, companions)
        baselines = [_baseline_facts(e) for e in matches]
        edge = edges.get(observation.get("graph_edge_id")); coverage = _coverage(snapshot, pair)
        shared_pmids = sorted(set(added["pmids"]) & {p for e in baselines for p in e["pmids"]})
        available = {k for b in baselines for k, value in b["context_availability"].items() if value}
        additions = [k for k, value in added["context_availability"].items() if value and k not in available]
        record = {"observation_id": observation["id"], "source_kind": observation.get("source_kind", "lambourne_y2h"),
            "source": deepcopy(observation.get("source", {})), "study": observation.get("study"),
            "source_locators": deepcopy(observation.get("source_locators", [])),
            "products": deepcopy(observation.get("products")), "source_evaluable": observation.get("evaluable"),
            "source_assay_status": observation.get("assay_status"), "source_qualified_context": deepcopy(observation.get("qualified_fields", {})),
            "current_graph_edge_id": observation.get("graph_edge_id"), "baseline_matches": baselines,
            "pair_representation": "represented_in_bounded_baseline" if matches else
                "not_represented_in_complete_bounded_baseline" if coverage["complete"] else "unknown_incomplete_or_unresolved",
            "exact_pair_match": bool(matches), "coverage": coverage,
            "same_local_qualified_claim_edge_ids": [e["id"] for e in matches if edge and _claim(e) == _claim(edge)],
            "shared_supporting_pmids": shared_pmids,
            "shared_supporting_publication_identifiers": sorted(set(added["publication_identifiers"])
                & {p for b in baselines for p in b["publication_identifiers"]}),
            "baseline_record_identity_overlap": None, "baseline_experiment_identity_overlap": None,
            "baseline_identity_overlap_status": "unknown_baseline_identifiers_not_available",
            "added_source": added, "additional_context_fields_available": additions,
            "added_context_comparison": "matched_baseline_pair" if matches else "no_matching_baseline_record_to_compare",
            "experiment_lineage": "unresolved", "independent_evidence_count": None,
            "same_pair_added_records": [], "shared_added_record_identities": [], "shared_added_external_identities": [],
            "shared_added_experiments": [], "shared_added_publications": []}
        records.append(record)
    # Evidence repetition within the supplied publication is an independent
    # dimension from pair representation in Pharos.
    for row in records:
        for other in records:
            if row is other:
                continue
            same_pair = _pair(row["products"]) is not None and _pair(row["products"]) == _pair(other["products"])
            if same_pair:
                row["same_pair_added_records"].append(other["observation_id"])
            publications = sorted(set(row["added_source"]["publication_identifiers"])
                                  & set(other["added_source"]["publication_identifiers"]))
            if publications:
                row["shared_added_publications"].append({"other_observation_id": other["observation_id"],
                    "publication_identifiers": publications, "same_pair": same_pair, "same_experiment_established": False})
            for key, source in (("shared_added_record_identities", "record_identity_aliases"),
                                ("shared_added_external_identities", "external_identity_aliases")):
                shared = sorted(set(row["added_source"][source]) & set(other["added_source"][source]))
                if shared:
                    row[key].append({"other_observation_id": other["observation_id"], "identifiers": shared,
                                     "same_pair": same_pair, "merged": False})
            global_ids = sorted(set(row["added_source"]["experiment_ids"]) & set(other["added_source"]["experiment_ids"]))
            local = sorted(set(row["added_source"]["local_experiment_keys"]) & set(other["added_source"]["local_experiment_keys"]))
            if global_ids or local:
                row["shared_added_experiments"].append({"other_observation_id": other["observation_id"],
                    "global_identity_qualified_ids": global_ids, "same_artifact_scoped_experiment_keys": local,
                    "same_pair": same_pair, "independence_established": False})
    summary = {"workspace_observations": len(records), "source_evaluable_observations": sum(r["source_evaluable"] is True for r in records),
        "excluded_observations_retained": sum(r["source_evaluable"] is not True for r in records),
        "pair_representation_counts": dict(Counter(r["pair_representation"] for r in records)),
        "records_with_added_context": sum(bool(r["additional_context_fields_available"]) and r["exact_pair_match"] for r in records),
        "records_with_shared_supporting_pmid": sum(bool(r["shared_supporting_pmids"]) for r in records),
        "records_with_shared_added_record_identity": sum(bool(r["shared_added_record_identities"]) for r in records),
        "records_with_shared_added_experiment": sum(bool(r["shared_added_experiments"]) for r in records),
        "records_with_shared_added_publication": sum(bool(r["shared_added_publications"]) for r in records),
        "unresolved_experiment_lineage_records": len(records), "verified_independent_evidence": 0,
        "baseline_annotations": len(baseline), "baseline_ppi_annotations": sum(map(len, ppis.values())),
        "source_publication_accounting": {k: deepcopy(v) for k, v in attachment.get("summary", {}).items()
            if k in {"source_observations", "selected_observations", "eligible_observations", "excluded_observations",
                     "outside_cohort_observations", "assay_status_counts", "source_kind", "source_accounting"}},
        "automatic_merges": 0, "automatic_pruning": 0, "confidence_scores_combined": 0}
    return {"policy": POLICY, "summary": summary, "records": records, "limitations": list(LIMITATIONS)}


def _source_files(source):
    if any(p.is_symlink() for p in (source, *source.parents)) or not source.is_dir():
        raise ValueError("Use an ordinary saved workspace without symlink traversal.")
    files = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Source workspace contains a symlink.")
        if path.is_file():
            files[path.relative_to(source).as_posix()] = sha(path)
    return files


def _payload(source, mapping_date):
    from .assay_attachment import read_assay, source_material
    from .evidence_mapping import build_mapping_set
    from .reviews import read_run
    snapshot, _, graph = read_run(source)
    attachment = read_assay(source)
    if attachment is None:
        raise ValueError("Choose a saved workspace with a qualified assay attachment.")
    material = source_material(snapshot, attachment, source / "assay_source")
    value = analyze_overlap(snapshot, graph, attachment, material)
    snapshot_sha = sha(source / "snapshot.json")
    endpoints = [{"endpoint_id": "snapshot_target:" + str(i), "role": "baseline",
        "resource_id": snapshot["endpoint"], "resource_version": snapshot["db_version"],
        "record_locator": "urn:sha256:" + snapshot_sha + "#/targets/" + str(i),
        "entity_type": "protein", "identity_role": "source_primary", "primary_ids": ["UniProtKB:" + row["uniprot"]]}
        for i, row in enumerate(snapshot["targets"])]
    for i, row in enumerate(graph["assay_observations"]):
        resource = "https://www.ebi.ac.uk/intact" if row.get("source_kind") == "intact_mitab27" else "https://doi.org/10.1038/s41467-026-70942-x"
        version = (row.get("source") or {}).get("release") or "artifact-sha256:" + graph["assay_publication_sha256"]
        for side, product in enumerate(row.get("products") or []):
            endpoints.append({"endpoint_id": row["id"] + ":participant:" + str(side), "role": "added",
                "resource_id": resource, "resource_version": version,
                "record_locator": "urn:sha256:" + sha(source / "assay_observations.json") + "#/" + str(i) + "/products/" + str(side),
                "entity_type": "protein", "identity_role": "source_primary", "primary_ids": [product]})
    mappings = build_mapping_set(endpoints, mapping_set_id="urn:sha256:" + graph["assay_attachment_sha256"],
        mapping_set_version=POLICY, license_url=LICENSE, mapping_date=mapping_date)
    value.update(format=FORMAT, mapping_date=mapping_date, snapshot_sha256=snapshot["content_sha256"], data_kind=snapshot["data_kind"],
        pharos_endpoint=snapshot["endpoint"], pharos_database_version=snapshot["db_version"],
        assay_publication_sha256=graph["assay_publication_sha256"], assay_attachment_sha256=graph["assay_attachment_sha256"],
        mappings=mappings, scientific_accuracy_measured=False, model_calls=0, new_source_calls=0)
    return value


def _html(value):
    labels = {"publication": "Publication identifier", "curated_record_identity": "Curated record identifiers",
        "assay_method": "Detection method", "interaction_type": "Interaction type", "experimental_host": "Experimental host",
        "participant_roles": "Biological and assay roles", "constructs_features_or_stoichiometry": "Constructs, features or stoichiometry",
        "source_outcome_or_negative_state": "Source outcome or negative flag", "scoped_experiment_identity": "Experiment locator"}
    rows = []
    for row in value["records"]:
        details = escape(json.dumps(row, indent=2))
        rows.append("<tr><td>" + escape(row["observation_id"]) + "</td><td>" + escape(row["pair_representation"].replace("_", " "))
            + "</td><td>" + escape((", ".join(labels[k] for k in row["additional_context_fields_available"]) or "No added fields identified")
                                   if row["exact_pair_match"] else "No comparable baseline record")
            + "</td><td>Unresolved</td></tr><tr><td colspan='4'><details><summary>Source records and separate overlap flags</summary><pre>"
            + details + "</pre></details></td></tr>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Pharos evidence overlap</title>"
        "<style>body{font:16px system-ui;max-width:1200px;margin:36px auto;padding:0 20px;color:#17232c}"
        "table{border-collapse:collapse;width:100%}td,th{padding:12px;border:1px solid #c8d1d8;text-align:left;vertical-align:top;overflow-wrap:anywhere}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}li{margin:8px 0}</style>"
        "<h1>What the added assay records contribute</h1><p>Pharos release: <strong>" + escape(value["pharos_database_version"])
        + "</strong>. This is an audit of the selected saved workspace. It changes no graph records or review decisions.</p>"
        "<p><strong>Matching a protein pair does not identify its underlying experiment.</strong> Additional source context is distinguished from independent support.</p>"
        "<p><a href='report.json'>Report JSON</a> · <a href='records.jsonl'>Record ledger</a> · <a href='mappings.sssom.tsv'>SSSOM mappings</a> · "
        "<a href='mappings.json'>Mapping provenance and unresolved identifiers</a></p><h2>Selected source records</h2>"
        "<table><thead><tr><th>Observation</th><th>Pair in baseline</th><th>Source context available beyond baseline</th><th>Experiment lineage</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table><h2>Interpretation limits</h2><ul>" + "".join("<li>" + escape(s) + "</li>" for s in LIMITATIONS)
        + "</ul><p>SSSOM production targets the published 1.0 subset. Integrity verification is separate from an upstream validator run and scientific validation.</p></html>")


def _files(value):
    from .evidence_mapping import serialize_mapping_set
    encode = lambda obj: (json.dumps(obj, indent=2, ensure_ascii=True) + "\n").encode()
    return {"report.json": encode(value), "records.jsonl": b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in value["records"]),
        "mappings.json": encode(value["mappings"]), "mappings.sssom.tsv": serialize_mapping_set(value["mappings"]),
        "index.html": _html(value).encode()}


def _implementation():
    from . import evidence_mapping
    from . import assertions, assay_attachment, graph, intact_evidence, intact_final_publication
    from . import intact_publication, lambourne_evidence, normalization, reviews
    return {"evidence_overlap": sha(__file__), **{module.__name__: sha(module.__file__) for module in
        (evidence_mapping, assertions, assay_attachment, graph, intact_evidence, intact_final_publication,
         intact_publication, lambourne_evidence, normalization, reviews)}}


def publish_overlap(source, output):
    source = Path(source).absolute()
    before = _source_files(source)
    value = _payload(source, utcnow()[:10])
    value["source_workspace"] = str(source)
    value["source_files_sha256"] = before
    value["content_sha256"] = digest(value)
    if before != _source_files(source):
        raise ValueError("Source workspace changed during overlap analysis.")
    files = _files(value)
    folder = new_output(output, source)
    for name, raw in files.items():
        (folder / name).write_bytes(raw)
    manifest = {"format": FORMAT, "implementation_sha256": _implementation(),
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "manifest.json", manifest)
    verify_overlap(folder)
    return value


def verify_overlap(output):
    output = Path(output).absolute()
    inventory = _source_files(output)
    manifest = json.loads((output / "manifest.json").read_text())
    if (manifest.get("format") != FORMAT or manifest.get("content_sha256") != digest({k: v for k, v in manifest.items() if k != "content_sha256"})
            or manifest.get("implementation_sha256") != _implementation()
            or set(inventory) != set(manifest["files"]) | {"manifest.json"}
            or any(inventory[name] != pin for name, pin in manifest["files"].items())):
        raise ValueError("Overlap report inventory or implementation changed.")
    recorded = json.loads((output / "report.json").read_text())
    source = Path(recorded["source_workspace"])
    if recorded.get("source_files_sha256") != _source_files(source):
        raise ValueError("Overlap source workspace changed.")
    value = _payload(source, recorded["mapping_date"])
    value.update(source_workspace=str(source), source_files_sha256=recorded["source_files_sha256"])
    value["content_sha256"] = digest(value)
    if (value != recorded or any((output / name).read_bytes() != raw for name, raw in _files(value).items())
            or recorded["source_files_sha256"] != _source_files(source)):
        raise ValueError("Overlap classification or mappings do not reproduce from the recorded sources.")
    return recorded
