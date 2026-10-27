"""Separate frozen IntAct assessment publication; historical development guards stay intact.

The row projection adapts the existing qualified-evidence implementation and reuses
its pure field, citation and readable-display helpers. Scope is exactly the four
original reserved studies or the four consumed studies for a named replay. This
module accepts supplied bytes only; it never fetches or opens reserved sources.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .client import digest, utcnow, write_json
from .file_utils import new_output, sha
from .assertions import build_assertions, assertion_summary
from .intact_evidence import (
    FORMAT as EVIDENCE_FORMAT, SOURCE_KIND, RELEASE, PREDICATE, LICENSE,
    _sha, _check_eligible, _values, _participants, _qualifications, _groups,
    _citations, _terms, _identifier, answer_observation, publication_html,
)

FORMAT = "biograph-steward.intact-final-evidence-publication.v1"
DEVELOPMENT = ("40075158", "40404733", "40071126", "40739265")
RESERVED = ("39833857", "40211762", "39972491", "40555359")
LIMITATIONS = [
    "Source fidelity is preservation of supplied curation, not independent scientific accuracy or prediction gain.",
    "Physical association, binary views and bait/prey roles do not establish direct binding or biological direction.",
    "Missing expansion annotations do not establish true-binary origin; raw missing/default states remain explicit.",
    "Negative interaction evidence is conditional on the source experiment; absent pairs are unlabeled.",
    "Rows, experiment accessions and database names do not establish independent study counts.",
    "The execution freeze declares the exact assessment scope; replay results are consumed development checks.",
    "Original source records are preserved without automatic acceptance, pruning or a standards-conformance claim.",
]


def _scope(bindings):
    if not isinstance(bindings, dict):
        raise ValueError("Explicit final-assessment bindings are required.")
    split = bindings.get("assessment_split")
    expected = RESERVED if split == "reserved_final" else DEVELOPMENT if split == "development_replay" else None
    if (expected is None or bindings.get("publication_ids") != list(expected)
            or not _sha(bindings.get("execution_freeze_sha256"))
            or any(not isinstance(bindings.get(k), dict) or set(bindings[k]) != set(expected)
                   or any(not _sha(v) for v in bindings[k].values())
                   for k in ("source_sha256", "reader_sha256"))):
        raise ValueError("Require the exact original four-study split and a bound pre-access freeze.")
    return expected


def build_evidence(records, ledger, bindings):
    """Build an existing-assay-compatible publication from complete reader rows.

    The caller first verifies captured source/reader/ledger byte hashes. No source
    bytes are opened here. Records are flat publication wrappers; all source rows
    join the complete ledger, while only source-eligible rows become observations.
    """
    allowed = _scope(bindings)
    if (not isinstance(bindings,dict) or any(not _sha(bindings.get(key)) for key in
            ("protocol_sha256","amendment_sha256","result_sha256","ledger_sha256"))
            or any(not isinstance(bindings.get(key),dict) or not bindings[key]
                or any(pmid not in allowed or not _sha(value) for pmid,value in bindings[key].items())
                for key in ("source_sha256","reader_sha256"))):
        raise ValueError("IntAct publication requires complete frozen protocol/result/source/reader/ledger bindings.")
    if not isinstance(records,list) or not isinstance(ledger,list) or len(records)!=len(ledger):
        raise ValueError("Complete official reader rows and ledger must have equal length.")
    index = {}
    for item in ledger:
        key=(item.get("publication_id"),item.get("source_line"))
        if key in index: raise ValueError("Duplicate source row in IntAct ledger.")
        index[key]=deepcopy(item)
    observations, preserved, edges, nodes, seen = [],[],[],{},set()
    for wrapper in records:
        publication_id=wrapper["publication_id"]
        pmid=publication_id.removeprefix("pubmed:")
        row=wrapper["reader_record"]
        number=row.get("line_number")
        if pmid not in allowed or publication_id!="pubmed:"+pmid or type(number)is not int or number<1:
            raise ValueError("Only the exact predeclared final or consumed-replay publication rows are accepted.")
        key=(publication_id,number)
        if key in seen or key not in index: raise ValueError("Reader and ledger source rows are not a bijection.")
        seen.add(key); assessment=index[key]
        source_sha=wrapper["artifact_sha256"]
        if (bindings["source_sha256"].get(pmid)!=source_sha
                or assessment.get("artifact_sha256")!=source_sha
                or wrapper["source_file"]!="source/"+pmid+".txt"
                or wrapper["reader_file"]!="reader/"+pmid+".jsonl"
                or not isinstance(row.get("raw_line"),str)
                or assessment.get("raw_row_sha256")!=hashlib.sha256(row["raw_line"].encode()).hexdigest()
                or row.get("raw_cells")!=row["raw_line"].split("\t")):
            raise ValueError("IntAct source row, locator or raw-field binding disagrees.")
        preserved.append({**deepcopy(assessment),"reader_record":deepcopy(row),
                          "source_file":wrapper["source_file"],"reader_file":wrapper["reader_file"]})
        if assessment.get("eligible") is not True: continue
        if assessment.get("kind")!="evidence" or assessment.get("exclusion_reasons"):
            raise ValueError("Eligible ledger status contradicts its source assessment.")
        products=_check_eligible(row,pmid)
        source={"publication_id":publication_id,"artifact_sha256":source_sha,"release":RELEASE,
                "source_line":number,"raw_row_sha256":assessment["raw_row_sha256"],
                "url":"https://ftp.ebi.ac.uk/pub/databases/intact/"+RELEASE+"/psimitab/pmid/2025/"+pmid+".txt"}
        identity={**source,"evidence_ids":_values(row,"evidence_ids")}
        oid="intact.observation:"+digest(identity)[:24]
        participants=_participants(row,products); qualifications=_qualifications(row)
        provenance=[{"locator":wrapper["source_file"]+"#line="+str(number),"file_sha256":source_sha,"role":"curated_source_evidence"},
            {"locator":wrapper["reader_file"]+"#line="+str(number),"file_sha256":bindings["reader_sha256"][pmid],
             "record_sha256":digest(row),"role":"official_reader_record"}]
        observation={"id":oid,"source_kind":SOURCE_KIND,"source":source,"source_file":wrapper["source_file"],
            "source_row":number,"study":publication_id,"products":products,"participants":participants,
            "assay":_terms(_values(row,"detection_methods")),
            "detection_method":{"terms":_values(row,"detection_methods")},
            "participant_taxon":"NCBITaxon:9606","assay_host_taxon":None,
            "assay_hosts":_values(row,"host_taxa"),"constructs":{},
            "assay_status":"curated_negative" if qualifications["negative"]["value"] else "curated_positive",
            "evaluable":True,"local_review_state":"candidate","biologically_validated":False,"independent_evidence_count":None,
            "qualifications":qualifications,"qualified_fields":_groups(row,participants,qualifications),
            "raw_cells":deepcopy(row["raw_cells"]),"source_fields":deepcopy(row["source_fields"]),
            "reader_record":deepcopy(row),"original":deepcopy(row),"source_locators":provenance,
            "citations":_citations(row,source),"graph_edge_id":"edge:"+digest({"observation_id":oid})[:20]}
        observation["display"]=answer_observation(observation)
        observations.append(observation)
        for uid in products: nodes.setdefault(uid,{"id":uid,"name":uid,"category":"biolink:Protein","identifier_mapped":True,"data_kind":"published_assay_observations"})
        source_names=[term.get("name") or term.get("mi_id") for term in _values(row,"source_databases")]
        edges.append({"id":observation["graph_edge_id"],"subject":products[0],"predicate":PREDICATE,"object":products[1],
            "record_kind":"assay_observation","symmetric":False,
            "qualifiers":{"assay":observation["assay"],"observation_id":oid,"measurement_qualifier":observation["assay_status"],"species":"NCBITaxon:9606"},
            "status":"passed_structural_checks","review_reasons":[],"publications":[_identifier(x) for x in _values(row,"publication_ids")],
            "primary_source_raw":"; ".join(source_names),"evidence_sources":source_names,
            "aggregator":"IntAct/IMEx distribution; BioGraph Steward source-preserving projection",
            "evidence_record":deepcopy(observation),"source_record_count":1,"record_locators":[x["locator"] for x in provenance],
            "retrieval_provenance":deepcopy(provenance),"observation":deepcopy(observation),
            "normalization_notes":list(LIMITATIONS),"snapshot_sha256":bindings["result_sha256"],
            "data_kind":"published_assay_observations","biologically_validated":False})
    if seen!=set(index): raise ValueError("Complete IntAct ledger contains an unmatched source row.")
    counts=Counter(item["kind"] for item in ledger)
    summary={"source_kind":SOURCE_KIND,"source_physical_rows":len(records),"source_evidence_rows":counts["evidence"],
        "source_metadata_rows":len(records)-counts["evidence"],"primary_eligible":len(observations),
        "excluded_evidence":counts["evidence"]-len(observations),"observations":len(observations),
        "assay_evaluable":len(observations),"assay_excluded":0,"graph_nodes":len(nodes),"graph_edges":len(edges),
        "assay_status_counts":dict(Counter(o["assay_status"] for o in observations)),"independent_evidence_count":None,
        "pharos_records_modified":0,"automatically_accepted_assertions":0,"reserved_final_rows_opened":bindings["assessment_split"] == "reserved_final"}
    graph={"graph_format":"biograph-steward.assay-observation-graph.v1","data_kind":"published_assay_observations",
        "snapshot_sha256":bindings["result_sha256"],"nodes":sorted(nodes.values(),key=lambda x:x["id"]),
        "edges":sorted(edges,key=lambda x:x["id"]),"review_events":[],"biologically_validated":False,
        "independent_evidence_count":None,"interpretation":"Source-qualified IntAct/IMEx observations under a separate frozen fidelity assessment; no unqualified PPI assertion.","summary":deepcopy(summary)}
    graph["assertions"]=build_assertions(graph);graph["assertion_summary"]=assertion_summary(graph["assertions"])
    value={"format":EVIDENCE_FORMAT,"source_kind":SOURCE_KIND,"bindings":deepcopy(bindings),"observations":observations,"graph":graph,
        "summary":summary,"limitations":list(LIMITATIONS),"row_ledger":preserved,"source_license":deepcopy(LICENSE)}
    value["content_sha256"]=digest(value)
    return value


def records_from_material(files, catalog, bindings):
    """Verify an explicit four-study byte catalog, never discover source files."""
    from .assay_attachment import _decode
    pmids = _scope(bindings)
    if (not isinstance(catalog, list) or len(catalog) != len(pmids)
            or [x.get("publication_id") for x in catalog] != ["pubmed:" + p for p in pmids]):
        raise ValueError("Final source catalog must retain the complete original study order.")
    records, expected_names = [], set()
    for pmid, entry in zip(pmids, catalog):
        source_name, reader_name = "source/" + pmid + ".txt", "reader/" + pmid + ".jsonl"
        if entry.get("source_file") != source_name or entry.get("reader_file") != reader_name:
            raise ValueError("Unexpected final source path.")
        source, reader = files[source_name], files[reader_name]
        source_sha = hashlib.sha256(source).hexdigest()
        reader_sha = hashlib.sha256(reader).hexdigest()
        if (source_sha != entry.get("artifact_sha256") or source_sha != bindings["source_sha256"][pmid]
                or reader_sha != entry.get("reader_sha256") or reader_sha != bindings["reader_sha256"][pmid]):
            raise ValueError("Final source or official-reader bytes changed.")
        lines = source.decode("utf-8").splitlines()
        parsed = [_decode(line) for line in reader.splitlines()]
        if len(lines) != len(parsed):
            raise ValueError("Every physical source row must have one official-reader record.")
        for number, (line, row) in enumerate(zip(lines, parsed), 1):
            if (row.get("line_number") != number or row.get("raw_line") != line
                    or row.get("raw_cells") != line.split("\t")):
                raise ValueError("Final raw cells, physical line or side orientation changed.")
            records.append({"publication_id": "pubmed:" + pmid, "artifact_sha256": source_sha,
                            "source_file": source_name, "reader_file": reader_name, "reader_record": row})
        expected_names.update((source_name, reader_name))
    if {n for n in files if n.startswith(("source/", "reader/"))} != expected_names:
        raise ValueError("Uncatalogued source or reader files are forbidden.")
    return records


def load_projection(manifest, files):
    """Reproduce only a separately frozen assessment publication, including zero rows."""
    from .assay_attachment import _decode, _sealed
    required = {"LICENSE.md", "protocol.json", "semantic_amendment.json", "execution_freeze.json",
                "inspection_report.json", "row_ledger.jsonl", "controls_report.json",
                "xml_controls_report.json", "evidence.json", "graph.json", "index.html"}
    if (manifest.get("format") != FORMAT or not required <= set(files)
            or not isinstance(manifest.get("implementation_sha256"), dict)
            or not manifest["implementation_sha256"]
            or any(not _sha(v) for v in manifest["implementation_sha256"].values())
            or any(manifest.get(k) is not False for k in
                   ("baseline_modified", "automatic_pruning", "independent_validation_performed",
                    "standard_conformance_claimed"))):
        raise ValueError("Unsupported final-assessment publication or interpretation policy.")
    try:
        bindings = manifest["bindings"]
        pmids = _scope(bindings)
        for filename, field in (("protocol.json", "protocol_sha256"),
                ("semantic_amendment.json", "amendment_sha256"),
                ("execution_freeze.json", "execution_freeze_sha256"),
                ("inspection_report.json", "result_sha256"), ("row_ledger.jsonl", "ledger_sha256"),
                ("controls_report.json", "controls_report_sha256"),
                ("xml_controls_report.json", "xml_controls_report_sha256")):
            if hashlib.sha256(files[filename]).hexdigest() != bindings.get(field):
                raise ValueError("Final-assessment binding changed: " + filename)
        if (bindings["protocol_sha256"] != "d4948f584b8eed374ddfa49084ee58f1fb352d3d68a6630a202bf25742f8920a"
                or bindings["amendment_sha256"] != "2cd2cb485836228ce71dd9d62201c61dd5de45d18563894ac883f188f245e98c"):
            raise ValueError("The original protocol and mandatory semantic amendment must remain unchanged.")
        freeze = _decode(files["execution_freeze.json"])
        if (not _sealed(freeze) or freeze.get("format") != "biograph-steward.intact-final-execution-freeze.v1"
                or freeze.get("pre_access") is not True
                or freeze.get("publication_ids") != list(pmids)
                or freeze.get("assessment_split") != bindings["assessment_split"]):
            raise ValueError("Require the complete sealed pre-access execution freeze for this exact split.")
        controls = _decode(files["controls_report.json"])
        xml_controls = _decode(files["xml_controls_report.json"])
        for obj, fmt, runtime_key, access_key in (
                (controls, "biograph-steward.intact-reader-controls-result.v1", "reader_runtime", "reference_rows_accessed"),
                (xml_controls, "biograph-steward.intact-xml-controls-result.v1", "xml_reader_runtime", "selected_xml_bodies_accessed")):
            if (not _sealed(obj) or obj.get("format") != fmt or obj.get("status") != "passed"
                    or obj.get("all_checks_passed") is not True or obj.get("synthetic_only") is not True
                    or obj.get(access_key) is not False
                    or obj.get("runtime_bindings") != bindings.get(runtime_key)):
                raise ValueError("Passing original reader/runtime controls must accompany the final publication.")
        inspection = _decode(files["inspection_report.json"])
        expected_status = ("final_inspected_not_fidelity_scored" if bindings["assessment_split"] == "reserved_final"
                           else "development_full_flow_replay_not_final_score")
        if (inspection.get("status") != expected_status
                or inspection.get("publication_ids") != list(pmids)
                or inspection.get("bindings", {}).get("runtime_bindings") != bindings["reader_runtime"]
                or inspection.get("bindings", {}).get("controls_report_sha256") != bindings["controls_report_sha256"]
                or inspection.get("bindings", {}).get("execution_freeze_sha256") != bindings["execution_freeze_sha256"]):
            raise ValueError("Final inspection, execution freeze and reader controls disagree.")
        records = records_from_material(files, manifest["source_catalog"], bindings)
        ledger = [_decode(line) for line in files["row_ledger.jsonl"].splitlines()]
        evidence = build_evidence(records, ledger, deepcopy(bindings))
        if (evidence != _decode(files["evidence.json"]) or evidence["graph"] != _decode(files["graph.json"])
                or evidence["summary"] != manifest.get("summary")
                or files["index.html"].decode("utf-8") != publication_html(evidence)):
            raise ValueError("Final evidence, graph and readable display must reproduce from preserved records.")
    except (KeyError, TypeError, UnicodeError) as exc:
        raise ValueError("Incomplete final-assessment source publication.") from exc
    return manifest, evidence, files


def publish_material(files, catalog, bindings, inspection, output):
    """Publish a complete supplied assessment packet; no retrieval or source discovery."""
    from .assay_attachment import _decode, load_publication
    files = dict(files)
    if _decode(files["inspection_report.json"]) != inspection:
        raise ValueError("Supplied inspection differs from its preserved bytes.")
    records = records_from_material(files, catalog, bindings)
    ledger = [_decode(line) for line in files["row_ledger.jsonl"].splitlines()]
    evidence = build_evidence(records, ledger, bindings)
    for name, obj in (("evidence.json", evidence), ("graph.json", evidence["graph"])):
        files[name] = (json.dumps(obj, indent=2, ensure_ascii=True) + "\n").encode()
    files["index.html"] = publication_html(evidence).encode()
    manifest = {"format": FORMAT, "created_at": utcnow(), "bindings": deepcopy(bindings),
                "source_catalog": deepcopy(catalog), "summary": evidence["summary"],
                "implementation_sha256": {"final_projection": sha(__file__),
                    "shared_field_projection": sha(Path(__file__).with_name("intact_evidence.py"))},
                "baseline_modified": False, "automatic_pruning": False,
                "independent_validation_performed": False, "standard_conformance_claimed": False,
                "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}}
    manifest["content_sha256"] = digest(manifest)
    load_projection(manifest, files)
    for name in files:
        if (not name or Path(name).is_absolute() or ".." in Path(name).parts
                or str(Path(name)) != name or name == "publication.json"):
            raise ValueError("Only ordinary relative publication paths are accepted.")
    folder = new_output(output)
    for name, raw in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    write_json(folder / "publication.json", manifest)
    load_publication(folder)
    return manifest

