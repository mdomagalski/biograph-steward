"""Invented-tested transport, strict identity mapping and standard rank scoring.

This module performs no file or network access and no propagation. Measurement
preparation has no reference-metadata argument. Root owns prediction sealing,
the reference-access boundary and execution of unchanged author RoKAI code.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import csv
import hashlib
from io import StringIO
import json
import math
from numbers import Real
import re
from statistics import fmean

import numpy as np
from scipy import sparse
from scipy.stats import rankdata

from biograph_steward.cohort_mapping import Registry, table


SITE = re.compile(r"[STY][1-9][0-9]*\Z")
PROTEIN = re.compile(r"UniProtKB:[A-Z0-9]{6}(?:[A-Z0-9]{4})?\Z")
MISSING = {"", "NA", "NaN"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _need(value, message):
    if not value:
        raise ValueError(message)


def _csv(raw):
    """Explicit comma CSV; no delimiter inference or file-path argument."""
    _need(isinstance(raw, bytes), "Pass CSV bytes, never a file path.")
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")), delimiter=",", strict=True)
    header = reader.fieldnames
    _need(header and len(header) == len(set(header)) and all(header),
          "CSV requires distinct nonempty headers.")
    return reader, header


def _rows(reader):
    rows = list(reader)
    _need(all(None not in row and all(v is not None for v in row.values()) for row in rows),
          "CSV row width differs from its header.")
    return rows


def parse_numeric_cell(value):
    """Exact supplied missing tokens; finite zero is an observed value."""
    _need(isinstance(value, str), "Measurement CSV cells must be strings.")
    if value in MISSING:
        return None
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError("Invalid numeric measurement cell.") from error
    _need(math.isfinite(number), "Nonfinite measurement is not an allowed missing token.")
    return number


def parse_sequence_reference(raw):
    """Reuse the project's strict TSV parser for captured sequence references."""
    rows = table(raw, ["Entry", "Gene Names (primary)", "Organism (ID)", "Reviewed", "Sequence"])
    result = {}
    for ordinal, row in enumerate(rows, 1):
        accession = row["Entry"]
        _need(accession not in result, "Duplicate captured accession.")
        result[accession] = {**row, "reference_data_row_ordinal": ordinal}
    return result


def approved_gene(symbol, registry):
    """Resolve only unshadowed primary or uniquely HGNC-curated legacy tokens.

    Applies the pre-data activity correspondence amendment 850da46e...0b82.
    UniProt-only synonyms never qualify; no namespace or fuzzy fallback exists.
    """
    _need(isinstance(registry, Registry), "Use the project's Registry.")
    _need(isinstance(symbol, str), "Gene token must be a string.")
    resolution = registry.resolve(symbol)
    gid = resolution["hgnc_id"]
    hgnc_support = [r for r in resolution["matched_relations"]
                    if r["source"] == "HGNC" and r["field"] in {"prev_symbol", "alias_symbol"}
                    and r["hgnc_id"] == gid]
    primary = resolution["status"] == "approved_symbol" and not resolution["shadowed_relation_candidates"]
    legacy = (resolution["status"] == "unique_registry_relation" and bool(hgnc_support)
              and resolution["candidate_hgnc_ids"] == [gid]
              and all(r["hgnc_id"] == gid for r in resolution["matched_relations"]))
    eligible = primary or legacy
    return {"reported_gene": symbol, "eligible": bool(eligible),
            "resolution": deepcopy(resolution),
            "hgnc_id": gid if eligible else None,
            "approved_symbol": registry.genes[gid]["symbol"] if eligible else None,
            "accepted_relation_kind": "approved_symbol" if primary else "curated_hgnc_legacy" if legacy else None,
            "curated_hgnc_support": deepcopy(hgnc_support)}


