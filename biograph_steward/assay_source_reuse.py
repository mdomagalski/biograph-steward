"""Expose an existing provider trace without changing its assay workspace.

Identity semantics come from the existing PSI-MI/JAMI source reader and overlap
audit. This supplement records an observed aggregator source link; it neither
deduplicates biology nor estimates independence or confidence.
"""
from html import escape
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

from .assay_attachment import _decode, _ordinary, _sealed, read_assay, source_material
from .client import digest, write_json
from .evidence_overlap import _source_files, _xml_companions, _source_facts
from .file_utils import sha
from .questions import graph_basis
from .reviews import read_run

FORMAT = "biograph-steward.assay-source-reuse.v1"
TRACE_FORMAT = "biograph-steward.bounded-provider-pair-lineage.v1"
MARKERS = ("source_reuse.json", "source_reuse_records.jsonl", "source_reuse.html",
           "source_reuse_manifest.json", "source_reuse_source")
PROOF_FILES = {"trace_report.json": "report.json", "trace_ledger.jsonl": "record_reuse.jsonl",
               "trace_manifest.json": "manifest.json"}
IMPLEMENTATION = ("assay_source_reuse.py", "evidence_overlap.py", "assay_attachment.py",
                  "reviews.py", "questions.py", "file_utils.py")
LIMITATIONS = [
    "Current STRING source-link reuse and inclusion in the historical Pharos import are separate questions.",
    "The STRING source link was copied by the user; it is not an automated browser or API capture.",
    "An unobserved record remains unresolved; it is not evidence of absence or independence.",
    "Shared curated records do not quantify independent studies or experiments. Assay context remains useful.",
    "No graph, source observation, saved answer, review state, confidence or pruning decision is changed.",
    "This consumed development example does not measure scientific accuracy or biological improvement.",
]


def _require(condition, message):
    if not condition:
        raise ValueError("Source-reuse audit: " + message)


def _json(raw):
    value = _decode(raw)
    _require(isinstance(value, dict), "expected a JSON object.")
    return value


def _seal(value):
    return {**value, "content_sha256": digest(value)}


def _safe_name(name):
    _require(isinstance(name, str) and bool(name) and "\\" not in name
             and not PurePosixPath(name).is_absolute()
             and all(p not in {"", ".", ".."} for p in name.split("/")), "unsafe source filename.")
    return name


def _implementation():
    return {name: sha(Path(__file__).with_name(name)) for name in IMPLEMENTATION}


def _capture_trace(trace):
    trace = Path(trace).absolute()
    inventory = _source_files(trace)
    manifest = _json(_ordinary(trace / "manifest.json"))
    _require(_sealed(manifest) and manifest.get("format") == TRACE_FORMAT, "invalid trace manifest.")
    declared = manifest.get("files")
    _require(isinstance(declared, dict), "trace inventory is missing.")
    for name in declared:
        _safe_name(name)
    _require(inventory == {**declared, "manifest.json": sha(trace / "manifest.json")},
             "trace file inventory changed.")
    files = {dest: _ordinary(trace / name) for dest, name in PROOF_FILES.items()}
    report = _json(files["trace_report.json"])
    preparation = Path(report["input_directories"]["preparation"])
    for name in ("scope.json", "user_intact_record_link.json"):
        files[name] = _ordinary(preparation / name)
    return files


def _binding(graph):
    return {"graph_basis_sha256": graph_basis(graph), **{key: graph[key] for key in
        ("snapshot_sha256", "assay_attachment_sha256", "assay_publication_sha256")}}


