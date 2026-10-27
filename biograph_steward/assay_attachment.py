"""Attach preserved assay observations to an exact Pharos protein cohort.

Intake checks saved bytes and reproduces the observation projection. It does
not rerun the historical assay assessment, authenticate its publisher, or turn
the consumed panel into independent validation data.
"""
from collections import Counter
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil
import tempfile

from .client import digest
from .lambourne_evidence import build_evidence

FORMAT = "biograph-steward.assay-attachment.v1"
PUBLICATION_FORMAT = "biograph-steward.lambourne-evidence-publication.v1"
SIDECAR = "assay_attachment.json"
SOURCE = "assay_source"
POLICY = "both_exact_resolved_cohort_endpoints.v1"
VERIFICATION = "preserved_file_integrity_and_observation_reprojection"


def _decode(raw):
    from .gold_packet import _decode as strict_decode
    return strict_decode(raw)


def _ordinary(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError("Assay sources require ordinary files without symlink traversal.")
    return path.read_bytes()


def _sealed(value):
    return (isinstance(value, dict) and value.get("content_sha256") ==
            digest({k: v for k, v in value.items() if k != "content_sha256"}))


def _capture(folder, receipt_name):
    """Use the publisher's receipt/hash-inventory contract without code replay."""
    folder = Path(folder)
    if (any(p.is_symlink() for p in (folder, *folder.parents)) or not folder.is_dir()
            or any(p.is_symlink() for p in folder.rglob("*"))):
        raise ValueError("Assay publication must be an ordinary directory without symlinks.")
    receipt_bytes = _ordinary(folder / receipt_name)
    receipt = _decode(receipt_bytes)
    files = {p.relative_to(folder).as_posix(): _ordinary(p)
             for p in sorted(folder.rglob("*")) if p.is_file()
             and p.relative_to(folder).as_posix() != receipt_name}
    inventory = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}
    if not _sealed(receipt) or receipt.get("files") != inventory:
        raise ValueError("Assay publication receipt or saved file inventory changed.")
    return receipt, {receipt_name: receipt_bytes, **files}


def load_publication(publication):
    """Return manifest, reproduced evidence, and exact captured publication bytes.

Historical implementation pins are preserved, not compared to today's code.
Exact scientific replay uses the original checkpoint and its recorded runtime.
"""
    manifest, files = _capture(publication, "publication.json")
    from .intact_publication import FORMAT as INTACT_FORMAT, load_projection
    if manifest.get("format") == INTACT_FORMAT:
        return load_projection(manifest, files)
    from .intact_final_publication import FORMAT as FINAL_FORMAT, CONSUMED_FORMAT, load_projection as load_final
    if manifest.get("format") in {FINAL_FORMAT, CONSUMED_FORMAT}:
        return load_final(manifest, files)
    if (manifest.get("format") != PUBLICATION_FORMAT
            or not isinstance(manifest.get("implementation_sha256"), dict)
            or not manifest["implementation_sha256"]
            or any(manifest.get(k) is not False for k in
                   ("baseline_modified", "automatic_pruning", "independent_validation_performed",
                    "standard_conformance_claimed"))):
        raise ValueError("Unsupported assay publication or interpretation policy.")
    if not {"index.html", "source/freeze/source/LICENSE"} <= set(files):
        raise ValueError("Assay publication is missing its original source license or viewer.")
    try:
        protocol = _decode(files["source/freeze/protocol.json"])
        report = _decode(files["source/results/report.json"])
        audit = _decode(files["source/results/assay_audit.json"])
        for prefix, receipt, name in (("source/freeze/", protocol, "protocol.json"),
                                      ("source/results/", report, "report.json")):
            inventory = {key[len(prefix):]: hashlib.sha256(value).hexdigest()
                         for key, value in files.items() if key.startswith(prefix)
                         and key != prefix + name}
            if not _sealed(receipt) or receipt.get("files") != inventory:
                raise ValueError("Preserved assay assessment receipt or file inventory changed.")
        if report.get("protocol_sha256") != protocol["content_sha256"]:
            raise ValueError("Assay assessment is bound to a different frozen protocol.")
        source_hashes = audit["source_sha256"]
        for key, name in (("panel", "panel.tsv"), ("raw", "raw_human.tsv"), ("orf_map", "orf_map.tsv")):
            if source_hashes[key] != hashlib.sha256(files["source/freeze/source/" + name]).hexdigest():
                raise ValueError("Assay source-table hash does not match its audit.")
        bindings = {"protocol_sha256": protocol["content_sha256"],
                    "result_sha256": report["content_sha256"], "source_sha256": source_hashes,
                    "artifact_sha256": {"rows": report["files"]["rows.json"],
                        "lookup": protocol["files"]["lookup/pair_lookup.json"]}}
        evidence = build_evidence(_decode(files["source/results/rows.json"]),
                                  _decode(files["source/freeze/lookup/pair_lookup.json"]), bindings)
        if (evidence != _decode(files["evidence.json"])
                or evidence["graph"] != _decode(files["graph.json"])
                or evidence["bindings"] != manifest.get("bindings")
                or evidence["summary"] != manifest.get("summary")):
            raise ValueError("Saved assay observation projection does not reproduce from its preserved records.")
    except (KeyError, TypeError) as exc:
        raise ValueError("Assay publication is missing its complete source-bound observation records.") from exc
    return manifest, evidence, files


