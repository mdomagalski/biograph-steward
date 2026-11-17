"""Apply explicit reviewed source dispositions without interpreting biology.

This optional, pure helper operates before source support is collapsed into
links. Callers supply parser records and the complete frozen source bytes. It
checks the bytes/release binding and exact reviewed record identities, then
retains unreviewed records and explicit abstentions. It performs no file or
network access, identifier resolution, source rewriting or activity inference.

Row digests use the existing ``biograph_steward.client.digest`` canonical JSON
of the decoded raw row, preserving every supplied string. They are not physical
line hashes. Older caller fields named ``source_row_sha256`` may use another
serialization; this helper never treats those fields as its review binding.
Parser correctness and scientific review remain caller responsibilities.
"""
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import re

from biograph_steward.client import digest


POLICY = "exact-reviewed-source-dispositions.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REVIEW_FIELDS = {"source_release", "source_sha256", "source_record_id",
                  "source_data_record_ordinal", "canonical_source_row_sha256",
                  "disposition", "reason", "method", "actor"}


def _need(condition, message):
    if not condition:
        raise ValueError("Source eligibility: " + message)


def canonical_source_row_digest(raw_row):
    """Digest an unchanged decoded source row using the project's convention."""
    _need(isinstance(raw_row, Mapping) and bool(raw_row)
          and all(isinstance(k, str) and isinstance(v, str) for k, v in raw_row.items()),
          "a nonempty string-valued raw source row is required.")
    return digest(dict(raw_row))


def apply_reviewed_source_dispositions(records, reviews, *, source_release,
                                       source_bytes, source_sha256,
                                       raw_record_id_field,
                                       link_fields=("enzyme", "site_host", "residue", "position")):
    """Apply a partial exact-record review ledger to already eligible records.

    Each record supplies ``source_record_id``, positive data-record ordinal,
    ``source_row`` and explicit link fields. The caller names the native ID
    column; no column or alias is guessed. Reviews pin release, full-file hash,
    record ID, ordinal and ``canonical_source_row_sha256``, with a disposition
    of ``exclude``, ``retain`` or ``abstain`` plus actor/method/reason. Every
    review must match exactly once; stale or unknown bindings raise ValueError.

    Returned source records are copies with unchanged fields. Link support is
    grouped by the supplied exact keys; removing one record does not remove a
    link supported by another retained record. Unreviewed records remain, but
    their retention does not establish truth or complete source qualification.
    """
    _need(isinstance(source_release, str) and bool(source_release.strip()),
          "an explicit source release is required.")
    _need(isinstance(source_bytes, bytes) and bool(source_bytes)
          and isinstance(source_sha256, str) and _SHA256.fullmatch(source_sha256)
          and hashlib.sha256(source_bytes).hexdigest() == source_sha256,
          "source bytes do not match the pinned full-file SHA256.")
    _need(isinstance(raw_record_id_field, str) and bool(raw_record_id_field),
          "name the exact raw source record-ID field.")
    _need(isinstance(link_fields, tuple) and bool(link_fields)
          and all(isinstance(k, str) and bool(k) for k in link_fields)
          and len(link_fields) == len(set(link_fields)),
          "link fields must be a nonempty tuple of distinct field names.")
    _need(isinstance(records, (list, tuple)) and isinstance(reviews, (list, tuple)),
          "records and explicit reviews must be lists or tuples.")

    indexed, original_support, ordinals = {}, defaultdict(list), set()
    for row in records:
        _need(isinstance(row, Mapping), "source record must be an object.")
        sid, ordinal, raw = (row.get("source_record_id"),
                             row.get("source_data_record_ordinal"), row.get("source_row"))
        _need(isinstance(sid, str) and bool(sid) and sid not in indexed
              and type(ordinal) is int and ordinal > 0 and ordinal not in ordinals,
              "source record IDs must be unique and ordinals positive integers.")
        ordinals.add(ordinal)
        row_digest = canonical_source_row_digest(raw)
        _need(raw.get(raw_record_id_field) == sid,
              "wrapper record ID differs from the native source row.")
        _need(all(isinstance(row.get(k), str) and bool(row[k]) for k in link_fields),
              "source record lacks an exact string-valued link key.")
        key = tuple(row[k] for k in link_fields)
        binding = {"source_record_id": sid, "source_data_record_ordinal": ordinal,
                   "canonical_source_row_sha256": row_digest}
        indexed[sid] = (row, key, binding)
        original_support[key].append(binding)

    dispositions, applied = {}, []
    for review in reviews:
        _need(isinstance(review, Mapping) and set(review) == _REVIEW_FIELDS,
              "review must contain the exact explicit binding and disposition fields.")
        sid = review["source_record_id"]
        _need(isinstance(sid, str) and sid in indexed and sid not in dispositions,
              "review record ID is unknown or duplicated.")
        _need(review["source_release"] == source_release
              and review["source_sha256"] == source_sha256,
              "review source release or full-file hash is stale.")
        binding = indexed[sid][2]
        _need(type(review["source_data_record_ordinal"]) is int
              and review["source_data_record_ordinal"] == binding["source_data_record_ordinal"]
              and review["canonical_source_row_sha256"] == binding["canonical_source_row_sha256"],
              "review ordinal or canonical raw-row digest is stale.")
        _need(isinstance(review["disposition"], str)
              and review["disposition"] in {"exclude", "retain", "abstain"}
              and all(isinstance(review[k], str) and bool(review[k].strip())
                      for k in ("reason", "method", "actor")),
              "review requires a supported disposition, reason, method and actor.")
        dispositions[sid] = review["disposition"]
        applied.append(deepcopy(dict(review)))

    retained, excluded, support = [], [], defaultdict(list)
    for sid, (row, key, binding) in indexed.items():
        if dispositions.get(sid) == "exclude":
            excluded.append(deepcopy(dict(row)))
        else:
            retained.append(deepcopy(dict(row)))
            support[key].append(deepcopy(binding))
    return {"policy": POLICY,
            "source_binding": {"source_release": source_release, "source_sha256": source_sha256,
                               "raw_record_id_field": raw_record_id_field},
            "retained_records": retained, "excluded_records": excluded,
            "applied_dispositions": applied,
            "unreviewed_records_retained": len(indexed) - len(dispositions),
            "retained_link_support": [
                {"link": dict(zip(link_fields, key)),
                 "source_records": sorted(rows, key=lambda r: r["source_record_id"])}
                for key, rows in sorted(support.items())],
            "removed_link_keys": [dict(zip(link_fields, key))
                                  for key in sorted(set(original_support) - set(support))],
            "identifiers_remapped": False, "biological_truth_assessed": False}
