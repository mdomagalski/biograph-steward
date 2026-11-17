"""A reversible current-GO-ID view, not a biological truth classifier.

Reuse GO's GORULE:0000020 lifecycle policy on the main annotation term only.
Obsolete identifiers are excluded from this derived view; explicit, unique,
active replacements are proposals rather than edits to historical records.
Missing relation, NOT and context fields are never supplied by this adapter.
"""
from collections import Counter
import gzip
import hashlib
from pathlib import Path
import re

from . import gold_packet
from .client import digest, utcnow, write_json
from .file_utils import new_output, sha


FORMAT = "biograph-steward.go-ontology-qualification.v1"
PROFILE = "current-go-primary-term-identifiers.v1"
ACTOR = "BioGraph Steward deterministic GO ontology qualification"
RULE_URL = "https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000020.md"
UPSTREAM_IMPLEMENTATION = "https://raw.githubusercontent.com/biolink/ontobio/master/ontobio/io/assocparser.py"
UPSTREAM_IMPLEMENTATION_SHA256 = "93bd7dbe964529992b04dc1320fbba0cf55005c0e8d7e18237c13ca8b1270242"
RULE_TEXT_SHA256 = "60dc5a4f175d26479b7a816634bff4839902cb3f003442fb13e93db8727c1a0a"
GO_IRI = "http://purl.obolibrary.org/obo/GO_"
REPLACED_BY = "http://purl.obolibrary.org/obo/IAO_0100001"
CONSIDER = "http://www.geneontology.org/formats/oboInOwl#consider"
LICENSE = "http://purl.org/dc/terms/license"
LIMITATIONS = [
    "Active identifier means ontology currency, not a correct gene-function claim or accepted review state.",
    "Obsolete identifiers are excluded only from a current-ontology view; historical annotation existence is not refuted.",
    "Replacement proposals are not applied; consider suggestions never become replacements.",
    "Unrecognized or absent term identifiers remain unknown and retained, not false.",
    "This is the primary-term lifecycle subset of GORULE:0000020, not full GO pipeline conformance.",
    "Relation, NOT polarity, annotation extensions, With/From, taxon and references are not reconstructed or validated.",
    "No ontology inference or taxon-constraint reasoning is performed; no annotation evidence code is ranked as biological quality.",
    "A checksum pins supplied bytes; it does not authenticate a publisher or prove experimental truth.",
    "A release comparison may expose update effects; the omitted Pharos GO vintage remains unknown.",
]


def _need(condition, message):
    if not condition:
        raise ValueError("GO ontology qualification: " + message)


def _go_id(value):
    if isinstance(value, str):
        if value.startswith(GO_IRI):
            value = "GO:" + value[len(GO_IRI):]
        if re.fullmatch(r"GO:[0-9]{7}", value):
            return value
    return None


def _properties(meta):
    values = meta.get("basicPropertyValues", [])
    _need(isinstance(values, list) and all(isinstance(x, dict)
          and isinstance(x.get("pred"), str) and isinstance(x.get("val"), str)
          for x in values), "invalid OBO Graphs basic property values.")
    return values


