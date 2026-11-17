#!/usr/bin/env python3
"""Package provided native WikiPathways files without cohort-specific labels.

The existing hash-pinned author reader and reference verifier run before any
successful reference packet is published. This is offline source packaging,
not a new GMT parser, identifier mapper or biological assessment method.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward import gold_packet
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.sampled_audit.wiki_current_view import (AUTHOR_COMMIT,
    AUTHOR_DOCUMENTATION_PINS, AUTHOR_PINS, AUTHOR_REPOSITORY,
    REFERENCE_FORMAT, load_reference, pinned)

INPUT_FORMAT = "biograph-steward.wikipathways-reference-inputs.v1"
PACKET_FORMAT = "biograph-steward.wikipathways-native-reference-packet.v1"
FILE_KEYS = frozenset({"gmt", "read_gmt", "read_pathway_gmt", "reader_license",
                      "r_reader_documentation", "r_reader_license", "primary_paper_bioc", "gpml_version_proof"})


def need(condition, message):
    if not condition:
        raise ValueError("WikiPathways reference preparation: " + message)


def prepare_reference(metadata, output):
    """Create a minimal reusable reference from an explicit pinned file config."""
    metadata = Path(metadata).absolute()
    need(metadata.is_file() and not metadata.is_symlink(), "metadata must be an ordinary file.")
    metadata_pin, implementation_pin = sha(metadata), sha(Path(__file__))
    config = gold_packet._read(metadata)
    need(isinstance(config, dict) and set(config) == {"format", "source_release", "source_url", "files", "version_proof"}
         and config["format"] == INPUT_FORMAT, "unsupported or extra metadata fields.")
    release = config["source_release"]
    need(isinstance(release, str) and re.fullmatch(r"[0-9]{8}", release), "provide the explicit native YYYYMMDD release.")
    gmt_name = "wikipathways-" + release + "-gmt-Homo_sapiens.gmt"
    need(config["source_url"] == "https://data.wikipathways.org/current/gmt/" + gmt_name,
         "provide the matching official native human GMT URL.")
    files, proof = config["files"], config["version_proof"]
    need(isinstance(files, dict) and set(files) == FILE_KEYS, "all eight named source/proof inputs are required.")
    need(isinstance(proof, dict) and set(proof) == {"Version", "canonical_WPID"}
         and isinstance(proof["Version"], str) and re.fullmatch(r"WP[1-9][0-9]*_r[1-9][0-9]*", proof["Version"])
         and proof["Version"].split("_r")[0] == proof["canonical_WPID"], "provide the exact native version/canonical-pathway relation.")
    paths = {}
    for key, record in files.items():
        need(isinstance(record, dict) and set(record) == {"path", "sha256"}
             and isinstance(record["path"], str) and bool(record["path"]), "each file needs only an explicit path and SHA256.")
        path = Path(record["path"])
        path = path if path.is_absolute() else metadata.parent / path
        paths[key] = pinned(path.absolute(), record["sha256"])
    for key in AUTHOR_PINS:
        need(files[key]["sha256"] == AUTHOR_PINS[key], "author-reader source differs from the reviewed code.")
    for key, name in (("reader_license", "pywp_LICENSE"), ("r_reader_documentation", "rWikiPathways_readPathwayGMT.R"),
                      ("r_reader_license", "rWikiPathways_LICENSE")):
        need(files[key]["sha256"] == AUTHOR_DOCUMENTATION_PINS[name], "author license/documentation differs from the reviewed source.")
    names = {"gmt": gmt_name, "read_gmt": "pywp_pywikipathways_read_gmt.py",
        "read_pathway_gmt": "pywp_pywikipathways_read_pathway_gmt.py", "reader_license": "pywp_LICENSE",
        "r_reader_documentation": "rWikiPathways_readPathwayGMT.R", "primary_paper_bioc": "wiki2024_primary_bioc.xml",
        "r_reader_license": "rWikiPathways_LICENSE",
        "gpml_version_proof": "native_version_example.gpml"}
    folder = new_output(output, metadata, *paths.values())
    with tempfile.TemporaryDirectory(prefix=".reference_build_", dir=folder) as temporary:
        stage = Path(temporary)
        for key, path in paths.items():
            shutil.copyfile(path, stage / names[key])
            pinned(stage / names[key], files[key]["sha256"])
        reference = {"format": REFERENCE_FORMAT, "created_at": utcnow(), "source_release": release,
            "source_url": config["source_url"], "source_sha256": files["gmt"]["sha256"], "species": "Homo sapiens",
            "native_author_parser": {"repository": AUTHOR_REPOSITORY, "commit": AUTHOR_COMMIT,
                "function": "read_pathway_gmt", "source_sha256": AUTHOR_PINS,
                "r_reader_license_sha256": files["r_reader_license"]["sha256"]},
            "version_mapping": {"relation": "dcterms:isVersionOf", "source_version_content_equivalence_claimed": False,
                "paper_bioc_sha256": files["primary_paper_bioc"]["sha256"],
                "native_legacy_GPML_example": {"file": names["gpml_version_proof"],
                    "sha256": files["gpml_version_proof"]["sha256"], **proof}},
            "scope": "Provided native human GMT and source-version proof only; no cohort labels or biological correctness judgments."}
        reference["content_sha256"] = digest(reference)
        pending = stage / "reference.json"
        write_json(pending, reference)
        memberships, replay = load_reference(pending, sha(pending))
        # Existing native reader validates actual file/version/key coverage.
        # No success report exists if that replay or any stability check fails.
        need(sha(metadata) == metadata_pin and sha(Path(__file__)) == implementation_pin,
             "metadata or implementation changed during preparation.")
        for key, path in paths.items():
            pinned(path, files[key]["sha256"])
            pinned(stage / names[key], files[key]["sha256"])
        (stage / "input_metadata.json").write_bytes(metadata.read_bytes())
        need(sha(stage / "input_metadata.json") == metadata_pin and sha(metadata) == metadata_pin,
             "metadata changed during export.")
        for key, path in paths.items():
            pinned(path, files[key]["sha256"])
        need(sha(Path(__file__)) == implementation_pin, "implementation changed during export.")
        for path in stage.iterdir():
            path.rename(folder / path.name)
    manifest = {"format": PACKET_FORMAT, "created_at": utcnow(), "status": "native_reference_replayed",
        "source_release": release, "source_url": config["source_url"],
        "reference_file": "reference.json", "reference_content_sha256": reference["content_sha256"],
        "reference_file_sha256": sha(folder / "reference.json"), "native_replay": replay,
        "pathways": len(memberships), "input_metadata_sha256": metadata_pin,
        "input_files_sha256": {key: {"path": str(path), "sha256": files[key]["sha256"]} for key, path in paths.items()},
        "files": {p.name: sha(p) for p in folder.iterdir() if p.is_file()},
        "implementation_sha256": implementation_pin, "cohort_specific_outcomes_included": False,
        "source_graph_changed": False, "scientific_accuracy_measured": False, "source_fetches": 0,
        "limits": ["Hashes/native replay establish local byte and format consistency, not publisher authentication or biological truth.",
            "The current author reader is pinned; its MIT license and identifier documentation are retained.",
            "The provided primary paper and GPML prove the declared version relation without asserting equal contents across releases.",
            "Data/provider terms remain separate from the project's software license."]}
    manifest["content_sha256"] = digest(manifest)
    write_json(folder / "reference_manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = prepare_reference(args.metadata, args.out)
    print(json.dumps({"output": str(args.out.resolve()), "reference_sha256": report["reference_file_sha256"],
           "pathways": report["pathways"], "manifest_sha256": report["content_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
