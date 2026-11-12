"""Compose explicit, source-preserving biological additions to a saved run.

Source adapters replay their own publications. This hook handles the ordinary
workspace lifecycle; it does not harmonize scores or infer scientific truth.
The original assay attachment contract and its cohort bounds stay unchanged.
"""
from copy import deepcopy
import importlib
from pathlib import Path
import shutil
import tempfile

from .client import digest
from .assay_attachment import _decode, _ordinary, _sealed

FORMAT = "biograph-steward.evidence-extension.v1"
SIDECAR = "evidence_extension.json"
SOURCE = "extension_sources"
LEDGER = "extension_observations.json"
ADAPTERS = {"string": "string_source_update", "mapit": "mapit_source", "signor": "signor_source",
            "bioplex": "bioplex_source"}


def _adapter(kind):
    if kind not in ADAPTERS:
        raise ValueError("Unsupported biological extension source.")
    return importlib.import_module("." + ADAPTERS[kind], __package__)


def prepare_extension(snapshot, baseline_graph, publications):
    if (not isinstance(publications, dict) or not publications
            or set(publications) - set(ADAPTERS)):
        raise ValueError("Supply one or more supported source publications.")
    sources, licenses = {}, []
    for kind, folder in sorted(publications.items()):
        adapter = _adapter(kind)
        manifest, projection, _ = adapter.load_publication(folder)
        prepared = adapter.prepare(snapshot, baseline_graph, manifest, projection)
        if (not isinstance(prepared, dict) or set(prepared) != {"nodes", "edges", "observations", "summary"}
                or any(not isinstance(prepared[k], list) for k in ("nodes", "edges", "observations"))
                or not isinstance(prepared["summary"], dict)):
            raise ValueError("Source adapter returned an unsupported addition.")
        license_ = manifest.get("source_license")
        if not isinstance(license_, dict):
            raise ValueError("A biological publication requires its original source license.")
        licenses.append(deepcopy(license_))
        sources[kind] = {"publication_sha256": manifest["content_sha256"],
                         "projection_sha256": digest(projection), "prepared": prepared}
    summary = {"sources": {k: deepcopy(v["prepared"]["summary"]) for k, v in sources.items()},
               "added_source_edges": sum(len(v["prepared"]["edges"]) for v in sources.values()),
               "added_nodes": sum(len(v["prepared"]["nodes"]) for v in sources.values()),
               "preserves_original_pharos": True, "automatic_acceptance": False,
               "independent_validation": False,
               "interpretation": ("Source-preserving biological records and cell-model context; source records are not independent experiment counts."
                                  if "bioplex" in publications else
                                  "Versioned associations, qualified tissue observations and source-reported regulation; source records are not independent experiment counts."
                                  if "signor" in publications else
                                  "Versioned source associations and qualified tissue observations; source records are not independent experiment counts.")}
    value = {"format": FORMAT, "snapshot_sha256": snapshot["content_sha256"],
             "sources": sources, "summary": summary, "source_licenses": licenses}
    value["content_sha256"] = digest(value)
    return value


def validate_extension(snapshot, extension):
    if (not _sealed(extension) or extension.get("format") != FORMAT
            or extension.get("snapshot_sha256") != snapshot["content_sha256"]
            or not isinstance(extension.get("sources"), dict) or not extension["sources"]
            or set(extension["sources"]) - set(ADAPTERS)):
        raise ValueError("Biological extension snapshot or content binding changed.")
    return extension


def apply_extension(snapshot, nodes, edges, extension):
    """Add checked source records before ordinary assertion/review construction."""
    validate_extension(snapshot, extension)
    for kind, source in sorted(extension["sources"].items()):
        prepared = source["prepared"]
        for node in prepared["nodes"]:
            if node["id"] in nodes or node.get("category") != "biolink:Protein":
                raise ValueError("Source extension conflicts with an existing protein record.")
            nodes[node["id"]] = deepcopy(node)
        for edge in prepared["edges"]:
            if (edge["id"] in edges or any(edge[k] not in nodes for k in ("subject", "object"))
                    or edge.get("snapshot_sha256") != snapshot["content_sha256"]
                    or edge.get("biologically_validated") is not False
                    or edge.get("extension_source_kind") != kind
                    or edge.get("extension_publication_sha256") != source["publication_sha256"]):
                raise ValueError("Source edge conflicts with its preserved workspace or participants.")
            expected = {"string": "protein_interaction", "mapit": "tissue_proximity_observation",
                        "signor": "source_regulatory_observation"}[kind]
            if edge.get("record_kind") != expected:
                raise ValueError("Source association and tissue observations must retain their distinct meanings.")
            edges[edge["id"]] = deepcopy(edge)


