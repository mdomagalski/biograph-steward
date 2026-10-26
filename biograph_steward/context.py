"""Inspectable source context, kept separate from reviewed scientific assertions."""
from .client import digest

NOTES = {
    "go": "Pharos GO annotation with original evidence code and assigning source; not disease-specific.",
    "ppis": "Database-reported interaction between selected cohort proteins; source scores are not calibrated probabilities.",
    "drugs": "Target-linked drug listing in Pharos; no indication, mechanism, variant response or resistance is inferred.",
    "expressions": "Source tissue measurement, including low/absent expression; source scales are not combined or compared.",
    "publications": "Target-linked publication discovery; this paper is not automatically evidence for a disease or therapy claim.",
}


def context_records(snapshot, quarantine=None):
    groups = {}
    for i, target in enumerate(snapshot["targets"]):
        if not isinstance(target, dict):
            continue
        accession = target.get("uniprot") if isinstance(target.get("uniprot"), str) else ""
        context = target.get("pharos_context", {})
        if not isinstance(context, dict):
            if quarantine is not None:
                quarantine.append({"reason": "malformed_pharos_context", "locator": f"snapshot.json#/targets/{i}/pharos_context", "record": context})
            continue
        for family, note in NOTES.items():
            values = context.get(family, [])
            if not isinstance(values, list):
                if quarantine is not None:
                    quarantine.append({"reason": "malformed_context_list", "locator": f"snapshot.json#/targets/{i}/pharos_context/{family}", "record": values})
                continue
            for j, record in enumerate(values):
                locator = f"snapshot.json#/targets/{i}/pharos_context/{family}/{j}"
                # Exact duplicate rows share one context entry while every source
                # locator and original row remain available. No semantic merging.
                key = digest({"uniprot": target.get("uniprot", ""), "family": family, "record": record})
                if key in groups:
                    groups[key]["record_locators"].append(locator)
                    continue
                fields = record if isinstance(record, dict) else {}
                label = (fields.get("term") if family == "go" else
                         (fields.get("target") if isinstance(fields.get("target"), dict) else {}).get("sym") if family == "ppis" else
                         fields.get("name") if family == "drugs" else
                         fields.get("tissue") if family == "expressions" else fields.get("title"))
                source = (fields.get("assigned_by") if family == "go" else
                          fields.get("type") if family in {"ppis", "expressions"} else "Pharos")
                groups[key] = {"id": "context:" + key[:24], "subject": "UniProtKB:" + accession,
                               "symbol": target.get("sym"), "family": family, "label": label,
                               "source": source, "record": record, "record_locators": [locator],
                               "snapshot_sha256": snapshot["content_sha256"],
                               "interpretation": note, "review_status": "unreviewed_context"}
    return sorted(groups.values(), key=lambda r: (r["symbol"] or "", r["family"], r["id"]))


def attach_response_provenance(records, snapshot, *, families=None):
    """Link retained context to exact raw response rows, including cache times."""
    lookup = {}
    for entry in records:
        entry['source_response_locators'] = []
        uid = entry['subject'].removeprefix('UniProtKB:')
        lookup.setdefault((uid, entry['family'], digest(entry['record'])), []).append(entry)
    envelopes = snapshot.get('requests', [])
    coverage = snapshot.get('retrieval', {}).get('context', {})
    for row in coverage.get('targets', []):
        if row['family'] not in (NOTES if families is None else families):
            continue
        for page in row.get('pages', []):
            index = page['request_index']
            if not isinstance(index, int) or not 0 <= index < len(envelopes):
                continue
            envelope = envelopes[index]
            pointer = page['response_pointer']
            value = envelope['response']
            try:
                for part in pointer.strip('/').split('/'):
                    value = value[int(part)] if isinstance(value, list) else value[part]
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if not isinstance(value, list):
                continue
            for j, raw in enumerate(value):
                matches = lookup.get((row['uniprot'], row['family'], digest(raw)), [])
                for entry in matches:
                    entry['source_response_locators'].append({
                        'request_index': index, 'response_pointer': pointer + '/' + str(j),
                        'response_sha256': envelope['response_sha256'], 'retrieved_at': envelope['retrieved_at'],
                        'loaded_from_cache': envelope.get('loaded_from_cache', False)})
