"""Explicit, read-only export of the optional native GO and saved QC packet.

The ordinary saved-workspace ZIP deliberately keeps its existing inventory.
This separate attachment reuses the selected-claim/source-frame inspector and
copies its twelve fixed source files unchanged; it is not a new scientific
validator or a general browser-selected file exporter.
"""
import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from . import gold_packet, go_context_inspection, go_context_qc
from .client import canonical, digest


FORMAT = "biograph-steward.native-go-portable-export.v1"
ROOT = "native_go_context_qc"
SOURCE_FILES = frozenset(
    {"context/" + name for name in go_context_inspection.FILES | {go_context_inspection.REPORT}}
    | {"qc/" + name for name in go_context_qc.FILES | {"report.json"}})

README = """Native GO source context and saved quality checks

This separate packet contains the full supplied native GO/QC source packet:
twelve unchanged files, their byte inventory in manifest.json, and this guide.
It includes the preserved GAF's broader source scope, not only the selected
claim's displayed rows. The selection binds eligibility, not a row filter.
It does not contain the saved
workspace, graph, question, application code, ontology or reasoner/runtime
dependencies, and is not a complete backup. Obtain the matching complete
workspace separately and use application code supporting native GO inspection.

Extract this ZIP OUTSIDE the strict saved workspace, with context/ and qc/
remaining separate. Do not add files inside either of those two directories.
For example, after extraction set these operator-controlled absolute paths:

export BIOGRAPH_GO_CONTEXT_DIR=/absolute/path/native_go_context_qc/context
export BIOGRAPH_GO_QC_DIR=/absolute/path/native_go_context_qc/qc

Then start the application normally with those environment variables, for
example: python3 app.py serve --runs-dir /absolute/path/runs --host 127.0.0.1
Open the matching workspace, select an existing GO claim in Evidence & sources,
and choose Inspect preserved native GO annotations. The source/graph/frame
binding must pass; this packet does not enable other unmatched workspaces.
Unset the two variables to disable it. Python/CPU is sufficient; no Brev model,
GPU, source retrieval, parser, GO rule or reasoner rerun is needed for inspection.

The original GAF headers, references, provenance, QC output and source policies
are preserved. Original producer receipts can contain original operator paths;
the consumer does not follow those paths. A private download is not clearance
to redistribute upstream data. The project's MIT code license does not
relicense source content: retain attribution and consult the upstream source
terms before sharing. This packet makes no blanket source-license assertion.

Hashes detect changed bytes relative to this manifest; they do not authenticate
the publisher or establish biological correctness. Current graph, original
baseline, context-report content seals and file-byte hashes are separate
bindings. Exact five-field compatibility does not establish historical source
row identity. Native NOT qualifiers, isoforms and context belong to their own
versioned source rows. Saved normalization and context/taxon findings do not
repair or prune a historical graph claim. No independent biological accuracy,
absence, prediction gain, new labels or automatic biological pruning is implied.
"""


def _need(value, message):
    if not value:
        raise ValueError("Native GO export: " + message)


def _inventory(context, qc):
    """Only the existing two fixed source inventories can enter an archive."""
    paths = {}
    for label, folder, names, directories in (
            ("context", context, go_context_inspection.FILES | {go_context_inspection.REPORT}, {"source"}),
            ("qc", qc, go_context_qc.FILES | {"report.json"}, set())):
        _need(folder.is_dir() and not folder.is_symlink(), "ordinary configured source directories required.")
        found = list(folder.rglob("*"))
        _need(not any(path.is_symlink() for path in found)
              and {path.relative_to(folder).as_posix() for path in found if path.is_file()} == names
              and {path.relative_to(folder).as_posix() for path in found if path.is_dir()} == directories
              and all(path.is_file() or path.is_dir() for path in found), "source inventory differs.")
        paths.update({label + "/" + name: folder / name for name in names})
    _need(set(paths) == SOURCE_FILES and len(paths) == 12, "twelve fixed source files required.")
    return paths


