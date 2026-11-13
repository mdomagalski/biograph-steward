#!/usr/bin/env python3
"""Freeze a normalized-versus-qualified Wiki context development replay.

The native PyKEEN learner and recorded INMC endpoint already exist in this
project. This adapter changes only the Wiki membership adjacency. INMC has been
consumed previously: this is a retrospective sensitivity check, not confirmation.
Repeated source evidence stays in the source packages; a simple learner uses one
triple per exact protein/version claim. No biological edge is added or accepted.
"""
from collections import Counter, defaultdict
import argparse
import csv
import json
from pathlib import Path
import random
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json, utcnow
from biograph_steward.cohort_mapping import load_registry
from biograph_steward.file_utils import sha, new_output
from biograph_steward.wiki_projection import project_graph
import run_inmc_comparison as inmc

FORMAT = "biograph-steward.wiki-utility-development-packet.v1"
RELATION = "source_reported_exact_version_wiki_membership"
ARMS = ("normalized_unqualified", "fixed_qualified", "equal_count_random", "qualified_degree_permutation")
SEEDS = [17, 43, 101]
CONTROL_SEED = 2026111201
XS_SEED = 2026111202
CONSUMED_OUTCOMES = "runs/inmc_comparison_20261023/scored/outcomes.json"
IMPLEMENTATION = ["tools/wiki_utility/prepare.py", "tools/wiki_utility/run.py", "tools/wiki_utility/score.py",
    "tools/wiki_utility/historical.py", "biograph_steward/wiki_history.py", "biograph_steward/human_gene_relation.py",
    "biograph_steward/cohort_mapping.py", "biograph_steward/gold_packet.py", "biograph_steward/client.py", "biograph_steward/file_utils.py",
    "biograph_steward/wiki_projection.py", "tools/sampled_audit/wiki_version_projection.py",
    "scripts/run_reactome_context.py", "scripts/run_inmc_comparison.py", "biograph_steward/inmc_outcomes.py"]


def need(value, message):
    if not value:
        raise ValueError("Wiki utility: " + message)


def memberships(graph):
    """Exact source-profile projection; no alias, revision or organism repair."""
    projected = project_graph(graph)
    rows = {(e["subject"], RELATION, e["object"]) for e in projected["edges"]}
    need(rows, "no exact-version Wiki memberships")
    return sorted(rows), projected["counts"]


def degrees(rows):
    return {"source": dict(sorted(Counter(a for a, _, _ in rows).items())),
            "target": dict(sorted(Counter(b for _, _, b in rows).items()))}


def degree_permutation(rows, permute):
    """Use the author XSwap backend, then verify both bipartite degree vectors.

    Source and target integer indices occupy disjoint ranges. Thus self-loop
    rejection cannot confuse e.g. protein index zero with pathway index zero.
    """
    left = sorted({a for a, _, _ in rows}); right = sorted({b for _, _, b in rows})
    left_ids = {v: i for i, v in enumerate(left)}
    right_ids = {v: i + len(left) for i, v in enumerate(right)}
    encoded = [(left_ids[a], right_ids[b]) for a, _, b in rows]
    result, stats = permute(encoded, allow_self_loops=False, allow_antiparallel=True,
                           multiplier=10, seed=XS_SEED, max_malloc=64 * 1024 * 1024)
    need(len(result) == len(set(result)) == len(rows), "XSwap changed simple edge count")
    need(all(0 <= a < len(left) and len(left) <= b < len(left) + len(right) for a, b in result),
         "XSwap crossed bipartite node types")
    decoded = sorted((left[a], RELATION, right[b - len(left)]) for a, b in result)
    need(degrees(decoded) == degrees(rows), "XSwap changed degree sequence")
    need(set(decoded) != set(rows), "degree control did not change adjacency")
    return decoded, stats


def registry_links(proteins, registry, existing_genes):
    links, ledger = [], []
    for protein in sorted(proteins):
        accession = protein.removeprefix("UniProtKB:")
        p = registry.proteins.get(accession)
        gids = p["hgnc_ids"] if p else []
        reason, gene = "ambiguous_or_missing_reviewed_HGNC_mapping", None
        if len(gids) == 1 and gids[0] in registry.genes:
            g = registry.genes[gids[0]]
            native = [v for v in registry.products(gids[0]) if v["uniprot_id"] == protein]
            candidate = g["ensembl_gene_id"]
            if (g["status"] == "Approved" and inmc.GENE.fullmatch(candidate or "") and len(native) == 1
                    and native[0]["status"] == "reviewed_human_hgnc_match"):
                gene = candidate
                reason = "exact_reviewed_registry_gene_in_frozen_scaffold" if gene in existing_genes else "exact_registry_gene_outside_frozen_scaffold"
                if gene in existing_genes:
                    links.append((gene, "reviewed_product_context", protein))
        ledger.append({"protein": protein, "hgnc_ids": gids, "ensembl_gene": gene, "disposition": reason,
                       "mapping_is_identity_equivalence": False})
    return sorted(set(links)), ledger


