"""Synthetic integration guards; no public reference or reserved artifact access."""
from copy import deepcopy
import hashlib
import unittest

from biograph_steward.client import digest
from biograph_steward.intact_evidence import build_evidence, answer_observation, publication_html


def term(identifier, name):
    return {"mi_id":identifier,"mod_id":None,"par_id":None,"name":name,"full_name":name}


def identifier(database, value):
    return {"database":term(None,database),"id":value,"version":None,"qualifier":term("MI:0356","identity")}


def fixture():
    pmid="40075158"
    raw=["-"]*42
    entries={
        "primary_ids_a":(1,"uniprotkb:P04637",[identifier("uniprotkb","P04637")]),
        "primary_ids_b":(2,"uniprotkb:P00533",[identifier("uniprotkb","P00533")]),
        "alternative_ids_a":(3,"intact:EBI-SYNTHETIC-A",[identifier("intact","EBI-SYNTHETIC-A")]),
        "alternative_ids_b":(4,"-",[]),
        "taxa_a":(10,"taxid:9606(human)",[{"taxid":9606,"common_name":"human","scientific_name":None}]),
        "taxa_b":(11,"taxid:9606(human)",[{"taxid":9606,"common_name":"human","scientific_name":None}]),
        "biological_roles_a":(17,'psi-mi:"MI:0499"(unspecified role)',[term("MI:0499","unspecified role")]),
        "biological_roles_b":(18,'psi-mi:"MI:0499"(unspecified role)',[term("MI:0499","unspecified role")]),
        "experimental_roles_a":(19,'psi-mi:"MI:0498"(prey)',[term("MI:0498","prey")]),
        "experimental_roles_b":(20,'psi-mi:"MI:0496"(bait)',[term("MI:0496","bait")]),
        "interactor_types_a":(21,'psi-mi:"MI:0326"(protein)',[term("MI:0326","protein")]),
        "interactor_types_b":(22,'psi-mi:"MI:0326"(protein)',[term("MI:0326","protein")]),
        "identification_methods_a":(41,'psi-mi:"MI:0113"(western blot)',[term("MI:0113","western blot")]),
        "identification_methods_b":(42,'psi-mi:"MI:0113"(western blot)',[term("MI:0113","western blot")]),
        "detection_methods":(7,'psi-mi:"MI:0006"(anti bait coimmunoprecipitation)',[term("MI:0006","anti bait coimmunoprecipitation")]),
        "publication_ids":(9,"pubmed:"+pmid+"|imex:IM-SYNTHETIC",[identifier("pubmed",pmid),identifier("imex","IM-SYNTHETIC")]),
        "interaction_types":(12,'psi-mi:"MI:0915"(physical association)',[term("MI:0915","physical association")]),
        "source_databases":(13,'psi-mi:"MI:0471"(MINT)',[term("MI:0471","MINT")]),
        "evidence_ids":(14,"intact:EBI-SYNTHETIC|imex:IM-SYNTHETIC-1",[identifier("intact","EBI-SYNTHETIC"),identifier("imex","IM-SYNTHETIC-1")]),
        "complex_expansion":(16,"-",[]),
        "interaction_annotations":(28,"figure legend:Synthetic Fig 1",[{"topic":term(None,"figure legend"),"value":"Synthetic Fig 1"}]),
        "host_taxa":(29,"taxid:9606(Synthetic host 1)|taxid:9606(Synthetic host 2)",[
            {"taxid":9606,"common_name":"Synthetic host 1","scientific_name":None},
            {"taxid":9606,"common_name":"Synthetic host 2","scientific_name":None}]),
    }
    fields={}
    for name,(column,text,values) in entries.items():
        raw[column-1]=text
        fields[name]={"column":column,"raw":text,"status":"missing" if text=="-" else "parsed","values":values,"diagnostics":[]}
    raw[35]="false";raw[38]="0"
    row={"line_number":2,"raw_line":"\t".join(raw),"raw_cells":raw,"row_status":"parsed","parsed_count":1,"diagnostics":[],"source_fields":fields,
        "interaction":{"negative":False,"participants":[{"side":"A","features":[],"stoichiometry":{"min":0,"max":0}}, {"side":"B","features":[],"stoichiometry":None}]}}
    source_sha="a"*64
    wrapper={"publication_id":"pubmed:"+pmid,"artifact_sha256":source_sha,"source_file":"source/"+pmid+".txt","reader_file":"reader/"+pmid+".jsonl","reader_record":row}
    ledger={"publication_id":"pubmed:"+pmid,"artifact_sha256":source_sha,"release":"2026-10-17","source_line":2,
        "raw_row_sha256":hashlib.sha256(row["raw_line"].encode()).hexdigest(),"kind":"evidence","eligible":True,"exclusion_reasons":[]}
    bindings={"protocol_sha256":"c"*64,"amendment_sha256":"d"*64,"result_sha256":"e"*64,"ledger_sha256":"f"*64,
        "source_sha256":{pmid:source_sha},"reader_sha256":{pmid:"b"*64}}
    return [wrapper],[ledger],bindings


