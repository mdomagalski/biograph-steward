"""Read-only application use of an existing Gold disposition package.

The established Gold loader verifies the original packet and reapplies every
declared decision. This consumer does not independently adjudicate decisions.
Source snapshots and review states remain in the preserved original packet.
"""
from copy import deepcopy
from pathlib import Path
import argparse
from functools import lru_cache
import json
import shutil
import stat
import threading

from .client import digest, utcnow, write_json
from .file_utils import new_output, sha
from . import gold_packet

FORMAT = "biograph-steward.qualified-workspace.v1"
MARKER = "qualified_workspace.json"
PACKAGE = "source_retained_package"
HISTORY = "pathway_history"
# Only source-reader/reprojection helpers participate. UI/web routes and
# unrelated research code cannot silently change a verified reader result.
_READER_HELPERS = (
    'qualified_workspace', 'gold_packet', 'client', 'file_utils', 'assertions',
    'graph', 'normalization', 'context', 'civic', 'civic_context', 'benchmark',
    'questions', 'wiki_history', 'human_gene_relation', 'cohort_mapping',
    'assay_attachment', 'lambourne_evidence', 'intact_evidence',
    'intact_publication', 'intact_final_publication', 'evidence_extension',
    'mapit_source', 'signor_source', 'string_source_update', 'bioplex_source',
    'construction', 'construction_planning', 'refresh', 'refresh_workflow',
    'guided_construction', 'retrieval', 'string_component', 'literature',
)
_CACHE_LOCK = threading.Lock()
_CACHE_KEY = None


def _need(ok, message):
    if not ok:
        raise ValueError("Qualified workspace: " + message)


def _summary(report, graph):
    return {"format": FORMAT, "read_only": True,
        "packet_id": report["packet_id"], "retained_graph_sha256": report["retained_graph_sha256"],
        "disposition_report_content_sha256": report["content_sha256"],
        "method": deepcopy(report["method"]),
        "retained_evidence_edges": len(graph["edges"]),
        "baseline_evidence_edges": sum(report["counts"].values()),
        "decision_replay_verified": True, "independent_scientific_accuracy_established": False,
        "interpretation": "Declared keep/prune/abstain decisions replayed against their preserved source. "
            "Abstentions stay in the graph. Review carry-forward follows the saved Gold policy; nothing is promoted to accepted."}


def _app_graph(report, retained, baseline, history_binding=None):
    from .questions import graph_basis
    # The Gold retained exchange deliberately omits app cohort/retrieval
    # metadata. Restore that verified metadata, then replace every retained
    # evidence collection from the Gold replay. Never rebuild from snapshot.
    graph = deepcopy(baseline)
    for key in ('nodes', 'edges', 'assertions', 'context_records', 'quarantine',
                'assertion_changes', 'assertion_summary'):
        graph[key] = deepcopy(retained[key])
    for key in ('assay_observations', 'extension_observations'):
        if key in retained:
            graph[key] = deepcopy(retained[key])
    graph['summary'] = {**deepcopy(baseline['summary']), **deepcopy(retained['summary'])}
    graph['summary']['passed_structural_checks'] = sum(e['status'] == 'passed_structural_checks' for e in retained['edges'])
    graph['summary']['needs_review'] = sum(e['status'] == 'needs_review' for e in retained['edges'])
    from collections import Counter
    graph['summary']['assertions_by_kind'] = dict(Counter(a['kind'] for a in retained['assertions']))
    graph['interpretation'] = retained['interpretation']
    graph['warnings'] = [*graph.get('warnings', []),
        'Read-only retained workspace: retrieval and source-normalization coverage describe the preserved baseline; '
        'the retained edge and assertion counts describe the current decision view.']
    from .benchmark import audit_graph
    graph['benchmark_readiness'] = audit_graph(graph)
    graph["qualified_view"] = _summary(report, retained)
    if history_binding is not None:
        graph["qualified_view"]["pathway_history"] = deepcopy(history_binding)
        graph["qualified_view"]["source_support_default"] = 'native_supported'
    graph["question_basis_sha256"] = graph_basis(graph)
    return graph


