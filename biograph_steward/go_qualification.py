"""Immutable native GOA context beside a lossy Pharos GO projection.

The official Biopython GAF reader supplies parsed records. Matching projection
tuples supplies compatibility candidates, never historical record identity or
independent experimental validation. Original graph qualifiers remain unknown.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
from itertools import zip_longest
from pathlib import Path
import re
import shutil

from . import gold_packet
from .client import canonical, digest, utcnow, write_json
from .file_utils import new_output, sha


FORMAT = "biograph-steward.native-go-context.v1"
PARSER_VERSION = "1.88"
GAF_FIELDS = ("DB", "DB_Object_ID", "DB_Object_Symbol", "Qualifier", "GO_ID",
              "DB:Reference", "Evidence", "With", "Aspect", "DB_Object_Name",
              "Synonym", "DB_Object_Type", "Taxon_ID", "Date", "Assigned_By",
              "Annotation_Extension", "Gene_Product_Form_ID")
SPEC = "https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/"
# This already consumed study is a known overlap flag, not a complete mask.
CONSUMED_REFERENCE_IDS = frozenset({"PMID:36949045"})
LIMITATIONS = [
    "A compatible native row is not identified as the historical Pharos source record, even when unique.",
    "Native qualifiers belong to their preserved GAF row; they do not backfill original graph qualifiers.",
    "Missing native matches remain unknown and are never biological negatives.",
    "Positive and NOT rows may coexist because of context, product forms or conflicting evidence; none is deleted here.",
    "Extension and With/From logical groups are preserved literally, without ontology reasoning or context equivalence inference.",
    "Reference identifiers can alias one reference and are not counted as independent experiments.",
    "Known consumed-reference flags are incomplete; their absence does not establish benchmark or study independence.",
    "UniProt cross-reference positivity and historical native-record identity are not established by this adapter.",
    "No scientific truth, accuracy improvement or automatic false-edge pruning is established.",
]


def _need(condition, message):
    if not condition:
        raise ValueError("GO context qualification: " + message)


def _groups(text):
    """Preserve GAF's OR-of-AND literal groups; do not resolve identifiers."""
    return [group.split(",") for group in text.split("|")] if text else []


def native_record(number, raw, fields, parsed, gaf_sha256):
    """Bind official-parser output to one original, 17-field native record."""
    _need(isinstance(number, int) and number > 0, "invalid native line number.")
    _need(len(fields) == 17 and raw.split("\t") == fields, "native row must contain exactly 17 fields.")
    _need(isinstance(parsed, dict) and set(parsed) == set(GAF_FIELDS), "unexpected official parser fields.")
    for field, literal in zip(GAF_FIELDS, fields):
        value = parsed[field]
        rebound = "|".join(value) if isinstance(value, list) else value
        _need(rebound == literal, "parsed field differs from native source: " + field)
    _need(all(fields[i] for i in (0, 1, 2, 3, 4, 5, 6, 8, 11, 12, 13, 14)),
          "required GAF 2.2 field is missing.")
    _need(bool(re.fullmatch(r"GO:[0-9]{7}", fields[4])) and fields[8] in {"P", "F", "C"},
          "invalid GO identifier or aspect.")
    qualifiers = parsed["Qualifier"]
    relations = [q for q in qualifiers if q != "NOT"]
    _need(len(relations) == 1 and len(qualifiers) == len(set(qualifiers))
          and bool(re.fullmatch(r"[a-z][a-z_]*", relations[0])),
          "GAF 2.2 requires one relation and an optional NOT modifier.")
    _need(len(parsed["Taxon_ID"]) in {1, 2} and all(re.fullmatch(r"taxon:[0-9]+", t)
          for t in parsed["Taxon_ID"]), "invalid native taxon field.")
    _need(bool(re.fullmatch(r"[0-9]{8}", fields[13])), "invalid GAF annotation date literal.")
    rid = "goa.native:" + digest({"gaf_sha256": gaf_sha256, "source_line": number,
                                  "raw_line": raw})[:24]
    return {"id": rid, "source_line": number, "raw_line": raw,
        "raw_line_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "raw_fields": list(fields), "parsed": deepcopy(parsed),
        "source_gaf_sha256": gaf_sha256, "subject": fields[0] + ":" + fields[1],
        "go_id": fields[4], "aspect": fields[8], "relation_literal": relations[0],
        "relation_ontology_validation_performed": False, "qualifier_tokens": list(qualifiers),
        "negated": "NOT" in qualifiers, "reference_identifiers": list(parsed["DB:Reference"]),
        "reference_group_semantics": "Identifiers for one cited reference, not independent studies.",
        "with_from_raw": fields[7], "with_from_or_groups_raw": _groups(fields[7]),
        "annotation_extension_raw": fields[15], "extension_or_groups_raw": _groups(fields[15]),
        "extension_semantic_validation_performed": False,
        "gene_product_form_id": fields[16] or None, "taxon_ids": list(parsed["Taxon_ID"]),
        "subject_taxon_is_human": parsed["Taxon_ID"][0] == "taxon:9606",
        "evidence_code": fields[6], "assigned_by": fields[14], "annotation_date": fields[13],
        "known_consumed_reference_ids": sorted(set(parsed["DB:Reference"]) & CONSUMED_REFERENCE_IDS),
        "reference_independence_established": False, "historical_pharos_record_identity_established": False}