def build_packet(base, original_graph, qualified_graph, registry, permute):
    ordinary, ordinary_counts = memberships(original_graph)
    qualified, qualified_counts = memberships(qualified_graph)
    return build_features(base, ordinary, qualified, registry, permute,
                          ordinary_counts=ordinary_counts, qualified_counts=qualified_counts)


def build_features(base, ordinary, qualified, registry, permute, *, ordinary_counts, qualified_counts):
    """Shared learner adapter: source selection is supplied by its native reader."""
    need(set(qualified) < set(ordinary), "qualified memberships must be a proper subset")
    proteins = {a for a, _, _ in ordinary}
    genes = {n for n in base["entities"] if inmc.GENE.fullmatch(n)}
    links, mapping = registry_links(proteins, registry, genes)
    shared = set(base["arms"]["baseline"]) | set(links)
    need(all(r in {"interacts", "reviewed_product_context", "pharos_cc_annotation"} for _, r, _ in shared),
         "shared context contains an unselected source family")
    variants = {ARMS[0]: ordinary, ARMS[1]: qualified,
                ARMS[2]: sorted(random.Random(CONTROL_SEED).sample(ordinary, len(qualified)))}
    variants[ARMS[3]], swap_stats = degree_permutation(qualified, permute)
    entities = sorted(set(base["entities"]) | {v for a, _, b in ordinary for v in (a, b)})
    arms = {arm: sorted(shared | set(rows)) for arm, rows in variants.items()}
    packet = {"entities": entities, "relations": sorted(set(base["relations"]) | {RELATION}),
        "supervision": base["supervision"], "arms": arms, "candidates": base["candidates"],
        "development": base["development"], "masked_gene_pairs": base["masked_gene_pairs"]}
    validate(packet)
    adj = defaultdict(set)
    for a, _, b in shared:
        adj[a].add(b); adj[b].add(a)
    changed = {v for a, _, b in set(ordinary) - set(qualified) for v in (a, b)}
    reachable, frontier = set(changed), set(changed)
    reach = {}
    for hop in range(4):
        reach[str(hop)] = {"entities": len(reachable), "candidate_pairs_touching": sum(
            bool(set(r["original_genes"]) & reachable) for r in packet["candidates"])}
        frontier = {b for a in frontier for b in adj[a]} - reachable
        reachable |= frontier
    coverage = {"ordinary_projection": ordinary_counts, "qualified_projection": qualified_counts,
        "unique_memberships_by_arm": {a: len(v) for a, v in variants.items()},
        "removed_unique_memberships": len(set(ordinary) - set(qualified)),
        "changed_proteins": len({a for a, _, _ in set(ordinary) - set(qualified)}),
        "shared_registry_product_links": len(links), "registry_mapping": mapping,
        "native_candidate_pairs": len(packet["candidates"]),
        "candidate_pairs_both_Wiki_products": sum(
            all(g in {a for a,_,_ in links} for g in r["original_genes"]) for r in base["candidates"]),
        "conservative_shared_adjacency_distance_from_changed_entities": reach,
        "reach_is_message_opportunity_not_verified_signal_or_biology": True,
        "xswap_statistics": swap_stats,
        "degree_control_preserves_qualified_protein_and_pathway_degrees": degrees(qualified) == degrees(variants[ARMS[3]]),
        "reference": "already-consumed INMC complete-scored recorded assay panel",
        "fresh_confirmation": False, "independent_reference_lineage_claimed": False,
        "assay_nondetection_means_universal_negative": False}
    return packet, coverage


def verify_source_graph_binding(original_graph, qualified_report):
    # Gold's graph fields are canonical JSON digests, not file-byte SHA fields.
    need(qualified_report.get("graph_sha256") == digest(original_graph),
         "qualified source package belongs to a different original graph")