def load_ontology(path, expected_sha256):
    """Read native OBO Graphs JSON metadata without propagation or a reasoner.

    The existing research loader builds a NetworkX hierarchy for an INMC task;
    this core adapter needs only exact node metadata, so does not import that
    optional research runtime or duplicate its graph reasoning.
    """
    path = Path(path)
    _need(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
          "supply the reviewed ontology file SHA256.")
    _need(path.is_file() and not path.is_symlink(), "ontology must be an ordinary file.")
    raw = path.read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == expected_sha256,
          "ontology bytes differ from the supplied SHA256.")
    compressed = raw.startswith(b"\x1f\x8b")
    try:
        value = gold_packet._decode(gzip.decompress(raw) if compressed else raw)
    except (OSError, EOFError, ValueError) as exc:
        raise ValueError("GO ontology qualification: invalid OBO Graphs JSON.") from exc
    _need(isinstance(value, dict) and isinstance(value.get("graphs"), list)
          and len(value["graphs"]) == 1 and isinstance(value["graphs"][0], dict),
          "expected exactly one native OBO Graphs graph.")
    graph = value["graphs"][0]
    meta = graph.get("meta")
    _need(graph.get("id") == "http://purl.obolibrary.org/obo/go.owl"
          and isinstance(meta, dict) and isinstance(meta.get("version"), str)
          and re.fullmatch(r"http://purl.obolibrary.org/obo/go/releases/[0-9]{4}-[0-9]{2}-[0-9]{2}/go.owl", meta["version"]),
          "expected native GO ontology identity and dated version metadata.")
    properties = _properties(meta)
    _need(isinstance(graph.get("nodes"), list) and bool(graph["nodes"]),
          "native ontology nodes are missing.")
    nodes = {}
    for node in graph["nodes"]:
        _need(isinstance(node, dict), "invalid ontology node.")
        if node.get("type") == "PROPERTY":
            continue
        _need(node.get("type") in (None, "CLASS"), "unsupported OBO Graphs node type.")
        uid = _go_id(node.get("id"))
        _need(uid is not None and uid not in nodes, "GO class identifier is invalid or repeated.")
        node_meta = node.get("meta", {})
        _need(isinstance(node_meta, dict), "invalid ontology node metadata.")
        _need("deprecated" not in node_meta or isinstance(node_meta["deprecated"], bool),
              "deprecated state must be an explicit boolean when supplied.")
        _properties(node_meta)
        nodes[uid] = node
    _need({"GO:0003674", "GO:0005575", "GO:0008150"} <= nodes.keys(),
          "GO ontology root classes are missing.")
    binding = {"file_sha256": expected_sha256, "file_bytes": len(raw),
        "ontology_id": graph["id"], "ontology_version": meta["version"],
        "ontology_metadata_sha256": digest(meta), "go_class_nodes": len(nodes),
        "license_metadata": [p["val"] for p in properties if p["pred"] == LICENSE],
        "source_file": "ontology/source.json.gz" if compressed else "ontology/source.json",
        "publisher_authenticated": False, "full_standard_conformance_claimed": False}
    return nodes, binding, raw


def classify_term(term_id, nodes):
    """Classify the literal term's declared lifecycle; do not infer its biology."""
    uid = _go_id(term_id)
    node = nodes.get(uid) if uid else None
    if node is None:
        return {"decision": "abstain", "state": "not_found_or_unrecognized",
                "reason_code": "term_state_unknown", "replacement_proposal": None,
                "declared_replaced_by": [], "consider_only": [], "ontology_node_sha256": None}
    meta = node.get("meta", {})
    properties = _properties(meta)
    replacements = [p["val"] for p in properties if p["pred"] == REPLACED_BY]
    considers = [p["val"] for p in properties if p["pred"] == CONSIDER]
    if not meta.get("deprecated", False):
        return {"decision": "keep", "state": "active", "reason_code": "active_term_identifier_only",
                "replacement_proposal": None, "declared_replaced_by": replacements,
                "consider_only": considers, "ontology_node_sha256": digest(node)}
    proposal = None
    if len(replacements) == 1:
        replacement = _go_id(replacements[0])
        target = nodes.get(replacement) if replacement else None
        if target is not None and not target.get("meta", {}).get("deprecated", False):
            proposal = {"from_id": uid, "to_id": replacement,
                        "basis": "single explicit native replaced_by target, present and active",
                        "applied": False, "target_node_sha256": digest(target)}
    return {"decision": "prune", "state": "obsolete", "reason_code": "obsolete_term_in_current_ontology_view",
            "replacement_proposal": proposal, "declared_replaced_by": replacements,
            "consider_only": considers, "ontology_node_sha256": digest(node)}


