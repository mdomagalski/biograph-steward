#!/usr/bin/env python3
"""Optional source-reported membership projection onto exact version URLs.

The source's WikiPathways URL is used verbatim. No URI identity conversion,
revision collapse, native-content verification or scientific truth is inferred.
This JSONL exchange view is separate from the app and standard-export profile.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha

FORMAT = "biograph-steward.exact-version-wikipathways-projection.v1"
PROFILE = "source-reported-exact-version-WikiPathways-URL.v1"
MANIFEST = "projection_manifest.json"
ROWS = ("nodes", "edges", "edge_mapping", "node_mapping", "assertion_mapping", "resource_mapping")
VERSION = re.compile(r"(WP[1-9][0-9]*)_r([1-9][0-9]*)\Z")
BOUNDARIES = {"source_graph_changed": False, "review_states_changed": False, "duplicate_triples_merged": False,
    "native_version_content_verified": False, "scientific_accuracy_measured": False,
    "standards_validation_executed": False, "full_standard_conformance_claimed": False,
    "new_protein_interactions_inferred": False, "downstream_utility_tested": False,
    "model_calls": 0, "source_fetches": 0}
LIMITS = [
    "Memberships are reported by the preserved source, not independently validated biology.",
    "A version-labelled source URL does not verify retrieval or content of that historical model; public links may redirect to current content.",
    "Different revisions and unversioned identifiers are never collapsed.",
    "Repeated triples keep distinct original evidence IDs and are not independent experiments.",
    "Excluded records remain in the complete preserved source; exclusion is not pruning or a biological negative.",
    "Shared pathway context is not a new protein interaction; downstream utility remains untested.",
    "Membership stays directed protein-to-pathway; A-to-version-from-B is shared context, not a new directed protein-to-protein path.",
    "No KGX validator, Biolink conformance or new identifier identity mapping is claimed.",
]


from biograph_steward.wiki_projection import need, version_url, project_graph
from biograph_steward import wiki_projection


def _inventory(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and p != folder / MANIFEST}


def _verify_rows(folder, replay):
    for name in ROWS:
        actual = [gold_packet._decode(line) for line in (folder / (name + ".jsonl")).read_bytes().splitlines()]
        need(actual == replay[name], "projection does not replay: " + name)


def export_projection(retained, output, *, retained_report_sha256):
    implementation_pin = sha(Path(__file__))
    core_pin = sha(wiki_projection.__file__)
    retained = Path(retained).absolute()
    need(re.fullmatch(r"[0-9a-f]{64}", retained_report_sha256 or "")
         and sha(retained / "report.json") == retained_report_sha256, "retained report differs from the explicit pin.")
    source_report, graph = gold_packet.load_decisions(retained)
    projection = project_graph(graph)
    folder = new_output(output, retained)
    copied = folder / "source_retained_package"
    shutil.copytree(retained, copied)
    copied_report, copied_graph = gold_packet.load_decisions(copied)
    need(copied_report == source_report and copied_graph == graph
         and sha(copied / "report.json") == retained_report_sha256, "preserved retained package differs.")
    for name in ROWS:
        gold_packet._jsonl(folder / (name + ".jsonl"), projection[name])
    need(gold_packet.load_decisions(retained)[0] == source_report
         and sha(retained / "report.json") == retained_report_sha256, "source changed during projection export.")
    need(gold_packet.load_decisions(copied)[0] == source_report, "preserved source changed during export.")
    _verify_rows(folder, projection)
    need(sha(Path(__file__)) == implementation_pin, "implementation changed during projection export.")
    need(sha(wiki_projection.__file__) == core_pin, "shared projection implementation changed during export.")
    report = {"format": FORMAT, "profile": PROFILE, "created_at": utcnow(),
        "source_retained_report_sha256": retained_report_sha256,
        "source_retained_report_content_sha256": source_report["content_sha256"],
        "source_retained_graph_sha256": source_report["retained_graph_sha256"],
        "source_packet_id": source_report["packet_id"], "counts": projection["counts"],
        **BOUNDARIES, "limits": LIMITS,
        "implementation_sha256": implementation_pin, "projection_core_sha256": core_pin, "files": _inventory(folder)}
    report["content_sha256"] = digest(report)
    write_json(folder / MANIFEST, report)
    try:
        verify_projection(folder)
    except Exception:
        (folder / MANIFEST).unlink(missing_ok=True)
        raise
    return report


def verify_projection(folder):
    folder = Path(folder)
    need(folder.is_dir() and not folder.is_symlink() and not any(p.is_symlink() for p in folder.rglob("*")),
         "projection must contain ordinary files/directories.")
    report = gold_packet._read(folder / MANIFEST)
    need(gold_packet._sealed(report) and report.get("format") == FORMAT and report.get("profile") == PROFILE,
         "projection identity or seal differs.")
    need(all(type(report.get(k)) is type(v) and report[k] == v for k, v in BOUNDARIES.items())
         and report.get("limits") == LIMITS, "projection interpretation boundary differs.")
    need(report.get("files") == _inventory(folder), "projection file inventory or bytes changed.")
    source_report, graph = gold_packet.load_decisions(folder / "source_retained_package")
    need(sha(folder / "source_retained_package/report.json") == report["source_retained_report_sha256"]
         and source_report["content_sha256"] == report["source_retained_report_content_sha256"]
         and source_report["retained_graph_sha256"] == report["source_retained_graph_sha256"]
         and source_report["packet_id"] == report["source_packet_id"], "preserved source binding differs.")
    replay = project_graph(graph)
    need(replay["counts"] == report["counts"], "projection counts do not replay.")
    _verify_rows(folder, replay)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    build = modes.add_parser("export")
    build.add_argument("--retained", type=Path, required=True)
    build.add_argument("--retained-report-sha256", required=True)
    build.add_argument("--out", type=Path, required=True)
    check = modes.add_parser("verify")
    check.add_argument("--projection", type=Path, required=True)
    args = parser.parse_args()
    report = (export_projection(args.retained, args.out, retained_report_sha256=args.retained_report_sha256)
              if args.mode == "export" else verify_projection(args.projection))
    print(report["content_sha256"])


if __name__ == "__main__":
    main()