def _analyze(source, files):
    """Replay the narrow source-link join using copied proof and verified sources."""
    snapshot, _, graph = read_run(source)
    attachment = read_assay(source)
    _require(attachment is not None, "a qualified assay workspace is required.")
    material = source_material(snapshot, attachment, source / "assay_source")
    report, manifest, scope, user = (_json(files[name]) for name in
        ("trace_report.json", "trace_manifest.json", "scope.json", "user_intact_record_link.json"))
    _require(_sealed(report) and report.get("format") == TRACE_FORMAT
             and _sealed(manifest) and manifest.get("format") == TRACE_FORMAT,
             "trace content seal or format changed.")
    import hashlib
    raw_sha = lambda raw: hashlib.sha256(raw).hexdigest()
    for dest, name in PROOF_FILES.items():
        if dest != "trace_manifest.json":
            _require(manifest["files"].get(name) == raw_sha(files[dest]), "copied trace file changed.")
    for name in ("scope.json", "user_intact_record_link.json"):
        _require(report["input_files_sha256"]["preparation"].get(name) == raw_sha(files[name]),
                 "copied preparation file changed.")
    _require(scope.get("format") == "biograph-steward.provider-pair-lineage-scope.v1"
             and scope.get("taxon") == report["scope"].get("taxon") == 9606
             and scope.get("pair") == report["scope"].get("pair"), "trace scope changed.")
    for name in ("snapshot.json", "assay_attachment.json", "assay_observations.json"):
        _require(scope["input_files_sha256"]["original_workspace"].get(name) == sha(source / name),
                 "trace belongs to a different saved source: " + name)
    provider = report["string"]
    _require(provider.get("source_release") == "12.5", "unsupported STRING trace release.")
    _require(report.get("verified_independent_evidence_count") is None
             and report.get("original_graph_modified") is False
             and report.get("scientific_accuracy_measured") is False
             and report.get("predictive_gain_measured") is False
             and report["historical_pharos"].get("current_provider_records_attested_as_original_inputs") is False,
             "trace makes unsupported historical or biological claims.")
    ledger = [_json(line) for line in files["trace_ledger.jsonl"].splitlines()]
    _require(ledger == report["original_overlap"]["observations"], "trace ledger and report differ.")
    observations = {row["id"]: row for row in graph["assay_observations"]}
    _require(len(ledger) == len(observations) and {row["id"] for row in ledger} == set(observations),
             "trace must identify every selected observation exactly once.")
    companions = _xml_companions(material)
    proof = provider["exact_intact_record_reuse_proof"]
    confirmed_id = proof.get("observation_id")
    _require(confirmed_id in observations and proof.get("status") == "confirmed_user_assisted_exact_curated_record"
             and proof.get("string_link_provenance") == user
             and proof.get("independent_additional_record_over_current_string") is False
             and proof.get("historical_pharos_record_inclusion_verified") is False
             and proof.get("source_experiment_identity_exposed_by_string_api") is False,
             "unsupported exact record proof.")
    accession = user.get("source_record_id")
    _require(isinstance(accession, str) and re.fullmatch(r"IM-[0-9]+-[0-9]+", accession)
             and user.get("source_namespace") == "imex"
             and user.get("source_record_curie") == proof.get("source_record_id") == "imex:" + accession
             and user.get("as_supplied") in {"ebi.ac.uk/intact/query/" + accession,
                                            "https://www.ebi.ac.uk/intact/query/" + accession,
                                            "https://ebi.ac.uk/intact/query/" + accession}
             and user.get("automated_string_api_exposes_this_record_link") is False,
             "user-assisted source link is not the proof's exact curated record.")
    output = []
    for row in ledger:
        observation = observations[row["id"]]
        facts = _source_facts(observation, companions)
        expected = "confirmed_user_assisted" if row["id"] == confirmed_id else "unknown_not_observed"
        _require(row.get("products") == observation.get("products") and row.get("study") == observation.get("study")
                 and row.get("current_string_curated_record_reuse") == expected
                 and row.get("original_pharos_import_reuse") is None
                 and sorted(row.get("record_ids", [])) == sorted(facts["record_identity_aliases"])
                 and sorted(row.get("experiment_ids", [])) == facts["experiment_ids"],
                 "observation source identities or reuse qualification differ.")
        if row["id"] == confirmed_id:
            _require(facts["xml_join_status"] == "one_captured_evidence_record"
                     and sorted(proof.get("identity_aliases", [])) == sorted(row["record_ids"])
                     and proof["source_record_id"] in row["record_ids"]
                     and sorted(proof.get("source_experiment_ids", [])) == facts["experiment_ids"]
                     and bool(facts["experiment_ids"])
                     and proof.get("publication") in facts["pmids"]
                     and set(observation["products"]) == {"UniProtKB:" + p for p in scope["pair"]},
                     "record proof does not match the typed source evidence.")
            matched = [c for c in companions if set(c["record_ids"]) & set(row["record_ids"])]
            _require(len(matched) == 1 and set(row["record_ids"]).issubset(matched[0]["record_ids"]),
                     "record aliases are not identity-qualified on one source object.")
            companion = matched[0]
            reader = proof["official_source_reader"]
            original_reader = Path(scope["input_directories"]["original_workspace"]) / "assay_source" / companion["file"]
            _require(Path(reader["file"]) == original_reader
                     and reader.get("sha256") == companion["file_sha256"]
                     and reader.get("line") == companion["line"]
                     and reader.get("source_xml_locator") == companion["record"].get("source_locator"),
                     "official reader locator changed.")
            for experiment in companion["record"].get("experiments", []):
                publication = experiment.get("publication") or {}
                pmids = {"PMID:" + ref["id"] for ref in publication.get("identifiers", [])
                    if (ref.get("database") or {}).get("name") == "pubmed"
                    and (ref.get("qualifier") or {}).get("mi_id") == "MI:0358"}
                _require(proof["publication"] in pmids
                         and (experiment.get("detection_method") or {}).get("mi_id")
                         == user.get("method_mi_id_from_existing_source"),
                         "source experiment publication or method differs from the observed link.")
        links = [{"label": record, "url": "https://www.ebi.ac.uk/intact/query/" + record.split(":", 1)[1]}
                 for record in row["record_ids"] if re.fullmatch(r"(?:imex:IM-[0-9]+-[0-9]+|intact:EBI-[0-9]+)", record)]
        output.append({"observation_id": row["id"], "products": row["products"], "study": row["study"],
            "current_string_status": expected, "provider": "STRING", "provider_version": "12.5",
            "record_ids": row["record_ids"], "historical_pharos_reuse": None,
            "observation_provenance": "user_assisted_source_link" if row["id"] == confirmed_id else "not_observed",
            "explanation": ("The user-copied STRING source link identifies this same IntAct/IMEx curated record. "
                "Its preserved typed source verifies the aliases; it is shared support, not an independent replication."
                if row["id"] == confirmed_id else "This record was not resolved in the observed, truncated STRING view. "
                "Current STRING reuse remains unknown; it is not classified as independent evidence."),
            "evidence_links": links})
    return _seal({"format": FORMAT, **_binding(graph), "observations": output,
        "trace_content_sha256": report["content_sha256"], "limitations": LIMITATIONS,
        "summary": {"selected_observations": len(output), "current_string_shared_user_assisted": 1,
                    "current_string_unresolved": len(output) - 1, "historical_pharos_unresolved": len(output),
                    "independent_evidence_count": None, "graph_modified": False}})


