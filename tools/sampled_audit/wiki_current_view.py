#!/usr/bin/env python3
"""Optional, reversible current encoded-WikiPathways-membership view.

Execute the reviewed author's GMT reader, then use exact explicit human registry
cross-references. This checks source eligibility, not biological truth. It never
supplies missing protein-form semantics or changes the historical source graph.
"""
from collections import Counter
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import types
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.cohort_mapping import SOURCES, load_registry
from biograph_steward.file_utils import new_output, sha

FORMAT = "biograph-steward.current-wikipathways-view.v1"
PROFILE = "current-encoded-WikiPathways-human-GeneID-membership.v1"
ACTOR = "BioGraph Steward deterministic current WikiPathways eligibility"
REFERENCE_FORMAT = "biograph-steward.exploratory-current-wikipathways-membership.v1"
AUTHOR_COMMIT = "2e77a5665f8261b56e2ef61d8b0106c220193ac5"
AUTHOR_REPOSITORY = "https://github.com/wikipathways/pywikipathways"
AUTHOR_PINS = {
    "read_gmt": "a948bb97c86f9b49620bf2379a59766f98a92ea73be42bdd19523b1b5d23d137",
    "read_pathway_gmt": "160a35afc641ad04aae56a3e7c507564357a7da3a327f5386dcf8fe27e59780e",
}
AUTHOR_DOCUMENTATION_PINS = {
    "rWikiPathways_readPathwayGMT.R": "0d5d075499aed9e2c433ec8a3405d776889a4cf9a57db9fd216d0bc526cdba76",
    "rWikiPathways_LICENSE": "977b55a44719c39674d06b0a2eb51cf4b09f04f3a0164f108634e3b0fed2ac2f",
    "pywp_LICENSE": "0d39700839296c06c5eb8d7936de63240bf740d88d63f8efd4e3cc1a95b83520",
}
RELATION = "http://purl.org/dc/terms/isVersionOf"
LIMITATIONS = [
    "Exploratory development after the frozen probability sample; not a confirmatory test of this intervention.",
    "Pruning means not encoded in this pinned current source view, not biologically false or experimentally disproven.",
    "Current membership cannot refute historical release membership; version relations do not imply content equivalence.",
    "Explicit UniProt/HGNC/NCBI Gene cross-references establish a gene-to-protein relation, not protein or isoform identity.",
    "GMT encodes gene membership, without recovering all graphical interactions, molecular forms or causal mechanisms.",
    "Absent pathways and missing, ambiguous or conflicting identifiers are unknown and retained.",
    "Repeated native rows and distinct local pwid values are preserved; they are not independent evidence.",
    "No primary biological truth or independent scientific accuracy is assessed; existing review states are preserved.",
    "Checksums bind reviewed bytes but do not authenticate the publisher or prove experimental truth.",
]


def need(condition, message):
    if not condition:
        raise ValueError("Current WikiPathways view: " + message)


def pinned(path, expected):
    path = Path(path)
    need(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "invalid SHA256 pin.")
    need(path.is_file() and not path.is_symlink() and sha(path) == expected,
         "input missing, symlinked or changed: " + path.name)
    return path


