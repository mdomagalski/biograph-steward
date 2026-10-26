"""Bounded human Y2H adapter, to be invoked only after the protocol is sealed.

Reproduce the published author status, then qualify it separately. The author's
pandas 1.4.3 nullable mask does not reject an unknown sequence confirmation.
We retain that status and exclude the observation from the confirmed endpoint;
we do not silently relabel it as a failure or nondetection.

This module does not retrieve sources, alter Pharos, select a comparator, or
claim that assay nondetection is a biologically false interaction.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import re


FORMAT = "biograph-steward.lambourne-outcomes.v1"
AUTHOR_COMMIT = "fb05ab3ca2cc0fcaf402bb0df568e95a5158178b"
RECIPE_COMMIT = "ec477f7043195c46ce1787cbd7e09fd407d21b97"
PANEL_HEADER = (b"uniprot_ac_a\tuniprot_ac_b\tAD_CCSB_ORF_ID\tDB_CCSB_ORF_ID"
                b"\tsource_dataset\tsource_dataset\tresult\tin_biorxiv_version\tin_published_version")
RAW_HEADER = (b"db_orf_id\tad_orf_id\tcategory\tfinal_score"
              b"\tseq_confirmation_final_3at\tseq_confirmation_final_lw")
ORF_HEADER = b"uniprot_ac\torf_id"
ACCESSION = re.compile(r"[A-Z0-9]{6}(?:[A-Z0-9]{4})?(?:-[1-9][0-9]*)?\Z")
PUBLISHED_STATES = frozenset({"Positive", "Negative", "Test failed", "Autoactivator",
                              "Failed sequence confirmation"})
# The ordinary missing spellings used by pandas.read_csv for these fields.
# Unsupported values are reported, never coerced using Python truthiness.
MISSING = frozenset({"", "NULL", "NA", "NaN", "nan", "<NA>", "N/A",
                     "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN",
                     "-nan", "1.#IND", "1.#QNAN", "n/a", "null"})
IDENTITY_KEYS = ("source_row", "uniprot_a", "uniprot_b", "ad_orf_id", "db_orf_id",
                 "source_dataset_column_5", "source_dataset_column_6",
                 "in_biorxiv_version", "in_published_version")


def _table(raw, header):
    if not isinstance(raw, bytes):
        raise ValueError("Assay sources must be exact bytes.")
    lines = raw.splitlines()
    if not lines or lines[0] != header:
        raise ValueError("Unexpected assay source schema; headers are positional.")
    width = len(header.split(b"\t"))
    rows = []
    for number, line in enumerate(lines[1:], 2):
        fields = line.split(b"\t")
        if len(fields) != width:
            raise ValueError(f"Unexpected assay source width at row {number}.")
        rows.append((number, fields))
    if not rows:
        raise ValueError("Empty assay source.")
    return rows


def _ascii(field):
    try:
        return field.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("Unexpected non-ASCII assay source field.") from exc


def _orf(value):
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError("Invalid experimental ORF identity.")
    return value


def _accession(value):
    if value in {"", "NULL", "None"}:
        return None
    if not ACCESSION.fullmatch(value):
        raise ValueError("Invalid author protein accession.")
    return value


def _confirmation(value):
    if value in MISSING:
        return None
    if value in {"True", "1", "1.0"}:
        return True
    if value in {"False", "0", "0.0"}:
        return False
    # read_csv infers numeric 0/1 columns before the author's BooleanDtype cast.
    # Keep the finite supported forms explicit; never use bool(value).
    raise ValueError("Unrecognized sequence-confirmation state.")


def author_status(final_score, confirmation_3at, confirmation_lw):
    """Apply the author's scalar status transformation, including its NA case.

    Arguments are a raw score string and already parsed bool-or-None values.
    Returns (published_status, nullable_combined_confirmation, raw_bool_result).
    The author raises if a raw negative has any nonmissing 3AT confirmation.
    """
    if any(value is not None and type(value) is not bool
           for value in (confirmation_3at, confirmation_lw)):
        raise ValueError("Confirmation must be a Boolean or null.")
    score = "NA" if final_score in MISSING else final_score
    if score not in {"0", "1", "AA", "NA"}:
        raise ValueError("Unrecognized raw assay score.")
    if score == "0" and confirmation_3at is not None:
        raise ValueError("Author inconsistency: raw negative has 3AT confirmation.")
    raw_result = {"0": False, "1": True, "AA": None, "NA": None}[score]
    # (result == True & confirm3at == True) |
    # (result == False & confirmlw == True), using pandas BooleanDtype.
    combined = (confirmation_3at if raw_result is True else
                confirmation_lw if raw_result is False else False)
    processed = None if combined is False else raw_result
    status = "Positive" if processed is True else "Negative" if processed is False else "Test failed"
    if score == "AA":
        status = "Autoactivator"
    if combined is False and status == "Test failed":
        status = "Failed sequence confirmation"
    if score == "NA":
        status = "Test failed"
    return status, combined, raw_result


def _panel_identity(number, fields):
    # Keep both duplicated source_dataset columns rather than DictReader's
    # last-column-wins behavior. Result is intentionally decoded separately.
    a, b, ad, db, s1, s2, preprint, published = (
        _ascii(fields[index]) for index in (0, 1, 2, 3, 4, 5, 7, 8))
    if preprint not in {"True", "False", "NULL"} or published not in {"True", "False", "NULL"}:
        raise ValueError("Unexpected nomination metadata.")
    return dict(zip(IDENTITY_KEYS, (number, _accession(a), _accession(b), _orf(ad), _orf(db),
                                    s1, s2, preprint, published)))


def _nominated(row):
    return (row["source_dataset_column_5"] == row["source_dataset_column_6"] == "Zhang_et_al"
            and row["in_published_version"] == "True")


def _orf_map(raw):
    result = defaultdict(set)
    for _, fields in _table(raw, ORF_HEADER):
        accession, orf = map(_ascii, fields)
        if not ACCESSION.fullmatch(accession):
            raise ValueError("Invalid ORF crosswalk accession.")
        result[accession].add(_orf(orf))
    return result


def adapt_outcomes(panel_raw, raw_raw, identity_rows, orf_map_raw):
    """Reconcile frozen nominations to raw constructs and published statuses.

    ``identity_rows`` is the complete pre-outcome identity audit, not an
    outcome-selected subset. Every nominated row remains in ``rows``. A single
    consistency issue prevents scoring of the whole panel. Failures and missing
    confirmation remain explicit exclusions, with all source locators retained.
    The caller must verify source hashes and seal its protocol before invoking.
    """
    panel = _table(panel_raw, PANEL_HEADER)
    identities = [_panel_identity(number, fields) for number, fields in panel]
    if (not isinstance(identity_rows, list) or identities != identity_rows
            or any(set(row) != set(IDENTITY_KEYS) for row in identity_rows)):
        raise ValueError("Panel identities differ from the frozen complete audit.")
    if any(row["source_dataset_column_5"] != row["source_dataset_column_6"] for row in identities):
        raise ValueError("Duplicated source_dataset columns disagree.")
    nominations = [row for row in identities if _nominated(row)]
    if not nominations:
        raise ValueError("Frozen audit has no published nominated pairs.")
    crosswalk = _orf_map(orf_map_raw)
    raw_by_construct = defaultdict(list)
    for number, fields in _table(raw_raw, RAW_HEADER):
        db, ad, category = map(_ascii, fields[:3])
        raw_by_construct[(category, _orf(ad), _orf(db))].append((number, fields))

    issues, results = [], []
    seen_pairs, seen_constructs = set(), set()
    fields_by_row = dict(panel)
    for identity in nominations:
        source_row = identity["source_row"]
        a, b = identity["uniprot_a"], identity["uniprot_b"]
        ad, db = identity["ad_orf_id"], identity["db_orf_id"]
        products = sorted((a, b)) if a and b else [a, b]
        key = tuple(products)
        construct = tuple(sorted((ad, db), key=int))
        one = {"products": products, "source_row": source_row, "ad_orf_id": ad, "db_orf_id": db,
               "published_result": _ascii(fields_by_row[source_row][6]), "raw_source_rows": [],
               "raw_final_score": None, "confirmation_3at": None, "confirmation_lw": None,
               "required_confirmation": None, "author_sequence_confirmation_combined": None,
               "author_result": None, "assay_status": "inconsistent", "evaluable": False,
               "detected": None, "construct_match": False, "issues": []}
        def issue(code):
            one["issues"].append(code)
            issues.append({"source_row": source_row, "products": products, "code": code})

        if not a or not b or a == b:
            issue("invalid_nominated_pair")
        if key in seen_pairs:
            issue("duplicate_nominated_pair")
        seen_pairs.add(key)
        if construct in seen_constructs:
            issue("duplicate_nominated_construct")
        seen_constructs.add(construct)
        one["construct_match"] = bool(a and b and (
            (ad in crosswalk.get(a, ()) and db in crosswalk.get(b, ())) or
            (db in crosswalk.get(a, ()) and ad in crosswalk.get(b, ()))))
        if not one["construct_match"]:
            issue("orf_crosswalk_mismatch")
        if one["published_result"] not in PUBLISHED_STATES:
            issue("unexpected_published_result")
            one["assay_status"] = "unexpected_state"
        raw_matches = raw_by_construct.get(("Zhang_et_al", ad, db), [])
        one["raw_source_rows"] = [number for number, _ in raw_matches]
        if not raw_matches:
            code = ("raw_construct_orientation_mismatch" if
                    ("Zhang_et_al", db, ad) in raw_by_construct else "raw_construct_missing")
            issue(code)
        else:
            # Upstream drops duplicate category/AD/DB rows keeping the first.
            # Preserve exact repeated records, but do not hide conflicting raw
            # observations behind that operation in this corroboration report.
            if len({tuple(fields) for _, fields in raw_matches}) != 1:
                issue("conflicting_raw_construct_rows")
            fields = raw_matches[0][1]
            score, confirm3, confirmlw = map(_ascii, fields[3:])
            one["raw_final_score"] = score
            try:
                one["confirmation_3at"] = _confirmation(confirm3)
                one["confirmation_lw"] = _confirmation(confirmlw)
                status, combined, raw_result = author_status(
                    score, one["confirmation_3at"], one["confirmation_lw"])
                one["author_result"] = status
                one["author_sequence_confirmation_combined"] = combined
                one["required_confirmation"] = "3at" if raw_result is True else "lw" if raw_result is False else None
                if status != one["published_result"]:
                    issue("raw_published_status_mismatch")
                if status in {"Positive", "Negative"}:
                    if combined is None:
                        one["assay_status"] = "ambiguous_sequence_confirmation"
                    else:
                        one["assay_status"] = "detected" if status == "Positive" else "not_detected"
                        one["evaluable"], one["detected"] = True, status == "Positive"
                else:
                    one["assay_status"] = {"Test failed": "test_failed", "Autoactivator": "autoactivator",
                                           "Failed sequence confirmation": "failed_sequence_confirmation"}[status]
            except ValueError as exc:
                issue("unexpected_raw_state" if str(exc).startswith("Unrecognized") else "author_preprocessing_inconsistency")
                one["assay_status"] = "unexpected_state" if str(exc).startswith("Unrecognized") else "inconsistent"
        if one["issues"]:
            one["evaluable"], one["detected"] = False, None
            if any(code.startswith("unexpected_") for code in one["issues"]):
                one["assay_status"] = "unexpected_state"
            else:
                one["assay_status"] = "inconsistent"
        results.append(one)

    counts = {"published_nominations": len(results), "panel_source_rows": len(panel),
              "excluded_nonnomination_rows": len(panel) - len(results),
              "assay_status": dict(sorted(Counter(row["assay_status"] for row in results).items())),
              "published_result": dict(sorted(Counter(row["published_result"] for row in results).items())),
              "evaluable": sum(row["evaluable"] for row in results),
              "consistency_issues": len(issues),
              "rows_with_identical_raw_repeats": sum(len(row["raw_source_rows"]) > 1 and
                  "conflicting_raw_construct_rows" not in row["issues"] for row in results)}
    return {"format": FORMAT, "author_commit": AUTHOR_COMMIT, "recipe_commit": RECIPE_COMMIT,
            "source_sha256": {"panel": hashlib.sha256(panel_raw).hexdigest(),
                              "raw": hashlib.sha256(raw_raw).hexdigest(),
                              "orf_map": hashlib.sha256(orf_map_raw).hexdigest()},
            "scoring_allowed": not issues, "counts": counts, "issues": issues, "rows": results,
            "qualification": "Explicit applicable sequence confirmation is required; null is excluded.",
            "endpoint": "Detection in the reported human Y2H-v1 assessment; nondetection is not biological falsity.",
            "controls": "Not scored or mapped; private author control mapping is not reconstructed.",
            "processed_intermediate": "Not distributed in the pinned repository; raw status is compared to published supplementary status."}