def _load_workspace_uncached(folder):
    """Replay a published retained workspace; no source fetches or inference."""
    folder = Path(folder)
    _need(folder.is_dir() and not folder.is_symlink()
          and not any(p.is_symlink() for p in folder.rglob("*")), "ordinary nonsymlink files are required.")
    receipt = gold_packet._read(folder / MARKER)
    _need(gold_packet._sealed(receipt) and receipt.get("format") == FORMAT,
          "publication seal or format differs.")
    _need(all(receipt.get(k) is False for k in ('source_graph_mutated', 'review_states_promoted',
              'independent_scientific_accuracy_established'))
          and all(type(receipt.get(k)) is int and receipt[k] == 0 for k in ('model_calls', 'source_fetches')),
          "publication interpretation policy differs.")
    history_binding = receipt.get('pathway_history')
    expected = {MARKER, PACKAGE, "run_manifest.json", "graph.json", "snapshot.json"}
    if history_binding is not None:
        expected.add(HISTORY)
    _need(set(p.name for p in folder.iterdir()) == expected,
          "publication file inventory differs.")
    report, retained = gold_packet.load_decisions(folder / PACKAGE)
    _need(receipt["source_report_sha256"] == sha(folder / PACKAGE / "report.json")
          and receipt["source_report_content_sha256"] == report["content_sha256"],
          "source disposition report differs.")
    baseline = gold_packet._read(folder / PACKAGE / "baseline_packet/source/graph.json")
    if history_binding is not None:
        from .wiki_history import load_history_packet
        packet = load_history_packet(folder/HISTORY, expected_content_sha256=history_binding['content_sha256'])
        _need(sha(folder/HISTORY/'historical_verification.json') == history_binding['report_file_sha256']
              and packet['report']['source_graph_file_sha256'] == sha(folder/PACKAGE/'baseline_packet/source/graph.json'),
              'historical pathway proof belongs to different source bytes.')
    graph = _app_graph(report, retained, baseline, history_binding)
    snapshot = gold_packet._read(folder / PACKAGE / "baseline_packet/source/snapshot.json")
    manifest = {"starter_version": receipt["starter_version"], "run_mode": "qualified_workspace",
        "created_at": receipt["created_at"], "data_kind": graph["data_kind"], "graph_format": graph["graph_format"],
        "snapshot_sha256": graph["snapshot_sha256"], "qualified_workspace_sha256": receipt["content_sha256"]}
    _need(gold_packet._read(folder / "snapshot.json") == snapshot
          and gold_packet._read(folder / "graph.json") == graph
          and gold_packet._read(folder / "run_manifest.json") == manifest,
          "application graph, snapshot or manifest does not replay from the retained package.")
    return snapshot, graph.get("review_events", []), graph


def _reader_code_pins():
    """Full helper bytes, plus replaced in-process reader entry points."""
    root = Path(__file__).resolve().parent
    pins = []
    for name in _READER_HELPERS:
        path = root / (name + '.py')
        _need(path.is_file() and not path.is_symlink(), 'source-reader helper is missing or symlinked.')
        pins.append((name, sha(path)))
    pins.extend((name, id(value)) for name, value in (
        ('uncached_loader', _load_workspace_uncached), ('app_graph', _app_graph),
        ('Gold_load_decisions', gold_packet.load_decisions), ('Gold_load_packet', gold_packet.load_packet)))
    return tuple(pins)


def _workspace_fingerprint(folder):
    """Read every byte and inventory every ordinary file/directory on each hit.

    No timestamp is trusted. A changed/resealed file, added file, missing file,
    changed helper or symlink cannot reuse a prior validation result.
    """
    _need(folder.is_dir() and not folder.is_symlink(), 'ordinary workspace directory is required.')
    rows = []
    for path in sorted(folder.rglob('*')):
        mode = path.lstat().st_mode
        relative = path.relative_to(folder).as_posix()
        if stat.S_ISDIR(mode):
            rows.append((relative, 'directory'))
        elif stat.S_ISREG(mode):
            rows.append((relative, 'file', path.stat().st_size, sha(path)))
        else:
            raise ValueError('Qualified workspace: sources must contain only ordinary files and directories, without symlinks.')
    return tuple(rows), _reader_code_pins()


@lru_cache(maxsize=1)
def _cached_full_load(folder, fingerprint):
    # The key is intentionally the complete content/code fingerprint. The
    # original full semantic replay remains unchanged on each cold miss.
    return _load_workspace_uncached(Path(folder))


