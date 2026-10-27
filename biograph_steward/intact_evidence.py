"""Qualified IntAct/IMEx development evidence through the existing assay overlay.

Interpretation uses the validated official reader's full source fields. Every
source row remains preserved; row objects, source qualifiers and graph review
states are distinct. This module neither parses MITAB nor runs a source query.
"""
from collections import Counter
from copy import deepcopy
import hashlib
from html import escape
from urllib.parse import quote, urlparse

from .client import digest
from .graph import UNIPROT
from .assertions import build_assertions, assertion_summary

FORMAT = "biograph-steward.intact-qualified-evidence.v1"
SOURCE_KIND = "intact_mitab27"
DEVELOPMENT = frozenset(("40075158", "40404733", "40071126", "40739265"))
RELEASE = "2026-10-17"
PREDICATE = "biograph:has_assay_observation_with"
LIMITATIONS = [
    "These are source-qualified curated records, not independent biological confirmations or an accuracy score.",
    "A physical association and bait/prey roles do not establish direct binding or biological direction.",
    "Full source host labels are preserved as labels; no tissue, disease mechanism or cell-line identifier is inferred.",
    "Missing expansion annotation does not establish true-binary experimental origin or absence of expansion.",
    "Qualified negative evidence is conditional on the source experiment; absent pairs never become negative evidence.",
    "Source databases, distributed IntAct/IMEx identifiers and multiple rows are not independent experiment counts.",
    "The four development publications are consumed; the reserved publications are not included.",
    "The original Pharos source records are preserved; no automatic acceptance, pruning or standard-conformance claim is made.",
]
LICENSE = {"source": "IntAct/IMEx distribution; source database attribution retained per row",
           "license": "CC-BY-4.0", "license_file": "assay_source/LICENSE.md",
           "license_url": "https://creativecommons.org/licenses/by/4.0/",
           "note": "Attribute IntAct/IMEx, the original source database and publication. Preserve the source license and receipts."}

COLUMNS = ["Unique identifier A", "Unique identifier B", "Alternative identifiers A", "Alternative identifiers B",
    "Aliases A", "Aliases B", "Interaction detection methods", "First author", "Publication identifiers",
    "Participant taxonomy A", "Participant taxonomy B", "Interaction types", "Source databases", "Interaction evidence identifiers",
    "Confidence scores", "Complex expansion", "Biological role A", "Biological role B", "Experimental role A", "Experimental role B",
    "Interactor type A", "Interactor type B", "Interactor xrefs A", "Interactor xrefs B", "Interaction xrefs",
    "Participant annotations A", "Participant annotations B", "Interaction annotations", "Experimental host", "Interaction parameters",
    "Creation date", "Update date", "Participant checksum A", "Participant checksum B", "Interaction checksum", "Negative flag",
    "Participant features A", "Participant features B", "Stoichiometry A", "Stoichiometry B", "Participant identification methods A", "Participant identification methods B"]
GROUPS = {
    "participant_identity": ([1,2,3,4,5,6,10,11,21,22,33,34],
        ["primary_ids_a","primary_ids_b","alternative_ids_a","alternative_ids_b","taxa_a","taxa_b","interactor_types_a","interactor_types_b"]),
    "source_and_publication": ([8,9,13,14,25,31,32,35], ["publication_ids","source_databases","evidence_ids"]),
    "detection_and_type": ([7,12,41,42], ["detection_methods","interaction_types","identification_methods_a","identification_methods_b"]),
    "roles_and_experimental_context": ([17,18,19,20,26,27,28,29,30],
        ["biological_roles_a","biological_roles_b","experimental_roles_a","experimental_roles_b","interaction_annotations","host_taxa"]),
    "complex_expansion": ([14,16], ["complex_expansion","evidence_ids"]),
    "negative": ([36], []), "features_and_stoichiometry": ([37,38,39,40], []),
    "other_missing_values_and_confidence": ([15,23,24], []),
}
FIELD_COLUMNS = {"primary_ids_a":1,"primary_ids_b":2,"alternative_ids_a":3,"alternative_ids_b":4,
    "detection_methods":7,"publication_ids":9,"taxa_a":10,"taxa_b":11,"interaction_types":12,
    "source_databases":13,"evidence_ids":14,"complex_expansion":16,"biological_roles_a":17,
    "biological_roles_b":18,"experimental_roles_a":19,"experimental_roles_b":20,
    "interactor_types_a":21,"interactor_types_b":22,"interaction_annotations":28,"host_taxa":29,
    "identification_methods_a":41,"identification_methods_b":42}


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _values(record, name):
    return deepcopy(record["source_fields"][name]["values"])


