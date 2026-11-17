"""Execute a frozen, explicitly configured workbook/signature comparison.

This optional runner has no study names, gene names, worksheet defaults or
sample-name inference. A plan supplies those source-specific contracts. Raw
workbooks and row-level outputs retain their upstream rights outside the repo.
"""
import argparse
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from biograph_steward.client import digest
from biograph_steward.cohort_mapping import load_registry, SOURCES
from tools.kinase_utility import measurement_adapter as adapter
from tools.kinase_utility import signature_comparison as comparison
from tools.kinase_utility.pilot_methods import parse_sequence_reference, resolve_gene_protein
from tools.kinase_utility.source_identity import resolve_source_protein_context


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Expected an ordinary, pinned file: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as handle:
        handle.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def seal(value):
    return {**value, "content_sha256": digest(value)}


def jsonl(path, records):
    with Path(path).open("x") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")


def numeric_values(qualified):
    """Interpret only native numeric cells; retain other source states explicitly."""
    values, diagnostics = {}, []
    for item in qualified["raw_quant_values"]:
        cell, name = item["cell"], item["sample_id"]
        number, reason = None, None
        if cell["formula"] is not None or cell["cell_type"] == "e":
            reason = "formula_or_error_quantitation"
        elif item["source_value_state"] in {"blank", "missing_cell", "declared_missing_token"}:
            reason = item["source_value_state"]
        elif cell["cell_type"] != "n":
            reason = "non_numeric_cell_type_no_string_or_boolean_coercion"
        else:
            try:
                number = float(cell["text"])
            except (TypeError, ValueError):
                reason = "invalid_native_numeric_literal"
            else:
                if not math.isfinite(number):
                    reason, number = "nonfinite_native_numeric_value", None
        values[name] = number
        if reason is not None:
            diagnostics.append({"sample_id": name, "cell": cell["address"], "code": reason})
    return values, diagnostics


def _signatures(path, *, roster, partial):
    members = {} if partial else {row["gene"]: set() for row in roster}
    roster_lookup = {row["enzyme"]: row["gene"] for row in roster}
    for line in Path(path).read_text().splitlines():
        link = json.loads(line)
        enzyme, gene = link["enzyme"], link["enzyme_current_gene"]
        if (roster_lookup.get(enzyme) != gene or type(link["phosphorylation_incidence"]) is not int
                or link["phosphorylation_incidence"] != 1):
            raise ValueError("Signature membership differs from the supplied literal source roster.")
        position, residue = str(link["position"]), link["residue"]
        if (not position.isascii() or not position.isdigit() or position.startswith("0")
                or residue not in {"S", "T", "Y"}):
            raise ValueError("Signature source site is malformed.")
        site = link["site_host"] + ":" + residue + position
        members.setdefault(gene, set()).add(site)
    return members