def load_workspace(folder):
    """Reuse a full replay only while every source byte/code binding is equal.

    A single lock bounds cold-load memory and prevents duplicate concurrent
    misses. The internal graph is never exposed: each caller gets a deepcopy.
    Complete file/directory/code fingerprints are checked before and after the
    read/copy. Failures clear the cache and never fall back to stale data.
    """
    global _CACHE_KEY
    folder = Path(folder)
    with _CACHE_LOCK:
        try:
            _need(folder.is_dir() and not folder.is_symlink(), 'ordinary workspace directory is required.')
            folder = folder.resolve()
            before = _workspace_fingerprint(folder)
            key = (str(folder), before)
            if _CACHE_KEY != key:
                # Evict the old parsed graph before allocating another one.
                _cached_full_load.cache_clear()
                _CACHE_KEY = None
            result = deepcopy(_cached_full_load(str(folder), before))
            _need(_workspace_fingerprint(folder) == before, 'source bytes, inventory or reader code changed during the request.')
            _CACHE_KEY = key
            return result
        except Exception:
            _cached_full_load.cache_clear()
            _CACHE_KEY = None
            raise


def publish_workspace(retained, output, *, history=None, history_content_sha256=None):
    """Publish a portable copy of a verified retained package for app queries."""
    from . import __version__
    from . import questions, gold_packet as gold_module
    _need((history is None) == (history_content_sha256 is None), 'supply both the history packet and its explicit content pin.')
    implementation = {p.name: sha(p) for p in map(Path, (__file__, questions.__file__, gold_module.__file__))}
    source = Path(retained)
    history_binding = None
    if history is not None:
        from .wiki_history import load_history_packet
        packet = load_history_packet(history, expected_content_sha256=history_content_sha256)
        _need(packet['report']['source_graph_file_sha256'] == sha(source/'baseline_packet/source/graph.json'),
              'historical packet belongs to different source graph bytes.')
        history_binding = {'content_sha256': packet['report']['content_sha256'],
            'report_file_sha256': sha(Path(history)/'historical_verification.json'),
            'schema_validation': 'byte-bound producer receipt; not reexecuted by the core consumer',
            'counts': deepcopy(packet['report']['counts'])}
    report, graph = gold_packet.load_decisions(source)
    output = new_output(output, source, *([history] if history is not None else []))
    shutil.copytree(source, output / PACKAGE)
    if history is not None:
        shutil.copytree(history, output/HISTORY)
    copied_report, copied = gold_packet.load_decisions(output / PACKAGE)
    _need(copied == graph and copied_report == report, "source changed during publication.")
    receipt = {"format": FORMAT, "starter_version": __version__, "created_at": utcnow(),
        "source_report_sha256": sha(output / PACKAGE / "report.json"),
        "source_report_content_sha256": report["content_sha256"],
        "source_graph_mutated": False, "review_states_promoted": False,
        "independent_scientific_accuracy_established": False, "model_calls": 0, "source_fetches": 0,
        "producer_implementation_sha256": implementation}
    if history_binding is not None:
        receipt['pathway_history'] = history_binding
    receipt["content_sha256"] = digest(receipt)
    baseline = gold_packet._read(output / PACKAGE / "baseline_packet/source/graph.json")
    published = _app_graph(report, graph, baseline, history_binding)
    snapshot = gold_packet._read(output / PACKAGE / "baseline_packet/source/snapshot.json")
    write_json(output / "snapshot.json", snapshot)
    write_json(output / "graph.json", published)
    write_json(output / "run_manifest.json", {"starter_version": __version__, "run_mode": "qualified_workspace",
        "created_at": receipt["created_at"], "data_kind": published["data_kind"], "graph_format": published["graph_format"],
        "snapshot_sha256": graph["snapshot_sha256"], "qualified_workspace_sha256": receipt["content_sha256"]})
    write_json(output / MARKER, receipt)
    try:
        load_workspace(output)
        _need(implementation == {p.name: sha(p) for p in map(Path,
            (__file__, questions.__file__, gold_module.__file__))}, 'implementation changed during publication.')
    except Exception:
        (output / MARKER).unlink(missing_ok=True)
        raise
    return receipt


def read_pathway_history(source, graph):
    """Load only the history explicitly bound to this verified workspace."""
    binding = graph.get('qualified_view', {}).get('pathway_history')
    if binding is None:
        return None
    from .wiki_history import load_history_packet
    return load_history_packet(Path(source)/HISTORY, expected_content_sha256=binding['content_sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retained", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument('--history')
    parser.add_argument('--history-content-sha256')
    args = parser.parse_args()
    print(json.dumps(publish_workspace(args.retained, args.out, history=args.history,
        history_content_sha256=args.history_content_sha256), indent=2))


if __name__ == "__main__":
    main()
