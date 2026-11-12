"""Compatibility adapters for released benchmarKIN gene/site transports.

Reuses the existing gene/product and coordinate checks. This reads supplied
library membership, not direct-catalysis truth or independent experimental
support. Present 15-mer sequences must agree with the captured canonical
reference, including the author's underscore terminal padding. A declared
unavailable sequence stays unreported; it is never manufactured from a match.
No measurement values, reference targets, expected directions or scores enter
these adapters.
"""
from collections import Counter, defaultdict
import csv
import hashlib
from io import StringIO
import re

from biograph_steward.client import digest
from pilot_methods import map_measurement_identifier, resolve_gene_protein


HEADER = ["source", "target", "target_protein", "position", "mor", "sequence"]


def map_ensembl_measurement_identifier(identifier, *, registry, sequence_reference):
    """Author four-field gene|site|ENSG|ENSP grammar, not a flanked peptide.

    The supplied ENSG must corroborate the qualified HGNC gene. ENSP is
    preserved but not inferred to identify the captured canonical product;
    the returned site is a gene/canonical-coordinate proxy for inference,
    not verification of an experimental proteoform or protein isoform.
    """
    fields = identifier.split("|") if isinstance(identifier, str) else []
    failure = {"reported_identifier": identifier, "status": "quarantined", "reasons": [],
               "protein_id": None, "site": None}
    if len(fields) != 4:
        return {**failure, "reasons": ["measurement_id_requires_exactly_four_declared_fields"]}
    gene, site, ensg, ensp = fields
    if not re.fullmatch(r"ENSG[0-9]{11}", ensg) or not re.fullmatch(r"ENSP[0-9]{11}", ensp):
        return {**failure, "reasons": ["declared_ensembl_fields_malformed_or_unreported"],
                "source_ensembl_gene": ensg, "source_ensembl_protein": ensp}
    result = map_measurement_identifier(gene + "_" + site + "|" + gene + "|" + site,
                                        registry, sequence_reference)
    result.update(reported_identifier=identifier, source_ensembl_gene=ensg, source_ensembl_protein=ensp,
                  ensembl_protein_correspondence="not_assessed", experimental_proteoform_identity_established=False)
    if result["status"] == "qualified":
        gid = result["gene_protein_mapping"]["hgnc_id"]
        declared = {s.strip() for s in registry.genes[gid]["ensembl_gene_id"].split("|") if s.strip()}
        if ensg not in declared:
            result.update(status="protein_context_unresolved", protein_id=None, site=None,
                          reasons=["source_ensembl_gene_does_not_corroborate_qualified_gene"])
        else:
            result["ensembl_gene_corroboration"] = "exact_captured_HGNC_relation"
    return result


def canonical_window(sequence, position):
    """The exact 15-mer around a one-based position, '_' outside the protein."""
    return "".join(sequence[i] if 0 <= i < len(sequence) else "_"
                   for i in range(position - 8, position + 7))


def qualify_library(raw, *, registry, sequence_reference, sequence_missing_tokens):
    """Preserve every source row and qualify unique binary memberships.

    The caller must explicitly declare the source's unavailable-sequence
    tokens. All other descriptor fields are required. Duplicate memberships
    retain row support but receive no additional numerical weight. Other
    libraries require their own documented transport contract.
    """
    if (not isinstance(raw, bytes) or isinstance(sequence_missing_tokens, str)
            or not isinstance(sequence_missing_tokens, (list, tuple, set, frozenset))
            or any(not isinstance(s, str) for s in sequence_missing_tokens)):
        raise ValueError("Supply original CSV bytes and explicit sequence missing tokens.")
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")), delimiter=",", strict=True)
    if reader.fieldnames != HEADER:
        raise ValueError("Library header differs from the released positional contract.")
    missing = set(sequence_missing_tokens)
    ledger, support, candidates, contexts = [], defaultdict(list), {}, {}
    for ordinal, row in enumerate(reader, 1):
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Library CSV row width differs from its header.")
        entry = {"source_row_ordinal": ordinal, "raw_row": row,
                 "raw_row_sha256": digest(row), "status": "unresolved", "reasons": []}
        ledger.append(entry)
        if row["target"] != row["target_protein"] + "_" + row["position"]:
            entry["reasons"].append("target_host_position_disagree")
        if row["mor"] != "1":
            entry["reasons"].append("membership_not_literal_positive_incidence")
        if not re.fullmatch(r"[STY][1-9][0-9]*", row["position"]):
            entry["reasons"].append("site_not_one_exact_positive_coordinate")
        if entry["reasons"]:
            continue
        enzyme = contexts.setdefault(row["source"], None)
        if enzyme is None:
            enzyme = resolve_gene_protein(row["source"], registry, sequence_reference)
            contexts[row["source"]] = enzyme
        host = map_measurement_identifier(
            row["target"] + "|" + row["target_protein"] + "|" + row["position"],
            registry, sequence_reference)
        entry.update(enzyme_context=enzyme, host_context=host)
        if enzyme["status"] != "qualified":
            entry["reasons"].append("source_gene_product_context_unresolved")
        if host["status"] != "qualified":
            entry["reasons"].append("host_gene_site_context_unresolved")
        if entry["reasons"]:
            continue
        sequence = row["sequence"]
        entry["flank_reporting"] = "unreported" if sequence in missing else "reported"
        if sequence not in missing:
            reference = sequence_reference[host["protein_id"].removeprefix("UniProtKB:")]["Sequence"]
            if (not re.fullmatch(r"[A-Z_]{15}", sequence)
                    or sequence != canonical_window(reference, int(row["position"][1:]))):
                entry["reasons"].append("present_flank_conflicts_with_canonical_reference")
                continue
        gene = enzyme["approved_symbol"]
        site = host["protein_id"] + "|" + host["site"]
        entry.update(status="compatible_membership", gene=gene, site_id=site,
                     exact_experimental_proteoform_established=False,
                     catalytic_truth_established=False)
        support[(gene, site)].append(ordinal)
        candidate = {"gene": gene, "enzyme": enzyme["protein_id"], "hgnc_id": enzyme["hgnc_id"]}
        if gene in candidates and candidates[gene] != candidate:
            raise ValueError("One library gene maps to conflicting protein contexts.")
        candidates[gene] = candidate
    if not ledger:
        raise ValueError("Library has no source rows.")
    signatures = {gene: [] for gene in sorted(candidates)}
    memberships = []
    for (gene, site), rows in sorted(support.items()):
        signatures[gene].append(site)
        memberships.append({"gene": gene, "site_id": site, "supporting_row_ordinals": rows})
    return {"source_sha256": hashlib.sha256(raw).hexdigest(), "rows": ledger,
            "candidates": list(candidates[g] for g in sorted(candidates)),
            "signatures": signatures, "memberships": memberships,
            "summary": {"input_rows": len(ledger), "compatible_rows": sum(r["status"] == "compatible_membership" for r in ledger),
                        "unique_memberships": len(memberships), "candidate_genes": len(candidates),
                        "unresolved_reasons": dict(Counter(reason for r in ledger for reason in r["reasons"]))},
            "independent_experiment_count_established": False,
            "source_citation_exclusion_possible_from_this_csv": False}