def _html(report):
    rows = "".join("<tr><td>" + escape(row["observation_id"]) + "<br>" + escape(" / ".join(row["record_ids"]))
        + "</td><td>" + escape("Shared record (user-assisted)" if row["current_string_status"] == "confirmed_user_assisted"
            else "Unresolved") + "</td><td>Unknown</td><td>" + escape(row["explanation"]) + "</td></tr>"
        for row in report["observations"])
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Source reuse audit</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><style>'
        'body{font:16px/1.5 system-ui;max-width:1100px;margin:3rem auto;padding:0 1rem;color:#172b36}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #b7c6cc;padding:1rem;text-align:left}'
        'td{overflow-wrap:anywhere}a{color:#006685}</style><h1>Source reuse audit</h1>'
        '<p>The assay workspace is preserved. This supplement distinguishes the current STRING 12.5 source trace '
        'from the historical Pharos import. It does not measure biological improvement.</p>'
        '<table><tr><th>Observation and source record</th><th>Current STRING 12.5</th>'
        '<th>Historical Pharos</th><th>Qualification</th></tr>' + rows + '</table><ul>'
        + ''.join('<li>' + escape(value) + '</li>' for value in report["limitations"]) + '</ul>'
        '<p>The downloaded workspace includes source_reuse.json, source_reuse_records.jsonl and '
        'source_reuse_source/ with the copied trace, scope and user-assisted source-link proof. '
        'Original trace paths are provenance labels; offline verification uses the copied proof and assay_source/.</p></html>')