def qualify_go_ontology(packet, ontology, output, *, ontology_sha256, actor=ACTOR):
    """Create a complete Gold ledger and separate ontology-compatible graph."""
    _need(isinstance(actor, str) and bool(actor.strip()) and actor.strip().casefold() != "unassigned",
          "an explicit software actor is required.")
    manifest, graph = gold_packet.load_packet(packet)
    nodes, binding, raw = load_ontology(ontology, ontology_sha256)
    decisions, traces, proposals = [], [], []
    family_counts = {}
    for edge in graph["edges"]:
        trace = None
        if edge.get("record_kind") == "go_annotation":
            _need(edge.get("predicate") == "biograph:has_go_annotation"
                  and isinstance(edge.get("evidence_record"), dict)
                  and edge["evidence_record"].get("goid") == edge.get("object"),
                  "GO annotation does not match its literal primary source term.")
            result = classify_term(edge["object"], nodes)
            trace = {"edge_id": edge["id"], "subject": edge["subject"],
                     "term_id": edge["object"], "source_record_sha256": digest(edge["evidence_record"]),
                     "source_locators": edge.get("record_locators", []), **result}
            traces.append(trace)
            if result["replacement_proposal"] is not None:
                proposals.append({"edge_id": edge["id"], **result["replacement_proposal"]})
        decision = trace["decision"] if trace else "abstain"
        reason = (PROFILE + "; " + trace["reason_code"] + "; identifier currency only, not biological truth"
                  if trace else "outside_go_primary_term_profile; not assessed by " + PROFILE)
        decisions.append({"edge_id": edge["id"], "decision": decision, "reason": reason, "confidence": None})
        family = family_counts.setdefault(edge["record_kind"],
                                           {"total": 0, "keep": 0, "prune": 0, "abstain": 0})
        family["total"] += 1
        family[decision] += 1
    counts = Counter(d["decision"] for d in decisions)
    source_counts = Counter(d["decision"] for d in traces)
    folder = new_output(output, packet, ontology)
    (folder / "ontology").mkdir()
    (folder / binding["source_file"]).write_bytes(raw)
    write_json(folder / "decisions.json", {"format": gold_packet.DECISION_FORMAT,
               "packet_id": manifest["packet_id"], "method": PROFILE, "actor": actor, "decisions": decisions})
    write_json(folder / "replacement_proposals.json", {"profile": PROFILE,
               "ontology_sha256": ontology_sha256, "applied": False, "proposals": proposals})
    retained = gold_packet.save_decisions(packet, folder / "decisions.json", folder / "retained")
    _need(all(retained["counts"][k] == counts[k] for k in ("keep", "prune", "abstain")),
          "retained graph decisions disagree.")
    report = {"format": FORMAT, "profile": PROFILE, "created_at": utcnow(), "actor": actor,
        "packet_id": manifest["packet_id"], "graph_sha256": manifest["graph_sha256"],
        "snapshot_sha256": manifest["snapshot_sha256"], "ontology": binding,
        "existing_method": {"rule": "GORULE:0000020", "rule_url": RULE_URL,
            "reviewed_implementation_url": UPSTREAM_IMPLEMENTATION,
            "reviewed_implementation_sha256": UPSTREAM_IMPLEMENTATION_SHA256,
            "rule_text_sha256": RULE_TEXT_SHA256,
            "reviewed_implementation_version": "Captured upstream master source; exact package release version not inferred.",
            "adapter_scope": "Primary-term obsolete filtering, analogous to repair_obsoletes=False; exact active replacements are proposals only.",
            "official_ontobio_executed": False, "full_GO_pipeline_executed": False},
        "counts": {"total_edges": len(decisions), **{k: counts[k] for k in ("keep", "prune", "abstain")},
            "go_profile_edges": len(traces), "go_profile": {k: source_counts[k] for k in ("keep", "prune", "abstain")},
            "outside_profile_abstain": len(decisions) - len(traces),
            "explicit_active_replacement_proposals": len(proposals),
            "obsolete_without_safe_active_replacement": source_counts["prune"] - len(proposals)},
        "edge_family_counts": family_counts, "source_decisions": traces,
        "source_graph_mutated": False, "source_review_states_mutated": False,
        "biological_truth_assessed": False, "independent_biological_accuracy": False,
        "functional_relations_or_polarities_recovered": False, "replacement_proposals_applied": False,
        "taxon_constraints_assessed": False, "model_calls": 0, "source_fetches": 0,
        "retained_package": "retained", "retained_report_sha256": retained["content_sha256"],
        "limitations": LIMITATIONS, "implementation_sha256": sha(Path(__file__)),
        "files": {p.relative_to(folder).as_posix(): sha(p) for p in
            (folder / "decisions.json", folder / "replacement_proposals.json",
             folder / binding["source_file"], folder / "retained/report.json")}}
    report["content_sha256"] = digest(report)
    write_json(folder / "go_ontology_qualification.json", report)
    return report