def _database(value):
    return ((value.get("database") or {}).get("name") or "").lower()


def _identifier(value):
    return (_database(value) + ":" + str(value.get("id"))) if value.get("id") else "Not supplied"


def _terms(values):
    return "; ".join((str(value.get("name") or "Unnamed term") +
        (" (" + str(value["mi_id"]) + ")" if value.get("mi_id") else "")) for value in values) or "Not supplied"


def _ids(values):
    return "; ".join(_identifier(value) for value in values) or "Not supplied"


def _hosts(values):
    return "; ".join(str(value.get("common_name") or value.get("scientific_name") or "Label not supplied")
        + " [NCBI taxid " + str(value.get("taxid")) + "]" for value in values) or "Not supplied"


def _check_eligible(record, pmid):
    """Validate explicit source facts, without reinterpreting excluded evidence."""
    raw, fields = record.get("raw_cells"), record.get("source_fields")
    if (not isinstance(raw, list) or len(raw) != 42 or record.get("parsed_count") != 1
            or not isinstance(fields, dict) or raw[35] not in {"true", "false", "-"}):
        raise ValueError("Eligible IntAct rows require complete MITAB27 framing and an explicit valid negative flag/default.")
    required = {name for _, names in GROUPS.values() for name in names}
    for name in required:
        field = fields.get(name)
        if (not isinstance(field, dict) or not isinstance(field.get("values"), list)
                or field.get("status") not in {"parsed", "missing", "parsed_with_diagnostics"}
                or type(field.get("column")) is not int or field["column"] != FIELD_COLUMNS[name]
                or field.get("raw") != raw[field["column"]-1]):
            raise ValueError("Full official source field is missing or disagrees with raw cells: " + name)
    diagnostics = list(record.get("diagnostics", [])) + [d for field in fields.values() for d in field.get("diagnostics", [])]
    if any(str(event.get("callback", "")).startswith(("onInvalid", "bridge_")) for event in diagnostics):
        raise ValueError("Invalid official-reader diagnostics cannot become eligible evidence.")
    products = []
    for side in ("a", "b"):
        identities = {item.get("id") for item in _values(record, "primary_ids_"+side) if _database(item) == "uniprotkb"}
        if len(identities) != 1 or any(not isinstance(uid, str) or not UNIPROT.fullmatch(uid) for uid in identities):
            raise ValueError("Eligible source primary protein identity is missing or ambiguous.")
        if ({item.get("taxid") for item in _values(record, "taxa_"+side)} != {9606}
                or {item.get("mi_id") for item in _values(record, "interactor_types_"+side)} != {"MI:0326"}):
            raise ValueError("Eligible participants must be source-explicit human proteins.")
        products.append("UniProtKB:" + next(iter(identities)))
    if (pmid not in {item.get("id") for item in _values(record,"publication_ids") if _database(item)=="pubmed"}
            or not _values(record,"source_databases") or not _values(record,"evidence_ids")):
        raise ValueError("Eligible evidence requires its selected publication, source and evidence identifiers.")
    for item in _values(record, "evidence_ids"):
        if not _database(item) or not item.get("id"):
            raise ValueError("Source evidence identity is not traceable.")
    if any(not item.get("mi_id") and not item.get("name") for item in _values(record,"source_databases")):
        raise ValueError("Source database identity is not traceable.")
    if (not isinstance(record.get("interaction"),dict)
            or record["interaction"].get("negative") is not (raw[35]=="true")):
        raise ValueError("Official negative value disagrees with its source flag/default.")
    return products