def resolve_gene_protein(symbol, registry, sequence_reference):
    """One total product, exact primary gene and captured human sequence only."""
    gene = approved_gene(symbol, registry)
    result = {**gene, "status": "protein_context_unresolved", "protein_id": None,
              "candidate_protein_id": None, "reasons": [], "protein_candidates": []}
    if not gene["eligible"]:
        result["reasons"].append("gene_not_unshadowed_primary_or_unique_hgnc_curated_legacy")
        return result
    gid = gene["hgnc_id"]
    approved = gene["approved_symbol"]
    products = registry.products(gid)
    result["protein_candidates"] = deepcopy(products)
    result["hgnc_source_row"] = registry.genes[gid]["source_row"]
    if len(products) != 1:
        result["reasons"].append("requires_exactly_one_total_registry_product")
        return result
    product = products[0]
    pid = product["uniprot_id"]
    result["candidate_protein_id"] = pid
    if product["status"] != "reviewed_human_hgnc_match":
        result["reasons"].append("product_not_reviewed_human_hgnc_match")
    if product["shared_across_genes"] is not False:
        result["reasons"].append("product_shared_or_sharing_unresolved")
    accession = pid.removeprefix("UniProtKB:")
    protein = registry.proteins.get(accession)
    primary = protein.get("Gene Names (primary)") if protein else None
    result["registry_primary_gene_literal"] = primary
    if primary != approved or (primary or "").split() != [approved]:
        result["reasons"].append("registry_primary_gene_not_exact_single_approved_gene")
    captured = sequence_reference.get(accession)
    if captured is None:
        result["reasons"].append("captured_sequence_reference_missing")
    else:
        # Preserve supplied provenance without repeating entire sequences per row.
        sequence = captured.get("Sequence")
        result["sequence_reference"] = {k: deepcopy(v) for k, v in captured.items() if k != "Sequence"}
        if isinstance(sequence, str):
            result["sequence_reference"].update(sequence_length=len(sequence),
                sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest())
        if (captured.get("Entry") != accession
                or captured.get("Gene Names (primary)") != approved
                or captured.get("Organism (ID)") != "9606"
                or captured.get("Reviewed") != "reviewed"):
            result["reasons"].append("captured_reference_identity_gene_or_taxon_mismatch")
        if not isinstance(sequence, str) or not re.fullmatch(r"[A-Z]+", sequence):
            result["reasons"].append("captured_sequence_invalid")
        captured_hgnc = [v.strip() for v in str(captured.get("HGNC", "")).split(";") if v.strip()]
        if captured_hgnc and set(captured_hgnc) != {gid}:
            result["reasons"].append("captured_hgnc_conflicts_with_resolved_gene")
    if not result["reasons"]:
        result.update(status="qualified", protein_id=pid)
    return result


def map_measurement_identifier(identifier, registry, sequence_reference):
    result = {"reported_identifier": identifier, "status": "quarantined",
              "protein_id": None, "site": None, "reasons": []}
    fields = identifier.split("|") if isinstance(identifier, str) else []
    if len(fields) != 3:
        result["reasons"] = ["measurement_id_requires_exactly_three_pipe_fields"]
        return result
    first, symbol, site = fields
    result.update(reported_gene=symbol, reported_site=site)
    if not symbol or not SITE.fullmatch(site) or first != symbol + "_" + site:
        result["reasons"] = ["measurement_id_first_field_or_site_inconsistent"]
        return result
    mapping = resolve_gene_protein(symbol, registry, sequence_reference)
    result["gene_protein_mapping"] = mapping
    if mapping["status"] != "qualified":
        result.update(status="protein_context_unresolved", reasons=list(mapping["reasons"]))
        return result
    pid = mapping["protein_id"]
    sequence = sequence_reference[pid.removeprefix("UniProtKB:")]["Sequence"]
    position = int(site[1:])
    if position > len(sequence) or sequence[position - 1] != site[0]:
        result["reasons"] = ["observed_site_does_not_match_captured_sequence"]
        return result
    result.update(status="qualified", protein_id=pid, site=site,
                  sequence_position=position, reasons=[], experimental_proteoform_identity_established=False)
    return result


