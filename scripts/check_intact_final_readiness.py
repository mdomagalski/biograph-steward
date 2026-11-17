#!/usr/bin/env python3
"""Prepare-only IntAct rules preflight; never opens a reference body or runs it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.file_utils import sha

RULES = "docs/evaluations/intact_final_evaluation_20261026_rules.json"
PROTOCOL = "docs/evaluations/intact_fidelity_20261026_protocol.json"
AMENDMENT = "docs/evaluations/intact_fidelity_20261026_semantic_amendment.json"
ORIGINAL_PINS = {
    PROTOCOL: "d4948f584b8eed374ddfa49084ee58f1fb352d3d68a6630a202bf25742f8920a",
    AMENDMENT: "2cd2cb485836228ce71dd9d62201c61dd5de45d18563894ac883f188f245e98c",
}
RESERVED = ["39833857", "40211762", "39972491", "40555359"]
REQUIRED_METADATA = {
    "docs/evaluations/intact_fidelity_20261026_preparation.json",
    "docs/evaluations/intact_xml_development_20261026_summary.json",
    "docs/evaluations/intact_evidence_flow_20261026_summary.json",
    "docs/evaluations/intact_provenance_readiness_20261026_summary.json",
    "docs/evaluations/intact_development_provenance_audit_20261026_summary.json",
}
ALLOWED = {
    RULES, *ORIGINAL_PINS, *REQUIRED_METADATA,
    "docs/evaluations/intact_development_provenance_audit_20261026_summary.json",
    "docs/evaluations/intact_reader_development_20261026_summary.json",
    "docs/evaluations/intact_xml_development_20261026_summary.json",
    "docs/evaluations/intact_evidence_flow_20261026_summary.json",
    "docs/evaluations/intact_final_execution_readiness_20261026.json",
    "docs/evaluations/intact_final_synthetic_20261026_summary.json",
    "docs/evaluations/intact_final_development_20261026_summary.json",
    "scripts/run_intact_final_evaluation.py",
    "scripts/check_intact_final_readiness.py",
}


def safe_path(root, relative):
    """Validate an explicit allowlisted path without opening its target."""
    if (not isinstance(relative, str) or relative not in ALLOWED
            or str(PurePosixPath(relative)) != relative
            or PurePosixPath(relative).is_absolute()):
        raise ValueError("Unapproved metadata/code path: " + str(relative))
    path = Path(root)
    if path.is_symlink():
        raise ValueError("Symlink root is not permitted.")
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Symlink metadata/code path is not permitted.")
    return path


def verify_bindings(root, bindings):
    """Reject every unsafe path before hashing any declared input."""
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("Explicit nonempty metadata bindings are required.")
    paths = []
    for binding in bindings:
        if (not isinstance(binding, dict) or set(binding) != {"path", "sha256"}
                or not re.fullmatch(r"[0-9a-f]{64}", str(binding.get("sha256", "")))):
            raise ValueError("Use explicit path/SHA-256 bindings.")
        paths.append(safe_path(root, binding["path"]))
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate metadata/code binding.")
    for path, binding in zip(paths, bindings):
        if not path.is_file() or sha(path) != binding["sha256"]:
            raise ValueError("Pinned metadata/code changed or missing: " + binding["path"])


def check(root=ROOT):
    """Check metadata and declarations only; no permission to open held-out rows."""
    rules = json.loads(safe_path(root, RULES).read_text(encoding="utf-8"))
    if not isinstance(rules, dict) or rules.get("format") != "biograph-steward.intact-final-evaluation-rules.v1":
        raise ValueError("Unsupported final-rules format.")
    if rules.get("reserved_publication_ids") != RESERVED:
        raise ValueError("The exact frozen reserved publication list is required.")
    if (rules.get("prepare_only_checker_authorizes_reserved_access") is not False
            or rules.get("reserved_bodies_accessed_for_these_rules") is not False):
        raise ValueError("Rules must remain prepare-only with reserved bodies unopened.")
    metadata_bindings = rules.get("metadata_bindings")
    if (not isinstance(metadata_bindings, list)
            or any(not isinstance(item, dict) for item in metadata_bindings)
            or {item.get("path") for item in metadata_bindings} != REQUIRED_METADATA):
        raise ValueError("All five explicit preparation/development metadata seals are required.")
    declared = [rules.get("original_protocol"), rules.get("semantic_amendment")]
    declared += metadata_bindings
    for binding, (path, expected) in zip(declared[:2], ORIGINAL_PINS.items()):
        if binding != {"path": path, "sha256": expected}:
            raise ValueError("Original protocol/amendment seals may not change.")
    policy = rules.get("rules", {})
    if (not isinstance(policy, dict) or policy.get("unknown_lineage_is_independent") is not False
            or policy.get("overlap_exclusions_change_source_eligibility") is not False
            or policy.get("source_eligibility_denominator") !=
            "all_source_eligible_records_before_cohort_resolution"):
        raise ValueError("Lineage, overlap or source-eligibility denominator rule is unsafe.")
    readiness = rules.get("execution_readiness", {})
    if not isinstance(readiness, dict):
        raise ValueError("Execution-readiness declarations must be a metadata object.")
    future = readiness.get("metadata")
    if future is not None:
        if (not isinstance(future, dict)
                or future.get("path") != "docs/evaluations/intact_final_execution_readiness_20261026.json"):
            raise ValueError("Use the explicitly allowed separate execution-readiness metadata.")
        declared.append(future)
    elif (readiness.get("status") != "not_ready"
          or any(readiness.get(key) is not None for key in
                 ("full_flow_runner", "synthetic_checks", "development_checks"))
          or readiness.get("immutable_bindings_declared") is not False):
        raise ValueError("A ready claim requires separate sealed full-flow readiness metadata.")
    verify_bindings(root, declared)
    remaining = readiness.get("remaining_checks")
    if not isinstance(remaining, list) or any(not isinstance(item, str) for item in remaining):
        raise ValueError("Declare the remaining checks as a list of descriptions.")
    remaining = list(remaining)
    if future is None:
        remaining.append("No sealed full-flow runner and synthetic/development readiness metadata.")
    else:
        meta = json.loads(safe_path(root, future["path"]).read_text(encoding="utf-8"))
        if (not isinstance(meta, dict)
                or meta.get("format") != "biograph-steward.intact-final-execution-readiness.v1"
                or meta.get("full_flow_runner_declared") is not True
                or meta.get("immutable_bindings_declared") is not True):
            raise ValueError("Execution metadata must declare the full flow and immutable bindings.")
        checks = [meta.get("full_flow_runner"), meta.get("synthetic_checks"), meta.get("development_checks")]
        if any(not isinstance(item, dict) for item in checks):
            raise ValueError("A runner, synthetic checks and development checks are all required.")
        if any(item.get("status") != "passed" for item in checks[1:]):
            raise ValueError("Synthetic and development full-flow checks must pass.")
        verify_bindings(root, [{"path": item.get("path"), "sha256": item.get("sha256")} for item in checks])
        if checks[0]["path"] != "scripts/run_intact_final_evaluation.py":
            raise ValueError("Use the explicit full-flow runner, not a development reader.")
        remaining.append("Execution declarations checked only; held-out access and scoring not authorized by this preflight.")
    return {"format": "biograph-steward.intact-final-readiness-check.v1",
            "status": "blocked", "rules_metadata_verified": True,
            "rules_sha256": sha(safe_path(root, RULES)),
            "verified_metadata_sha256": {item["path"]: item["sha256"] for item in declared},
            "reserved_reference_bodies_accessed": False, "evaluation_executed": False,
            "authorizes_reference_access": False, "remaining_checks": remaining}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        result = check()
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc),
                          "reserved_reference_bodies_accessed": False,
                          "evaluation_executed": False, "authorizes_reference_access": False}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