def replay_features(base, ordinary, qualified, registry, packet, coverage, *, ordinary_counts, qualified_counts):
    """Rebuild deterministic arms and authenticate the stored degree control.

    A consumer without the author's native backend checks the fixed stored
    degree-arm inventory, type boundaries and both degree vectors. It does not
    claim to reexecute XSwap's seed. The producer and separate actual-run receipt
    pin/reexecute that native implementation; hashes alone do not prove execution.
    """
    degree_rows=sorted(t for t in packet['arms'][ARMS[3]] if t[1]==RELATION)
    left=sorted({a for a,_,_ in qualified});right=sorted({b for _,_,b in qualified})
    li={v:i for i,v in enumerate(left)};ri={v:i+len(left) for i,v in enumerate(right)}
    need(all(a in li and b in ri for a,_,b in degree_rows),'degree control contains a foreign source endpoint')
    stats=coverage.get('xswap_statistics',{})
    keys={'swap_attempts','same_edge','self_loop','duplicate','undir_duplicate','excluded'}
    need(set(stats)==keys and all(type(v) is int and v>=0 for v in stats.values())
         and stats['swap_attempts']==10*len(qualified)
         and sum(v for k,v in stats.items() if k!='swap_attempts')<=stats['swap_attempts'],
         'stored native swap statistics differ from the fixed attempt budget')
    def stored_control(edges,**kwargs):
        return [(li[a],ri[b]) for a,_,b in degree_rows],stats
    replay,replayed_coverage=build_features(base,ordinary,qualified,registry,stored_control,
        ordinary_counts=ordinary_counts,qualified_counts=qualified_counts)
    need(digest(replay)==digest(packet),'source-derived vocabulary, supervision, queries, masks or arm inventory differs')
    need(replayed_coverage==coverage,'source-derived coverage or degree-control inventory differs')


def validate(packet):
    need(set(packet["arms"]) == set(ARMS), "all fixed arms are required")
    entities, relations = set(packet["entities"]), set(packet["relations"])
    need(len(entities) == len(packet["entities"]) and len(relations) == len(packet["relations"]), "duplicate vocabulary")
    need(relations == {"interacts", "reviewed_product_context", "pharos_cc_annotation", "go_is_a", RELATION},
         "relations outside selected native profile")
    masked = {tuple(sorted(p)) for p in packet["masked_gene_pairs"]}
    known = []
    for partition in ("candidates", "development"):
        for row in packet[partition]:
            need(not (set(row) & {"label", "outcome", "assay_codes", "score"}), "outcome field in prepared query")
            need(tuple(sorted(row["original_genes"])) in masked, "query missing from shared mask")
            need(all(g in entities and inmc.GENE.fullmatch(g) for g in row["original_genes"]), "unknown query gene")
            known.append(row["id"])
    need(len(known) == len(set(known)), "query identities overlap")
    supervision = set(map(tuple, packet["supervision"]))
    need(len(supervision) == len(packet["supervision"]), "duplicate supervision")
    need(all(r == "interacts" and inmc.GENE.fullmatch(a) and inmc.GENE.fullmatch(b)
             and tuple(sorted((a,b))) not in masked for a,r,b in supervision), "supervision leaks held-out pair")
    shared = None
    for arm, rows in packet["arms"].items():
        triples = set(map(tuple, rows))
        need(len(triples) == len(rows) and supervision <= triples, "arm drops supervision or duplicates triples")
        need(all(a in entities and b in entities and r in relations for a,r,b in triples), "unknown triple vocabulary")
        need(all(a.startswith("UniProtKB:") and b.startswith(("http://www.wikipathways.org/instance/WP", "https://www.wikipathways.org/instance/WP",
                      "http://wikipathways.org/instance/WP", "https://wikipathways.org/instance/WP"))
                 for a,r,b in triples if r == RELATION), "Wiki context endpoint type differs")
        need(all(tuple(sorted((a,b))) not in masked for a,r,b in triples if r == "interacts"), "adjacency leaks query")
        nonwiki = {t for t in triples if t[1] != RELATION}
        if shared is None: shared = nonwiki
        need(nonwiki == shared, "non-Wiki adjacency differs across arms")
    packet["supervision"] = sorted(map(tuple, packet["supervision"]))
    packet["arms"] = {arm: sorted(map(tuple, rows)) for arm, rows in packet["arms"].items()}
    return packet


