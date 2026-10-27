"""Conservative primary-identifier correspondence in the published SSSOM 1.0 subset.

This is a bounded producer, not a general SSSOM parser or validator. The official
``sssom`` package validates exported artifacts in a separate optional environment.
Correspondence means that two source records explicitly use the same UniProtKB
identifier. It establishes neither experiment independence nor sequence, isoform,
construct, gene/protein, or assay equivalence. Source graph versions below are not
asserted to be UniProt release versions.

References: https://mapping-commons.github.io/sssom/1.0/spec-model/ and
https://mapping-commons.github.io/sssom/1.0/spec-formats-tsv/
"""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
from datetime import date
import hashlib
from io import StringIO
import json
from urllib.parse import urlsplit

from .graph import UNIPROT


FORMAT = "biograph-steward.primary-identifier-correspondence.v1"
SSSOM_SPEC = "https://mapping-commons.github.io/sssom/1.0/"
TOOL_VERSION = "1"
COLUMNS = (
    "subject_id", "predicate_id", "object_id", "mapping_justification",
    "subject_source", "subject_source_version", "object_source",
    "object_source_version", "subject_match_field", "object_match_field",
    "match_string", "mapping_date", "mapping_tool", "mapping_tool_version",
    "see_also", "comment",
)
CURIE_MAP = {
    "UniProtKB": "http://purl.uniprot.org/uniprot/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "dcterms": "http://purl.org/dc/terms/",
    "HTTPSIRI": "https://",
    "HTTPIRI": "http://",
    "URNIRI": "urn:",
}
DESCRIPTION = (
    "Exact, source-explicit primary UniProtKB identifier correspondence between "
    "baseline and added endpoint records. Resource source/version slots identify "
    "the supplying source graph and its release, not the UniProt identifier "
    "registry release. Selfsame CURIE identity is not evidence, experiment, "
    "sequence, proteoform, construct or gene/protein equivalence. No identifier "
    "remapping, synonym matching or isoform collapse is performed. The mapping "
    "set license applies to the generated correspondence assertions; it does "
    "not relicense upstream records, which retain their own source terms."
)


def _text(value, name):
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or any(ord(c) < 32 for c in value)):
        raise ValueError(name + " must be a nonempty string without surrounding whitespace or controls.")
    return value


def _uri(value, name):
    value = _text(value, name)
    parsed = urlsplit(value)
    if ("|" in value or any(c.isspace() for c in value)
            or parsed.scheme not in {"https", "http", "urn"}
            or (parsed.scheme in {"http", "https"} and not parsed.netloc)
            or (parsed.scheme == "urn" and not parsed.path)):
        raise ValueError(name + " must be an absolute HTTP(S) or URN identifier.")
    return value


def _reference(uri):
    """Contract an explicit URI using declared prefixes; invent no resource URI."""
    scheme, local = uri.split(":", 1)
    return ({"https": "HTTPSIRI:", "http": "HTTPIRI:", "urn": "URNIRI:"}[scheme]
            + (local[2:] if scheme in {"http", "https"} else local))


def _identity(endpoint):
    if endpoint.get("entity_type") != "protein":
        return None, "unsupported_entity_type"
    if endpoint.get("identity_role") != "source_primary":
        return None, "identity_not_source_primary"
    primary = endpoint.get("primary_ids")
    if not isinstance(primary, list) or not primary:
        return None, "missing_primary_identifier"
    if any(not isinstance(value, str) for value in primary):
        return None, "invalid_primary_identifier"
    if len(set(primary)) != 1:
        return None, "ambiguous_primary_identifiers"
    value = primary[0]
    if not value.startswith("UniProtKB:") or not UNIPROT.fullmatch(value[len("UniProtKB:"):]):
        return None, "unsupported_primary_identifier"
    return value, None