@dataclass
class PreparedMeasurements:
    condition_ids: tuple
    enzyme_ids: tuple
    site_ids: tuple
    X: np.ndarray
    Wkin2site: sparse.csr_matrix
    Wsite2site: sparse.csr_matrix
    rows: list
    aggregation: list
    qualified_ks_links: list
    provenance: dict


def prepare_measurements(raw_csv, *, condition_ids, registry, sequence_reference,
                         qualified_ks_links, provenance=None, id_column="ID"):
    """Prepare ONLY measurements and prior inputs. No metadata path/API exists.

    ``qualified_ks_links`` is root's already source-qualified prior, with fields
    enzyme/site_host/residue/position. This function does not re-curate it.
    All arrays are fixed once here and are reused unchanged for every PPI arm.
    """
    conditions = tuple(condition_ids)
    _need(conditions and len(set(conditions)) == len(conditions)
          and all(isinstance(c, str) and c for c in conditions), "Invalid condition roster.")
    reader, header = _csv(raw_csv)
    _need(header == [id_column, *conditions],
          "Measurement CSV must contain only ID and the explicit ordered condition columns.")
    raw_rows = _rows(reader)
    _need(raw_rows, "Measurement CSV is empty.")
    ledger = []
    observed = defaultdict(list)
    for ordinal, raw in enumerate(raw_rows, 1):
        values = {c: parse_numeric_cell(raw[c]) for c in conditions}
        mapped = map_measurement_identifier(raw[id_column], registry, sequence_reference)
        row = {"data_row_ordinal": ordinal, "raw_row": deepcopy(raw),
               "raw_row_sha256": _digest(raw), "mapping": mapped, "parsed_values": values}
        ledger.append(row)
        if mapped["status"] == "qualified":
            observed[(mapped["protein_id"], mapped["site"])].append(row)

    links = deepcopy(list(qualified_ks_links))
    incidence = set()
    for link in links:
        enzyme, host = link.get("enzyme"), link.get("site_host")
        residue, position = link.get("residue"), str(link.get("position", ""))
        _need(isinstance(enzyme, str) and PROTEIN.fullmatch(enzyme)
              and isinstance(host, str) and PROTEIN.fullmatch(host), "Invalid qualified KS identifier.")
        _need(residue in {"S", "T", "Y"} and re.fullmatch(r"[1-9][0-9]*", position),
              "Invalid qualified KS residue/position.")
        if "phosphorylation_incidence" in link:
            _need(type(link["phosphorylation_incidence"]) is int and link["phosphorylation_incidence"] == 1,
                  "Qualified KS incidence must be binary positive.")
        incidence.add((enzyme, (host, residue + position)))
    _need(incidence, "At least one qualified source KS link is required.")
    enzymes = tuple(sorted({enzyme for enzyme, _ in incidence}))
    source_sites = {site for _, site in incidence}
    sites = tuple(sorted(source_sites | set(observed)))
    ei = {enzyme: i for i, enzyme in enumerate(enzymes)}
    si = {site: i for i, site in enumerate(sites)}
    rr, cc = zip(*[(ei[enzyme], si[site]) for enzyme, site in sorted(incidence)])
    Wks = sparse.csr_matrix((np.ones(len(rr), dtype=np.uint8), (rr, cc)),
                           shape=(len(enzymes), len(sites)))
    X = np.full((len(sites), len(conditions)), np.nan, dtype=float)
    aggregation = []
    for site in sites:
        rows = observed.get(site, [])
        entry = {"protein_id": site[0], "site": site[1],
                 "measurement_data_row_ordinals": [r["data_row_ordinal"] for r in rows],
                 "source_ks_site": site in source_sites, "conditions": {}}
        for j, condition in enumerate(conditions):
            finite = sorted({r["parsed_values"][condition] for r in rows
                             if r["parsed_values"][condition] is not None})
            state = ("single_unique_finite_value" if len(finite) == 1 else
                     "conflicting_finite_values" if finite else
                     "no_finite_observation" if rows else "not_observed")
            value = finite[0] if len(finite) == 1 else None
            if value is not None:
                X[si[site], j] = value
            entry["conditions"][condition] = {"status": state, "unique_finite_values": finite,
                "value": value, "finite_data_row_ordinals": [r["data_row_ordinal"] for r in rows
                    if r["parsed_values"][condition] is not None]}
        aggregation.append(entry)
    provenance = deepcopy(provenance or {})
    provenance.update(measurement_csv_sha256=hashlib.sha256(raw_csv).hexdigest(),
        qualified_ks_links_sha256=_digest(links), metadata_accessed=False,
        zero_values_changed_to_missing=False, duplicate_groups_averaged=False,
        observed_site_groups=len(observed), qualified_measurement_rows=sum(len(x) for x in observed.values()),
        unresolved_measurement_rows=len(ledger) - sum(len(x) for x in observed.values()))
    return PreparedMeasurements(conditions, enzymes, sites, X, Wks,
        sparse.csr_matrix((len(sites), len(sites)), dtype=float), ledger, aggregation, links, provenance)