def read_native_gaf(path, accessions, expected_sha256):
    """Read a byte-pinned GAF2.2 with the inspected optional official parser."""
    path = Path(path).absolute()
    _need(path.is_file() and not path.is_symlink(), "GAF input must be an ordinary nonsymlink file.")
    _need(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
          "an explicit GAF SHA-256 pin is required.")
    _need(sha(path) == expected_sha256, "GAF bytes differ from the supplied source pin.")
    try:
        import Bio
        from Bio.UniProt.GOA import gafiterator
    except ModuleNotFoundError as exc:
        if exc.name != "Bio" and not str(exc.name).startswith("Bio."):
            raise
        raise ValueError("Native GAF parsing requires optional biopython==1.88.") from exc
    _need(Bio.__version__ == PARSER_VERSION, "use the inspected biopython==1.88 GAF parser.")
    headers = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for line in handle:
            if not line.startswith("!"):
                break
            headers.append(line.rstrip("\r\n"))
    _need(headers and headers[0] == "!gaf-version: 2.2", "only the reviewed GAF 2.2 source format is supported.")
    _need(any(h.startswith("!generated-by:") for h in headers)
          and any(h.startswith("!date-generated:") for h in headers), "mandatory GAF headers are missing.")

    def raw_rows():
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            for number, line in enumerate(handle, 1):
                if line.startswith("!") or not line.rstrip("\r\n"):
                    continue
                raw = line.rstrip("\r\n")
                fields = raw.split("\t")
                _need(len(fields) == 17, "native GAF line " + str(number) + " does not have 17 fields.")
                yield number, raw, fields

    rows, total = [], 0
    with gzip.open(path, "rt", encoding="utf-8", newline=None) as handle:
        for raw_entry, parsed in zip_longest(raw_rows(), gafiterator(handle)):
            _need(raw_entry is not None and parsed is not None, "official parser and native row counts disagree.")
            number, raw, fields = raw_entry
            total += 1
            if fields[0] == "UniProtKB" and fields[1] in accessions:
                rows.append(native_record(number, raw, fields, parsed, expected_sha256))
    _need(sha(path) == expected_sha256, "GAF source changed during parsing.")
    return rows, {"headers": headers, "total_source_rows": total,
        "gaf_sha256": expected_sha256,
        "parser": {"package": "biopython", "version": PARSER_VERSION, "function": "Bio.UniProt.GOA.gafiterator"}}


def project_compatibilities(graph, native_rows):
    """Enumerate every exact projection candidate without selecting a winner."""
    groups = defaultdict(list)
    ids = set()
    for row in native_rows:
        _need(row["id"] not in ids, "native row IDs repeat.")
        ids.add(row["id"])
        key = (row["subject"], row["go_id"], row["evidence_code"], row["assigned_by"], row["aspect"])
        groups[key].append(row)
    results = []
    for edge in graph["edges"]:
        if edge.get("record_kind") != "go_annotation":
            continue
        record = edge["evidence_record"]
        _need(edge["subject"].startswith("UniProtKB:") and edge["object"] == record.get("goid"),
              "GO edge does not match its exact source projection.")
        key = (edge["subject"], edge["object"], record.get("evidence"), record.get("assigned_by"), record.get("type"))
        candidates = sorted(groups.get(key, []), key=lambda r: r["source_line"])
        status = ("no_compatible_native_record" if not candidates else "one_compatible_native_record"
                  if len(candidates) == 1 else "multiple_compatible_native_records")
        polarities = sorted({"NOT" if row["negated"] else "positive" for row in candidates})
        results.append({"edge_id": edge["id"], "assertion_id": edge.get("assertion_id"),
            "compatibility_key": list(key), "status": status,
            "native_record_ids": [row["id"] for row in candidates], "candidate_count": len(candidates),
            "candidate_polarities": polarities, "both_positive_and_not_candidates": len(polarities) > 1,
            "candidate_product_forms": sorted({row["gene_product_form_id"] or "" for row in candidates}),
            "candidate_extension_literals": sorted({row["annotation_extension_raw"] for row in candidates}),
            "historical_record_identity_established": False, "original_qualifiers_backfilled": False,
            "biological_truth_assessed": False, "pruning_decision": "abstain"})
    return results


