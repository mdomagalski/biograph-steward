"""Qualify explicit identifiers in one immutable, source-scoped record.

This optional, pure reader does not repair a gene-only benchmark label. A
reported symbol is interpreted only alongside stable identifiers supplied in
the same bound record. Gene qualification never selects a protein; a literal
UniProt identifier additionally uses the existing source-protein audit. Neither
qualification establishes assay identity, catalysis or citation correctness.
"""
from collections.abc import Mapping
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import re

from biograph_steward.client import digest
from biograph_steward.cohort_mapping import Registry, split
from tools.kinase_utility.source_eligibility import canonical_source_row_digest
from tools.kinase_utility.source_identity import resolve_source_protein_context


POLICY = "exact-record-explicit-identifier-context.v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_BINDING = {"source_id", "source_release", "source_sha256", "source_record_id",
            "source_data_record_ordinal", "canonical_source_row_sha256"}
_NAMESPACES = {"HGNC", "ENSEMBL", "UniProtKB"}


def _need(condition, message):
    if not condition:
        raise ValueError("Scoped identity: " + message)


def _bound_row(source_bytes, binding, *, delimiter, record_id_field):
    _need(isinstance(binding, Mapping) and set(binding) == _BINDING,
          "supply the exact source/version/record/ordinal/row-digest binding.")
    _need(all(isinstance(binding[k], str) and bool(binding[k].strip())
              for k in ("source_id", "source_release", "source_record_id")),
          "source ID, release and native record ID must be explicit.")
    _need(isinstance(source_bytes, bytes) and bool(source_bytes)
          and isinstance(binding["source_sha256"], str)
          and _HASH.fullmatch(binding["source_sha256"])
          and hashlib.sha256(source_bytes).hexdigest() == binding["source_sha256"],
          "complete source bytes differ from the pinned SHA256.")
    ordinal = binding["source_data_record_ordinal"]
    _need(type(ordinal) is int and ordinal > 0
          and isinstance(binding["canonical_source_row_sha256"], str)
          and _HASH.fullmatch(binding["canonical_source_row_sha256"]),
          "require a positive data-record ordinal and canonical row SHA256.")
    _need(isinstance(delimiter, str) and delimiter in {",", "\t"}
          and isinstance(record_id_field, str) and bool(record_id_field),
          "declare comma/tab transport and the native record-ID column.")
    try:
        reader = csv.DictReader(StringIO(source_bytes.decode("utf-8-sig")), delimiter=delimiter, strict=True)
        _need(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames)
              and record_id_field in reader.fieldnames, "missing or duplicate source columns.")
        selected = None
        for number, row in enumerate(reader, 1):
            _need(None not in row and all(isinstance(value, str) for value in row.values()),
                  "malformed source row width.")
            if number == ordinal:
                selected = row
        _need(selected is not None, "bound data-record ordinal is absent.")
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("Scoped identity: source is not the declared UTF-8 CSV/TSV.") from error
    _need(selected[record_id_field] == binding["source_record_id"]
          and canonical_source_row_digest(selected) == binding["canonical_source_row_sha256"],
          "native record ID or canonical row digest is stale.")
    return selected