def parse_reference_csv(raw_csv, *, condition_column, drug_column, cell_column,
                        targets_column, sign_column, provenance=None):
    """Separate post-sealing boundary; caller explicitly supplies column names."""
    reader, header = _csv(raw_csv)
    columns = [condition_column, drug_column, cell_column, targets_column, sign_column]
    _need(len(set(columns)) == len(columns) and set(columns) <= set(header),
          "Explicit reference columns are missing or repeat.")
    result = []
    for ordinal, row in enumerate(_rows(reader), 1):
        raw_sign = row[sign_column]
        try:
            number = float(raw_sign)
        except ValueError:
            number = math.nan
        sign = int(number) if math.isfinite(number) and number in {-1.0, 1.0} else None
        result.append({"condition": row[condition_column], "drug": row[drug_column],
            "cell": row[cell_column], "source_targets": row[targets_column],
            "expected_sign": sign, "raw_sign": raw_sign, "raw_row": deepcopy(row),
            "reference_data_row_ordinal": ordinal, "provenance": deepcopy(provenance or {})})
    return result


@dataclass
class QualifiedReferences:
    cases: list
    exclusions: list
    duplicate_condition_target_sign_rows_collapsed: int
    input_rows: list


def qualify_expected_targets(typed_rows, registry):
    """Semicolon tokens use only the same frozen HGNC correspondence policy."""
    input_rows = deepcopy(list(typed_rows))
    groups = defaultdict(list)
    exclusions = []
    for ordinal, row in enumerate(input_rows, 1):
        condition, drug, cell = (row.get(k) for k in ("condition", "drug", "cell"))
        if not all(isinstance(x, str) and x for x in (condition, drug, cell)):
            exclusions.append({"reason": "invalid_reference_condition_drug_or_cell",
                               "input_ordinal": ordinal, "raw": row})
            continue
        groups[condition].append((ordinal, row))
    cases = []
    collapsed = 0
    for condition, records in sorted(groups.items()):
        contexts = {(r["drug"], r["cell"]) for _, r in records}
        if len(contexts) != 1:
            exclusions.append({"condition": condition, "reason": "conflicting_reference_condition_contexts",
                               "input_ordinals": [i for i, _ in records]})
            continue
        by_target = defaultdict(lambda: defaultdict(list))
        for ordinal, row in records:
            sign, targets = row.get("expected_sign"), row.get("source_targets")
            if type(sign) is not int or sign not in {-1, 1}:
                exclusions.append({"condition": condition, "input_ordinal": ordinal,
                    "reason": "invalid_numeric_expected_sign", "raw_sign": row.get("raw_sign", sign)})
                continue
            if not isinstance(targets, str):
                exclusions.append({"condition": condition, "input_ordinal": ordinal,
                                   "reason": "invalid_reference_target_field"})
                continue
            tokens = [token.strip() for token in targets.split(";")]
            if not any(tokens):
                exclusions.append({"condition": condition, "input_ordinal": ordinal,
                                   "reason": "empty_reference_target_field"})
            for token in tokens:
                if not token:
                    continue
                gene = approved_gene(token, registry)
                if not gene["eligible"]:
                    exclusions.append({"condition": condition, "input_ordinal": ordinal,
                        "reported_target": token, "reason": "reference_target_not_qualified_gene_token",
                        "resolution": gene["resolution"]})
                    continue
                by_target[gene["approved_symbol"]][sign].append({"input_ordinal": ordinal,
                    "hgnc_id": gene["hgnc_id"], "reported_token": token,
                    "gene_correspondence": deepcopy(gene)})
        targets = []
        for gene, signs in sorted(by_target.items()):
            collapsed += sum(max(0, len(rows) - 1) for rows in signs.values())
            if len(signs) != 1:
                exclusions.append({"condition": condition, "reported_target": gene,
                    "reason": "conflicting_expected_signs", "signs": sorted(signs),
                    "input_ordinals": sorted({r["input_ordinal"] for rows in signs.values() for r in rows})})
                continue
            sign, rows = next(iter(signs.items()))
            targets.append({"gene": gene, "hgnc_id": rows[0]["hgnc_id"], "sign": sign,
                "reported_tokens": sorted({r["reported_token"] for r in rows}),
                "gene_correspondence_records": [r["gene_correspondence"] for r in rows],
                "input_ordinals": [r["input_ordinal"] for r in rows]})
        drug, cell = next(iter(contexts))
        if targets:
            cases.append({"condition": condition, "drug": drug, "cell": cell, "targets": targets})
        else:
            exclusions.append({"condition": condition, "drug": drug, "cell": cell,
                               "reason": "no_qualified_atomic_reference_targets"})
    return QualifiedReferences(cases, exclusions, collapsed, input_rows)