def _record_id(subject, obj):
    raw = json.dumps([subject, obj], sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    return "urn:sha256:" + hashlib.sha256(raw).hexdigest()


def build_mapping_set(endpoints, *, mapping_set_id, mapping_set_version,
                      license_url, mapping_date):
    """Return standard SSSOM rows, stable record links and unresolved endpoints.

    Each endpoint has ``endpoint_id``, ``role`` (baseline/added), ``resource_id``
    (absolute URI of the supplying graph), ``resource_version``,
    ``record_locator`` (absolute URI, including content-addressed URNs),
    ``primary_ids`` (list), ``entity_type`` (protein), and ``identity_role``
    (source_primary). Other source metadata is retained in unresolved records.
    Invalid framing is an error; unsupported or ambiguous identities are retained
    as unresolved. Only baseline-to-added matches are produced.

    ``mapping_records`` is an application sidecar, not invented SSSOM columns.
    SSSOM ``record_id`` is deliberately not used: it belongs to the 1.1 draft.
    No NoTermFound assertion is made: a bounded input lacks registry-wide scope.
    """
    _uri(mapping_set_id, "mapping_set_id")
    _uri(license_url, "license_url")
    _text(mapping_set_version, "mapping_set_version")
    if not isinstance(mapping_date, str) or date.fromisoformat(mapping_date).isoformat() != mapping_date:
        raise ValueError("mapping_date must be an ISO calendar date.")
    if not isinstance(endpoints, list):
        raise ValueError("endpoints must be an explicit list.")
    endpoints = deepcopy(endpoints)
    index, valid, unresolved = {}, defaultdict(lambda: defaultdict(list)), []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            raise ValueError("Each endpoint must be an object.")
        endpoint_id = _text(endpoint.get("endpoint_id"), "endpoint_id")
        if endpoint_id in index:
            raise ValueError("Endpoint identifiers must be unique.")
        if endpoint.get("role") not in {"baseline", "added"}:
            raise ValueError("Endpoint role must be baseline or added.")
        _uri(endpoint.get("resource_id"), "resource_id")
        _text(endpoint.get("resource_version"), "resource_version")
        _uri(endpoint.get("record_locator"), "record_locator")
        index[endpoint_id] = endpoint
        identifier, reason = _identity(endpoint)
        if reason:
            unresolved.append({"endpoint_id": endpoint_id, "reason": reason,
                               "endpoint": deepcopy(endpoint)})
        else:
            valid[identifier][endpoint["role"]].append(endpoint)
    mappings, records, matched = [], [], set()
    for identifier, roles in sorted(valid.items()):
        for subject in sorted(roles["baseline"], key=lambda value: value["endpoint_id"]):
            for obj in sorted(roles["added"], key=lambda value: value["endpoint_id"]):
                mapping_id = _record_id(subject, obj)
                context = {"mapping_id": mapping_id,
                           "subject_endpoint_id": subject["endpoint_id"],
                           "object_endpoint_id": obj["endpoint_id"],
                           "subject_record_locator": subject["record_locator"],
                           "object_record_locator": obj["record_locator"],
                           "scope": "source_primary_identifier_correspondence_only"}
                mappings.append({
                    "subject_id": identifier, "predicate_id": "owl:sameAs",
                    "object_id": identifier, "mapping_justification": "semapv:LexicalMatching",
                    "subject_source": _reference(subject["resource_id"]),
                    "subject_source_version": subject["resource_version"],
                    "object_source": _reference(obj["resource_id"]),
                    "object_source_version": obj["resource_version"],
                    "subject_match_field": "dcterms:identifier",
                    "object_match_field": "dcterms:identifier", "match_string": identifier,
                    "mapping_date": mapping_date, "mapping_tool": "BioGraph Steward exact primary identifier equality",
                    "mapping_tool_version": TOOL_VERSION,
                    # see_also is NonRelativeURI, not EntityReference: retain IRIs.
                    "see_also": sorted({subject["record_locator"], obj["record_locator"]}),
                    "comment": json.dumps(context, sort_keys=True, ensure_ascii=False),
                })
                records.append({**context, "subject_id": identifier, "object_id": identifier})
                matched.update((subject["endpoint_id"], obj["endpoint_id"]))
    for roles in valid.values():
        for group in roles.values():
            for endpoint in group:
                if endpoint["endpoint_id"] not in matched:
                    unresolved.append({"endpoint_id": endpoint["endpoint_id"],
                                       "reason": "no_exact_counterpart_in_supplied_endpoints",
                                       "endpoint": deepcopy(endpoint)})
    unresolved.sort(key=lambda value: value["endpoint_id"])
    return {"format": FORMAT,
            "metadata": {"curie_map": dict(CURIE_MAP), "mapping_set_id": mapping_set_id,
                         "mapping_set_version": mapping_set_version, "license": license_url,
                         "mapping_set_description": DESCRIPTION},
            "mappings": mappings, "mapping_records": records, "unresolved": unresolved,
            "summary": {"input_endpoints": len(endpoints), "matched_endpoints": len(matched),
                        "mapping_rows": len(mappings), "unresolved_endpoints": len(unresolved),
                        "unresolved_reasons": dict(sorted(Counter(row["reason"] for row in unresolved).items())),
                        "identity_scope": "exact_source_primary_UniProtKB_CURIE_only",
                        "sssom_specification": SSSOM_SPEC,
                        "full_sssom_validation_performed": False,
                        "biological_equivalence_or_evidence_independence_measured": False}}


def serialize_mapping_set(value):
    """Serialize this producer's output as embedded-metadata SSSOM/TSV bytes.

    JSON scalar/object syntax is valid YAML 1.2, avoiding a YAML runtime dependency.
    This serializes the bounded producer's shape; it is not a conformance test.
    """
    if not isinstance(value, dict) or value.get("format") != FORMAT:
        raise ValueError("Expected this producer's primary identifier mapping set.")
    output = StringIO(newline="")
    for key, item in value["metadata"].items():
        output.write("# " + key + ": " + json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    writer = csv.DictWriter(output, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for original in value["mappings"]:
        row = dict(original)
        row["see_also"] = "|".join(row["see_also"])
        writer.writerow(row)
    return output.getvalue().encode("utf-8")