def qualify_scoped_identity(source_bytes, *, binding, delimiter, record_id_field,
                            identifier_fields, symbol_field, unavailable_values,
                            registry, sequence_reference):
    """Audit one exact source record with declared HGNC/ENSG/UniProt columns.

    ``identifier_fields`` maps a supported namespace to its native source
    column. No columns, aliases, delimiters, missing markers or identifiers
    are guessed. ``unavailable_values`` explicitly lists unavailable strings
    for each declared column, including an optional symbol column. A full HGNC
    CURIE is required; ENSG and primary UniProt accessions may be bare only when
    their namespace is declared by this column contract.

    Invalid/stale source bindings raise ValueError. Identity disagreements are
    returned as conflicts with no qualified identity, so their evidence remains
    inspectable. Unknown/unavailable metadata remains unresolved. Registry input
    verification belongs to the existing captured-registry loader; the returned
    context digest binds the registry records actually used by this audit.
    """
    if not isinstance(registry, Registry) or not isinstance(sequence_reference, Mapping):
        raise TypeError("Use the captured project Registry and sequence-reference mapping.")
    _need(isinstance(identifier_fields, Mapping) and set(identifier_fields) <= _NAMESPACES
          and all(isinstance(column, str) and bool(column) for column in identifier_fields.values())
          and len(set(identifier_fields.values())) == len(identifier_fields),
          "declare distinct columns for supported stable-identifier namespaces.")
    _need(symbol_field is None or isinstance(symbol_field, str) and bool(symbol_field),
          "symbol column must be explicit or None.")
    columns = set(identifier_fields.values()) | ({symbol_field} if symbol_field else set())
    _need(symbol_field not in identifier_fields.values(), "symbol and identifier columns must differ.")
    _need(isinstance(unavailable_values, Mapping) and set(unavailable_values) == columns
          and all(isinstance(values, (list, tuple, set, frozenset))
                  and all(isinstance(value, str) for value in values)
                  for values in unavailable_values.values()),
          "declare unavailable strings separately for every supplied column.")
    row = _bound_row(source_bytes, binding, delimiter=delimiter, record_id_field=record_id_field)
    _need(columns <= set(row), "declared identifier/symbol column is absent.")
    result = {"policy": POLICY, "source_binding": deepcopy(dict(binding)), "source_row": deepcopy(row),
        "column_contract": {"identifier_fields": dict(identifier_fields), "symbol_field": symbol_field,
                            "unavailable_values": {k: sorted(v) for k, v in unavailable_values.items()}},
        "status": "source_identity_unresolved", "gene_status": "unresolved", "hgnc_id": None,
        "approved_symbol": None, "protein_id": None, "protein_status": "not_reported",
        "identifier_audit": [], "reasons": [], "conflicts": [],
        "global_alias_override": False, "source_identifiers_rewritten": False,
        "gene_protein_identity_equivalence": False, "experimental_proteoform_identity_established": False,
        "catalytic_truth_established": False, "citation_grounding_status": "not_assessed",
        "mapping_scope": "one source release, file, native record and data-record ordinal",
        "publisher_authenticity_established": False}
    genes, context = set(), {}
    protein_audit = None
    for namespace, column in sorted(identifier_fields.items()):
        value = row[column]
        audit = {"namespace": namespace, "source_column": column, "reported_value": value,
                 "status": "unresolved", "candidate_hgnc_ids": []}
        if value in unavailable_values[column]:
            audit["status"] = "unavailable"
            result["identifier_audit"].append(audit)
            continue
        gids = set()
        if namespace == "HGNC":
            if re.fullmatch(r"HGNC:[1-9][0-9]*", value):
                gene = registry.genes.get(value)
                if gene and gene["status"] == "Approved":
                    gids.add(value)
        elif namespace == "ENSEMBL":
            ensg = value.removeprefix("ENSEMBL:")
            if re.fullmatch(r"ENSG[0-9]{11}", ensg):
                gids = {gid for gid, gene in registry.genes.items() if gene["status"] == "Approved"
                        and ensg in set(split(gene["ensembl_gene_id"]))}
        else:
            literal = value if value.startswith("UniProtKB:") else "UniProtKB:" + value
            protein_audit = resolve_source_protein_context(literal, registry, sequence_reference)
            result["protein_audit"] = protein_audit
            result["protein_status"] = protein_audit["status"]
            if protein_audit["status"] == "qualified_source_protein_context":
                gids.add(protein_audit["hgnc_id"])
        audit["candidate_hgnc_ids"] = sorted(gids)
        if len(gids) == 1:
            audit["status"] = "unique_captured_context"
            genes.update(gids)
            for gid in gids:
                context[gid] = deepcopy(registry.genes[gid])
        else:
            audit["status"] = "ambiguous_captured_context" if gids else "not_qualified_in_captured_context"
            result["reasons"].append("reported_" + namespace + "_identifier_not_uniquely_qualified")
        result["identifier_audit"].append(audit)
    if not any(a["status"] != "unavailable" for a in result["identifier_audit"]):
        result["reasons"].append("no_explicit_source_stable_identifier")
    if len(genes) > 1:
        result["conflicts"].append("explicit_identifiers_resolve_to_different_genes")
    if symbol_field:
        symbol = row[symbol_field]
        result["reported_symbol"] = symbol
        if symbol not in unavailable_values[symbol_field]:
            result["symbol_resolution_audit"] = deepcopy(registry.resolve(symbol))
            if len(genes) == 1:
                gid = next(iter(genes)); gene = registry.genes[gid]
                labels = {gene["symbol"]} | set(split(gene["prev_symbol"])) | set(split(gene["alias_symbol"]))
                if symbol not in labels:
                    candidates = (set(result["symbol_resolution_audit"]["candidate_hgnc_ids"])
                                  | set(result["symbol_resolution_audit"]["shadowed_relation_candidates"]))
                    if candidates:
                        result["conflicts"].append("reported_symbol_disagrees_with_explicit_stable_gene")
                    else:
                        result["reasons"].append("reported_symbol_not_a_captured_HGNC_label_for_stable_gene")
                else:
                    result["symbol_supported_by_explicit_identifier"] = True
    result["registry_gene_context"] = context
    result["registry_gene_context_sha256"] = digest(context)
    if result["conflicts"]:
        result["status"] = "source_identity_conflict"
    elif not result["reasons"] and len(genes) == 1:
        gid = next(iter(genes))
        result.update(status="qualified_source_gene_context", gene_status="qualified",
                      hgnc_id=gid, approved_symbol=registry.genes[gid]["symbol"])
        if protein_audit and protein_audit["status"] == "qualified_source_protein_context":
            result["protein_id"] = protein_audit["protein_id"]
    return result
