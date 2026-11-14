#!/usr/bin/env python3
"""Audit saved historical hypotheses against preserved annotation sources.

This is a display-source diagnostic, never a forecasting or evaluation arm.
The CAFA author's unchanged parser supplies historical ancestor membership;
the existing native GAF reader and NetworkX supply current-source inspection.
"""
from collections import Counter
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha
from biograph_steward.function_context import load_publication
from biograph_steward.go_qualification import read_native_gaf
from biograph_steward.go_ontology_qualification import load_ontology


def need(ok, message):
    if not ok:
        raise ValueError("Historical display overlap: " + message)


def source(path):
    return {"path": str(Path(path).absolute()), "sha256": sha(path),
            "bytes": Path(path).stat().st_size}


def membership(gts, ontologies, accession, term):
    for ns, ontology in ontologies.items():
        if term in ontology.terms_dict and ns in gts and accession in gts[ns].ids:
            return bool(gts[ns].matrix[gts[ns].ids[accession], ontology.terms_dict[term]["index"]])
    return False


def run(config_path):
    config = json.loads(Path(config_path).read_text())
    output = Path(config["output"]).absolute()
    need(not output.exists(), "output already exists; preserve earlier audit versions.")
    output.mkdir(parents=True)
    manifest, queries = load_publication(config["publication"], config["publication_sha256"])
    accessions = {p.split(":", 1)[1] for p in queries}
    candidates = [(p.split(":", 1)[1], row) for p, q in queries.items() for row in q["candidates"]]
    need(len(candidates) == 36 and len(accessions) == 6, "this receipt audits the six saved usability examples only.")
    pinned = {}
    for name, item in config["inputs"].items():
        pinned[name] = source(item["path"])
        need(pinned[name]["sha256"] == item["sha256"], "source bytes differ: " + name)

    sys.path.insert(0, config["author_src"])
    from cafaeval.parser import obo_parser, gt_parser
    ontologies = obo_parser(config["inputs"]["historical_ontology"]["path"], ("is_a", "part_of"), None, False)

    # The member is the author baseline, not native GAF. Preserve literal rows
    # before the author's parser canonicalizes aliases and admits ancestors.
    archive = config["inputs"]["baseline_archive"]["path"]
    baseline_path = output / "all_evidence_selected.tsv"
    member_hash = hashlib.sha256()
    member_rows = 0
    baseline_literal = set()
    baseline_target_rows = Counter()
    with tarfile.open(archive, "r|gz") as tar, baseline_path.open("wb") as selected:
        found = False
        for member in tar:
            if member.name != "baselines/all_evidence.tsv":
                continue
            found = True
            for raw in tar.extractfile(member):
                member_hash.update(raw)
                fields = raw.split()
                need(len(fields) == 3, "unexpected all-evidence row shape.")
                member_rows += 1
                accession = fields[0].decode()
                if accession in accessions:
                    need(float(fields[2]) == 1.0, "author all-evidence score is not one.")
                    baseline_target_rows[accession] += 1
                    baseline_literal.add((accession, fields[1].decode()))
                    selected.write(raw)
            break
    need(found and member_hash.hexdigest() == config["baseline_member_sha256"], "full all-evidence member hash differs.")
    baseline_gts = gt_parser(str(baseline_path), ontologies)
    known_path = output / "known_t0_selected.tsv"
    known_literal = set()
    with open(config["inputs"]["known_t0"]["path"]) as stream, known_path.open("w") as selected:
        for line in stream:
            fields = line.split()
            if fields and fields[0] in accessions:
                need(len(fields) == 3, "unexpected known_t0 row shape.")
                known_literal.add((fields[0], fields[1]))
                selected.write(line)
    known_gts = gt_parser(str(known_path), ontologies)

    # Read all 17 native fields with the project's already qualified Bio1.88
    # adapter. No NOT assertion is turned into a positive or propagated upward.
    native, native_source = read_native_gaf(config["inputs"]["current_gaf"]["path"], accessions,
                                           config["inputs"]["current_gaf"]["sha256"])
    nodes, ontology_binding, raw_ontology = load_ontology(
        config["inputs"]["current_ontology"]["path"], config["inputs"]["current_ontology"]["sha256"])
    import networkx as nx
    native_graph = json.loads(gzip.decompress(raw_ontology))["graphs"][0]
    graph = nx.DiGraph()
    iri_prefix = "http://purl.obolibrary.org/obo/GO_"

    def go_id(iri):
        return "GO:" + iri[len(iri_prefix):] if isinstance(iri, str) and iri.startswith(iri_prefix) else None

    graph.add_nodes_from(nodes)
    relations = {"is_a", "http://purl.obolibrary.org/obo/BFO_0000050"}
    for edge in native_graph["edges"]:
        left, right = go_id(edge["sub"]), go_id(edge["obj"])
        if edge["pred"] in relations and left in nodes and right in nodes:
            if not nodes[left].get("meta", {}).get("deprecated", False) and not nodes[right].get("meta", {}).get("deprecated", False):
                graph.add_edge(left, right, native_predicate=edge["pred"])
    need(nx.is_directed_acyclic_graph(graph), "admitted current GO hierarchy is not acyclic.")
    # Source-specific rows retain their original polarity, relations and forms.
    with (output / "current_native_selected.jsonl").open("w") as stream:
        for row in native:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    output_rows = []
    for accession, candidate in candidates:
        term = candidate["GO_ID"]
        descendant_terms = nx.ancestors(graph, term) if term in graph else set()
        matches, not_matches = [], []
        for row in native:
            if row["subject"] != "UniProtKB:" + accession:
                continue
            native_term = row["parsed"]["GO_ID"]
            if row["negated"]:
                if native_term == term:
                    not_matches.append(row["id"])
                continue
            if native_term != term and native_term not in descendant_terms:
                continue
            path = [term] if native_term == term else nx.shortest_path(graph, native_term, term)
            form = row["gene_product_form_id"]
            same_identifier = form == row["subject"] if form else None
            context_specific = bool(row["annotation_extension_raw"] or form and same_identifier is False)
            matches.append({"native_record_id": row["id"], "source_line": row["source_line"],
                "membership": "literal_term" if native_term == term else "admitted_ancestor",
                "source_term": native_term, "source_relation": row["relation_literal"],
                "evidence": row["parsed"]["Evidence"], "references": row["parsed"]["DB:Reference"],
                "product_form": form, "product_form_equals_query_identifier": same_identifier,
                "extension": row["annotation_extension_raw"],
                "with_from": row["parsed"]["With"], "taxa": row["parsed"]["Taxon_ID"],
                "context_or_form_specific": context_specific,
                "ontology_path": path, "path_predicates": [graph[a][b]["native_predicate"] for a, b in zip(path, path[1:])]})
        direct = (accession, term) in baseline_literal
        admitted = membership(baseline_gts, ontologies, accession, term)
        baseline_status = ("literal_released_row" if direct else "author_admitted_ancestor_or_alias"
                           if admitted else "not_in_released_target_annotations" if baseline_target_rows[accession]
                           else "outside_released_baseline_target_scope")
        output_rows.append({"query": "UniProtKB:" + accession, "GO_ID": term, "aspect": candidate["aspect"],
            "label": candidate["label"], "published_score": candidate["score"],
            "known_t0_literal": (accession, term) in known_literal,
            "known_t0_author_closure": membership(known_gts, ontologies, accession, term),
            "pre_t0_all_evidence": {"status": baseline_status, "literal_source_row": direct,
                "author_admitted": admitted, "released_target_rows": baseline_target_rows[accession]},
            "july2026_goa": {"term_in_matching_ontology": term in nodes,
                "term_deprecated": nodes.get(term, {}).get("meta", {}).get("deprecated", False),
                "positive_matches": matches, "exact_NOT_record_ids": not_matches,
                "absence_is_biological_negative": False}})
    counts = {"candidates": len(output_rows), "queries": len(queries),
        "known_t0_literal": sum(row["known_t0_literal"] for row in output_rows),
        "known_t0_author_closure": sum(row["known_t0_author_closure"] for row in output_rows),
        "all_evidence_status": dict(Counter(row["pre_t0_all_evidence"]["status"] for row in output_rows)),
        "july2026_positive_literal": sum(any(m["membership"] == "literal_term" for m in r["july2026_goa"]["positive_matches"]) for r in output_rows),
        "july2026_positive_ancestor_only": sum(bool(r["july2026_goa"]["positive_matches"]) and not any(m["membership"] == "literal_term" for m in r["july2026_goa"]["positive_matches"]) for r in output_rows),
        "july2026_no_positive_match": sum(not r["july2026_goa"]["positive_matches"] for r in output_rows),
        "july2026_exact_NOT_present": sum(bool(r["july2026_goa"]["exact_NOT_record_ids"]) for r in output_rows)}
    report = {"format": "biograph-steward.historical-display-annotation-overlap.v1", "created_at": utcnow(),
        "purpose": "Post-forecast display novelty/source overlap audit, not evaluation or a new forecasting arm.",
        "publication_manifest_sha256": sha(Path(config["publication"]) / "publication.json"),
        "publication_content_sha256": manifest["content_sha256"], "inputs": pinned,
        "baseline_member": {"name": "baselines/all_evidence.tsv", "sha256": member_hash.hexdigest(), "rows": member_rows},
        "native_gaf": native_source, "matching_current_ontology": ontology_binding,
        "author_parser": {"revision": config["author_revision"], "sha256": sha(Path(config["author_src"]) / "cafaeval/parser.py"),
            "calls": ["obo_parser(is_a,part_of,orphans=False)", "gt_parser"], "future_labels_read": False},
        "current_hierarchy": {"library": "networkx", "version": nx.__version__, "method": "ancestors and shortest_path", "admitted_predicates": sorted(relations)},
        "implementation": source(__file__), "counts": counts, "rows": output_rows,
        "limitations": ["Examples are usability-selected, not a representative accuracy sample.",
            "A released all-evidence row is not necessarily a direct native GAF assertion; the author may have already propagated it.",
            "All-evidence concept overlap does not establish an exact native record, independent study, or contradiction.",
            "Native positive associations retain their relation, evidence, form and contextual extensions; contextual/form-specific matches do not backfill canonical model claims.",
            "A populated product-form field equal to the exact query identifier is not evidence of a distinct form restriction. A different literal identifier remains unresolved and does not prove a distinct isoform.",
            "is_a and part_of paths group positive term associations; other ontology relations and NOT propagation are excluded.",
            "July 2026 rows are later source coverage, not independent accuracy labels or proof of novel discovery.",
            "Missing matches remain unknown; references may alias one study and are not counted as independent votes.",
            "Forecasts, saved publications, labels, weights, thresholds and holdout evaluation remain unchanged."]}
    report["content_sha256"] = digest(report)
    write_json(output / "report.json", report)
    print(json.dumps({"path": str(output / "report.json"), "content_sha256": report["content_sha256"], "counts": counts}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    run(parser.parse_args().config)
