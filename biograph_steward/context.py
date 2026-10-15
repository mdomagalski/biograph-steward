"""Inspectable source context, kept separate from reviewed scientific assertions."""
from .client import digest

NOTES = {
    "go": "Pharos GO annotation with original evidence code and assigning source; not disease-specific.",
    "ppis": "Database-reported interaction between selected cohort proteins; source scores are not calibrated probabilities.",
    "drugs": "Target-linked drug listing in Pharos; no indication, mechanism, variant response or resistance is inferred.",
    "expressions": "Source tissue measurement, including low/absent expression; source scales are not combined or compared.",
    "publications": "Target-linked publication discovery; this paper is not automatically evidence for a disease or therapy claim.",
}


def context_records(snapshot):
    result = []
    for i, target in enumerate(snapshot["targets"]):
        if not isinstance(target, dict):
            continue
        context = target.get("pharos_context", {})
        for family, note in NOTES.items():
            groups = {}
            for j, record in enumerate(context.get(family, [])):
                locator = f"snapshot.json#/targets/{i}/pharos_context/{family}/{j}"
                # Exact duplicate rows share one context entry while every source
                # locator and original row remain available. No semantic merging.
                key = digest({"uniprot": target["uniprot"], "family": family, "record": record})
                if key in groups:
                    groups[key]["record_locators"].append(locator)
                    continue
                label = (record.get("term") if family == "go" else
                         (record.get("target") or {}).get("sym") if family == "ppis" else
                         record.get("name") if family == "drugs" else
                         record.get("tissue") if family == "expressions" else record.get("title"))
                source = (record.get("assigned_by") if family == "go" else
                          record.get("type") if family in {"ppis", "expressions"} else "Pharos")
                groups[key] = {"id": "context:" + key[:24], "subject": "UniProtKB:" + target["uniprot"],
                               "symbol": target.get("sym"), "family": family, "label": label,
                               "source": source, "record": record, "record_locators": [locator],
                               "snapshot_sha256": snapshot["content_sha256"],
                               "interpretation": note, "review_status": "unreviewed_context"}
            result.extend(groups.values())
    return sorted(result, key=lambda r: (r["symbol"] or "", r["family"], r["id"]))