def _participants(record, products):
    raw, result = record["raw_cells"], []
    model = {p.get("side"): p for p in record["interaction"].get("participants", [])}
    for offset, side in enumerate(("A","B")):
        suffix = side.lower()
        value = {"side":side, "product_id":products[offset],
            **{key: _values(record, name+"_"+suffix) for key,name in
                (("primary_ids","primary_ids"),("alternative_ids","alternative_ids"),("taxa","taxa"),
                 ("interactor_types","interactor_types"),("biological_roles","biological_roles"),
                 ("experimental_roles","experimental_roles"),("identification_methods","identification_methods"))},
            "aliases_raw":raw[4+offset], "features_raw":raw[36+offset], "stoichiometry_raw":raw[38+offset],
            "reader_fields":deepcopy(model.get(side)), "identity_inferred":False}
        result.append(value)
    return result


def _qualifications(record):
    raw = record["raw_cells"]
    return {"negative":{"literal":raw[35], "value":raw[35]=="true",
                        "origin":"mitab27_default_false" if raw[35]=="-" else "explicit"},
            "expansion":{"literal":raw[15], "annotation_origin":"not_supplied" if raw[15]=="-" else "supplied",
                         "methods":_values(record,"complex_expansion")},
            "binary_origin":"unknown_no_inference", "direct_binding_inferred":False,
            "independent_evidence_count":None}


def _groups(record, participants, qualifications):
    groups = {}
    for name,(columns,fields) in GROUPS.items():
        groups[name] = {"raw_fields":[{"column":column,"label":COLUMNS[column-1],"value":record["raw_cells"][column-1]} for column in columns],
                        "parsed_fields":{field:_values(record,field) for field in fields}, "semantics":{}}
    groups["participant_identity"]["semantics"] = {"identity_basis":"exact source primary identifiers", "A_B_orientation_preserved":True}
    groups["source_and_publication"]["semantics"] = {"independent_evidence_count":None}
    groups["detection_and_type"]["semantics"] = {"direct_binding_inferred":False}
    groups["roles_and_experimental_context"]["semantics"] = {"host_labels_are_literal":True, "cell_line_identifier_inferred":False}
    groups["complex_expansion"]["semantics"] = {**deepcopy(qualifications["expansion"]),"binary_origin":qualifications["binary_origin"]}
    groups["negative"]["semantics"] = deepcopy(qualifications["negative"])
    groups["features_and_stoichiometry"]["reader_fields"] = [{"side":p["side"],
        "features":deepcopy((p["reader_fields"] or {}).get("features")),
        "stoichiometry":deepcopy((p["reader_fields"] or {}).get("stoichiometry"))} for p in participants]
    groups["features_and_stoichiometry"]["semantics"] = {"sequence_or_construct_identity_inferred":False}
    groups["other_missing_values_and_confidence"]["semantics"] = {"confidence_is_calibrated_truth_probability":False}
    return groups


def _citations(record, source):
    citations = [{"kind":"source_artifact", "identifier":source["artifact_sha256"],
        "label":"Pinned MITAB source, line "+str(source["source_line"]), "url":source["url"]}]
    for field in ("publication_ids","evidence_ids"):
        for item in _values(record,field):
            db,uid = _database(item), item.get("id")
            if not uid: continue
            url = ("https://pubmed.ncbi.nlm.nih.gov/"+quote(uid,safe="")+"/" if db=="pubmed" else
                   "https://www.ebi.ac.uk/intact/search?query="+quote(uid,safe="") if db in {"intact","imex"} else None)
            if url: citations.append({"kind":"publication" if field=="publication_ids" else "evidence",
                "identifier":db+":"+uid,"label":db+":"+uid+(" lookup" if db!="pubmed" else ""),"url":url})
    return citations