def prepare(base_path, original, qualified, registry_path, xswap_path, output):
    pins = {p: sha(ROOT/p) for p in IMPLEMENTATION}
    # resource_smoke bypasses only old full-run code/runtime checks; packet bytes,
    # source masks, identities and graph shape are still replayed by the reader.
    base = inmc.validate_packet(Path(base_path), resource_smoke=True)
    original = Path(original); qualified = Path(qualified)
    raw_graph = gold_packet._read(original)
    source_report, retained_graph = gold_packet.load_decisions(qualified)
    verify_source_graph_binding(raw_graph,source_report)
    manifest, registry = load_registry(registry_path)
    sys.path.insert(0, str(Path(xswap_path).resolve()))
    import xswap
    from xswap.permute import permute_edge_list
    packet, coverage = build_packet(base, raw_graph, retained_graph, registry, permute_edge_list)
    out = new_output(output, base_path, original, qualified, registry_path)
    sources = out / "sources"; sources.mkdir()
    shutil.copytree(base_path, sources / "inmc")
    shutil.copytree(qualified, sources / "qualified")
    shutil.copytree(registry_path, sources / "registry")
    shutil.copyfile(original, sources / "original_graph.json")
    write_json(out / "packet.json", packet); write_json(out / "coverage.json", coverage)
    report = {"format": FORMAT, "created_at": utcnow(), "seeds": SEEDS,
        "qualification_kind":"current_release_eligibility_ablation",
        "model": {"native": "PyKEEN 1.11.1 RGCN", "embedding_dim":32, "layers":3,"bases":4,"decoder":"DistMult","dropout":None},
        "training": {"epochs":20,"batch_size":4096,"negative_proposals_per_positive":16,"optimizer":"Adam","learning_rate":0.001},
        "controls": {"random_seed":CONTROL_SEED,"xswap_seed":XS_SEED,"xswap_multiplier":10,
                     "xswap_commit":"ffbb933d1731c2ce4e4e24f00a9a909b53ddf75c","xswap_module_sha256":sha(Path(xswap.__file__).parent/'permute.py'),
                     "xswap_backend_sha256":sha(next(Path(xswap.__file__).parent.glob('_xswap_backend*.so')))},
        "source_report_bindings": {"base":sha(Path(base_path)/'report.json'),"qualified":sha(qualified/'report.json'),"original_graph":sha(original),"registry":sha(Path(registry_path)/'manifest.json')},
        "consumed_outcome_cache": {"path":CONSUMED_OUTCOMES,"sha256":sha(ROOT/CONSUMED_OUTCOMES),
                                   "previously_exposed":True,"opened_by_preparer":False},
        "implementation_sha256":pins,"candidate_outcomes_loaded":False,"retrospective_consumed_reference":True,
        "automatic_graph_changes":False,"biological_improvement_claimed":False,
        "files":{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}}
    need({p:sha(ROOT/p) for p in IMPLEMENTATION}==pins,"implementation changed during freeze")
    # Revalidate the preserved source packages before sealing success.
    need(gold_packet.load_decisions(sources/'qualified')[0]==source_report,"copied qualified packet differs")
    need(load_registry(sources/'registry')[0]==manifest,"copied registry differs")
    need(sha(sources/'original_graph.json')==report['source_report_bindings']['original_graph'],"copied original differs")
    need(inmc.validate_packet(sources/'inmc',resource_smoke=True)['report_sha256']==base['report_sha256'],"copied INMC packet differs")
    report['content_sha256']=digest(report);write_json(out/'report.json',report)
    return report


def verify(folder, *, code=True):
    folder=Path(folder);report=gold_packet._read(folder/'report.json')
    need(gold_packet._sealed(report) and report.get('format')==FORMAT,"packet seal or format differs")
    need(not any(p.is_symlink() for p in [folder,*folder.parents,*folder.rglob('*')]),"symlink in packet")
    actual={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file() and p!=folder/'report.json'}
    need(actual==report['files'],"packet inventory differs")
    if code:need(report['implementation_sha256']=={p:sha(ROOT/p) for p in IMPLEMENTATION},"frozen implementation differs")
    packet=validate(gold_packet._read(folder/'packet.json'))
    need(report.get('candidate_outcomes_loaded') is False and report.get('retrospective_consumed_reference') is True
         and report.get('automatic_graph_changes') is False and report.get('biological_improvement_claimed') is False,"interpretation differs")
    sources=folder/'sources'
    base=inmc.validate_packet(sources/'inmc',resource_smoke=True)
    source_report,retained_graph=gold_packet.load_decisions(sources/'qualified')
    raw_graph=gold_packet._read(sources/'original_graph.json')
    verify_source_graph_binding(raw_graph,source_report)
    _,registry=load_registry(sources/'registry')
    need(report['source_report_bindings']=={
        'base':sha(sources/'inmc/report.json'),'qualified':sha(sources/'qualified/report.json'),
        'original_graph':sha(sources/'original_graph.json'),'registry':sha(sources/'registry/manifest.json')},
        'copied source byte bindings differ')
    ordinary,ordinary_counts=memberships(raw_graph)
    kind=report.get('qualification_kind','current_release_eligibility_ablation')
    if kind=='current_release_eligibility_ablation':
        qualified,qualified_counts=memberships(retained_graph)
    elif kind=='historical_native_xref_compatible_context':
        from tools.wiki_utility.historical import select_history
        qualified,qualified_counts,selection=select_history(sources/'history',report['historical_source_content_sha256'],raw_graph,ordinary)
        need(selection==gold_packet._read(folder/'historical_selection.json'),'historical source selection differs')
    else:raise ValueError('Unknown qualification kind.')
    replay_features(base,ordinary,qualified,registry,packet,gold_packet._read(folder/'coverage.json'),
                    ordinary_counts=ordinary_counts,qualified_counts=qualified_counts)
    return report,packet


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('base','original','qualified','registry','xswap','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=prepare(a.base,a.original,a.qualified,a.registry,a.xswap,a.out);print(r['content_sha256'])
if __name__=='__main__':main()