def author_memberships(gmt, directory):
    """Execute only the two reviewed, hash-pinned unmodified author functions.

    No full package is installed or claimed. Pandas is an optional research
    runtime requirement; it is never imported by the core application.
    """
    namespace = "_biograph_reviewed_pywp_" + uuid.uuid4().hex
    package = types.ModuleType(namespace)
    package.__path__ = []
    sys.modules[namespace] = package
    try:
        for name, pin in AUTHOR_PINS.items():
            path = pinned(Path(directory) / ("pywp_pywikipathways_" + name + ".py"), pin)
            qualified = namespace + "." + name
            spec = importlib.util.spec_from_file_location(qualified, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[qualified] = module
            spec.loader.exec_module(module)
        reader = sys.modules[namespace + ".read_pathway_gmt"]
        # The native helper is also used for exact row locators. No parallel GMT
        # parser or name/symbol matcher is substituted for the author reader.
        records = sys.modules[namespace + ".read_gmt"]._read_gmt_records(gmt)
        return reader.read_pathway_gmt(gmt), records
    finally:
        for name in list(sys.modules):
            if name == namespace or name.startswith(namespace + "."):
                del sys.modules[name]


def load_reference(reference_report, expected_sha256):
    """Replay native data; diagnostic cohort labels are deliberately ignored."""
    path = pinned(reference_report, expected_sha256)
    report = gold_packet._read(path)
    need(gold_packet._sealed(report) and report.get("format") == REFERENCE_FORMAT,
         "reference report format or content seal differs.")
    release = report.get("source_release")
    need(isinstance(release, str) and re.fullmatch(r"[0-9]{8}", release)
         and report.get("species") == "Homo sapiens", "only a dated human reference is supported.")
    author = report.get("native_author_parser", {})
    need(author.get("repository") == AUTHOR_REPOSITORY and author.get("commit") == AUTHOR_COMMIT
         and author.get("function") == "read_pathway_gmt" and author.get("source_sha256") == AUTHOR_PINS,
         "author reader identity/version differs from the reviewed implementation.")
    r_license = author.get("r_reader_license_sha256")
    need(r_license is None or r_license == AUTHOR_DOCUMENTATION_PINS["rWikiPathways_LICENSE"],
         "R author documentation license differs from the reviewed source.")
    gmt = pinned(path.parent / ("wikipathways-" + release + "-gmt-Homo_sapiens.gmt"), report.get("source_sha256"))
    expected_url = "https://data.wikipathways.org/current/gmt/" + gmt.name
    need(report.get("source_url") == expected_url, "reference URL is not the corresponding official native GMT.")
    version = report.get("version_mapping", {})
    need(version.get("relation") == "dcterms:isVersionOf"
         and version.get("source_version_content_equivalence_claimed") is False,
         "explicit non-equivalent source-version relationship proof is required.")
    paper = pinned(path.parent / "wiki2024_primary_bioc.xml", version.get("paper_bioc_sha256"))
    example = version.get("native_legacy_GPML_example", {})
    need(gold_packet._safe_relative(example.get("file")), "unsafe native GPML proof path.")
    gpml = pinned(path.parent / example["file"], example.get("sha256"))
    need(re.fullmatch(r"WP[1-9][0-9]*_r[1-9][0-9]*", example.get("Version", ""))
         and example["Version"].split("_r")[0] == example.get("canonical_WPID"), "invalid version proof binding.")
    # A native GPML version label is checked without inferring its membership.
    import xml.etree.ElementTree as ET
    need(ET.fromstring(gpml.read_bytes()).attrib.get("Version") == example["Version"], "native GPML version differs.")
    frame, native_records = author_memberships(gmt, path.parent)
    need(list(frame.columns) == ["name", "version", "wpid", "org", "gene"]
         and not frame.empty and set(frame["version"]) == {"WikiPathways_" + release}
         and set(frame["org"]) == {"Homo sapiens"}, "native GMT metadata is missing or inconsistent.")
    need(all(isinstance(x, str) and re.fullmatch(r"WP[1-9][0-9]*", x) for x in frame["wpid"])
         and all(isinstance(x, str) and re.fullmatch(r"[1-9][0-9]*", x) for x in frame["gene"]),
         "native pathway or Entrez Gene identifiers are malformed.")
    # Bind native reader results to literal line hashes for transparent review.
    raw_lines = gmt.read_text(encoding="utf-8").splitlines()
    need(len(raw_lines) == len(native_records) and all("\t".join(r) == raw for r, raw in zip(native_records, raw_lines)),
         "native reader skipped or changed a source row.")
    memberships, by_term = {}, {}
    for name, version_label, wpid, org, gene in frame.itertuples(index=False, name=None):
        term = "%".join((name, version_label, wpid, org))
        entry = by_term.setdefault(term, {"name": name, "wpid": wpid, "genes": []})
        entry["genes"].append(gene)
    pairs = set(frame[["wpid", "gene"]].itertuples(index=False, name=None))
    for number, fields in enumerate(native_records, 1):
        # Format/meaning comes from the author's dataframe; original fields only
        # supply native byte locators and validate its exact row coverage.
        parsed = by_term.get(fields[0])
        need(len(fields) >= 3 and parsed is not None,
             "native GMT source row has no unique author-parsed pathway.")
        wpid = parsed["wpid"]
        need(wpid not in memberships and Counter(parsed["genes"]) == Counter(fields[2:]),
             "native pathway row is repeated or differs from the author parser.")
        memberships[wpid] = {"wpid": wpid, "name": parsed["name"], "genes": set(parsed["genes"]),
            "source_line": number, "source_url": fields[1],
            "raw_line_sha256": hashlib.sha256(raw_lines[number - 1].encode()).hexdigest()}
    need(pairs == {(wpid, gene) for wpid, row in memberships.items() for gene in row["genes"]}
         and len(frame) == sum(len(r) - 2 for r in native_records), "native memberships do not replay exactly.")
    proof_files = {gmt.name: sha(gmt), paper.name: sha(paper), gpml.name: sha(gpml)}
    for name, pin in AUTHOR_PINS.items():
        proof_files["pywp_pywikipathways_" + name + ".py"] = pin
    for name, pin in AUTHOR_DOCUMENTATION_PINS.items():
        # Legacy private reference reports did not include this additional
        # attribution file. New reusable packets declare and require it.
        if name == "rWikiPathways_LICENSE" and r_license is None:
            continue
        pinned(path.parent / name, pin)
        proof_files[name] = pin
    binding = {"reference_report_file_sha256": expected_sha256, "reference_content_sha256": report["content_sha256"],
        "source_release": release, "source_url": expected_url, "source_sha256": sha(gmt), "taxon_id": 9606,
        "identifier_namespace": "NCBIGene", "membership_unit": "encoded gene membership, not protein-form identity",
        "native_membership_rows": len(frame), "unique_memberships": len(pairs), "pathways": len(memberships),
        "author_repository": AUTHOR_REPOSITORY, "author_commit": AUTHOR_COMMIT,
        "author_reader_executed": True, "full_package_installed_or_claimed": False,
        "r_reader_mit_license_preserved": r_license is not None,
        "version_mapping": version, "proof_files": proof_files}
    return memberships, binding


def gene_relationship(subject, registry):
    """No names, aliases, isoform stripping or inferred identity are used."""
    unknown = {"qualified": False, "ncbi_gene_id": None, "hgnc_id": None,
               "uniprot_source_row": None, "hgnc_source_row": None}
    if not isinstance(subject, str) or not re.fullmatch(r"UniProtKB:[A-Z0-9]{6}(?:[A-Z0-9]{4})?", subject):
        return {**unknown, "status": "unrecognized_exact_protein_identifier"}
    accession = subject[len("UniProtKB:"):]
    protein = registry.proteins.get(accession)
    if protein is None:
        return {**unknown, "status": "protein_not_in_human_registry"}
    genes, hgnc = protein["ncbi_gene_ids"], protein["hgnc_ids"]
    if len(genes) != 1 or not re.fullmatch(r"[1-9][0-9]*", genes[0]) or len(hgnc) != 1:
        return {**unknown, "status": "ambiguous_or_missing_explicit_gene_relation", "uniprot_source_row": protein["source_row"]}
    gene = registry.genes.get(hgnc[0])
    if gene is None or gene["status"] != "Approved" or gene["entrez_id"] != genes[0] or accession not in gene["uniprot_ids"].split("|"):
        return {**unknown, "status": "registry_cross_reference_conflict", "uniprot_source_row": protein["source_row"]}
    return {"qualified": True, "status": "explicit_human_UniProt_HGNC_Entrez_agreement",
        "ncbi_gene_id": genes[0], "hgnc_id": hgnc[0], "uniprot_source_row": protein["source_row"],
        "hgnc_source_row": gene["source_row"], "relation": "gene_to_protein_relationship_not_identity"}


def classify_membership(source_id, relationship, memberships):
    """Exact source-version relationship and closed current-file eligibility."""
    match = re.fullmatch(r"(WP[1-9][0-9]*)(?:_r([1-9][0-9]*))?", source_id) if isinstance(source_id, str) else None
    canonical, revision = (match.group(1), match.group(2)) if match else (None, None)
    row = memberships.get(canonical)
    state = ("unrecognized_source_identifier" if match is None else
             "gene_relationship_unknown" if not relationship["qualified"] else
             "pathway_not_in_current_GMT" if row is None else
             "current_gene_membership_present" if relationship["ncbi_gene_id"] in row["genes"] else
             "current_gene_membership_not_listed")
    return {"decision": {"current_gene_membership_present": "keep", "current_gene_membership_not_listed": "prune"}.get(state, "abstain"),
        "state": state, "legacy_source_id": source_id, "canonical_wpid": canonical, "legacy_revision": revision,
        "source_version_relation": ({"subject": source_id, "predicate": RELATION, "object": canonical,
            "content_equivalence": False} if revision else None),
        "current_source_line": row["source_line"] if row else None,
        "current_source_row_sha256": row["raw_line_sha256"] if row else None,
        "encoded_membership_present": (relationship["ncbi_gene_id"] in row["genes"]
            if row is not None and relationship["qualified"] else None)}


def qualify_current_wikipathways(packet, reference_report, registry_directory, output, *, reference_sha256,
                                registry_sha256, actor=ACTOR):
    need(isinstance(actor, str) and actor.strip() and actor.strip().casefold() != "unassigned", "explicit actor required.")
    implementation_pin = sha(Path(__file__))
    manifest, graph = gold_packet.load_packet(packet)
    memberships, binding = load_reference(reference_report, reference_sha256)
    registry_manifest, registry = load_registry(registry_directory)
    need(registry_manifest["registry_sha256"] == registry_sha256, "registry seal differs from the explicit pin.")
    decisions, traces, groups, family_counts = [], [], {}, {}
    for edge in graph["edges"]:
        trace = None
        native = edge.get("evidence_record", {})
        if edge.get("record_kind") == "pathway_membership" and native.get("type") == "WikiPathways":
            need(edge.get("predicate") == "biolink:participates_in" and edge.get("object") == "pharos.pathway:" + str(native.get("pwid")),
                 "WikiPathways edge does not bind its exact native local source identifier.")
            relationship = gene_relationship(edge.get("subject"), registry)
            trace = {"edge_id": edge["id"], "assertion_id": edge["assertion_id"], "subject": edge["subject"],
                "object": edge["object"], "native_pwid": native.get("pwid"), "native_source_type": native["type"],
                "source_record_sha256": digest(native), "source_locators": edge.get("record_locators", []),
                "gene_relationship": relationship, **classify_membership(native.get("sourceID"), relationship, memberships)}
            traces.append(trace)
            key = (edge["subject"], native["type"], native.get("sourceID"))
            group = groups.setdefault(key, {"subject": key[0], "provider_type": key[1], "full_source_id": key[2],
                "canonical_wpid": trace["canonical_wpid"], "source_version_relation": trace["source_version_relation"],
                "edge_ids": [], "assertion_ids": [], "native_pwids": [], "decisions": []})
            for field, value in (("edge_ids", edge["id"]), ("assertion_ids", edge["assertion_id"]),
                                 ("native_pwids", native.get("pwid")), ("decisions", trace["decision"])):
                group[field].append(value)
        decision = trace["decision"] if trace else "abstain"
        reason = (PROFILE + "; " + trace["state"] + "; current encoded membership eligibility only, not biological truth"
                  if trace else "outside_current_WikiPathways_membership_profile; retain without assessment")
        decisions.append({"edge_id": edge["id"], "decision": decision, "reason": reason, "confidence": None})
        family = family_counts.setdefault(edge["record_kind"], {"total": 0, "keep": 0, "prune": 0, "abstain": 0})
        family["total"] += 1
        family[decision] += 1
    for group in groups.values():
        group["raw_edge_count"] = len(group["edge_ids"])
        group["group_id"] = "wiki-source-group:" + digest({k: group[k] for k in ("subject", "provider_type", "full_source_id")})
        group["decisions"] = dict(Counter(group["decisions"]))
        group["native_rows_merged"] = False
        group["independent_evidence_count"] = None
    counts, profile_counts = Counter(x["decision"] for x in decisions), Counter(x["decision"] for x in traces)
    folder = new_output(output, packet, reference_report, Path(reference_report).parent, registry_directory)
    source_folder, registry_folder = folder / "reference", folder / "registry"
    source_folder.mkdir()
    registry_folder.mkdir()
    shutil.copyfile(reference_report, source_folder / "reviewed_reference_report.json")
    for name in binding["proof_files"]:
        target = source_folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pinned(Path(reference_report).parent / name, binding["proof_files"][name]), target)
        pinned(target, binding["proof_files"][name])
    for name in ["manifest.json", *SOURCES]:
        shutil.copyfile(Path(registry_directory) / name, registry_folder / name)
    write_json(folder / "decisions.json", {"format": gold_packet.DECISION_FORMAT, "packet_id": manifest["packet_id"],
        "method": PROFILE, "actor": actor, "decisions": decisions})
    write_json(folder / "source_groups.json", {"profile": PROFILE, "group_key": ["subject", "provider_type", "full_source_id"],
        "native_rows_merged": False, "groups": sorted(groups.values(), key=lambda x: x["group_id"])})
    retained = gold_packet.save_decisions(packet, folder / "decisions.json", folder / "retained")
    need(all(retained["counts"][k] == counts[k] for k in ("keep", "prune", "abstain")), "retained decisions disagree.")
    # Rebind every input before writing any completion-looking sealed report.
    # A failure leaves only incomplete artifacts, never a successful view seal.
    need(gold_packet.load_packet(packet)[0] == manifest, "source packet changed during qualification.")
    pinned(reference_report, reference_sha256)
    pinned(source_folder / "reviewed_reference_report.json", reference_sha256)
    for name, pin in binding["proof_files"].items():
        pinned(Path(reference_report).parent / name, pin)
        pinned(source_folder / name, pin)
    need(load_registry(registry_directory)[0] == registry_manifest, "registry changed during qualification.")
    need(load_registry(registry_folder)[0] == registry_manifest,
         "copied registry differs from the verified input registry.")
    pinned(Path(__file__), implementation_pin)
    report = {"format": FORMAT, "profile": PROFILE, "created_at": utcnow(), "actor": actor,
        "packet_id": manifest["packet_id"], "graph_sha256": manifest["graph_sha256"], "snapshot_sha256": manifest["snapshot_sha256"],
        "reference": binding, "registry_sha256": registry_sha256, "registry_files": registry_manifest["files"],
        "counts": {"total_edges": len(decisions), **{k: counts[k] for k in ("keep", "prune", "abstain")},
            "WikiPathways_edges": len(traces), "WikiPathways": {k: profile_counts[k] for k in ("keep", "prune", "abstain")},
            "exact_subject_type_full_sourceID_groups": len(groups), "outside_profile_abstain": len(decisions) - len(traces)},
        "edge_family_counts": family_counts, "source_decisions": traces,
        "source_graph_mutated": False, "source_review_states_mutated": False, "native_rows_merged": False,
        "biological_truth_assessed": False, "independent_biological_accuracy": False,
        "historical_claims_refuted": False, "protein_form_identity_inferred": False,
        "exploratory_post_sample_development": True, "frozen_audit_intervention_changed": False,
        "model_calls": 0, "source_fetches": 0, "retained_package": "retained",
        "retained_report_sha256": retained["content_sha256"], "limitations": LIMITATIONS,
        "implementation_sha256": implementation_pin,
        "files": {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*") if p.is_file() and "retained" not in p.relative_to(folder).parts}}
    report["files"]["retained/report.json"] = sha(folder / "retained/report.json")
    report["content_sha256"] = digest(report)
    write_json(folder / "wiki_current_qualification.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--reference-report", required=True)
    parser.add_argument("--reference-sha256", required=True, help="Reviewed reference report file SHA256")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-sha256", required=True, help="Frozen human registry manifest content seal")
    parser.add_argument("--out", required=True)
    parser.add_argument("--actor", default=ACTOR)
    args = parser.parse_args()
    report = qualify_current_wikipathways(args.packet, args.reference_report, args.registry, args.out,
        reference_sha256=args.reference_sha256, registry_sha256=args.registry_sha256, actor=args.actor)
    print(json.dumps({"report": str(Path(args.out) / "wiki_current_qualification.json"),
        "content_sha256": report["content_sha256"], "counts": report["counts"]}, indent=2))


if __name__ == "__main__":
    main()