def answer_observation(observation):
    """Deterministic readable source-field explanation shared by UI and answers."""
    participants = observation["participants"]
    qualified = observation["qualified_fields"]
    source = qualified["source_and_publication"]["parsed_fields"]
    methods = qualified["detection_and_type"]["parsed_fields"]
    roles = qualified["roles_and_experimental_context"]["parsed_fields"]
    negative = observation["qualifications"]["negative"]
    expansion = observation["qualifications"]["expansion"]
    summaries = {
        "participant_identity":"; ".join("Participant "+p["side"]+": "+p["product_id"]+"; source primary identifiers "+_ids(p["primary_ids"])+"; taxonomy "+_hosts(p["taxa"])+"; type "+_terms(p["interactor_types"]) for p in participants)+". A/B source orientation is preserved; alternative IDs do not replace primary IDs.",
        "source_and_publication":"Source database: "+_terms(source["source_databases"])+". Publication identifiers: "+_ids(source["publication_ids"])+". Evidence identifiers: "+_ids(source["evidence_ids"])+". Source row "+str(observation["source_row"])+", artifact SHA-256 "+observation["source"]["artifact_sha256"]+". These records are not an independent-experiment count.",
        "detection_and_type":"Interaction detection method: "+_terms(methods["detection_methods"])+". Source interaction type: "+_terms(methods["interaction_types"])+". Participant A identification: "+_terms(methods["identification_methods_a"])+"; participant B identification: "+_terms(methods["identification_methods_b"])+". Direct binding is not inferred from these annotations.",
        "roles_and_experimental_context":"; ".join("Participant "+p["side"]+" "+p["product_id"]+": experimental role "+_terms(p["experimental_roles"])+"; biological role "+_terms(p["biological_roles"]) for p in participants)+". Experimental host labels: "+_hosts(roles["host_taxa"])+". These are source labels; no cell-line identifier or disease mechanism is inferred. Bait/prey do not establish biological direction.",
        "complex_expansion":("No expansion annotation was supplied; binary experimental origin is unknown." if expansion["annotation_origin"]=="not_supplied" else "Source expansion annotation: "+_terms(expansion["methods"])+". Binary experimental origin is not inferred.")+" Expanded records do not become independent direct-binding experiments.",
        "negative":("Negative flag: true, explicitly supplied. This is source-qualified negative interaction evidence under the reported conditions, not universal absence." if negative["value"] else
            "Negative flag: false, "+("from the MITAB27 '-' default" if negative["origin"]=="mitab27_default_false" else "explicitly supplied")+". This is positive interaction evidence under the source conditions, not an unconditional interaction claim.")+" Missing pairs and failed imports never become negative evidence.",
        "features_and_stoichiometry":"Participant features and stoichiometry are retained in their source A/B orientation below. '-' means not supplied here; zero stoichiometry is preserved. No full sequence or construct identity is inferred.",
        "other_missing_values_and_confidence":"Source confidence scores and other cross-references are retained below. A score is not a calibrated truth probability; missing optional fields remain not supplied.",
    }
    groups = [{"group":name,"text":summaries[name],"fields":[{"label":field["label"],"value":field["value"],"columns":[field["column"]]} for field in qualified[name]["raw_fields"]]} for name in GROUPS]
    return {"observation_id":observation["id"],"text":"\n\n".join(group["text"] for group in groups),
            "field_groups":groups,"citations":deepcopy(observation["citations"]),"qualified_fields":deepcopy(qualified)}


