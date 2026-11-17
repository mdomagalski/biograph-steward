"""Shared invented native source bytes; never biological truth fixtures."""
from copy import deepcopy
import hashlib
import json

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from biograph_steward.go_qualification import GAF_FIELDS, native_record


WHEN = "2026-01-01T00:00:00+00:00"
IPR = "IPR999999"
SEQUENCE = "M" + "A" * 37 + "XU"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def match_rows():
    """One shared accession, distinct origins, a discontinuous hit and sites."""
    regular = {
        "signature": {"accession": "PF99999", "name": "INVENTED", "description": "Invented domain",
            "type": "Domain", "signatureLibraryRelease": {"library": "Pfam", "version": "39.0"},
            "entry": {"accession": IPR, "name": "INVENTED", "description": "Invented class",
                      "type": "Domain", "parent": None}},
        "model-ac": None, "source": "Pfam", "score": 11.2, "evalue": 0.0001,
        "locations": [{"start": 2, "end": 20, "location-fragments": [
            {"start": 2, "end": 8, "dc-status": "C_TERMINAL_DISC"},
            {"start": 15, "end": 20, "dc-status": "N_TERMINAL_DISC"}],
            "hmmStart": 1, "hmmEnd": 13, "hmmLength": 15, "score": 11.2,
            "evalue": 0.0001, "sites": None}],
    }
    neural = deepcopy(regular)
    neural.update({"source": "InterPro-N", "score": None, "evalue": None})
    neural["signature"]["signatureLibraryRelease"]["version"] = "37.3"
    neural["signature"]["entry"] = None
    neural["signature"]["type"] = None
    neural["locations"] = [{"start": 3, "end": 19, "location-fragments": [
        {"start": 3, "end": 19, "dc-status": "CONTINUOUS"}]}]
    sites = deepcopy(regular)
    sites.update({"source": "PIRSR", "score": None, "evalue": None})
    sites["signature"].update({"accession": "PIRSR999999-1", "entry": None, "type": None,
        "signatureLibraryRelease": {"library": "PIRSR", "version": "2025_05"}})
    sites["locations"] = [{"start": 2, "end": 20, "location-fragments": [
        {"start": 2, "end": 20, "dc-status": "CONTINUOUS"}], "sites": [
            {"description": "INVENTED residue context", "numLocations": 2,
             "siteLocations": [{"start": 3, "end": 3, "residue": "A"},
                               {"start": 18, "end": 18, "residue": "A"}]}]}]
    return [regular, neural, sites]


