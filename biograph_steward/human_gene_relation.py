"""Exact human gene-to-protein cross-references, never inferred identity.

This is the unchanged relation rule originally used by the optional current
WikiPathways view. Keeping it in core avoids making ordinary source inspection
depend on research-tool modules or their optional libraries.
"""
import re


def gene_relationship(subject, registry):
    """No names, aliases, isoform stripping or inferred identity are used."""
    unknown = {"qualified": False, "ncbi_gene_id": None, "hgnc_id": None,
               "uniprot_source_row": None, "hgnc_source_row": None}
    if not isinstance(subject, str) or not re.fullmatch(r"UniProtKB:[A-Z0-9]{6}(?:[A-Z0-9]{4})?", subject):
        return {**unknown, "status": "unrecognized_exact_protein_identifier"}
    accession = subject[len("UniProtKB:"):]
    protein = registry.proteins.get(accession)
    if protein is None:
        return {**unknown, "status": "protein_not_in_human_registry"}
    genes, hgnc = protein["ncbi_gene_ids"], protein["hgnc_ids"]
    if len(genes) != 1 or not re.fullmatch(r"[1-9][0-9]*", genes[0]) or len(hgnc) != 1:
        return {**unknown, "status": "ambiguous_or_missing_explicit_gene_relation", "uniprot_source_row": protein["source_row"]}
    gene = registry.genes.get(hgnc[0])
    if gene is None or gene["status"] != "Approved" or gene["entrez_id"] != genes[0] or accession not in gene["uniprot_ids"].split("|"):
        return {**unknown, "status": "registry_cross_reference_conflict", "uniprot_source_row": protein["source_row"]}
    return {"qualified": True, "status": "explicit_human_UniProt_HGNC_Entrez_agreement",
        "ncbi_gene_id": genes[0], "hgnc_id": hgnc[0], "uniprot_source_row": protein["source_row"],
        "hgnc_source_row": gene["source_row"], "relation": "gene_to_protein_relationship_not_identity"}
