"""Synthetic workflow fixture. Never a Pharos download or biomedical result."""
from copy import deepcopy
from .client import digest, utcnow


def demo_snapshot() -> dict:
    def detail(source="SYNTHETIC_SOURCE_A", reference="DEMO:REF-001", **kw):
        return {"name": "Demo colorectal cancer", "dataType": "synthetic_association",
                "evidence": "Invented solely to demonstrate the pipeline. Not scientific evidence.",
                "reference": reference, "source": source, "score": None, "conf": None,
                "zscore": None, "log2foldchange": None, "pvalue": None, **kw}
    def pathway(number, name):
        return {"pwid": number, "name": name + " (synthetic)", "type": "SYNTHETIC_PATHWAYS",
                "sourceID": f"DEMO:PATHWAY-{number}", "url": None}
    a = pathway(101, "Pathway Alpha")
    b = pathway(102, "Pathway Beta")
    c = pathway(103, "Pathway Gamma")
    d = pathway(104, "Pathway Delta")
    paths = [[a, b], [a, c], [b, c], [c, d], [d], [a, d]]
    levels = ["Tclin", "Tchem", "Tbio", "Tbio", "Tdark", "Tdark"]
    targets = []
    for i, (tdl, pws) in enumerate(zip(levels, paths), 1):
        records = [detail(reference=f"DEMO:REF-{i:03d}")]
        if i == 1:
            records += [detail("SYNTHETIC_SOURCE_B", "DEMO:REF-101", score=0.0)]
        if i == 4:
            records = [detail(source=None, reference=None)]
        if i == 5:
            records = []
        if i == 6:
            records = [detail(name="Demo rectal cancer", reference="DEMO:REF-006")]
        targets.append({"uniprot": f"DEMO_PROTEIN_{i:03d}", "sym": f"DEMO_P{i}",
                        "name": f"Synthetic protein {i}", "tdl": tdl, "fam": "DEMO_FAMILY",
                        "diseaseAssociationDetails": records, "pathways": pws})
    targets.append(deepcopy(targets[0]))
    targets.append({"uniprot": None, "sym": "DEMO_BAD", "name": "Intentionally invalid row",
                    "tdl": "Tbio", "diseaseAssociationDetails": [detail()], "pathways": []})
    snapshot = {
        "snapshot_format": "biograph-steward.pharos.v1", "data_kind": "synthetic_demo",
        "created_at": utcnow(), "endpoint": None, "db_version": None,
        "disease": {"name": "Demo colorectal cancer", "mondoID": "DEMO:DISEASE-CRC",
                    "associationCount": None, "directAssociationCount": None,
                    "mondoDescription": "Synthetic data for software demonstration only.", "dids": []},
        "targets": targets, "requests": [], "source_licenses": [],
        "schema_check": {"status": "synthetic_fixture_only"},
        "query_settings": {"max_targets": 8, "page_size": 8, "pathway_top": 5},
        "retrieval": {"total_targets_reported": 8, "records_retrieved": 8, "truncated": False, "pages": []},
        "warnings": ["SYNTHETIC DEMONSTRATION: all proteins, associations, pathways, scores and sources are invented.",
                     "This run is not Pharos data, not a benchmark and not scientific evidence."],
    }
    snapshot["content_sha256"] = digest(snapshot)
    return snapshot