def validate_plan(plan):
    """Reject incomplete designs and unpinned input roles before row access."""
    pins = plan.get("files_sha256", {})
    def pinned(path):
        if not isinstance(path, str) or not Path(path).is_absolute() or path not in pins:
            raise ValueError("An input role is absent from the absolute-path file freeze.")
    if (type(plan.get("minimum_finite_distinct_sites")) is not int
            or plan["minimum_finite_distinct_sites"] < 1):
        raise ValueError("Freeze a positive measured-site eligibility threshold.")
    if plan.get("roster_identity_policy") != "source_frozen_gene_product_correspondence.v1":
        raise ValueError("Declare the supported frozen catalogue-correspondence policy explicitly.")
    groups, control = plan["sample_groups"], plan["control_group"]
    if not isinstance(groups, Mapping) or any(not isinstance(members, (list, tuple)) for members in groups.values()):
        raise ValueError("Study groups require explicit lists of sample IDs.")
    samples = [sample for members in groups.values() for sample in members]
    # Exercise only schema validation with invented equal positive values.
    comparison.log2_contrasts({sample: 1.0 for sample in samples}, groups=groups, control=control)
    conditions = set(groups) - {control}
    if set(plan["workbooks"]) != {"protein", "phosphosite"}:
        raise ValueError("Freeze both protein and phosphosite workbook roles.")
    for role, entry in plan["workbooks"].items():
        pinned(entry["path"])
        contract = entry["contract"]
        adapter.validate_contract(contract)
        fields = set(contract.get("fields", {}))
        required = ({"accession", "source_group_count", "source_unique_peptides"} if role == "protein"
                    else {"accession", "peptide", "protein_site"})
        if role == "phosphosite":
            syntax = contract.get("modification_syntax")
            if syntax == "alphabase_separate":
                required |= {"modification_names", "modification_positions"}
            elif syntax == "counted_bracket_modifications.v1":
                required |= {"modifications_raw", "other_modifications", "phospho_modifications"}
            else:
                raise ValueError("The phosphosite descriptor grammar is unsupported.")
            if (contract.get("peptide_syntax") != "plain_uppercase"
                    or contract.get("protein_site_syntax") not in {"residue_position", "three_letter_position"}):
                raise ValueError("Declare supported literal peptide/site descriptor syntax.")
        if not required <= fields:
            raise ValueError("The workbook role lacks required descriptor columns.")
        if contract.get("accession_syntax") not in {"bare_uniprot", "uniprot_curie"}:
            raise ValueError("Declare a supported literal protein namespace representation.")
        declared_samples = [q["sample_id"] for q in contract["quant_columns"]]
        if set(declared_samples) != set(samples) or len(declared_samples) != len(samples):
            raise ValueError("Workbook samples and study-design samples differ.")
        if contract.get("workbook_sha256") != pins[entry["path"]]:
            raise ValueError("Workbook contract does not bind the same immutable input bytes.")
        if any(q.get("unit") != "source_reported_normalized_TMT_intensity" for q in contract["quant_columns"]):
            raise ValueError("This log-intensity runner needs an explicit source-reported TMT intensity profile.")
    pinned(plan["candidate_roster"])
    pinned(plan["sequence_reference"])
    for name in ["manifest.json", *SOURCES]:
        pinned(str(Path(plan["registry_directory"]) / name))
    if not plan["signature_profiles"]:
        raise ValueError("Freeze at least one complete-catalogue source profile.")
    kinds = []
    for profile in plan["signature_profiles"].values():
        pinned(profile["path"])
        kinds.append(profile["kind"])
        if profile["kind"] not in {"complete_candidate_universe", "partial_signature_diagnostic"}:
            raise ValueError("Signature profile kind is unsupported.")
    if "complete_candidate_universe" not in kinds:
        raise ValueError("A partial signature diagnostic cannot replace the primary comparison.")
    seen = set()
    for case in plan["expected_cases"]:
        key = (case["condition"], case["target"])
        if (case["condition"] not in conditions or not isinstance(case["target"], str) or not case["target"]
                or type(case["sign"]) is not int or case["sign"] not in {-1, 1} or key in seen):
            raise ValueError("Reference cases conflict with the frozen design or repeat.")
        seen.add(key)
    if not seen:
        raise ValueError("Freeze the complete declared target-case population.")


def validate_candidate_roster(roster, registry, sequences, *, policy):
    """Preserve the source catalogue's admission contract; retain audit warnings.

    The existing frozen gene/product resolver establishes correspondence for
    this historical catalogue. The newer literal-identifier audit is separate:
    a secondary cross-reference warning neither silently changes the source
    policy nor certifies the citation, experimental molecule or catalysis.
    """
    if policy != "source_frozen_gene_product_correspondence.v1":
        raise ValueError("Unsupported candidate-catalogue identity policy.")
    if (not isinstance(roster, list) or not roster
            or any(set(row) != {"gene", "enzyme", "hgnc_id"} for row in roster)):
        raise ValueError("Declare the exact qualified candidate roster fields.")
    for field in ["gene", "enzyme", "hgnc_id"]:
        values = [row[field] for row in roster]
        if any(not isinstance(value, str) or not value for value in values) or len(set(values)) != len(values):
            raise ValueError("Candidate roster is not injective.")
    audits = []
    for row in roster:
        context = resolve_gene_protein(row["gene"], registry, sequences)
        if (context["status"] != "qualified" or context["protein_id"] != row["enzyme"]
                or context["hgnc_id"] != row["hgnc_id"] or context["approved_symbol"] != row["gene"]):
            raise ValueError("Candidate roster differs from its frozen gene/product correspondence.")
        audit = resolve_source_protein_context(row["enzyme"], registry, sequences)
        audits.append({"source_roster_entry": row, "admission_policy": policy,
                       "source_correspondence_qualified": True, "separate_identity_audit": audit,
                       "audit_changes_source_admission": False})
    return audits


