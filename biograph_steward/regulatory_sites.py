"""Read-only, source-reported site/context views of verified SIGNOR answers.

PhosphoSIGNOR separates phosphate addition/removal from the protein's
regulatory effect. This view preserves that distinction without promoting a
source coordinate to a canonical phosphosite or inferring a causal site effect.
It adds display objects only; saved graph records and review states are intact.
"""
from collections import Counter
from copy import deepcopy
import re

from .client import digest
from .regulatory_questions import ANCHOR, answer_regulatory_question


FORMAT = "biograph-steward.regulatory-sites.v1"
TEMPLATE = "source_regulatory_sites_context.v1"
_AMINO_ACIDS = dict(zip(
    ("Ala", "Arg", "Asn", "Asp", "Cys", "Gln", "Glu", "Gly", "His", "Ile",
     "Leu", "Lys", "Met", "Phe", "Pro", "Ser", "Thr", "Trp", "Tyr", "Val"),
    "ARNDCQEGHILKMFPSTWYV"))
_SITE = re.compile(r"(" + "|".join(_AMINO_ACIDS) + r"|[ARNDCQEGHILKMFPSTWYV])([1-9][0-9]*)\Z")
_MODIFICATIONS = {"phosphorylation": ("phosphate_addition", 1),
                  "autophosphorylation": ("phosphate_addition", 1),
                  "dephosphorylation": ("phosphate_removal", -1)}
_BASIS = ("graph_basis_sha256", "snapshot_sha256", "evidence_extension_sha256",
          "review_events_sha256", "source_publication_sha256", "source_observations_sha256",
          "context_display_basis")


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _site(raw):
    match = _SITE.fullmatch(raw)
    if not match:
        return None
    residue, position = match.groups()
    return {"label": _AMINO_ACIDS.get(residue, residue) + position,
            "residue": _AMINO_ACIDS.get(residue, residue), "position": int(position)}


def _records(graph, protein, direction, source_run):
    """Use every page of the existing verified answer, never a second reader."""
    records, seals, offset, first = [], [], 0, None
    while True:
        page = answer_regulatory_question(graph, protein, direction=direction,
            offset=offset, limit=25, source_run=source_run)
        if first is None:
            first = page
        else:
            _need(all(page[k] == first[k] for k in _BASIS),
                  "Saved regulatory evidence changed between source answer pages.")
        records.extend(page["records"])
        seals.append(page["content_sha256"])
        following = page["summary"]["next_offset"]
        if following is None:
            break
        _need(type(following) is int and following == offset + len(page["records"])
              and following > offset, "Saved regulatory answer pagination is inconsistent.")
        offset = following
    _need(len(records) == first["summary"]["direction_observations"]
          and len({r["observation_id"] for r in records}) == len(records),
          "Saved regulatory answer does not cover its complete direction-selected scope.")
    return first, records, seals


def _view(row):
    raw = row["residue_raw"]
    site = _site(raw)
    modification = _MODIFICATIONS.get(row["mechanism_literal"])
    reasons = []
    if site is None:
        reasons.append("residue_unreported" if not raw else "residue_not_one_explicit_position")
    if modification is None:
        reasons.append("mechanism_not_supported_phosphate_addition_or_removal")
    reported = None if site is None else {**site, "substrate": row["object"],
        "substrate_label": row["object_label"], "residue_raw": raw,
        "canonical_coordinate_verified": False, "experimental_proteoform_verified": False}
    view = {"status": "unresolved" if reasons else "split_source_view", "reasons": reasons,
        "reported_site": reported, "residue_raw": raw,
        "modification_action": modification[0] if modification else None,
        "phosphate_change_sign": modification[1] if modification else None,
        "source_protein_effect_literal": row["effect_literal"],
        "site_effect_on_protein": {"status": "not_inferred", "sign": None,
            "reason": "The source net protein EFFECT is kept separately; it is not a deduced effect of phosphate occupancy."},
        "source_reported_direct": row["source_reported_direct"],
        "purified_catalysis_verified": False, "graph_assertions_added": 0,
        "projection_edges": []}
    if not reasons:
        # This is a source-scoped display identity, not a canonical site CURIE.
        display_id = "reported-site:" + digest({"observation_id": row["observation_id"],
            "substrate": row["object"], "residue_raw": raw})[:24]
        reported["display_id"] = display_id
        view["projection_edges"] = [
            {"kind": "source_reported_phosphate_change", "subject": row["subject"],
             "object": display_id, "action": modification[0], "sign": modification[1],
             "basis": "Source MECHANISM and single reported RESIDUE; source directness is preserved, not purified-catalysis proof."},
            {"kind": "source_net_protein_effect", "subject": row["subject"],
             "object": row["object"], "effect_literal": row["effect_literal"],
             "basis": "Original source EFFECT on the target protein, separate from phosphate occupancy."}]
    return view


def _tokens(raw):
    # Match the existing source/display contract: exact semicolon-delimited
    # values, without label matching, ontology expansion or whitespace repair.
    return {token for token in raw.split(";") if token} if raw else set()


