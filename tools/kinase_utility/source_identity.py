"""Resolve a reported primary protein using captured protein/gene context.

This source-only path requires an explicit canonical UniProtKB identifier. It
does not resolve gene-only observations, choose another gene product, normalize
sites or establish the identity of an experimental construct. No file/network
access, source rewriting or activity inference is performed. The literal
identifier can be valid even when a source assertion grounds its cited entity
incorrectly; citation/entity grounding is not assessed by this helper.
"""
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import re

from biograph_steward.cohort_mapping import Registry, split
from biograph_steward.signor_source import ACCESSION


POLICY = "reported-primary-protein-gene-context.v2"


def resolve_source_protein_context(protein_id, registry, sequence_reference):
    """Require reciprocal captured identity for the literal reported protein.

    An HGNC-approved symbol can also be another gene's historical alias; the
    supplied protein identifier and reciprocal cross-references disambiguate
    this source context. Other products of the same gene remain distinct and
    do not invalidate the literal product. Neither rule applies to a gene-only
    measurement whose product is unknown. NCBI Gene identifiers provide
    secondary corroboration when available; missing values are recorded as
    unavailable, while present conflicts or nonunique values remain unresolved.
    Qualification concerns the supplied identifier context, not whether that
    identifier represents the entity described in a source sentence or paper.
    """
    if not isinstance(registry, Registry) or not isinstance(sequence_reference, Mapping):
        raise TypeError("Use the captured project Registry and sequence-reference mapping.")
    result = {
        "policy": POLICY, "reported_protein_id": protein_id,
        "status": "source_protein_context_unresolved", "protein_id": None,
        "hgnc_id": None, "approved_symbol": None, "reasons": [],
        "source_accession_remapped": False,
        "gene_protein_identity_equivalence": False,
        "experimental_proteoform_identity_established": False,
        "catalytic_role_verified": False,
        "citation_grounding_status": "not_assessed",
    }
    if not isinstance(protein_id, str) or not protein_id.startswith("UniProtKB:"):
        result["reasons"].append("explicit_UniProtKB_namespace_required")
        return result
    accession = protein_id.removeprefix("UniProtKB:")
    if not ACCESSION.fullmatch(accession) or "-" in accession:
        result["reasons"].append("literal_canonical_accession_required_no_isoform_or_secondary_rescue")
        return result
    protein = registry.proteins.get(accession)
    captured = sequence_reference.get(accession)
    if protein is None:
        result["reasons"].append("literal_primary_accession_absent_from_captured_registry")
    if captured is None:
        result["reasons"].append("literal_primary_accession_absent_from_sequence_reference")
    if protein is None or captured is None:
        return result
    result["registry_protein_context"] = deepcopy(protein)
    result["sequence_reference_context"] = {k: deepcopy(v) for k, v in captured.items() if k != "Sequence"}
    if protein.get("Entry") != accession or captured.get("Entry") != accession:
        result["reasons"].append("captured_primary_accession_conflict")
    if protein.get("Organism (ID)") != "9606" or captured.get("Organism (ID)") != "9606":
        result["reasons"].append("captured_human_taxon_required")
    if captured.get("Reviewed") != "reviewed":
        result["reasons"].append("captured_reviewed_status_required")
    sequence = captured.get("Sequence")
    if not isinstance(sequence, str) or not re.fullmatch(r"[A-Z]+", sequence):
        result["reasons"].append("captured_sequence_invalid")
    else:
        result["sequence_reference_context"].update(
            sequence_length=len(sequence), sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest())
    registry_gids = set(protein.get("hgnc_ids", []))
    captured_gids = set(split(str(captured.get("HGNC", "")), ";"))
    if len(registry_gids) != 1 or captured_gids != registry_gids:
        result["reasons"].append("exact_single_reciprocal_HGNC_context_required")
        return result
    gid = next(iter(registry_gids))
    gene = registry.genes.get(gid)
    result["candidate_hgnc_id"] = gid
    if gene is None or gene.get("status") != "Approved":
        result["reasons"].append("captured_HGNC_gene_not_approved")
        return result
    approved = gene["symbol"]
    result["candidate_approved_symbol"] = approved
    result["hgnc_gene_context"] = deepcopy(gene)
    products = registry.products(gid)
    result["all_declared_or_linked_gene_products"] = deepcopy(products)
    literal_products = [product for product in products if product["uniprot_id"] == protein_id]
    if (len(literal_products) != 1 or literal_products[0]["status"] != "reviewed_human_hgnc_match"
            or literal_products[0]["shared_across_genes"] is not False):
        result["reasons"].append("literal_product_fails_existing_registry_context_validation")
    if registry.primary.get(approved, set()) != {gid}:
        result["reasons"].append("approved_symbol_not_unique_in_HGNC_registry")
    if (protein.get("Gene Names (primary)") != approved
            or captured.get("Gene Names (primary)") != approved
            or approved.split() != [approved]):
        result["reasons"].append("exact_single_current_primary_gene_context_required")
    if accession not in set(split(gene.get("uniprot_ids", ""))):
        result["reasons"].append("HGNC_does_not_reciprocally_declare_literal_protein")
    gene_id = gene.get("entrez_id", "")
    secondary = {
        "HGNC": {gene_id} if gene_id else set(),
        "registry_UniProt": set(protein.get("ncbi_gene_ids", [])),
        "sequence_reference_UniProt": set(split(str(captured.get("GeneID", "")), ";")),
    }
    present = [values for values in secondary.values() if values]
    invalid = any(not re.fullmatch(r"[1-9][0-9]*", value) for values in present for value in values)
    non_unique = any(len(values) > 1 for values in present)
    conflicting = len({next(iter(values)) for values in present if len(values) == 1}) > 1
    if invalid or conflicting:
        corroboration = "conflict"
        result["reasons"].append("conflicting_secondary_GeneID_context")
    elif non_unique:
        corroboration = "ambiguous"
        result["reasons"].append("non_unique_secondary_GeneID_context")
    elif len(present) != len(secondary):
        corroboration = "unavailable"
    else:
        corroboration = "corroborated"
    result["secondary_GeneID_corroboration"] = {
        "status": corroboration,
        "observed_ids": {source: sorted(values) for source, values in secondary.items()},
        "missing_sources": [source for source, values in secondary.items() if not values],
        "missing_is_not_a_conflicting_identifier": True,
    }
    if not result["reasons"]:
        result.update(status="qualified_source_protein_context", protein_id=protein_id,
                      hgnc_id=gid, approved_symbol=approved)
    return result