def run(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    plan = json.loads(plan_path.read_text())
    commitment = plan.pop("content_sha256")
    if digest(plan) != commitment or plan.get("format") != "biograph-steward.workbook-signature-execution.v1":
        raise ValueError("Broken or unsupported execution plan.")
    runtime = plan["runtime"]
    if platform.python_version() != runtime["python"]:
        raise ValueError("Python runtime differs from the execution freeze.")
    for package, version in runtime["packages"].items():
        if importlib.metadata.version(package) != version:
            raise ValueError("Package runtime differs from the execution freeze: " + package)
    for name, expected in plan["files_sha256"].items():
        if not Path(name).is_absolute() or sha(name) != expected:
            raise ValueError("Frozen file changed or lacks an absolute path: " + name)
    for path, expected in plan.get("sealed_json", {}).items():
        if path not in plan["files_sha256"]:
            raise ValueError("Sealed protocol is absent from the file freeze.")
        value = json.loads(Path(path).read_text())
        stored = value.pop("content_sha256")
        if stored != expected or digest(value) != stored:
            raise ValueError("Broken native project JSON protocol seal.")
    for code in [Path(__file__).resolve(), Path(adapter.__file__).resolve(), Path(comparison.__file__).resolve()]:
        if str(code) not in plan["files_sha256"]:
            raise ValueError("A directly executed helper is absent from the freeze.")
    validate_plan(plan)
    # Input defects must be diagnosed before any quantitative row access.
    _, registry = load_registry(Path(plan["registry_directory"]))
    sequences = parse_sequence_reference(Path(plan["sequence_reference"]).read_bytes())
    roster = json.loads(Path(plan["candidate_roster"]).read_text())
    catalogue_audit = validate_candidate_roster(roster, registry, sequences, policy=plan["roster_identity_policy"])
    candidates = [row["gene"] for row in roster]
    frozen_signatures = {name: _signatures(profile["path"], roster=roster,
        partial=profile["kind"] == "partial_signature_diagnostic")
        for name, profile in plan["signature_profiles"].items()}
    for entry in plan["workbooks"].values():
        contract = entry["contract"]
        metadata = adapter.inspect_workbook_headers(Path(entry["path"]).read_bytes(), contract["sheet_name"])
        if metadata["headers"] != contract["headers"]:
            raise ValueError("Workbook positional header differs from its frozen profile.")
    output.mkdir(parents=True, exist_ok=False)
    # Durable boundary before any quantitative workbook reader is called.
    write(output / "access_started.json", seal({"format": "biograph-steward.workbook-outcome-access.v1",
        "created_at": now(), "plan_file_sha256": sha(plan_path), "plan_content_sha256": commitment,
        "reference_is_predeclared_not_blinded": True}))
    write(output / "candidate_context_audit.json", catalogue_audit)
    groups, control = plan["sample_groups"], plan["control_group"]
    conditions = [name for name in groups if name != control]
    row_reports, site_records, protein_records, site_hosts = {}, [], [], {}
    for role, entry in plan["workbooks"].items():
        path = Path(entry["path"])
        if str(path) not in plan["files_sha256"]:
            raise ValueError("Workbook role is not bound to a frozen file.")
        contract = entry["contract"]
        transported = adapter.read_measurements(path.read_bytes(), contract, data_access_seal=commitment)
        reports = []
        for record in transported["records"]:
            if role == "phosphosite":
                qualified = adapter.qualify_record(record, contract, registry, sequences)
                accepted = qualified["status"] == "qualified_reference_coordinate_context"
            elif role == "protein":
                qualified = adapter.qualify_protein_record(record, contract, registry, sequences)
                accepted = qualified["status"] == "qualified_reference_protein_context"
            else:
                raise ValueError("Declare phosphosite or protein workbook roles explicitly.")
            report = {"record_id": role + ":row:" + str(record["row_number"]), "qualification": qualified}
            if accepted:
                numeric, issues = numeric_values(qualified)
                contrast = comparison.log2_contrasts(numeric, groups=groups, control=control)
                report.update(numeric_issues=issues, contrasts=contrast)
                key = qualified["canonical_site_id"] if role == "phosphosite" else qualified["protein_id"]
                typed = {"record_id": report["record_id"], "site_id": key, "contrasts": contrast["contrasts"]}
                (site_records if role == "phosphosite" else protein_records).append(typed)
                if role == "phosphosite":
                    if key in site_hosts and site_hosts[key] != qualified["protein_id"]:
                        raise ValueError("A canonical site has conflicting exact hosts.")
                    site_hosts[key] = qualified["protein_id"]
            reports.append(report)
        row_reports[role] = reports
        jsonl(output / (role + "_row_ledger.private.jsonl"), reports)
    if set(row_reports) != {"phosphosite", "protein"}:
        raise ValueError("Both declared phosphosite and protein input roles are required.")
    phospho = comparison.collapse_site_contrasts(site_records, conditions=conditions)
    protein = comparison.collapse_site_contrasts(protein_records, conditions=conditions)
    adjusted = comparison.adjust_for_host_protein(phospho["site_values"], site_hosts=site_hosts,
                                                  protein_values=protein["site_values"])
    common = {condition: {site: value if adjusted["site_values"][condition][site] is not None else None
                          for site, value in sites.items()}
              for condition, sites in phospho["site_values"].items()}
    backgrounds = {"unadjusted": phospho["site_values"], "common_support_unadjusted": common,
                   "protein_adjusted": adjusted["site_values"]}
    predictions = {}
    for name, profile in plan["signature_profiles"].items():
        signatures = frozen_signatures[name]
        predictions[name] = {background: comparison.infer_scores(values, signatures,
                            min_sites=plan["minimum_finite_distinct_sites"])
                            for background, values in backgrounds.items()}
    write(output / "predictions.private.json", predictions)
    prediction_seal = seal({"format": "biograph-steward.signature-predictions-sealed.v1",
        "created_at": now(), "execution_plan_content_sha256": commitment,
        "predictions_file_sha256": sha(output / "predictions.private.json"),
        "source_profile_kinds": {key: value["kind"] for key, value in plan["signature_profiles"].items()},
        "reference_is_predeclared_not_blinded": True})
    write(output / "prediction_seal.json", prediction_seal)
    # Inference above sees all declared sources/conditions and no expected sign.
    expected = plan["expected_cases"]
    results, partial_results = {}, {}
    for name, profile in plan["signature_profiles"].items():
        if profile["kind"] == "complete_candidate_universe":
            results[name] = {background: comparison.score_recovery(pred["scores"], expected,
                               candidate_ids=candidates, profile_kind=profile["kind"])
                             for background, pred in predictions[name].items()}
        else:
            partial_results[name] = {}
            for background, prediction in predictions[name].items():
                rows = []
                for case in expected:
                    score = prediction["scores"].get(case["condition"], {}).get(case["target"])
                    rows.append({**case, "score": score, "abstained": score is None,
                        "direction_agreement": bool(score is not None and case["sign"] * score > 0),
                        "eligibility": prediction["eligibility"].get(case["condition"], {}).get(case["target"]),
                        "cross_catalogue_rank_computed": False})
                partial_results[name][background] = rows
    coverage = {role: {"input_rows": len(rows), "qualification_states": dict(Counter(
        row["qualification"]["status"] for row in rows)), "diagnostic_codes": dict(Counter(
            issue["code"] for row in rows for issue in row["qualification"]["diagnostics"])),
        "quantitative_diagnostic_codes": dict(Counter(issue["code"] for row in rows
            for issue in row["qualification"].get("quantitative_diagnostics", []))),
        "numeric_issue_codes": dict(Counter(issue["code"] for row in rows for issue in row.get("numeric_issues", [])))}
                for role, rows in row_reports.items()}
    write(output / "site_aggregation.private.json", phospho)
    write(output / "protein_aggregation.private.json", protein)
    write(output / "host_adjustment.private.json", adjusted)
    result = seal({"format": "biograph-steward.workbook-signature-comparison.v1", "created_at": now(),
        "plan_content_sha256": commitment, "prediction_seal": prediction_seal["content_sha256"],
        "catalogue_identity_policy": plan["roster_identity_policy"],
        "separate_source_identity_audit_warnings": sum(
            row["separate_identity_audit"]["status"] != "qualified_source_protein_context" for row in catalogue_audit),
        "coverage": coverage, "primary_complete_catalogue": results,
        "partial_signature_diagnostics": partial_results,
        "site_counts_by_background": {background: {condition: sum(v is not None for v in sites.values())
            for condition, sites in values.items()} for background, values in backgrounds.items()},
        "biological_negatives_assumed": False, "inferential_precision_estimated": False,
        "whole_graph_accuracy_or_pruning_benefit_established": False})
    write(output / "results.private.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = run(args.plan, args.output)
    except (ValueError, OSError, KeyError) as error:
        diagnostic = getattr(error, "diagnostic", {"code": "comparison_validation_failed", "detail": str(error)})
        print(json.dumps({"status": "failed", "diagnostic": diagnostic,
                          "original_inputs_modified": False, "automatic_corrections_applied": False}), file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"result_seal": result["content_sha256"], "output": str(Path(args.output).resolve())}))