def _available(records):
    sites, contexts = {}, {"cell": {}, "tissue": {}}
    for row in records:
        site = row["site_view"]["reported_site"]
        if site:
            choice = sites.setdefault(site["label"], {"value": site["label"],
                "label": site["label"] + " · source-reported coordinate", "observations": 0})
            choice["observations"] += 1
        for kind in contexts:
            display = {v["id"]: v for v in row[kind + "_context_display"]}
            for token in sorted(_tokens(row[kind + "_context_raw"])):
                label = display[token]
                choice = contexts[kind].setdefault(token, {"value": token,
                    "label": label["label"], "mapping": label["mapping"],
                    "url": label["url"], "observations": 0})
                choice["observations"] += 1
    return {"sites": sorted(sites.values(), key=lambda r: (r["value"][0], int(r["value"][1:]))),
        "cell_contexts": sorted(contexts["cell"].values(), key=lambda r: (r["label"].casefold(), r["value"])),
        "tissue_contexts": sorted(contexts["tissue"].values(), key=lambda r: (r["label"].casefold(), r["value"]))}


def answer_regulatory_sites(graph, protein=ANCHOR, *, direction="both", site="",
                            cell_context="", tissue_context="", context_reporting="all",
                            offset=0, limit=25, source_run=None):
    """Inspect saved source coordinates and exact contexts without graph changes.

    ``reported`` means either cell or tissue context is supplied; ``unreported``
    means both are blank. A context filter selects one exact source token.
    Available choices and scope counts precede filters and pagination. A site
    filter compares the reported coordinate only, not canonical-site identity.
    """
    _need(isinstance(site, str) and len(site) <= 40,
          "Use one reported site such as Ser15 or S15, or an empty site filter.")
    query = _site(site.strip()) if site.strip() else None
    _need(not site.strip() or query is not None,
          "Use one explicit positive reported coordinate such as Ser15 or S15.")
    for value in (cell_context, tissue_context):
        _need(isinstance(value, str) and len(value) <= 200 and ";" not in value,
              "Choose one exact source context token, or an empty context filter.")
    _need(isinstance(context_reporting, str) and context_reporting in {"all", "reported", "unreported"},
          "Choose all, reported or unreported context availability.")
    _need(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 25,
          "Use a nonnegative offset and a page limit from 1 to 25.")
    basis, source_records, seals = _records(graph, protein, direction, source_run)
    records = [{**row, "site_view": _view(row)} for row in source_records]
    matched = []
    for row in records:
        reported = bool(row["cell_context_raw"] or row["tissue_context_raw"])
        coordinate = row["site_view"]["reported_site"]
        if (query and (not coordinate or coordinate["label"] != query["label"])):
            continue
        if cell_context and cell_context not in _tokens(row["cell_context_raw"]):
            continue
        if tissue_context and tissue_context not in _tokens(row["tissue_context_raw"]):
            continue
        if context_reporting != "all" and reported != (context_reporting == "reported"):
            continue
        matched.append(row)
    page = matched[offset:offset + limit]
    summary = deepcopy(basis["summary"])
    summary.pop("search", None)
    summary.update(matching_observations=len(matched), returned=len(page), offset=offset, limit=limit,
        next_offset=offset + limit if offset + limit < len(matched) else None,
        counts_scope="Direction-selected source observations before site/context filters and pagination.",
        site_view_status_counts=dict(sorted(Counter(r["site_view"]["status"] for r in records).items())),
        site_view_unresolved_reasons=dict(sorted(Counter(reason for r in records for reason in r["site_view"]["reasons"]).items())),
        context_reported_observations=sum(bool(r["cell_context_raw"] or r["tissue_context_raw"]) for r in records),
        context_unreported_observations=sum(not (r["cell_context_raw"] or r["tissue_context_raw"]) for r in records),
        available_filters=_available(records))
    result = {"format": FORMAT, "template": TEMPLATE, "source_kind": "signor", "source_run": source_run,
        "question": "Which source-reported sites and experimental contexts are recorded for " + protein + "?",
        "anchor": protein, "direction": direction, "read_only": True, "derived_view_only": True,
        "model_calls": 0, "source_fetches": 0, "graph_mutated": False,
        **{k: deepcopy(basis[k]) for k in _BASIS},
        "source_summary": deepcopy(basis["source_summary"]), "source_answer_page_seals": seals,
        "filters": {"site": site, "normalized_reported_site": query["label"] if query else None,
            "cell_context": cell_context, "tissue_context": tissue_context,
            "context_reporting": context_reporting}, "summary": summary, "records": page,
        "interpretation": "A source-scoped display of reported positions, phosphate addition/removal and the separate net protein effect. These display steps are not new graph assertions or independent biological validation.",
        "limitations": deepcopy(basis["limitations"]) + [
            "A single source coordinate is not verified against a canonical sequence or experimental proteoform here.",
            "Multiple, unlocalized or unrecognized residue descriptions remain unresolved; they are not split or guessed.",
            "Phosphate-change polarity is separate from protein EFFECT; a causal phosphate-occupancy effect is not inferred.",
            "Source-reported directness does not establish a purified kinase assay or direct catalysis.",
            "Context choices match exact supplied tokens; missing context stays unknown and no disease applicability is inferred.",
            "Source-scoped display identities are not canonical phosphosite identifiers or independent evidence counts."]}
    result["content_sha256"] = digest(result)
    return result