def read_reuse(source):
    """Return a replay-verified supplement, or None for an unannotated run."""
    source = Path(source).absolute()
    if not any((source / name).exists() or (source / name).is_symlink() for name in MARKERS):
        return None
    inventory = _source_files(source)
    manifest = _json(_ordinary(source / "source_reuse_manifest.json"))
    _require(_sealed(manifest) and manifest.get("format") == FORMAT
             and manifest.get("implementation_sha256") == _implementation(), "manifest or implementation changed.")
    _require(inventory == {**manifest["workspace_files"], **manifest["supplement_files"],
                          "source_reuse_manifest.json": sha(source / "source_reuse_manifest.json")},
             "workspace or supplement inventory changed.")
    files = {name: _ordinary(source / "source_reuse_source" / name)
             for name in (*PROOF_FILES, "scope.json", "user_intact_record_link.json")}
    expected = _analyze(source, files)
    _require(_json(_ordinary(source / "source_reuse.json")) == expected, "annotation does not replay.")
    rows = [_json(line) for line in _ordinary(source / "source_reuse_records.jsonl").splitlines()]
    _require(rows == expected["observations"] and _ordinary(source / "source_reuse.html") == _html(expected).encode(),
             "displayed records or report do not replay.")
    return expected


def reuse_view(source, source_run):
    _require(isinstance(source_run, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_run), "invalid run identifier.")
    report = read_reuse(source)
    if report is None:
        return {"status": "unavailable", "source_run": source_run, "observations": []}
    return {"status": "available", "source_run": source_run,
            **{key: report[key] for key in (*_binding(read_run(source)[2]), "observations")},
            "report_url": "/api/assay-source-reuse/" + source_run + "/report.html"}


def publish_reuse_workspace(source, trace, output):
    """Copy a verified source workspace and add a separate, portable supplement."""
    source, trace, output = (Path(p).absolute() for p in (source, trace, output))
    _require(not output.exists() and not output.is_symlink()
             and not any(output.resolve() == p.resolve() or p.resolve() in output.resolve().parents
                         or output.resolve() in p.resolve().parents for p in (source, trace)),
             "choose a new immutable output outside input directories.")
    inventory = _source_files(source)
    _require(not any((source / name).exists() for name in MARKERS), "source already has a reuse supplement.")
    files = _capture_trace(trace)
    report = _analyze(source, files)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".source-reuse-", dir=output.parent))
    try:
        for name in inventory:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_ordinary(source / name))
        (stage / "source_reuse_source").mkdir()
        for name, raw in files.items():
            (stage / "source_reuse_source" / name).write_bytes(raw)
        write_json(stage / "source_reuse.json", report)
        (stage / "source_reuse_records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in report["observations"]), encoding="utf-8")
        (stage / "source_reuse.html").write_text(_html(report), encoding="utf-8")
        extras = {name: value for name, value in _source_files(stage).items() if name not in inventory}
        write_json(stage / "source_reuse_manifest.json", _seal({"format": FORMAT,
            "workspace_files": inventory, "supplement_files": extras, "implementation_sha256": _implementation()}))
        _require(read_reuse(stage) == report and _source_files(source) == inventory,
                 "workspace changed during publication.")
        _require(not output.exists() and not output.is_symlink(), "output appeared during publication.")
        stage.rename(output)
        return report
    finally:
        if stage.exists():
            shutil.rmtree(stage)