def _zip_info(name):
    info = ZipInfo(ROOT + "/" + name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_go_context_archive(context, qc, graph, selection_id, *, source_run, source_folder=None):
    """Build one separate in-memory ZIP after exact saved-claim/frame validation.

    Paths come only from operator configuration, never the browser. Both
    packets are required; nothing is written to the source or a scratch area.
    Every copied byte is checked again while packing, before any response is
    returned. The result's ``content`` is a binary attachment, not JSON.
    """
    _need(context is not None and qc is not None, "both native context and saved QC must be configured.")
    context, qc = Path(context).absolute(), Path(qc).absolute()
    paths = _inventory(context, qc)
    report_bytes = {name: paths[name].read_bytes() for name in
                    ("context/" + go_context_inspection.REPORT, "qc/report.json")}
    selection = go_context_inspection.inspect_go_selection(
        context, graph, selection_id, source_run=source_run, source_folder=source_folder, qc=qc)
    report = gold_packet._decode(report_bytes["context/" + go_context_inspection.REPORT])
    quality = gold_packet._decode(report_bytes["qc/report.json"])
    _need(gold_packet._sealed(report) and gold_packet._sealed(quality)
          and report["content_sha256"] == selection["context_report_content_sha256"]
          and selection["quality_control"]["status"] == "verified_saved_output"
          and quality["content_sha256"] == selection["quality_control"]["report_content_sha256"]
          and hashlib.sha256(report_bytes["qc/report.json"]).hexdigest()
              == selection["quality_control"]["report_file_sha256"], "validated source report changed.")
    pins = {"context/" + name: value for name, value in report["files"].items()}
    pins.update({"qc/" + name: value for name, value in quality["files"].items()})
    pins.update({name: hashlib.sha256(value).hexdigest() for name, value in report_bytes.items()})
    _need(set(pins) == SOURCE_FILES, "validated source-file pins differ.")
    source_files = {}
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=1) as archive:
        for name in sorted(SOURCE_FILES):
            path = paths[name]
            _need(path.is_file() and not path.is_symlink(), "source path changed while packing.")
            checksum, size = hashlib.sha256(), 0
            with path.open("rb") as source, archive.open(_zip_info(name), "w") as target:
                while chunk := source.read(1024 * 1024):
                    checksum.update(chunk)
                    size += len(chunk)
                    target.write(chunk)
            _need(checksum.hexdigest() == pins[name], "source bytes changed while packing: " + name)
            source_files[name] = {"bytes": size, "sha256": pins[name]}
        _inventory(context, qc)
        manifest = {"format": FORMAT, "source_files": source_files,
            "source_file_count": 12, "source_bytes": sum(row["bytes"] for row in source_files.values()),
            "source_run": source_run, "selection_id": selection_id, "query": selection["query"],
            "selected_inspection_content_sha256": selection["content_sha256"],
            "current_graph_sha256": digest(graph), "snapshot_sha256": report["snapshot_sha256"],
            "original_packet_id": report["packet_id"], "original_graph_sha256": report["graph_sha256"],
            "original_graph_file_sha256": report["source_graph_file_sha256"],
            "context_report_content_sha256": report["content_sha256"],
            "qc_report_content_sha256": quality["content_sha256"],
            "read_only": True, "ordinary_workspace_export_changed": False,
            "selection_is_eligibility_check_not_source_row_filter": True,
            "source_bytes_changed": False, "source_graph_mutated": False,
            "parser_rules_or_reasoner_reexecuted": False,
            "historical_record_identity_established": False,
            "independent_biological_accuracy_established": False,
            "public_redistribution_rights_asserted": False, "model_calls": 0, "source_fetches": 0,
            "scope_note": "Separate native GO context and saved QC only; matching workspace and current application required. Preserve upstream attribution and permissions; hashes do not establish source identity or biological truth."}
        manifest["content_sha256"] = digest(manifest)
        archive.writestr(_zip_info("manifest.json"), canonical(manifest) + "\n")
        archive.writestr(_zip_info("README.txt"), README)
    content = buffer.getvalue()
    return {"content": content, "filename": "native_go_context_qc_" + report["snapshot_sha256"][:12] + ".zip",
            "manifest": manifest, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