def qualify_go_context(packet, gaf, output, *, expected_gaf_sha256, source_url=None):
    """Publish native row context beside a verified Gold graph, offline."""
    # Do not erase symlink evidence before Gold's ordinary-file validation.
    packet, gaf = Path(packet).absolute(), Path(gaf).absolute()
    _need(source_url is None or isinstance(source_url, str), "provided source URL must be text or unavailable.")
    manifest, graph = gold_packet.load_packet(packet)
    subjects = {edge["subject"].removeprefix("UniProtKB:") for edge in graph["edges"]
                if edge.get("record_kind") == "go_annotation" and edge["subject"].startswith("UniProtKB:")}
    rows, source = read_native_gaf(gaf, subjects, expected_gaf_sha256)
    compatibility = project_compatibilities(graph, rows)
    _need(sha(packet / "source/graph.json") == manifest["files"]["source/graph.json"],
          "packet source graph changed during qualification.")
    counts = Counter(row["status"] for row in compatibility)
    report = {"format": FORMAT, "created_at": utcnow(), "packet_id": manifest["packet_id"],
        "graph_sha256": manifest["graph_sha256"], "snapshot_sha256": manifest["snapshot_sha256"],
        "source_graph_file_sha256": sha(packet / "source/graph.json"),
        "source": {**source, "provided_source_url": source_url,
            "source_url_authentication_performed": False, "format_specification": SPEC},
        "scope": "Exact UniProt subjects of the original GO edges; all compatible native records, no graph mutation.",
        "compatibility_fields": ["exact_UniProt_accession", "GO_ID", "evidence_code", "assigned_by", "aspect"],
        "counts": {"original_go_edges": len(compatibility), "exact_go_subjects": len(subjects),
            "native_rows": len(rows), "native_subjects": len({row["subject"] for row in rows}),
            "native_not_rows": sum(row["negated"] for row in rows),
            "native_extension_rows": sum(bool(row["annotation_extension_raw"]) for row in rows),
            "native_product_form_rows": sum(bool(row["gene_product_form_id"]) for row in rows),
            "known_consumed_reference_rows": sum(bool(row["known_consumed_reference_ids"]) for row in rows),
            "edges_with_positive_and_not_candidates": sum(row["both_positive_and_not_candidates"] for row in compatibility),
            **{key: counts[key] for key in ("no_compatible_native_record", "one_compatible_native_record", "multiple_compatible_native_records")}},
        "historical_native_identity_established": False, "original_qualifiers_backfilled": False,
        "complete_gaf_rules_and_ontology_validation_performed": False,
        "source_graph_mutated": False, "scientific_accuracy_measured": False,
        "independent_reference_validation_performed": False, "source_fetches": 0, "model_calls": 0,
        "limitations": deepcopy(LIMITATIONS), "implementation_sha256": sha(Path(__file__))}
    folder = new_output(output, packet, gaf)
    for name, values in (("native_records.jsonl", rows), ("edge_compatibilities.jsonl", compatibility)):
        (folder / name).write_text("".join(canonical(value) + "\n" for value in values), encoding="utf-8")
    (folder / "source").mkdir()
    shutil.copyfile(gaf, folder / "source/annotations.gaf.gz")
    _need(sha(folder / "source/annotations.gaf.gz") == expected_gaf_sha256, "copied source bytes changed.")
    report["files"] = {name: sha(folder / name) for name in
                       ("native_records.jsonl", "edge_compatibilities.jsonl", "source/annotations.gaf.gz")}
    report["content_sha256"] = digest(report)
    write_json(folder / "go_context_qualification.json", report)
    return report