def rebind(wrapper, ledger):
    row=wrapper["reader_record"]
    row["raw_line"]="\t".join(row["raw_cells"])
    ledger["raw_row_sha256"]=hashlib.sha256(row["raw_line"].encode()).hexdigest()


class IntactEvidenceTests(unittest.TestCase):
    def test_full_source_and_readable_groups_survive_without_mutating_inputs(self):
        records,ledger,bindings=fixture();before=deepcopy((records,ledger,bindings))
        value=build_evidence(records,ledger,bindings);row=value["observations"][0]
        self.assertEqual((records,ledger,bindings),before)
        self.assertEqual(row["raw_cells"],records[0]["reader_record"]["raw_cells"])
        self.assertEqual(row["source_fields"],records[0]["reader_record"]["source_fields"])
        self.assertEqual([p["side"] for p in row["participants"]],["A","B"])
        self.assertEqual(row["participants"][0]["experimental_roles"][0]["name"],"prey")
        self.assertIn("Synthetic host 2",row["display"]["text"])
        self.assertIn("MINT",row["display"]["text"])
        self.assertIn("imex:IM-SYNTHETIC-1",row["display"]["text"])
        self.assertIn("positive interaction evidence",row["display"]["text"])
        self.assertIn("binary experimental origin is unknown",row["display"]["text"])
        self.assertEqual({c for group in row["display"]["field_groups"] for f in group["fields"] for c in f["columns"]},set(range(1,43)))
        self.assertTrue(all(isinstance(f["value"],str) for g in row["display"]["field_groups"] for f in g["fields"]))
        self.assertEqual(row["display"],answer_observation(row))
        self.assertEqual(value["graph"]["assertions"][0]["lifecycle_state"],"candidate")
        self.assertEqual(value["content_sha256"],digest({k:v for k,v in value.items() if k!="content_sha256"}))

    def test_excluded_rows_preserved_but_never_empty_product_observations(self):
        records,ledger,bindings=fixture();ledger[0]["eligible"]=False;ledger[0]["exclusion_reasons"]=["outside_primary_task"]
        value=build_evidence(records,ledger,bindings)
        self.assertEqual(value["observations"],[])
        self.assertEqual(value["graph"]["edges"],[])
        self.assertEqual(value["row_ledger"][0]["reader_record"],records[0]["reader_record"])
        self.assertEqual(value["summary"]["source_evidence_rows"],1)
        self.assertEqual(value["summary"]["excluded_evidence"],1)

    def test_negative_default_and_explicit_negative_keep_source_qualification(self):
        for literal,expected,origin in [("-",False,"mitab27_default_false"),("true",True,"explicit")]:
            records,ledger,bindings=fixture();records[0]["reader_record"]["raw_cells"][35]=literal
            records[0]["reader_record"]["interaction"]["negative"]=expected;rebind(records[0],ledger[0])
            row=build_evidence(records,ledger,bindings)["observations"][0]
            self.assertEqual(row["qualifications"]["negative"],{"literal":literal,"value":expected,"origin":origin})
            self.assertEqual(row["assay_status"],"curated_negative" if expected else "curated_positive")
            self.assertFalse(row["qualifications"]["direct_binding_inferred"])

    def test_same_pair_rows_and_homomers_are_not_collapsed(self):
        records,ledger,bindings=fixture();copy=deepcopy(records[0]);copy["reader_record"]["line_number"]=3
        second=deepcopy(ledger[0]);second["source_line"]=3
        value=build_evidence(records+[copy],ledger+[second],bindings)
        self.assertEqual(len(value["observations"]),2)
        self.assertEqual(len(value["graph"]["assertions"]),2)
        self.assertNotEqual(value["observations"][0]["id"],value["observations"][1]["id"])
        records,ledger,bindings=fixture();r=records[0]["reader_record"]
        r["raw_cells"][1]="uniprotkb:P04637";r["source_fields"]["primary_ids_b"]["raw"]=r["raw_cells"][1]
        r["source_fields"]["primary_ids_b"]["values"]=[identifier("uniprotkb","P04637")];rebind(records[0],ledger[0])
        self.assertEqual(build_evidence(records,ledger,bindings)["observations"][0]["products"],["UniProtKB:P04637"]*2)

    def test_source_or_raw_mismatch_and_ambiguous_primary_ids_rejected(self):
        for mutation in ("raw","hash","ambiguous","missing_type","duplicate"):
            records,ledger,bindings=fixture()
            if mutation=="raw": records[0]["reader_record"]["raw_cells"][0]="uniprotkb:P15056"
            if mutation=="hash": records[0]["artifact_sha256"]="0"*64
            if mutation=="ambiguous": records[0]["reader_record"]["source_fields"]["primary_ids_a"]["values"].append(identifier("uniprotkb","P15056"))
            if mutation=="missing_type": records[0]["reader_record"]["source_fields"]["interactor_types_a"]["values"]=[]
            if mutation=="duplicate": records*=2;ledger*=2
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): build_evidence(records,ledger,bindings)

    def test_reserved_publication_rejected_even_if_other_fields_are_valid(self):
        records,ledger,bindings=fixture();records[0]["publication_id"]="pubmed:39833857";ledger[0]["publication_id"]="pubmed:39833857"
        with self.assertRaises(ValueError):build_evidence(records,ledger,bindings)

    def test_publication_viewer_exposes_groups_graph_and_safe_source_links(self):
        records,ledger,bindings=fixture();value=build_evidence(records,ledger,bindings)
        before=deepcopy(value);page=publication_html(value);observation=value["observations"][0]
        self.assertEqual(value,before)
        self.assertIn("not a Pharos-attached run or fidelity score",page)
        self.assertIn('href="graph.json"',page)
        self.assertIn('href="row_ledger.jsonl"',page)
        self.assertIn('href="source/40075158.txt"',page)
        self.assertIn('https://pubmed.ncbi.nlm.nih.gov/40075158/',page)
        self.assertEqual(page.count('data-observation-id="'+observation["id"]+'"'),1)
        self.assertEqual(page.count('data-field-group="'),8)
        for group in observation["display"]["field_groups"]:
            self.assertIn('data-field-group="'+group["group"]+'"',page)
        self.assertIn("Synthetic host 2",page)
        self.assertIn("source-row structure",page)
        self.assertNotIn('<script',page.lower())

    def test_viewer_escapes_source_values_and_rejects_inconsistent_display(self):
        records,ledger,bindings=fixture();row=records[0]["reader_record"]
        row["raw_cells"][14]='<script>alert("untrusted")</script>';rebind(records[0],ledger[0])
        value=build_evidence(records,ledger,bindings);page=publication_html(value)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('<script>',page)
        value["observations"][0]["display"]["field_groups"][0]["text"]="Edited independently"
        with self.assertRaises(ValueError):publication_html(value)


if __name__=="__main__":unittest.main()