def _cohort(snapshot):
    scope = snapshot.get("scope") or {}
    requested = scope.get("requested_uniprot")
    if (snapshot.get("data_kind") != "live_pharos" or scope.get("kind") != "protein_cohort"
            or not isinstance(requested, list) or not 1 <= len(requested) <= 25
            or len(requested) != len(set(requested))):
        raise ValueError("Assay attachment requires an explicit live Pharos cohort of 1–25 exact proteins.")
    resolved = {"UniProtKB:" + row["uniprot"] for row in snapshot["targets"]}
    if not resolved <= {"UniProtKB:" + uid for uid in requested}:
        raise ValueError("Resolved assay attachment proteins must belong to the requested cohort.")
    return sorted(resolved)


def prepare_attachment(snapshot, manifest, evidence):
    cohort = _cohort(snapshot)
    selected = [deepcopy(o) for o in evidence["observations"] if set(o["products"]) <= set(cohort)]
    edge_ids = {o["graph_edge_id"] for o in selected if o["graph_edge_id"] is not None}
    edges = [deepcopy(e) for e in evidence["graph"]["edges"] if e["id"] in edge_ids]
    summary = {"publication_sha256": manifest["content_sha256"],
               "source_observations": len(evidence["observations"]),
               "selected_observations": len(selected), "eligible_observations": len(edges),
               "excluded_observations": sum(not o["evaluable"] for o in selected),
               "outside_cohort_observations": len(evidence["observations"]) - len(selected),
               "assay_status_counts": dict(sorted(Counter(o["assay_status"] for o in selected).items())),
               "selection_policy": POLICY, "verification": VERIFICATION,
               "source_locator_base": "assay_source/",
               "source_bindings": deepcopy(evidence["bindings"]),
               "historical_implementation_sha256": deepcopy(manifest["implementation_sha256"]),
               "historical_scientific_replay_performed": False,
               "automatic_acceptance_performed": False, "automatic_pruning_performed": False,
               "biological_validation_performed": False, "independent_evidence_count": None,
               "lookup_note": ("No Pharos match or novelty lookup is supplied by this IntAct attachment."
                               if evidence.get("source_kind") == "intact_mitab27" else
                               "Pharos match labels describe the original frozen comparison lookup, not a new lookup of this cohort."),
               "limitations": deepcopy(evidence["limitations"])}
    if evidence.get("source_kind") == "intact_mitab27":
        summary.update(source_kind="intact_mitab27", source_accounting=deepcopy(evidence["summary"]))
    value = {"format": FORMAT, "snapshot_sha256": snapshot["content_sha256"],
             "publication_sha256": manifest["content_sha256"],
             "publication_evidence_sha256": manifest["files"]["evidence.json"],
             "source_bindings": deepcopy(evidence["bindings"]), "cohort": cohort,
             "selection_policy": POLICY, "observations": selected, "edges": edges,
             "summary": summary,
             "source_license": {"source": "Lambourne et al. author publication",
                 "license_file": "assay_source/source/freeze/source/LICENSE",
                 "note": "The preserved author repository license covers its stated software/material scope; this attachment does not assign a new data license. Consult original paper and source terms before redistribution."}}
    if evidence.get("source_kind") == "intact_mitab27":
        value["source_license"] = deepcopy(evidence["source_license"])
    value["content_sha256"] = digest(value)
    return value


def validate_attachment(snapshot, attachment):
    if (not _sealed(attachment) or attachment.get("format") != FORMAT
            or attachment.get("snapshot_sha256") != snapshot["content_sha256"]
            or attachment.get("cohort") != _cohort(snapshot)
            or attachment.get("selection_policy") != POLICY):
        raise ValueError("Assay attachment source, cohort or content binding changed.")
    return attachment


def source_material(snapshot, attachment, publication):
    manifest, evidence, files = load_publication(publication)
    if prepare_attachment(snapshot, manifest, evidence) != attachment:
        raise ValueError("Assay sidecar differs from its preserved publication or cohort selection.")
    return files


def read_assay(source):
    source = Path(source)
    path, folder = source / SIDECAR, source / SOURCE
    if not path.exists() and not path.is_symlink():
        if folder.exists() or folder.is_symlink():
            raise ValueError("Assay publication is present without its attachment sidecar.")
        return None
    snapshot = _decode(_ordinary(source / "snapshot.json"))
    attachment = _decode(_ordinary(path))
    validate_attachment(snapshot, attachment)
    source_material(snapshot, attachment, folder)
    return attachment


def attach_assay(source, publication, output):
    """Publish a new ordinary workbench run; preserve both input directories."""
    from .reviews import read_run, read_civic, preserve_construction_plan
    from .graph import save_run
    source, publication, output = map(lambda p: Path(p).absolute(), (source, publication, output))
    if output.exists() or output.is_symlink() or any(
            output.resolve() == p.resolve() or p.resolve() in output.resolve().parents
            or output.resolve() in p.resolve().parents for p in (source, publication)):
        raise ValueError("Choose a new immutable assay run outside its input directories.")
    snapshot, events, _ = read_run(source)
    if read_assay(source) is not None:
        raise ValueError("This run already has an assay attachment. Select an unmodified Pharos cohort run.")
    manifest, evidence, _ = load_publication(publication)
    attachment = prepare_attachment(snapshot, manifest, evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".assay-run-", dir=output.parent))
    try:
        graph = save_run(snapshot, stage, run_mode="assay_attachment", review_events=events,
                         civic_snapshot=read_civic(source), assay_attachment=attachment,
                         assay_source=publication)
        preserve_construction_plan(source, stage)
        if read_run(stage)[2] != graph:
            raise ValueError("Attached assay run failed ordinary workbench replay.")
        if output.exists():
            raise ValueError("Assay run output appeared during publication.")
        stage.rename(output)
        return graph
    finally:
        if stage.exists():
            shutil.rmtree(stage)