def _prediction(value):
    if value is None:
        return None
    _need(isinstance(value, Real) and not isinstance(value, (bool, np.bool_)),
          "Predictions must be numeric or missing, without string coercion.")
    number = float(value)
    return number if math.isfinite(number) else None


def _macro(rows, key):
    return fmean(r[key] for r in rows) if rows else None


def score_predictions(predictions, references, *, candidate_genes, expected_cells):
    """Standard signed average-tie ranks; missing valid targets get rank M.

    Exactly one qualified condition per expected drug/cell is required for the
    primary two-cell drug macro. Incomplete/ambiguous reference groups remain
    explicitly unscorable rather than becoming model errors or invented labels.
    """
    _need(isinstance(references, QualifiedReferences), "Pass separately qualified references.")
    candidates = tuple(candidate_genes)
    cells = tuple(expected_cells)
    _need(candidates and len(candidates) == len(set(candidates))
          and all(isinstance(g, str) and g for g in candidates), "Invalid fixed enzyme candidate roster.")
    _need(len(cells) == 2 and len(set(cells)) == 2
          and all(isinstance(c, str) and c for c in cells), "Declare exactly two distinct expected cells.")
    M = len(candidates)
    candidate_set = set(candidates)
    scored = {}
    for condition, row in predictions.items():
        _need(isinstance(row, dict) and set(row) <= candidate_set,
              "Prediction contains a gene outside the fixed candidate roster.")
        scored[condition] = {g: _prediction(row.get(g)) for g in candidates}
    per_target, per_condition = [], []
    for case in references.cases:
        condition = case["condition"]
        values = scored.get(condition, {g: None for g in candidates})
        ranks = {}
        for sign in {-1, 1}:
            # Missing candidates remain in M and occupy the bottom tie group.
            ranks[sign] = rankdata([-(sign * values[g]) if values[g] is not None
                                    else math.inf for g in candidates], method="average")
        target_rows = []
        for target in case["targets"]:
            gene, sign = target["gene"], target["sign"]
            value = values.get(gene)
            abstain = gene not in candidate_set or value is None
            reason = ("valid_target_outside_fixed_prediction_universe" if gene not in candidate_set else
                      "condition_predictions_missing" if condition not in scored else
                      "target_score_missing_or_nonfinite" if value is None else None)
            rank = float(M) if abstain else float(ranks[sign][candidates.index(gene)])
            result = {"condition": condition, "drug": case["drug"], "cell": case["cell"],
                "gene": gene, "hgnc_id": target["hgnc_id"], "expected_sign": sign,
                "activity": value, "expected_signed_score": sign * value if value is not None else None,
                "rank": rank, "candidate_count_M": M, "normalized_rank": rank / M,
                "abstained": abstain, "abstention_reason": reason,
                "sign_agreement": bool(not abstain and sign * value > 0),
                "signed_top5_recovery": bool(not abstain and rank <= 5),
                "reported_target_tokens": list(target["reported_tokens"]),
                "gene_correspondence_records": deepcopy(target["gene_correspondence_records"]),
                "reference_input_ordinals": list(target["input_ordinals"])}
            per_target.append(result)
            target_rows.append(result)
        per_condition.append({"condition": condition, "drug": case["drug"], "cell": case["cell"],
            "atomic_target_count": len(target_rows),
            "normalized_rank": _macro(target_rows, "normalized_rank"),
            "sign_agreement": _macro(target_rows, "sign_agreement"),
            "signed_top5_recovery": _macro(target_rows, "signed_top5_recovery"),
            "target_score_coverage": fmean(not r["abstained"] for r in target_rows)})
    by_drug = defaultdict(list)
    for row in per_condition:
        by_drug[row["drug"]].append(row)
    per_drug, unscorable_drugs = [], []
    for drug, rows in sorted(by_drug.items()):
        counts = Counter(r["cell"] for r in rows)
        if set(counts) != set(cells) or any(counts[c] != 1 for c in cells):
            unscorable_drugs.append({"drug": drug, "reason": "requires_one_qualified_condition_per_expected_cell",
                                     "qualified_condition_counts_by_cell": dict(counts)})
            continue
        per_drug.append({"drug": drug, "conditions": sorted(r["condition"] for r in rows),
            "normalized_rank": _macro(rows, "normalized_rank"),
            "sign_agreement": _macro(rows, "sign_agreement"),
            "signed_top5_recovery": _macro(rows, "signed_top5_recovery"),
            "target_score_coverage": _macro(rows, "target_score_coverage")})
    n_scored = sum(not row["abstained"] for row in per_target)
    return {"candidate_genes": list(candidates), "candidate_count_M": M, "expected_cells": list(cells),
        "primary_macro_normalized_rank": _macro(per_drug, "normalized_rank"),
        "macro_sign_agreement": _macro(per_drug, "sign_agreement"),
        "macro_signed_top5_recovery": _macro(per_drug, "signed_top5_recovery"),
        "macro_target_score_coverage": _macro(per_drug, "target_score_coverage"),
        "per_target": per_target, "per_condition": per_condition, "per_drug": per_drug,
        "unscorable_reference_drug_groups": unscorable_drugs,
        "reference_exclusions": deepcopy(references.exclusions),
        "duplicate_condition_target_sign_rows_collapsed": references.duplicate_condition_target_sign_rows_collapsed,
        "coverage": {"qualified_reference_conditions": len(per_condition),
            "qualified_atomic_reference_targets": len(per_target), "scored_atomic_targets": n_scored,
            "abstained_atomic_targets": len(per_target) - n_scored,
            "atomic_target_score_coverage": n_scored / len(per_target) if per_target else None,
            "primary_drugs_with_both_cells": len(per_drug),
            "unscorable_reference_drug_groups": len(unscorable_drugs),
            "reference_exclusion_records": len(references.exclusions)}}
