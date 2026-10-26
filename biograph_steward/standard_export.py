"""Auditable KGX projection from an immutable source packet.

This is a bounded exchange profile, not a replacement for the workbench graph.
Unsupported annotations and every original qualification remain in the packet.
Official validator results do not establish biological truth or full conformance.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import re
import shutil
import tempfile

from .client import digest, utcnow, write_json
from .file_utils import sha
from .gold_packet import load_packet, _decode, _read, _jsonl
from .standards_validation import verify_resources

PROFILE = "biograph-steward.kgx-reactome-pathways.v1"
FORMAT = "biograph-steward.standard-projection.v1"
RECEIPT = "projection_manifest.json"


def project_graph(graph):
    """Project only supported exact source meanings, with a complete ledger."""
    if (any(key in graph for key in ('assay_evidence', 'assay_observations',
                                    'assay_publication_sha256', 'assay_attachment_sha256'))
            or any(edge.get('record_kind') == 'assay_observation' for edge in graph['edges'])):
        raise ValueError('Qualified assay observations are outside this KGX profile. '
                         'Use the complete source-preserving gold packet; a qualified standard mapping is not implemented.')
    nodes = {n["id"]: n for n in graph["nodes"]}
    assertions = {a["id"]: a for a in graph["assertions"]}
    edges, ledger, included_nodes = [], [], set()
    for edge in graph["edges"]:
        assertion = assertions[edge["assertion_id"]]
        subject, obj = nodes[edge["subject"]], nodes[edge["object"]]
        kind = edge.get("record_kind")
        reasons = []
        if kind != "pathway_membership":
            reasons.append({
                "go_annotation": "go_relation_polarity_and_extensions_unavailable",
                "drug_listing": "listing_does_not_assert_a_standard_drug_target_relation",
                "protein_interaction": "annotation_bundle_not_mapped_to_a_concrete_standard_interaction_predicate",
                "expression_observation": "qualified_expression_observation_outside_this_profile",
            }.get(kind, "relation_outside_reactome_pathway_profile"))
        if kind == "pathway_membership":
            if edge.get("predicate") != "biolink:participates_in":
                reasons.append("unexpected_source_predicate")
            if (subject.get("category") != "biolink:Protein" or subject.get("identifier_mapped") is not True
                    or not re.fullmatch(r"UniProtKB:[A-Z0-9]+(?:-[1-9][0-9]*)?", subject["id"])):
                reasons.append("subject_identity_outside_profile")
            if (obj.get("category") != "biolink:Pathway" or obj.get("identifier_mapped") is not True
                    or not re.fullmatch(r"REACT:R-[A-Z]{3}-[0-9]+(?:\.[0-9]+)?", obj["id"])
                    or edge.get("primary_source_raw") != "Reactome"):
                reasons.append("pathway_requires_exact_mapped_reactome_identity_and_source")
            if any(value is not None for record in (edge, assertion)
                   for value in record.get("qualifiers", {}).values()):
                reasons.append("nonempty_qualification_requires_a_separate_mapping_contract")
            if (assertion.get("kind") != kind or assertion.get("subject") != edge["subject"]
                    or assertion.get("object") != edge["object"]
                    or assertion.get("predicate") != edge["predicate"]
                    or edge["id"] not in assertion["evidence_edge_ids"]):
                raise ValueError("Source assertion and evidence identity disagree.")
            if assertion.get("lifecycle_state") not in {"candidate", "provisional", "accepted"}:
                reasons.append("local_review_state_excluded_from_inspectable_projection")
        status = "excluded" if reasons else "represented"
        ledger.append({"source_edge_id": edge["id"], "source_assertion_id": assertion["id"],
                       "source_kind": kind, "status": status, "reasons": reasons,
                       "projection_edge_id": None if reasons else edge["id"],
                       "source_edge_sha256": digest(edge), "source_assertion_sha256": digest(assertion)})
        if reasons:
            continue
        included_nodes.update((edge["subject"], edge["object"]))
        edges.append({"id": edge["id"], "subject": edge["subject"], "predicate": edge["predicate"],
                      "object": edge["object"], "knowledge_level": "not_provided", "agent_type": "not_provided",
                      "primary_knowledge_source": "infores:reactome",
                      "aggregator_knowledge_source": ["infores:pharos"],
                      "publications": deepcopy(edge.get("publications", []))})
    projected_nodes = [{"id": uid, "category": [nodes[uid]["category"]], "name": nodes[uid]["name"]}
                       for uid in sorted(included_nodes)]
    node_ledger = [{"source_node_id": n["id"], "source_node_sha256": digest(n),
                    "status": "represented" if n["id"] in included_nodes else "preserved_in_source_packet",
                    "reason": None if n["id"] in included_nodes else "not_an_endpoint_of_a_supported_projected_edge"}
                   for n in graph["nodes"]]
    groups = {}
    for assertion in graph["assertions"]:
        rows = [r for r in ledger if r["source_assertion_id"] == assertion["id"]]
        represented = sum(r["status"] == "represented" for r in rows)
        groups[assertion["id"]] = {"source_assertion_id": assertion["id"],
            "source_assertion_sha256": digest(assertion),
            "status": "represented" if rows and represented == len(rows) else
                      "partially_represented" if represented else "preserved_in_source_packet",
            "represented_edges": represented, "source_edges": len(rows)}
    return {"profile": PROFILE, "nodes": projected_nodes, "edges": edges,
            "edge_mapping": ledger, "node_mapping": node_ledger,
            "assertion_mapping": list(groups.values()),
            "counts": {"source_nodes": len(nodes), "source_edges": len(graph["edges"]),
                       "source_assertions": len(assertions), "projected_nodes": len(projected_nodes),
                       "projected_edges": len(edges), "excluded_edges": len(ledger) - len(edges),
                       "exclusions_by_reason": dict(sorted(Counter(reason for row in ledger for reason in row["reasons"]).items()))}}


def _files(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and p != folder / RECEIPT}


def export_standard(packet, output, resources_dir):
    """Preserve the source and official standards, then run the actual validators."""
    if Path(packet).is_symlink() or Path(resources_dir).is_symlink():
        raise ValueError("Use ordinary source packet and standards directories, not symlinks.")
    packet, output, resources_dir = Path(packet).resolve(), Path(output).absolute(), Path(resources_dir).resolve()
    if output.exists() or output.is_symlink() or packet in output.resolve().parents or resources_dir in output.resolve().parents:
        raise ValueError("Choose a new output outside the source packet and standards resources.")
    manifest, graph = load_packet(packet)
    projection = project_graph(graph)
    from .standards_validation import validate_projection
    # Verify optional dependencies and resources before making an output.
    validation = validate_projection(projection["nodes"], projection["edges"], resources_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".standard-projection-", dir=output.parent))
    try:
        shutil.copytree(packet, stage / "source_packet")
        copied_manifest, copied_graph = load_packet(stage / "source_packet")
        if copied_manifest != manifest or copied_graph != graph or load_packet(packet)[0] != manifest:
            raise ValueError("Source packet changed during export.")
        if any(p.is_symlink() for p in resources_dir.rglob("*")):
            raise ValueError("Standards resource bundle may not contain symlinks.")
        shutil.copytree(resources_dir, stage / "standards")
        if verify_resources(stage / "standards") != validation["resources"]:
            raise ValueError("Standards resources changed during export.")
        _jsonl(stage / "projection_nodes.jsonl", projection["nodes"])
        _jsonl(stage / "projection_edges.jsonl", projection["edges"])
        for name in ("edge_mapping", "node_mapping", "assertion_mapping"):
            _jsonl(stage / (name + ".jsonl"), projection[name])
        write_json(stage / "validation.json", validation)
        report = {"profile": PROFILE, "source_packet_id": manifest["packet_id"],
                  "source_graph_sha256": manifest["graph_sha256"], "data_kind": graph["data_kind"],
                  "counts": projection["counts"], "validation": validation,
                  "full_standard_conformance_claimed": False, "biological_validation_performed": False,
                  "scope_note": "Only mapped, unqualified Reactome pathway-membership records are projected. All other records, review states and qualifications remain in the complete source packet. Passing an algorithm's checks is not full standard conformance or biological truth."}
        write_json(stage / "report.json", report)
        (stage / "README.txt").write_text(
            "Bounded KGX projection — inspect report.json and validation.json before use.\n"
            "The full source graph is preserved in source_packet/. Excluded records are not pruned or declared false.\n"
            "Stable IDs and mapping ledgers link the plain KGX rows to full original evidence and assertions in source_packet/.\n"
            "No full standard-conformance or scientific-accuracy claim is made.\n", encoding="utf-8")
        receipt = {"format": FORMAT, "profile": PROFILE, "created_at": utcnow(),
                   "source_packet_id": manifest["packet_id"], "source_graph_sha256": manifest["graph_sha256"],
                   "projection_sha256": digest(projection), "validation_sha256": digest(validation),
                   "implementation_sha256": {"export": sha(__file__),
                       "validation": sha(Path(__file__).with_name("standards_validation.py"))},
                   "files": _files(stage), "full_standard_conformance_claimed": False,
                   "biological_validation_performed": False}
        receipt["content_sha256"] = digest(receipt)
        write_json(stage / RECEIPT, receipt)
        verify_standard(stage)
        if output.exists():
            raise ValueError("Output appeared during export; choose a new directory.")
        stage.rename(output)
        return report
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def verify_standard(folder):
    """Verify preserved output and deterministic projection, without network or KGX."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir() or any(p.is_symlink() for p in folder.rglob("*")):
        raise ValueError("Projection must contain regular files without symlinks.")
    try:
        receipt = _read(folder / RECEIPT)
        if (receipt.get("format") != FORMAT or receipt.get("profile") != PROFILE
                or receipt.get("content_sha256") != digest({k: v for k, v in receipt.items() if k != "content_sha256"})
                or receipt.get("files") != _files(folder)
                or receipt.get("full_standard_conformance_claimed") is not False
                or receipt.get("biological_validation_performed") is not False):
            raise ValueError("Standard projection receipt or files changed.")
        manifest, graph = load_packet(folder / "source_packet")
        projection = project_graph(graph)
        if (manifest["packet_id"] != receipt["source_packet_id"]
                or manifest["graph_sha256"] != receipt["source_graph_sha256"]
                or digest(projection) != receipt["projection_sha256"]):
            raise ValueError("Projection no longer matches its preserved source.")
        for name, key in (("projection_nodes", "nodes"), ("projection_edges", "edges"),
                          ("edge_mapping", "edge_mapping"), ("node_mapping", "node_mapping"),
                          ("assertion_mapping", "assertion_mapping")):
            rows = [_decode(line) for line in (folder / (name + ".jsonl")).read_bytes().splitlines()]
            if rows != projection[key]:
                raise ValueError("Projection rows do not reproduce from their source: " + name)
        validation, report = _read(folder / "validation.json"), _read(folder / "report.json")
        resources = verify_resources(folder / "standards")
        if (digest(validation) != receipt["validation_sha256"] or report.get("validation") != validation
                or validation.get("resources") != resources
                or validation.get("counts") != {"nodes": len(projection["nodes"]), "edges": len(projection["edges"])}
                or validation.get("input_sha256") != digest({"nodes": projection["nodes"], "edges": projection["edges"]})
                or validation.get("content_sha256") != digest({k: v for k, v in validation.items() if k != "content_sha256"})
                or validation.get("full_conformance") is not False
                or validation.get("biological_validation_performed") is not False
                or report.get("source_packet_id") != manifest["packet_id"]
                or report.get("source_graph_sha256") != manifest["graph_sha256"]
                or report.get("data_kind") != graph["data_kind"]
                or report.get("profile") != PROFILE
                or report.get("counts") != projection["counts"]
                or report.get("full_standard_conformance_claimed") is not False
                or report.get("biological_validation_performed") is not False):
            raise ValueError("Projection report does not match its validated material.")
        return report
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError("Invalid or incomplete standard projection: " + str(exc)) from exc