def source_material(snapshot, extension, folder, civic=None, assay=None, baseline_graph=None):
    """Verify complete adapter reprojection before returning preserved bytes."""
    from .graph import build_graph
    folder = Path(folder)
    validate_extension(snapshot, extension)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Biological sources require an ordinary directory.")
    if {p.name for p in folder.iterdir()} != set(extension["sources"]):
        raise ValueError("Preserved extension source inventory differs.")
    publications = {k: folder / k for k in extension["sources"]}
    baseline = (baseline_graph if baseline_graph is not None else
                build_graph(snapshot, civic_snapshot=civic, assay_attachment=assay))
    if prepare_extension(snapshot, baseline, publications) != extension:
        raise ValueError("Biological additions do not reproduce from their complete sources.")
    files = {}
    for kind, publication in sorted(publications.items()):
        _, _, material = _adapter(kind).load_publication(publication)
        files.update({kind + "/" + name: raw for name, raw in material.items()})
    return files


def read_extension(run, snapshot=None, civic=None, assay=None, baseline_graph=None):
    run = Path(run)
    sidecar, folder = run / SIDECAR, run / SOURCE
    if not sidecar.exists() and not sidecar.is_symlink():
        if folder.exists() or folder.is_symlink() or (run / LEDGER).exists():
            raise ValueError("Biological source material has no recorded extension.")
        return None
    snapshot = snapshot if snapshot is not None else _decode(_ordinary(run / "snapshot.json"))
    if civic is None and (run / "civic_snapshot.json").exists():
        civic = _decode(_ordinary(run / "civic_snapshot.json"))
    if assay is None:
        from .assay_attachment import read_assay
        assay = read_assay(run)
    value = _decode(_ordinary(sidecar))
    source_material(snapshot, value, folder, civic, assay, baseline_graph)
    return value


def publish_extension(run, publications, output):
    from .reviews import read_run, read_civic, read_assay, preserve_construction_plan
    from .graph import save_run
    run, output = Path(run).absolute(), Path(output).absolute()
    if (output.exists() or output.is_symlink() or run == output
            or run in output.parents or output in run.parents):
        raise ValueError("Choose a new output outside the unchanged source run.")
    snapshot, events, baseline = read_run(run)
    if read_extension(run, snapshot) is not None:
        raise ValueError("Compose the supported additions from the original source workspace.")
    extension = prepare_extension(snapshot, baseline, publications)
    import hashlib
    for kind, publication in publications.items():
        manifest, _, _ = _adapter(kind).load_publication(publication)
        for name, expected in manifest.get("baseline_source_files_sha256", {}).items():
            if name not in {"snapshot.json", "graph.json", "targets.tsv", "run_manifest.json"} or hashlib.sha256(_ordinary(run / name)).hexdigest() != expected:
                raise ValueError("Source publication belongs to a different saved baseline.")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".biological-update-", dir=output.parent))
    try:
        sources = stage / ".sources"
        sources.mkdir()
        for kind, publication in publications.items():
            _, _, material = _adapter(kind).load_publication(publication)
            for name, raw in material.items():
                path = sources / kind / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        # save_run requires an empty destination and validates before publication.
        destination = stage / "run"
        assay = read_assay(run)
        graph = save_run(snapshot, destination, run_mode="biological_extension", review_events=events,
                         civic_snapshot=read_civic(run), assay_attachment=assay,
                         assay_source=run / "assay_source" if assay else None,
                         evidence_extension=extension, extension_source=sources)
        # Preserve the original source snapshot byte-for-byte, including formatting.
        (destination / "snapshot.json").write_bytes(_ordinary(run / "snapshot.json"))
        preserve_construction_plan(run, destination)
        if read_run(destination)[2] != graph:
            raise ValueError("Extended workspace failed full ordinary source replay.")
        if output.exists():
            raise ValueError("Output appeared while publishing the biological update.")
        destination.rename(output)
        return graph
    finally:
        shutil.rmtree(stage, ignore_errors=True)
