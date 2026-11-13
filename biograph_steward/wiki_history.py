"""Literal historical GPML inspection, not biological pathway inference.

Legacy WikiPathways' official BatchDownloader names archive entries with the
pathway identifier and active MediaWiki revision. GPML2013a Pathway@Version is
optional GenMAPP export metadata, not that revision. These fields are separate.
The released author XSD can be executed by the optional lxml validator; no
alternate pathway, family, orthology or interaction parser is implemented.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET

from .file_utils import sha
from .human_gene_relation import gene_relationship

GPML = "http://pathvisio.org/GPML/2013a"
NS = {"gpml": GPML}
FULL_ID = re.compile(r"WP[1-9][0-9]*_r[1-9][0-9]*\Z")
MEMBER_ID = re.compile(r".*_(WP[1-9][0-9]*)_([1-9][0-9]*)\.gpml\Z")
SUPPORTED_NODE_TYPES = frozenset({"GeneProduct", "Protein"})
# These are literal BridgeDb names/codes, not guessed namespace aliases.
# Historical S=Uniprot-TrEMBL is documented by the official system-code page;
# the current official datasource table names S=UniProtKB.
DATASOURCE_CODES = {"Entrez Gene": "L", "Ensembl": "En", "HGNC": "H",
                    "HGNC Accession number": "Hac", "Uniprot-TrEMBL": "S", "UniProtKB": "S"}


def need(condition, message):
    if not condition:
        raise ValueError("Historical GPML: " + message)


def archive_member_id(name):
    """Recognize the verified publisher archive convention, without dates."""
    if not isinstance(name, str) or not name or "\\" in name or any(ord(c) < 32 for c in name):
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name or any(p in {".", ".."} for p in path.parts):
        return None
    match = MEMBER_ID.fullmatch(path.name)
    # Modern releases name files with YYYYMMDD last-edit dates. Those names
    # cannot establish a legacy MediaWiki revision, even if entirely numeric.
    if match and len(match.group(2)) == 8:
        try:
            datetime.strptime(match.group(2), "%Y%m%d")
        except ValueError:
            pass
        else:
            return None
    return match.group(1) + "_r" + match.group(2) if match else None


def inspect_fields(raw, *, validate=None, validation_receipt=None):
    """Preserve literal DataNodes, groups, states and linked pathway references.

    No label matching, group expansion, homology transfer, isoform collapse or
    causal/physical relation inference is performed. XML absence is never a
    biological negative. The complete raw GPML remains the authoritative copy.
    """
    need(isinstance(raw, bytes) and 0 < len(raw) <= 20_000_000, "invalid or over-budget model.")
    need(not (validate and validation_receipt), "use a validator or an attached producer receipt, not both.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("Historical GPML: malformed native XML.") from exc
    need(root.tag == "{" + GPML + "}Pathway", "only the reviewed native GPML2013a namespace is supported.")
    raw_pin = hashlib.sha256(raw).hexdigest()
    if validation_receipt is not None:
        need(isinstance(validation_receipt, dict) and validation_receipt.get("gpml_sha256") == raw_pin,
             "producer schema receipt does not bind these native bytes.")
        need(validation_receipt.get("executed") is True and isinstance(validation_receipt.get("passed"), bool),
             "attached receipt does not describe an executed producer check.")
        schema_result = {"executed": False, "reexecuted": False,
            "mode": "attached_byte_bound_producer_receipt", "passed": validation_receipt["passed"],
            "producer_receipt": deepcopy(validation_receipt)}
    else:
        schema_result = validate(raw) if validate else {"executed": False, "passed": None}
    groups = [{"attributes": dict(n.attrib), "xpath": "/gpml:Pathway/gpml:Group[%d]" % (i + 1)}
              for i, n in enumerate(root.findall("gpml:Group", NS))]
    states = [{"attributes": dict(n.attrib), "xpath": "/gpml:Pathway/gpml:State[%d]" % (i + 1),
               "xrefs": [dict(x.attrib) for x in n.findall("gpml:Xref", NS)]}
              for i, n in enumerate(root.findall("gpml:State", NS))]
    nodes = []
    for i, node in enumerate(root.findall("gpml:DataNode", NS), 1):
        xrefs = [dict(x.attrib) for x in node.findall("gpml:Xref", NS)]
        graph_id, group_ref = node.attrib.get("GraphId"), node.attrib.get("GroupRef")
        nodes.append({"xpath": "/gpml:Pathway/gpml:DataNode[%d]" % i,
            "attributes": dict(node.attrib), "xrefs": xrefs,
            "referenced_group_records": [g for g in groups if group_ref and g["attributes"].get("GroupId") == group_ref],
            "attached_state_records": [s for s in states if graph_id and s["attributes"].get("GraphRef") == graph_id],
            "comments": [{"attributes": dict(c.attrib), "text": c.text or ""}
                         for c in node.findall("gpml:Comment", NS)],
            "publication_xrefs": [dict(x.attrib) for x in node.findall("gpml:PublicationXref", NS)],
            "biopax_reference_ids": [n.text for n in node.findall("gpml:BiopaxRef", NS)],
            "parsed_node_serialization_sha256": hashlib.sha256(ET.tostring(node)).hexdigest()})
    # GPML's CommentGroup permits direct PublicationXref/BiopaxRef children on
    # several element types; their owner is preserved rather than assigning all
    # pathway citations to every member. BioPAX payloads stay literal XML.
    rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    biopax = "http://www.biopax.org/release/biopax-level3.owl#"
    publications, references, literal_biopax = [], [], []
    owners = [(root, "/gpml:Pathway")]
    for tag in ("DataNode", "Interaction", "GraphicalLine", "Group", "State", "Label", "Shape"):
        owners.extend((element, "/gpml:Pathway/gpml:%s[%d]" % (tag, i))
                      for i, element in enumerate(root.findall("gpml:" + tag, NS), 1))
    for owner, owner_xpath in owners:
        for i, ref in enumerate(owner.findall("gpml:PublicationXref", NS), 1):
            publications.append({"kind": "direct_gpml_PublicationXref", "owner_xpath": owner_xpath,
                "owner_attributes": dict(owner.attrib), "attributes": dict(ref.attrib),
                "xpath": owner_xpath + "/gpml:PublicationXref[%d]" % i,
                "scope": "whole_model" if owner is root else "native_element_attached",
                "supports_all_members_asserted": False})
        for i, ref in enumerate(owner.findall("gpml:BiopaxRef", NS), 1):
            references.append({"owner_xpath": owner_xpath, "owner_attributes": dict(owner.attrib),
                "literal_reference": ref.text or "", "attributes": dict(ref.attrib),
                "xpath": owner_xpath + "/gpml:BiopaxRef[%d]" % i,
                "scope": "whole_model" if owner is root else "native_element_attached"})
        if owner.attrib.get("BiopaxRef"):
            references.append({"owner_xpath": owner_xpath, "owner_attributes": dict(owner.attrib),
                "literal_reference": owner.attrib["BiopaxRef"], "attributes": {},
                "xpath": owner_xpath + "/@BiopaxRef",
                "scope": "whole_model" if owner is root else "native_element_attached"})
    for block_index, block in enumerate(root.findall("gpml:Biopax", NS), 1):
        literal_biopax.append({"xpath": "/gpml:Pathway/gpml:Biopax[%d]" % block_index,
                              "parsed_xml": ET.tostring(block, encoding="unicode")})
        for i, ref in enumerate(block.findall("{" + biopax + "}PublicationXref"), 1):
            ids = {ref.attrib[k] for k in ("{" + rdf + "}id", "{" + rdf + "}ID", "{" + rdf + "}about") if k in ref.attrib}
            linked = [deepcopy(x) for x in references if x["literal_reference"] in ids]
            publications.append({"kind": "native_BioPAX_PublicationXref", "attributes": dict(ref.attrib),
                "xpath": "/gpml:Pathway/gpml:Biopax[%d]/bp:PublicationXref[%d]" % (block_index, i),
                "literal_fields": [{"tag": x.tag, "attributes": dict(x.attrib), "text": x.text or ""} for x in ref],
                "native_exact_reference_links": linked, "parsed_xml": ET.tostring(ref, encoding="unicode"),
                "scope": "native_reference_record", "supports_all_members_asserted": False})
    return {"xml_author_version": root.attrib.get("Version"),
        "xml_version_is_wiki_revision_asserted": False,
        "native_namespace": GPML, "native_root_attributes": dict(root.attrib),
        "native_organism": root.attrib.get("Organism"), "native_license_literal": root.attrib.get("License"),
        "gpml_sha256": hashlib.sha256(raw).hexdigest(), "gpml_bytes": len(raw),
        "author_schema_validation": schema_result, "data_nodes": nodes, "groups": groups, "states": states,
        "native_datasource_counts": dict(Counter(x.get("Database", "") for n in nodes for x in n["xrefs"])),
        "native_node_type_counts": dict(Counter(n["attributes"].get("Type", "Unknown") for n in nodes)),
        "raw_model_required_for_complete_semantics": True, "group_or_pathway_expansion_performed": False,
        "publication_records": publications, "native_biopax_references": references,
        "literal_biopax_blocks": literal_biopax,
        "publication_support_for_membership_inferred": False,
        "biological_truth_assessed": False}


def inspect_model(raw, *, full_source_id, archive_member, validate=None, validation_receipt=None):
    """Add exact *legacy publisher filename* binding to literal field inspection.

    Current dated filenames cannot establish a legacy revision. For current
    native context use inspect_fields and pin the release archive separately.
    An attached producer receipt is reported as attached, never reexecuted.
    """
    need(isinstance(full_source_id, str) and FULL_ID.fullmatch(full_source_id), "invalid requested full version.")
    member_id = archive_member_id(archive_member)
    need(member_id == full_source_id, "archive member is not the exact requested publisher revision.")
    model = inspect_fields(raw, validate=validate, validation_receipt=validation_receipt)
    return {**model, "full_source_id": full_source_id, "archive_member": archive_member,
        "publisher_member_full_source_id": member_id,
        "exact_publisher_revision_binding": True,
        "revision_binding_method": "official_BatchDownloader_archive_member_WPID_activeRevision",
        "xml_author_version_equals_full_source_id": model["xml_author_version"] == full_source_id}


def bridge_for_subject(subject, registry):
    """Reuse the existing exact human UniProt/HGNC/Entrez agreement rule."""
    relation = gene_relationship(subject, registry)
    if not relation["qualified"]:
        return relation
    gene = registry.genes[relation["hgnc_id"]]
    return {**relation, "approved_symbol": gene["symbol"],
            "ensembl_gene_id": gene["ensembl_gene_id"], "historical_registry_identity_established": False}


def assess_subject(subject, model, registry):
    """Return literal protein encoding, qualified gene compatibility or UNKNOWN.

    A gene compatibility link never establishes protein/isoform identity. A
    missing match cannot refute family/group/linked-pathway context, an obsolete
    identifier or underlying biology, so every nonmatch remains unresolved.
    """
    bridge = bridge_for_subject(subject, registry)
    accession = subject[len("UniProtKB:"):] if isinstance(subject, str) and subject.startswith("UniProtKB:") else None
    exact, compatible, diagnostics = [], [], []
    for node in model["data_nodes"]:
        for xref in node["xrefs"]:
            database, identifier = xref.get("Database"), xref.get("ID")
            code = DATASOURCE_CODES.get(database)
            if not code or not isinstance(identifier, str) or not identifier:
                continue
            basis = None
            if code == "S" and identifier == accession:
                basis = "literal_exact_UniProt_accession"
            elif bridge["qualified"]:
                if code == "L" and identifier == bridge["ncbi_gene_id"]:
                    basis = "explicit_UniProt_HGNC_NCBI_Gene_agreement"
                elif code == "En" and identifier == bridge["ensembl_gene_id"]:
                    basis = "explicit_approved_HGNC_Ensembl_gene_cross_reference"
                elif code == "H" and identifier == bridge["approved_symbol"]:
                    basis = "source_declared_HGNC_symbol_namespace_exact_approved_primary_symbol"
                elif code == "Hac" and identifier in (bridge["hgnc_id"], bridge["hgnc_id"].removeprefix("HGNC:")):
                    basis = "source_declared_HGNC_accession_namespace_exact_identifier"
            if basis:
                record = {"node_xpath": node["xpath"], "native_node": deepcopy(node),
                          "datasource_system_code": code, "basis": basis,
                          "protein_form_or_construct_equivalence_established": False}
                if node["attributes"].get("Type") not in SUPPORTED_NODE_TYPES:
                    diagnostics.append({**record, "reason": "matching_reference_on_nonprotein_or_untyped_node"})
                elif code == "S":
                    exact.append(record)
                else:
                    compatible.append(record)
    human = model["native_organism"] == "Homo sapiens"
    schema_ok = model["author_schema_validation"].get("passed") is True
    status = ("unresolved" if not human or not schema_ok else
              "explicitly_encoded_protein_xref" if exact else
              "compatible_gene_level_xref" if compatible else "unresolved")
    barriers = []
    if not human:
        barriers.append("native_organism_not_explicitly_Homo_sapiens")
    if not schema_ok:
        barriers.append("official_native_schema_not_executed_or_not_passed")
    if not exact and not compatible:
        barriers.append("no_exact_protein_or_qualified_gene_xref_on_supported_entity_type_observed")
    if model["groups"]:
        barriers.append("groups_preserved_without_complex_or_family_expansion")
    if any(n["attributes"].get("Type") in {"Complex", "Pathway"} or
           any(x.get("Database") in {"WikiPathways", "Reactome", "KEGG Pathway", "InterPro", "Pfam", "Enzyme Nomenclature"}
               for x in n["xrefs"]) for n in model["data_nodes"]):
        barriers.append("family_complex_or_linked_pathway_references_preserved_without_expansion")
    if any(n["attributes"].get("Type") in SUPPORTED_NODE_TYPES and
           any(not x.get("ID") or x.get("Database") not in DATASOURCE_CODES for x in n["xrefs"])
           for n in model["data_nodes"]):
        barriers.append("unsupported_or_missing_identifier_namespaces_remain_unresolved")
    if diagnostics:
        barriers.append("matching_identifier_on_nonprotein_entity_does_not_establish_protein_membership")
    return {"subject": subject, "status": status, "gene_bridge": bridge,
        "exact_protein_matches": exact, "compatible_gene_matches": compatible,
        "other_entity_diagnostics": diagnostics, "unresolved_context": barriers,
        "no_qualified_xref_match_observed": not exact and not compatible,
        "absence_is_biological_negative": False, "historical_annotation_identity_established": False,
        "direct_binding_or_causal_relation_inferred": False,
        "independent_scientific_correctness": "unreviewed"}


def load_history_packet(directory, *, expected_content_sha256):
    """Verify a portable producer packet entirely offline with standard library.

    The caller supplies the trusted report seal. Checksums establish byte
    consistency, not publisher authentication or biological truth. Author XSD
    execution is a byte-bound producer receipt; this function never runs XSD.
    The packet includes native archives and the original human registry bytes.
    """
    import json
    from pathlib import Path
    from . import gold_packet
    from .cohort_mapping import load_registry

    folder = Path(directory).resolve()
    report = gold_packet._read(folder / "historical_verification.json")
    need(gold_packet._sealed(report) and report.get("content_sha256") == expected_content_sha256
         and report.get("format") == "biograph-steward.historical-WikiPathways-content-verification.v1",
         "portable packet report seal or format differs.")
    need(report.get("portable_archives_included") is True and report.get("portable_registry_directory") == "registry",
         "packet does not include offline native archive and registry proof.")
    files = report.get("files", {})
    required = {"resource_coverage.jsonl", "claim_assessments.jsonl", "edge_assessments.jsonl",
                "native_models.jsonl", "inventory.json", "source_inputs.json", "registry/manifest.json"}
    need(required <= set(files), "portable packet inventory is incomplete.")
    for name, pin in files.items():
        need(gold_packet._safe_relative(name), "unsafe packet path.")
        path = folder / name
        current = path
        while current != folder:
            need(not current.is_symlink(), "symlinked packet path.")
            current = current.parent
        need(path.is_file() and sha(path) == pin, "packet proof missing or changed: " + name)
    registry_manifest, registry = load_registry(folder / "registry")
    need(registry_manifest["registry_sha256"] == report.get("registry_sha256"), "portable registry binding differs.")

    def rows(name):
        with (folder / name).open(encoding="utf-8") as stream:
            return [json.loads(line) for line in stream]

    resources = rows("resource_coverage.jsonl")
    claims = rows("claim_assessments.jsonl")
    need(len({r["full_source_id"] for r in resources}) == len(resources)
         and len(resources) == report["counts"]["requested_distinct_versions"], "resource scope changed.")
    need(len({(r["subject"], r["full_source_id"]) for r in claims}) == len(claims)
         and len(claims) == report["counts"]["original_unique_subject_version_connections"], "claim scope changed.")
    need(all(gold_packet._sealed(row) for row in claims), "claim content seal differs.")
    return {"directory": folder, "report": report, "registry": registry,
        "resources": {r["full_source_id"]: r for r in resources},
        "connections": {(r["subject"], r["full_source_id"]): r for r in claims}}


def query_history(packet, subject, full_source_id):
    """Replay a selected original connection and return bounded source proof.

    Exact gene or protein encoding is source evidence. The native cited study
    inventory and native reference links are exposed separately; no paper is
    asserted to support all members or an inferred physical/causal relation.
    """
    import zipfile
    from pathlib import Path

    folder = packet["directory"]
    resource = packet["resources"].get(full_source_id)
    stored = packet["connections"].get((subject, full_source_id))
    result = {"subject": subject, "full_source_id": full_source_id,
        "packet_content_sha256": packet["report"]["content_sha256"],
        "resource": deepcopy(resource), "stored_assessment": deepcopy(stored),
        "independent_scientific_correctness": "unreviewed", "biological_negative_asserted": False,
        "schema_reexecuted_in_consumer": False, "source_fetches": 0, "model_calls": 0}
    if stored is None or resource is None or resource["status"] != "exact_publisher_revision_content_available":
        return {**result, "status": "unresolved", "reason": "no_original_connection_or_exact_native_model_in_packet"}
    model_file = resource["native_model_file"]
    need(model_file in packet["report"]["files"], "selected model is not in pinned packet scope.")
    raw = (folder / model_file).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == resource["gpml_sha256"] == stored["native_model_sha256"],
         "selected native model bytes differ.")
    candidate = resource["candidates"][0]
    archive_file = candidate.get("portable_archive_file")
    need(isinstance(archive_file, str) and archive_file in packet["report"]["files"], "selected native archive is not portable.")
    archive = folder / archive_file
    need(sha(archive) == candidate["archive_sha256"], "selected archive changed after packet loading.")
    with zipfile.ZipFile(archive) as z:
        entries = [e for e in z.infolist() if e.filename == candidate["archive_member"]]
        need(len(entries) == 1 and entries[0].file_size <= 20_000_000, "selected archive member binding differs.")
        need(z.read(entries[0]) == raw, "native archive member and extracted GPML differ.")
    receipt = deepcopy(resource["official_schema_validation"])
    receipt["gpml_sha256"] = resource["gpml_sha256"]
    model = inspect_model(raw, full_source_id=full_source_id, archive_member=candidate["archive_member"],
                          validation_receipt=receipt)
    replayed = assess_subject(subject, model, packet["registry"])
    need(replayed["status"] == stored["status"] and replayed["gene_bridge"] == stored["gene_bridge"],
         "selected literal identifier assessment differs from producer.")
    return {**result, "status": replayed["status"], "assessment": replayed,
        "model": model, "selected_archive_proof": deepcopy(candidate),
        "native_gpml_file": model_file, "registry_directory": "registry",
        "citation_interpretation": "literal model/element references; study support for membership is unadjudicated"}
