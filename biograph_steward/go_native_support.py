"""Shared native GO reference eligibility, without research/runtime dependencies.

Moved without changing the experimental-code or context policy from the
existing reference adapter. Outside-scope curation is not a false annotation.
"""
EXPERIMENTAL = ("EXP", "IDA", "IPI", "IMP", "IGI", "IEP", "HTP", "HDA", "HMP", "HGI", "HEP")
POLICY = {"strict_projection_fields": ["subject", "GO_ID", "evidence_code", "assigned_by", "aspect"],
    "experimental_codes": list(EXPERIMENTAL), "positive_only": True,
    "single_human_taxon_only": True, "no_isoform_or_other_product_form": True,
    "no_annotation_extensions": True, "with_from_empty_for_unqualified_scope": True,
    "opposing_strict_NOT_candidate_kept_unknown": True}


def exclusion_reasons(row):
    """All context gates are literal; canonical column17 repetition is not an isoform."""
    reasons = []
    if row["evidence_code"] not in EXPERIMENTAL:
        reasons.append("not_experimental_evidence_code")
    if row["taxon_ids"] != ["taxon:9606"]:
        reasons.append("not_single_human_taxon")
    if row["gene_product_form_id"] not in (None, "", row["subject"]):
        reasons.append("distinct_product_form_not_collapsed")
    if row["annotation_extension_raw"]:
        reasons.append("native_annotation_extension_not_in_original_claim")
    if row["with_from_raw"]:
        reasons.append("native_with_from_context_not_in_original_claim")
    return reasons