class ContractPacket:
    """Write native-shaped bytes independently of the context producer."""
    def __init__(self, root, protein, *, sequence=SEQUENCE, found=True, matches=None, name="context"):
        self.root, self.protein = root, protein
        self.folder = root / name
        self.folder.mkdir()
        self.accession = protein.split(":", 1)[1]
        normalized = "".join(sequence.split()).upper() if isinstance(sequence, str) else None
        md5 = hashlib.md5(normalized.encode()).hexdigest().upper() if normalized else None
        self.matches = match_rows() if matches is None else deepcopy(matches)
        target = {"uniprot": self.accession, "sym": "INVENTED", "name": "Invented protein",
                  "seq": sequence, "interpro": [{"source": "InterPro", "name": IPR, "value": "INVENTED"},
                      {"source": "InterPro", "name": "IPR888888", "value": "INVENTED OTHER"}],
                  "pfam": [{"source": "Pfam", "name": "PF99999", "value": "INVENTED"}],
                  "prosite": [], "smart": [], "panther": [], "sequence_annotations": []}
        response = {"data": {"target": target, "dbVersion": "INVENTED-V1"}}
        pharos = {"endpoint": "https://pharos-api.ncats.io/graphql",
            "request": {"query": "query Invented($uniprot: String!) { target { uniprot seq } }",
                        "variables": {"uniprot": self.accession}},
            "retrieved_at": WHEN, "response": response, "response_sha256": digest(response),
            "loaded_from_cache": False}
        tool = {"name": "matchSequences", "description": "Invented recorded schema",
                "inputSchema": {"type": "object", "properties": {"sequencesOrMd5s": {"type": "string"}},
                                "required": ["sequencesOrMd5s"]}}
        info = {"api": "0.6.0", "release": "111.0", "release_date": "2026-01-01",
                "analyses": [{"name": "Pfam", "version": "39.0"},
                             {"name": "InterPro-N", "version": "105.0"},
                             {"name": "PIRSR", "version": "2025_05"}]}
        files = {"pharos/" + self.accession + ".json": pharos,
                 "interpro/info_before.json": info, "interpro/info_after.json": deepcopy(info),
                 "interpro/tools.json": {"jsonrpc": "2.0", "id": 1, "result": {"tools": [tool]}},
                 "source_requests.json": {"requests": []}}
        match_file = "interpro/matches_000.json" if normalized else None
        if normalized:
            payload = {"results": [{"md5": md5.lower(), "found": found,
                                     "matches": self.matches if found else []}]}
            files[match_file] = {"jsonrpc": "2.0", "id": 2, "result": {"isError": False,
                "content": [{"type": "text", "text": json.dumps(payload)}]}}
        for relative, value in files.items():
            dump(self.folder / relative, value)
        if normalized:
            (self.folder / "interpro/matches_000.raw").write_bytes((self.folder / match_file).read_bytes())
        (self.folder / "DATA_TERMS.md").write_text("Invented local fixture; no provider data.\n")
        self.manifest = {"format": "biograph-steward.protein-context.v1", "created_at": WHEN,
            "proteins": [{"protein": protein, "pharos_file": "pharos/" + self.accession + ".json",
                "matches_file": match_file, "query_md5": md5,
                "sequence_sha256": hashlib.sha256(normalized.encode()).hexdigest() if normalized else None,
                "sequence_length": len(normalized) if normalized else None,
                "status": "sequence_available" if normalized else "sequence_unavailable"}],
            "info_before_file": "interpro/info_before.json", "info_after_file": "interpro/info_after.json",
            "tools_file": "interpro/tools.json", "requests_file": "source_requests.json",
            "tool_name": "matchSequences", "tool_schema_sha256": digest(tool),
            "source_code": {"official_mcp_commit": "ceb9b2177a5f8861634972fb8b2eacff64702890",
                            "official_client_sha256": "a" * 64, "producer_sha256": "b" * 64},
            "attribution": {"note": "Invented data only"}, "files": {},
            "source_scope": "current_retrieved_sequence_context", "app_or_graph_changed": False,
            "scientific_accuracy_assessed": False, "historical_pharos_record_identity_established": False,
            "model_calls": 0}
        self.seal()

    def seal(self):
        self.manifest["files"] = {p.relative_to(self.folder).as_posix():
            {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in self.folder.rglob("*") if p.is_file() and p.name != "protein_context.json"}
        self.manifest.pop("content_sha256", None)
        self.manifest["content_sha256"] = digest(self.manifest)
        dump(self.folder / "protein_context.json", self.manifest)
        self.pin = sha(self.folder / "protein_context.json")
        dump(self.root / "protein_context_index.json", {"format": "biograph-steward.protein-context-index.v1",
            "contexts": [{"id": self.folder.name, "manifest_sha256": self.pin}]})

    def change_json(self, relative, mutate):
        path = self.folder / relative
        value = json.loads(path.read_text())
        mutate(value)
        dump(path, value)
        self.seal()

    def change_matches(self, mutate):
        path = self.folder / "interpro/matches_000.json"
        rpc = json.loads(path.read_text())
        payload = json.loads(rpc["result"]["content"][0]["text"])
        mutate(payload)
        rpc["result"]["content"][0]["text"] = json.dumps(payload)
        dump(path, rpc)
        (self.folder / "interpro/matches_000.raw").write_bytes(path.read_bytes())
        self.seal()

    def add_entries(self, entries):
        requests_path = self.folder / "source_requests.json"
        requests = json.loads(requests_path.read_text())["requests"]
        self.manifest["entry_files"] = {}
        for identifier, (status, body) in entries.items():
            relative = "interpro/entries/" + identifier + ".json"
            requests = [row for row in requests if row.get("response_file") != relative]
            dump(self.folder / relative, body)
            self.manifest["entry_files"][identifier] = relative
            requests.append({"provider": "InterPro", "response_file": relative,
                "http_status": status, "method": "GET",
                "url": "https://www.ebi.ac.uk/interpro/api/entry/interpro/" + identifier + "/?format=json",
                "file_sha256": sha(self.folder / relative), "completed_at": WHEN})
        dump(requests_path, {"requests": requests})
        self.seal()


def write_packet(folder, proteins=None, **kwargs):
    """Return a source-bound packet at ``folder`` and register its parent.

    ``proteins`` is an ordered list of exact UniProtKB CURIEs, a single CURIE,
    or omitted (invented P04637). All supplied identifiers deliberately share
    the same invented sequence; the one native MD5 result remains reusable
    without collapsing those protein identities. ``kwargs`` accepts the
    ContractPacket sequence/found/matches fixture options.
    """
    if proteins is None:
        proteins = ["UniProtKB:P04637"]
    elif isinstance(proteins, str):
        proteins = [proteins]
    if not proteins or len(set(proteins)) != len(proteins):
        raise ValueError("Provide distinct invented fixture protein CURIEs.")
    packet = ContractPacket(folder.parent, proteins[0], name=folder.name, **kwargs)
    packet.proteins = tuple(proteins)
    source = json.loads((packet.folder / packet.manifest["proteins"][0]["pharos_file"]).read_text())
    for protein in proteins[1:]:
        accession = protein.split(":", 1)[1]
        item = deepcopy(source)
        item["request"]["variables"]["uniprot"] = accession
        item["response"]["data"]["target"]["uniprot"] = accession
        item["response_sha256"] = digest(item["response"])
        relative = "pharos/" + accession + ".json"
        dump(packet.folder / relative, item)
        row = deepcopy(packet.manifest["proteins"][0])
        row.update(protein=protein, pharos_file=relative)
        packet.manifest["proteins"].append(row)
    packet.seal()
    return packet


def native_go(protein, term, graph, selection):
    """Use the established row wrapper; this is not a second GAF parser."""
    accession = protein.split(":", 1)[1]
    rows = []
    for number, qualifier, form in ((8, "enables", ""), (9, "NOT|enables", protein + "-2")):
        fields = ["UniProtKB", accession, "INVENTED", qualifier, term,
            "GO_REF:0000002", "IEA", "InterPro:" + IPR + ",UniProtKB:P00002|InterPro:IPR888888|InterPro:" + IPR,
            "F", "Invented", "", "protein", "taxon:9606|taxon:10090", "20260101", "InterPro",
            "occurs_in(CL:0000001),part_of(GO:0000002)|occurs_in(CL:0000003)", form]
        parsed = dict(zip(GAF_FIELDS, fields))
        for key in ("Qualifier", "DB:Reference", "With", "Synonym", "Taxon_ID"):
            parsed[key] = parsed[key].split("|") if parsed[key] else []
        rows.append(native_record(number, "\t".join(fields), fields, parsed, "c" * 64))
    value = {"format": "biograph-steward.native-go-selection.v1", "read_only": True,
        "source_run": "run", "selection_id": selection, "snapshot_sha256": graph["snapshot_sha256"],
        "query": {"protein": protein, "go_id": term}, "records": rows, "record_count": len(rows),
        "source_bytes_and_native_scope_verified": True}
    value["content_sha256"] = digest(value)
    return value
