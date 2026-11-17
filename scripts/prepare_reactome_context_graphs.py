#!/usr/bin/env python3
"""Project the selected saved Pharos Reactome listings onto a frozen graph pair.

Versioned, outcome-blind preparation only. The historical GO experiment remains
immutable. A pathway listing is functional context, never a protein-pair label.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_pharos_inventory import BLOCKED_PMID, source_rows, verified_chunk, verified_header
from prepare_inmc_graphs import product_mapping
from biograph_steward.client import canonical, digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.graph import pathway_id
from retrieve_pharos_inventory import verify_sealed

FORMAT = "biograph-steward.reactome-context-projection.v1"
SELECTION = "docs/evaluations/reactome_context_intervention_20261026_selection.json"
SELECTION_SHA = "ed7d0efb4995c605f986943842be9d3d45e8fba1dbffad2405a29e9b9c6a08fe"
ORIGINAL = "runs/inmc_paired_graphs_20261023/frozen_cpu"
SNAPSHOT = "runs/inmc_pharos_uniform_20261022/retrieval"
RELATION = "pharos_reactome_membership"
ARMS = ("rgcn_baseline", "rgcn_reactome")
STABLE_ID = re.compile(r"R-HSA-[1-9][0-9]*")
HEX = re.compile(r"[0-9a-f]{64}")
PATHWAY_FIELDS = {"pwid", "name", "type", "sourceID", "url"}
BASE_RELATIONS = ("interacts", "reviewed_product_context", "pharos_cc_annotation")
ORIGINAL_FILES = (
    "annotation_dispositions.jsonl", "arms/baseline.tsv", "arms/enriched.tsv", "arms/scaffold.tsv",
    "assay_contract.json", "candidates.json", "development_pairs.json", "entities.json",
    "excluded_pharos_ppi.jsonl", "excluded_source_families.json", "protocol.json", "relations.json",
    "source_inventory.json", "split.json", "supervision.tsv",
    "validation/hierarchy_manifest.json", "validation/hierarchy_smoke.json", "validation/parent_graph_report.json",
    "validation/resource_runtime.json", "validation/resource_smoke.json",
)
COPY_FILES = ("supervision.tsv", "candidates.json", "split.json", "development_pairs.json",
              "source_inventory.json", "assay_contract.json")
HISTORICAL_PATHS = {
    "docs/evaluations/inmc_pharos_uniform_20261022_summary.json",
    "docs/evaluations/inmc_paired_graph_20261023_summary.json",
    "docs/evaluations/inmc_comparison_20261023_summary.json",
    "docs/evaluations/inmc_assay_contract_20261022.json",
    *(ORIGINAL + "/" + name for name in ("protocol.json", "report.json", "candidates.json", "split.json", "supervision.tsv")),
    "runs/inmc_comparison_20261023/scored/exposure_started.json",
    "scripts/prepare_inmc_graphs.py", "scripts/run_inmc_comparison.py", "scripts/score_inmc_comparison.py",
    "biograph_steward/inmc_outcomes.py", "biograph_steward/standard_export.py",
    "biograph_steward/graph.py", "docs/EXPERIMENT_HISTORY.md",
}
PREPARED_FILES = {
    *("arms/" + arm + ".tsv" for arm in ARMS), *COPY_FILES, "entities.json", "relations.json",
    "coverage.json", "membership_dispositions.jsonl", "eligible_memberships.tsv", "protocol.json",
}
CODE_FILES = {"scripts/prepare_reactome_context_graphs.py", "scripts/audit_pharos_inventory.py",
              "scripts/prepare_inmc_graphs.py", "scripts/retrieve_pharos_inventory.py",
              "biograph_steward/client.py", "biograph_steward/file_utils.py", "biograph_steward/graph.py"}


def ordinary(root, name):
    """Read one explicitly authorized member; never follow source-provided paths."""
    root, relative = Path(root).absolute(), Path(name)
    if (not isinstance(name, str) or relative.is_absolute() or ".." in relative.parts
            or not relative.parts or relative.as_posix() != name):
        raise ValueError("Unsafe member path.")
    path = root / relative
    if any(p.is_symlink() for p in (root, *root.parents, path, *path.parents)) or not path.is_file():
        raise ValueError("Inputs must be ordinary files without symlink traversal: " + name)
    return path


def bound_file(root, record):
    if (not isinstance(record, dict) or not isinstance(record.get("sha256"), str)
            or not HEX.fullmatch(record["sha256"]) or type(record.get("bytes")) is not int):
        raise ValueError("Malformed source binding.")
    path = ordinary(root, record["path"])
    if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
        raise ValueError("Source binding changed: " + record["path"])
    return path


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def selection_bindings():
    selected = ordinary(ROOT, SELECTION)
    if sha(selected) != SELECTION_SHA:
        raise ValueError("The selected intervention record changed.")
    selection = load_json(selected)
    if (selection.get("format") != "biograph-steward.reactome-context-intervention-selection.v1"
            or selection["source_inventory"]["snapshot"] != SNAPSHOT
            or selection["training"]["seeds"] != [17, 43, 101]):
        raise ValueError("Unexpected selection contract.")
    records = selection["historical_bindings"]
    if len(records) != len(HISTORICAL_PATHS) or {r["path"] for r in records} != HISTORICAL_PATHS:
        raise ValueError("Unexpected historical binding allowlist.")
    verified = {r["path"]: sha(bound_file(ROOT, r)) for r in records}
    metadata = selection["source_inventory"]["metadata_files"]
    expected = {SNAPSHOT + "/" + name for name in
                ("plan.json", "source.json", "summary.json", "context_targets.json", "gene_coverage.json")}
    if len(metadata) != len(expected) or {r["path"] for r in metadata} != expected:
        raise ValueError("Unexpected snapshot metadata allowlist.")
    verified.update({r["path"]: sha(bound_file(ROOT, r)) for r in metadata})
    check = selection["source_inventory"]["selection_source_check"]
    if check["path"] != "runs/reactome_context_selection_20261026/source_check.json":
        raise ValueError("Unexpected selection source-check path.")
    verified[check["path"]] = sha(bound_file(ROOT, check))
    archived = selection["archived_growth_report"]
    # The exact historical Git object is explicitly selected, never a worktree glob.
    if (archived["git_commit"] != "602681bc82417720e7a465bd19db7a7500c88f38"
            or archived["path"] != "docs/evaluations/CRC_FRESH_COMPARISON_20261020.md"):
        raise ValueError("Unexpected archived report binding.")
    raw = subprocess.run(["git", "show", archived["git_commit"] + ":" + archived["path"]],
                         cwd=ROOT, check=True, capture_output=True).stdout
    import hashlib
    if len(raw) != archived["bytes"] or hashlib.sha256(raw).hexdigest() != archived["sha256"]:
        raise ValueError("Archived comparison binding changed.")
    return selection, verified


def triples(path):
    with Path(path).open(newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        if next(reader, None) != ["subject", "predicate", "object"]:
            raise ValueError("Invalid triple header.")
        result = [tuple(row) for row in reader]
    if any(len(row) != 3 or any(not value for value in row) for row in result):
        raise ValueError("Malformed triple.")
    if result != sorted(set(result)):
        raise ValueError("Triples must be unique and ordered.")
    return result


def table(path, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["subject", "predicate", "object"])
        writer.writerows(rows)


def frozen_baseline(original, *, expected_files=None):
    original = Path(original)
    report = verify_sealed(load_json(ordinary(original, "report.json")))
    if set(report["files"]) != set(ORIGINAL_FILES):
        raise ValueError("Historical graph has an unexpected member allowlist.")
    if expected_files is not None and report["files"] != expected_files:
        raise ValueError("Original graph file bindings changed.")
    for name in ORIGINAL_FILES:
        if sha(ordinary(original, name)) != report["files"][name]:
            raise ValueError("Historical graph member changed: " + name)
    entities = load_json(original / "entities.json")
    relations = load_json(original / "relations.json")
    inventory = load_json(original / "source_inventory.json")
    split = load_json(original / "split.json")
    candidates = load_json(original / "candidates.json")
    baseline = triples(original / "arms/baseline.tsv")
    supervision = triples(original / "supervision.tsv")
    types = {row["id"]: row["type"] for row in entities}
    if len(types) != len(entities) or [r["id"] for r in relations] != [*BASE_RELATIONS, "go_is_a"]:
        raise ValueError("Historical vocabularies differ from selected original.")
    mappings = product_mapping(inventory)
    expected_links = {(gene, "reviewed_product_context", "UniProtKB:" + product)
                      for gene, products in mappings.items() for product in products}
    expected_supervision = sorted({(a, "interacts", b) for x, y in split["train_pairs"]
                                   for a, b in ((x, y), (y, x))})
    if supervision != expected_supervision:
        raise ValueError("Original supervision does not reproduce the split.")
    if ({row for row in baseline if row[1] == "reviewed_product_context"} != expected_links
            or {row for row in baseline if row[1] == "interacts"} != set(supervision)):
        raise ValueError("Original context mapping or supervision changed.")
    retained_go = set()
    with (original / "annotation_dispositions.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            if row["disposition"] == "retain_source_annotation_listing":
                retained_go.add((row["subject"], "pharos_cc_annotation", row["object"]))
    if set(baseline) != set(supervision) | expected_links | retained_go:
        raise ValueError("Original baseline includes an undeclared edge or omits a retained annotation.")
    if set(split["all_gene_ids"]) != {g for g, kind in types.items() if kind == "original_gene"}:
        raise ValueError("Original gene identities differ from the split.")
    for row in candidates:
        if (any(g not in types or types[g] != "original_gene" for g in row["original_genes"])
                or row["products_by_gene"] != {g: sorted(mappings[g]) for g in set(row["original_genes"])}):
            raise ValueError("Original candidate identities or reviewed mappings changed.")
    return {"report": report, "entities": entities, "relations": relations, "inventory": inventory,
            "split": split, "candidates": candidates, "baseline": baseline, "supervision": supervision}


def qualify_memberships(records, products):
    """Preserve every source row, disposition and uncertainty; never infer pairs."""
    ledger, stable_labels, local_ids = [], defaultdict(set), defaultdict(set)
    for uid, raw, locator in records:
        if not isinstance(raw, dict) or not isinstance(uid, str) or not isinstance(locator, str):
            raise ValueError("Malformed source-listed pathway record.")
        reasons = []
        selected = raw.get("type") == "Reactome"
        stable, label = raw.get("sourceID"), raw.get("name")
        if not selected:
            reasons.append("outside_selected_Reactome_source")
        else:
            if not isinstance(stable, str) or not STABLE_ID.fullmatch(stable):
                reasons.append("invalid_or_nonhuman_Reactome_stable_id")
            if not isinstance(label, str) or not label.strip():
                reasons.append("missing_pathway_label")
            if set(raw) != PATHWAY_FIELDS:
                reasons.append("unexpected_source_field_semantics")
            if uid not in products:
                reasons.append("product_absent_from_frozen_reviewed_vocabulary")
            if BLOCKED_PMID.search(canonical(raw)):
                reasons.append("blocked_reference_in_pathway_row")
            if isinstance(stable, str) and STABLE_ID.fullmatch(stable):
                if isinstance(label, str) and label.strip():
                    stable_labels[stable].add(label)
                if raw.get("pwid") is not None:
                    local_ids[str(raw["pwid"])].add(stable)
        ledger.append({"subject": "UniProtKB:" + uid, "source_locator": locator,
                       "source_row": raw, "source_row_sha256": digest(raw),
                       "primary_source": raw.get("type"), "selected_source": selected,
                       "source_identifier": stable, "reasons": reasons,
                       "qualifications": {
                           "meaning": "source_listed_product_pathway_membership_only",
                           "direct_binding_assertion": False, "biological_validation": False,
                           "assayed_construct_or_proteoform_identity_established": False,
                           "specific_pathway_role_or_reaction_established": False,
                           "import_release": "unknown", "study_lineage": "unverified",
                           "original_reference": "not_exposed_by_saved_Pharos_pathway_row",
                           "snapshot_postdates_assays": True}})
    label_conflicts = {key for key, values in stable_labels.items() if len(values) != 1}
    local_conflicts = {key for key, values in local_ids.items() if len(values) != 1}
    retained, nodes, raw_keys = set(), {}, set()
    duplicate_rows = 0
    for row in ledger:
        raw, stable = row["source_row"], row["source_identifier"]
        if row["selected_source"]:
            if isinstance(stable, str) and stable in label_conflicts:
                row["reasons"].append("conflicting_stable_id_labels")
            if str(raw.get("pwid")) in local_conflicts:
                row["reasons"].append("conflicting_Pharos_local_id_stable_ids")
        mapped, exact = pathway_id(raw)
        row["object"] = mapped if row["selected_source"] and exact else None
        if not row["reasons"]:
            key = (row["subject"], RELATION, mapped)
            if key in retained:
                row["reasons"].append("duplicate_product_pathway_membership")
                duplicate_rows += 1
            else:
                retained.add(key)
                nodes[mapped] = {"id": mapped, "type": "reactome_pathway", "label": raw["name"],
                                 "source_identifier": stable, "direct_binding_assertion": False}
        if row["selected_source"]:
            raw_keys.add((row["subject"], stable if isinstance(stable, str) else canonical(stable)))
        row["disposition"] = "exclude" if row["reasons"] else "retain_source_membership_listing"
    selected_rows = [r for r in ledger if r["selected_source"]]
    counts = {"source_pathway_rows": len(ledger), "selected_source_rows": len(selected_rows),
              "source_distinct_product_pathway_memberships": len(raw_keys),
              "source_products": len({r["subject"] for r in selected_rows}),
              "source_pathway_stable_ids": len({r["source_identifier"] for r in selected_rows
                                                if isinstance(r["source_identifier"], str)}),
              "eligible_memberships": len(retained), "eligible_products": len({a for a, _, _ in retained}),
              "eligible_pathways": len(nodes), "duplicate_membership_rows": duplicate_rows,
              "stable_id_label_conflicts": len(label_conflicts),
              "Pharos_local_id_stable_id_conflicts": len(local_conflicts),
              "invalid_human_stable_id_rows": sum("invalid_or_nonhuman_Reactome_stable_id" in r["reasons"] for r in ledger),
              "dispositions": dict(Counter(r["disposition"] for r in ledger)),
              "exclusion_reasons": dict(Counter(reason for row in ledger for reason in row["reasons"]))}
    return {"memberships": sorted(retained), "nodes": sorted(nodes.values(), key=lambda r: r["id"]),
            "ledger": ledger, "counts": counts}


def candidate_coverage(candidates, inventory, memberships):
    mappings = product_mapping(inventory)
    by_product = defaultdict(set)
    for product, relation, pathway in memberships:
        if relation != RELATION:
            raise ValueError("Coverage accepts only the selected membership relation.")
        by_product[product.removeprefix("UniProtKB:")].add(pathway)
    rows = []
    for candidate in candidates:
        genes = candidate["original_genes"]
        contexts = {g: sorted(set().union(*(by_product[p] for p in mappings[g]))) for g in set(genes)}
        rows.append({"candidate_id": candidate["id"], "original_genes": genes, "self_pair": candidate["self_pair"],
                     "pathways_by_gene": contexts,
                     "covered_endpoint_count": sum(bool(contexts[g]) for g in genes),
                     "coverage_only_score": sum(bool(contexts[g]) for g in genes)})
    return {"format": "biograph-steward.reactome-candidate-coverage.v1", "outcome_values_loaded": False,
            "population": "All original nominations; scoring eligibility is applied later by the unchanged assay contract.",
            "zero_context_means": "No eligible listing in this bounded snapshot, not biological absence.",
            "rows": rows, "counts": {
                "all_candidates": len(rows), "self_pairs": sum(r["self_pair"] for r in rows),
                "all_candidates_by_endpoint_coverage": dict(Counter(str(r["covered_endpoint_count"]) for r in rows)),
                "off_diagonal_candidates_by_endpoint_coverage": dict(Counter(str(r["covered_endpoint_count"])
                                                                           for r in rows if not r["self_pair"])),
                "panel_genes": len(mappings),
                "panel_genes_with_membership": sum(any(by_product[p] for p in products) for products in mappings.values())}}


def graph_pair(baseline, entities, relations, qualified):
    types = {r["id"]: r["type"] for r in entities}
    if len(types) != len(entities) or any(r[1] not in BASE_RELATIONS for r in baseline):
        raise ValueError("Baseline has a duplicate vocabulary or forbidden relation.")
    for subject, relation, obj in baseline:
        required = {"interacts": ("original_gene", "original_gene"),
                    "reviewed_product_context": ("original_gene", "reviewed_product_context"),
                    "pharos_cc_annotation": ("reviewed_product_context", "go_term")}[relation]
        if (types.get(subject), types.get(obj)) != required:
            raise ValueError("Forbidden direct protein-pair or mistyped baseline edge.")
    nodes = qualified["nodes"]
    if (len({r["id"] for r in nodes}) != len(nodes)
            or any(r["id"] in types or r["type"] != "reactome_pathway" for r in nodes)):
        raise ValueError("Invalid added pathway vocabulary.")
    for row in nodes:
        types[row["id"]] = row["type"]
    memberships = set(qualified["memberships"])
    for a, relation, b in memberships:
        if (relation != RELATION or types.get(a) != "reviewed_product_context"
                or types.get(b) != "reactome_pathway" or not b.startswith("REACT:R-HSA-")):
            raise ValueError("Only exact product-to-human-pathway context is permitted; direct protein-pair edges are forbidden.")
    baseline, enriched = sorted(set(baseline)), sorted(set(baseline) | memberships)
    if set(enriched) - set(baseline) != memberships or set(baseline) & memberships:
        raise ValueError("Intervention edge difference is not precisely the eligible ledger.")
    relation_ids = [r["id"] for r in relations]
    if relation_ids != [*BASE_RELATIONS, "go_is_a"]:
        raise ValueError("Original relation order changed.")
    return {"entities": sorted([*entities, *nodes], key=lambda r: r["id"]),
            "relations": [*relations, {"id": RELATION}],
            "arms": {ARMS[0]: baseline, ARMS[1]: enriched}}


def snapshot_records(frozen, selection):
    retrieval = ROOT / SNAPSHOT
    plan, source, summary, inventory, ids, names = verified_header(retrieval)
    if (inventory != frozen["inventory"] or source["db_version"] != selection["source_inventory"]["db_version"]
            or summary["files"] != frozen["report"]["chunk_files"]
            or {name: sha(ordinary(retrieval, name)) for name in frozen["report"]["retrieval_files"]}
            != frozen["report"]["retrieval_files"]):
        raise ValueError("Snapshot does not match the selected original graph inputs.")
    records = []
    for number, name in enumerate(names):
        ordinary(retrieval, name)
        chunk = verified_chunk(retrieval, name, plan, source, summary,
                               ids[number * plan["chunk_size"]:(number + 1) * plan["chunk_size"]])
        raw = defaultdict(list)
        for uid, row, locator in source_rows(chunk, name, "pathways"):
            raw[(uid, digest(row))].append(locator)
        for target_index, target in enumerate(chunk["targets"]):
            for row_index, row in enumerate(target["pathways"]):
                uid = target["uniprot"]
                key = uid, digest(row)
                if not raw[key]:
                    raise ValueError("Retained pathway row lacks an identical raw response.")
                raw_locator = raw[key].pop(0)
                retained_locator = f"{name}#/targets/{target_index}/pathways/{row_index}"
                records.append((uid, row, {"retained": retained_locator, "raw_response": raw_locator}))
        if any(raw.values()):
            raise ValueError("Unaccounted raw pathway response rows.")
    return records, summary


def qualify_snapshot(records, frozen):
    qualified = qualify_memberships([(uid, row, locator["retained"]) for uid, row, locator in records],
                                   {r["id"].removeprefix("UniProtKB:") for r in frozen["entities"]
                                    if r["type"] == "reviewed_product_context"})
    for entry, (_, _, locators) in zip(qualified["ledger"], records, strict=True):
        entry["raw_response_locator"] = locators["raw_response"]
    return qualified


def make_protocol(selection):
    return {"format": FORMAT, "fully_frozen": False, "selection_sha256": SELECTION_SHA,
            "arms": list(ARMS), "model": selection["learner"], "training": selection["training"],
            "evaluation": selection["evaluation"], "coverage_only_diagnostic": selection["coverage_only_diagnostic"],
            "population": selection["population"], "predictor_exclusions": selection["predictor_exclusions"],
            "source_independence_limit": selection["source_independence_limit"], "stopping": selection["stopping"],
            "runtime_proof": None, "resource_proof": None, "execution_freeze": None}


def prepare(output):
    selection, bindings = selection_bindings()
    original, retrieval = ROOT / ORIGINAL, ROOT / SNAPSHOT
    frozen = frozen_baseline(original)
    records, summary = snapshot_records(frozen, selection)
    qualified = qualify_snapshot(records, frozen)
    counts, expected = qualified["counts"], selection["source_inventory"]["available_reactome_counts"]
    checks = {"selected_source_rows": "source_rows", "source_products": "products",
              "source_pathway_stable_ids": "pathway_stable_ids",
              "source_distinct_product_pathway_memberships": "distinct_product_pathway_memberships",
              "stable_id_label_conflicts": "stable_id_label_conflicts",
              "Pharos_local_id_stable_id_conflicts": "pharos_pathway_id_to_multiple_stable_id_conflicts",
              "invalid_human_stable_id_rows": "invalid_human_stable_ids"}
    if any(counts[actual] != expected[key] for actual, key in checks.items()):
        raise ValueError("Pathway source inventory does not reproduce the selected source check.")
    if counts["source_pathway_rows"] != summary["families"]["pathways"]["retained"]:
        raise ValueError("Pathway source counts do not reconcile.")
    paired = graph_pair(frozen["baseline"], frozen["entities"], frozen["relations"], qualified)
    coverage = candidate_coverage(frozen["candidates"], frozen["inventory"], qualified["memberships"])
    protocol = make_protocol(selection)
    out = new_output(output, original, retrieval, ROOT / SELECTION)
    (out / "arms").mkdir()
    # Byte copies guarantee unchanged original candidates, masks and supervision.
    for name in COPY_FILES:
        (out / name).write_bytes((original / name).read_bytes())
    (out / "arms" / (ARMS[0] + ".tsv")).write_bytes((original / "arms/baseline.tsv").read_bytes())
    table(out / "arms" / (ARMS[1] + ".tsv"), paired["arms"][ARMS[1]])
    table(out / "eligible_memberships.tsv", qualified["memberships"])
    for name, value in (("entities.json", paired["entities"]), ("relations.json", paired["relations"]),
                        ("coverage.json", coverage), ("protocol.json", protocol)):
        write_json(out / name, value)
    with (out / "membership_dispositions.jsonl").open("w") as stream:
        for row in qualified["ledger"]:
            stream.write(canonical(row) + "\n")
    for name, expected_sha in bindings.items():
        if sha(ordinary(ROOT, name)) != expected_sha:
            raise ValueError("Bound inputs changed during preparation.")
    for name, expected_sha in summary["files"].items():
        if sha(ordinary(retrieval, name)) != expected_sha:
            raise ValueError("Bound snapshot changed during preparation.")
    report = {"format": FORMAT, "created_at": utcnow(), "status": "prepared_native_and_resource_checks_pending",
              "fully_frozen": False, "outcome_values_loaded": False, "model_fitting": False,
              "scientific_predictions_generated": False, "reserved_IntAct_access": False,
              "selection_sha256": SELECTION_SHA, "historical_bindings": bindings,
              "original_graph_report_sha256": sha(original / "report.json"),
              "original_graph_files": frozen["report"]["files"], "snapshot_chunk_files": summary["files"],
              "code_sha256": {name: sha(ROOT / name) for name in sorted(CODE_FILES)},
              "counts": {"memberships": counts, "coverage": coverage["counts"],
                         "entities": len(paired["entities"]), "relations": len(paired["relations"]),
                         "arms": {k: len(v) for k, v in paired["arms"].items()},
                         "supervised_directed_triples": len(frozen["supervision"])},
              "invariants": {"baseline_byte_identical": True, "original_supervision_candidates_and_masks_byte_identical": True,
                             "same_ordered_union_vocabulary": True, "only_exact_membership_edges_added": True,
                             "all_Pharos_PPI_excluded": True, "GO_hierarchy_edges_added": False,
                             "zero_context_candidates_preserved": True},
              "limits": ["Consumed retrospective development panel, not independent validation.",
                         "Reactome import release and study lineage remain unknown; no certified derivative exclusion.",
                         "Membership does not establish direct binding, molecular form or pathway reaction role.",
                         "Coverage is outcome-independent across all nominations; the original 1751-pair scoring denominator is applied only later.",
                         "No intended-runtime resource proof or real execution freeze exists yet."],
              "files": {name: sha(out / name) for name in sorted(PREPARED_FILES)}}
    report["content_sha256"] = digest(report)
    write_json(out / "report.json", report)
    validate_prepared_packet(out)
    return report


def validate_prepared_packet(folder):
    """Fail closed on a changed graph, mask, vocabulary, ledger or source binding."""
    folder = Path(folder)
    report = verify_sealed(load_json(ordinary(folder, "report.json")))
    if report.get("format") != FORMAT or report.get("selection_sha256") != SELECTION_SHA:
        raise ValueError("Unsupported Reactome preparation packet.")
    if set(report.get("files", {})) != PREPARED_FILES:
        raise ValueError("Unexpected prepared-packet member allowlist.")
    for name, expected in report["files"].items():
        if sha(ordinary(folder, name)) != expected:
            raise ValueError("Prepared graph member changed: " + name)
    selection, bindings = selection_bindings()
    if report["historical_bindings"] != bindings:
        raise ValueError("Selected historical bindings changed.")
    original = ROOT / ORIGINAL
    frozen = frozen_baseline(original, expected_files=report["original_graph_files"])
    if sha(original / "report.json") != report["original_graph_report_sha256"]:
        raise ValueError("Original graph report changed.")
    for name in COPY_FILES:
        if report["files"][name] != frozen["report"]["files"][name]:
            raise ValueError("Original candidate, supervision or mask bytes changed.")
    if report["files"]["arms/rgcn_baseline.tsv"] != frozen["report"]["files"]["arms/baseline.tsv"]:
        raise ValueError("Baseline triples changed.")
    # Read only the declared source manifest, never recursive source discovery.
    if report["snapshot_chunk_files"] != frozen["report"]["chunk_files"]:
        raise ValueError("Snapshot member inventory changed.")
    for name, expected in report["snapshot_chunk_files"].items():
        if not re.fullmatch(r"chunks/[0-9]{5}\.json", name) or sha(ordinary(ROOT / SNAPSHOT, name)) != expected:
            raise ValueError("Snapshot member changed.")
    if set(report["code_sha256"]) != CODE_FILES:
        raise ValueError("Unexpected preparation-code binding.")
    for name, expected in report["code_sha256"].items():
        if sha(ordinary(ROOT, name)) != expected:
            raise ValueError("Preparation implementation changed.")
    memberships = triples(folder / "eligible_memberships.tsv")
    ledger_rows = [json.loads(line) for line in (folder / "membership_dispositions.jsonl").read_text().splitlines()]
    records, _ = snapshot_records(frozen, selection)
    qualified = qualify_snapshot(records, frozen)
    if ledger_rows != qualified["ledger"] or memberships != qualified["memberships"]:
        raise ValueError("Eligible membership ledger differs from graph edges.")
    all_entities = load_json(folder / "entities.json")
    expected_pair = graph_pair(frozen["baseline"], frozen["entities"], frozen["relations"],
                               qualified)
    if all_entities != expected_pair["entities"] or load_json(folder / "relations.json") != expected_pair["relations"]:
        raise ValueError("Union vocabularies changed.")
    for arm in ARMS:
        if triples(folder / "arms" / (arm + ".tsv")) != expected_pair["arms"][arm]:
            raise ValueError("Forbidden arm delta or missing edge.")
    coverage = candidate_coverage(frozen["candidates"], frozen["inventory"], memberships)
    if load_json(folder / "coverage.json") != coverage:
        raise ValueError("Candidate coverage or missing-context identities changed.")
    protocol = load_json(folder / "protocol.json")
    if protocol != make_protocol(selection) or report["fully_frozen"] is not False:
        raise ValueError("Preparation cannot change selected settings or assert execution freeze.")
    if (report["counts"]["memberships"] != qualified["counts"]
            or report["counts"]["coverage"] != coverage["counts"]):
        raise ValueError("Preparation counts do not reconcile.")
    expected_totals = {"entities": len(expected_pair["entities"]), "relations": len(expected_pair["relations"]),
                       "arms": {arm: len(rows) for arm, rows in expected_pair["arms"].items()},
                       "supervised_directed_triples": len(frozen["supervision"])}
    if any(report["counts"].get(key) != value for key, value in expected_totals.items()):
        raise ValueError("Documented graph and supervision totals do not reconcile.")
    return {"report": report, "protocol": protocol,
            "files": report["files"], "entities": all_entities, "relations": expected_pair["relations"],
            "arms": expected_pair["arms"], "supervision": frozen["supervision"],
            "candidates": frozen["candidates"], "split": frozen["split"], "coverage": coverage}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()
    if bool(args.out) == bool(args.validate):
        parser.error("Choose exactly one of --out or --validate.")
    result = validate_prepared_packet(args.validate)["report"] if args.validate else prepare(args.out)
    print(json.dumps({"status": result["status"], "fully_frozen": result["fully_frozen"], "counts": result["counts"]}, indent=2))