def build_evidence(records, ledger, bindings):
    """Build an existing-assay-compatible publication from complete reader rows.

    The caller first verifies captured source/reader/ledger byte hashes. No source
    bytes are opened here. Records are flat publication wrappers; all source rows
    join the complete ledger, while only source-eligible rows become observations.
    """
    if (not isinstance(bindings,dict) or any(not _sha(bindings.get(key)) for key in
            ("protocol_sha256","amendment_sha256","result_sha256","ledger_sha256"))
            or any(not isinstance(bindings.get(key),dict) or not bindings[key]
                or any(pmid not in DEVELOPMENT or not _sha(value) for pmid,value in bindings[key].items())
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
        if pmid not in DEVELOPMENT or publication_id!="pubmed:"+pmid or type(number)is not int or number<1:
            raise ValueError("Only exact, explicitly allowed development publication rows are accepted.")
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
        "pharos_records_modified":0,"automatically_accepted_assertions":0,"reserved_final_rows_opened":False}
    graph={"graph_format":"biograph-steward.assay-observation-graph.v1","data_kind":"published_assay_observations",
        "snapshot_sha256":bindings["result_sha256"],"nodes":sorted(nodes.values(),key=lambda x:x["id"]),
        "edges":sorted(edges,key=lambda x:x["id"]),"review_events":[],"biologically_validated":False,
        "independent_evidence_count":None,"interpretation":"Source-qualified IntAct/IMEx development observations; no unqualified PPI assertion.","summary":deepcopy(summary)}
    graph["assertions"]=build_assertions(graph);graph["assertion_summary"]=assertion_summary(graph["assertions"])
    value={"format":FORMAT,"source_kind":SOURCE_KIND,"bindings":deepcopy(bindings),"observations":observations,"graph":graph,
        "summary":summary,"limitations":list(LIMITATIONS),"row_ledger":preserved,"source_license":deepcopy(LICENSE)}
    value["content_sha256"]=digest(value)
    return value


def publication_html(evidence):
    """Offline source-publication viewer using the exact saved display fragments.

    No Pharos graph, cohort retrieval, question answer or fidelity measurement is
    fabricated. The ordinary publisher supplies the linked immutable artifacts.
    """
    if evidence.get("format") != FORMAT or evidence.get("source_kind") != SOURCE_KIND:
        raise ValueError("This viewer requires a qualified IntAct source publication.")
    observations=evidence["observations"]
    summary=evidence["summary"]
    pairs={tuple(sorted(o["products"])) for o in observations}
    def link(label,url):
        parsed=urlparse(url)
        if parsed.scheme not in {"http","https"} or not parsed.netloc:
            raise ValueError("Source citations must use explicit HTTP(S) URLs.")
        return '<a href="'+escape(url,quote=True)+'" rel="noreferrer">'+escape(label)+'</a>'
    rows=[];details=[]
    for observation in observations:
        oid=observation["id"];display=observation["display"]
        if display != answer_observation(observation):
            raise ValueError("Saved human-readable display differs from its observation fields.")
        participants={p["side"]:p for p in observation["participants"]}
        rows.append('<tr data-source-observation-id="'+escape(oid,quote=True)+'"><td>'+escape(participants["A"]["product_id"])
            +'<br><span class="small">Experimental role: '+escape(_terms(participants["A"]["experimental_roles"]))+'</span></td>'
            +'<td><a href="#'+escape(oid,quote=True)+'">'+escape(oid)+'</a><br>'
            +escape(observation["assay_status"])+', candidate local review</td><td>'+escape(participants["B"]["product_id"])
            +'<br><span class="small">Experimental role: '+escape(_terms(participants["B"]["experimental_roles"]))+'</span></td></tr>')
        source_file=observation["source_file"]
        expected='source/'+observation["source"]["publication_id"].removeprefix('pubmed:')+'.txt'
        if source_file != expected or not expected.removeprefix('source/').removesuffix('.txt').isdigit():
            raise ValueError("Source viewer requires the exact relative publication file.")
        local='<a href="'+escape(source_file,quote=True)+'">Saved MITAB source file</a>, physical line '+str(observation["source_row"])
        citations=' · '.join(link(item["label"],item["url"]) for item in display["citations"])
        groups=[]
        for group in display["field_groups"]:
            name=group["group"]
            fields=''.join('<tr><td>'+escape(', '.join(str(c) for c in field["columns"]))+'</td><th scope="row">'
                +escape(field["label"])+'</th><td><code>'+escape(field["value"])+'</code></td></tr>' for field in group["fields"])
            groups.append('<section class="field-group" data-field-group="'+escape(name,quote=True)+'"><h3>'
                +escape(name.replace('_',' ').capitalize())+'</h3><p>'+escape(group["text"])
                +'</p><div class="table-scroll"><table><caption>Source MITAB 2.7 fields: '+escape(name.replace('_',' '))
                +'</caption><thead><tr><th scope="col">Column</th><th scope="col">Source field</th><th scope="col">Exact supplied value</th>'
                +'</tr></thead><tbody>'+fields+'</tbody></table></div></section>')
        details.append('<article class="observation" id="'+escape(oid,quote=True)+'" data-observation-id="'
            +escape(oid,quote=True)+'"><h2>'+escape(oid)+'</h2><p><strong>'+escape(observation["study"])
            +'</strong> · '+escape(observation["assay_status"])+' · candidate local review</p><p>'+local+'</p><p class="citations">'
            +citations+'</p>'+''.join(groups)+'</article>')
    limitations=''.join('<li>'+escape(item)+'</li>' for item in evidence["limitations"])
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>IntAct source publication</title><style>'
        'body{font:16px/1.55 system-ui,sans-serif;margin:0;background:#f4f7fa;color:#17313d}'
        'main{max-width:1180px;margin:auto;padding:2rem 1.25rem 4rem}h1{line-height:1.2;font-size:2rem}'
        'h2{font-size:1.35rem;overflow-wrap:anywhere}h3{font-size:1.1rem}a{color:#075a91;text-underline-offset:.15em}'
        'a:focus-visible{outline:3px solid #c36b00;outline-offset:3px}.notice,.observation{background:#fff;border:1px solid #c5d5df;border-radius:8px;padding:1.1rem;margin:1.25rem 0}'
        '.notice{border-left:5px solid #bf760d}.small,caption{font-size:.9rem;color:#425e6b}.table-scroll{overflow-x:auto}'
        'table{width:100%;border-collapse:collapse;background:white;margin:.75rem 0 1.3rem}th,td{border:1px solid #c5d5df;padding:.65rem;text-align:left;vertical-align:top}'
        'thead{background:#e5eef4}caption{text-align:left;padding:.35rem 0;font-weight:600}td code{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.9em}'
        '.field-group{border-top:1px solid #d9e3e9;padding-top:.8rem}.citations{overflow-wrap:anywhere}nav a{display:inline-block;margin:0 .8rem .5rem 0}'
        '</style></head><body><main><h1>IntAct source publication</h1><p class="notice"><strong>'
        'IntAct source publication — not a Pharos-attached run or fidelity score.</strong> This offline viewer explains the supplied curated records. '
        'No Pharos metadata, biological accuracy measurement or independent validation is implied.</p><p>'
        +str(len(observations))+' eligible source observations across '+str(len(pairs))+' unordered protein pairs; '
        +str(summary["source_evidence_rows"])+' source evidence rows and '+str(summary["excluded_evidence"])
        +' excluded evidence rows remain accounted for in the complete '+str(summary["source_physical_rows"])
        +'-row ledger. Excluded RNA or nonhuman evidence is outside this declared task, not an erroneous biological assertion.</p>'
        '<nav aria-label="Publication artifacts"><a href="graph.json">Qualified evidence graph JSON</a>'
        '<a href="evidence.json">Complete evidence publication JSON</a><a href="row_ledger.jsonl">All-row source ledger</a>'
        '<a href="publication.json">Publication receipt</a><a href="LICENSE.md">Source data license</a></nav>'
        '<h2>Qualified evidence graph</h2><p>Each row preserves one source observation: participant A → observation → participant B. '
        'Repeated pairs and reciprocal experimental roles remain separate. The arrows show source-row structure and do not infer biological direction.</p>'
        '<div class="table-scroll"><table><caption>Source-row evidence connections</caption><thead><tr><th scope="col">Participant A</th>'
        '<th scope="col">Qualified observation</th><th scope="col">Participant B</th></tr></thead><tbody>'+''.join(rows)
        +'</tbody></table></div>'+''.join(details)+'<aside aria-label="Interpretation limitations"><h2>Interpretation and reuse</h2><ul>'
        +limitations+'</ul><p>Source data: CC BY 4.0. Attribute IntAct/IMEx, each original source database and publication. '
        'External evidence-ID links are explicitly labeled lookups; lookup availability has not been verified in this offline publication.</p></aside>'
        '</main></body></html>')
