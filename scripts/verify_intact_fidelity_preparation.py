#!/usr/bin/env python3
"""Replay the preparation with an explicitly acknowledged semantic amendment.

The original preparation is immutable. This guard applies its linked semantic
correction in memory, without opening source MITAB bytes or evaluating evidence.
Any later interpreter/evaluator must bind this effective contract and amendment.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.file_utils import sha
from scripts.prepare_intact_fidelity_reference import verify_freeze

PROTOCOL_SHA = "d4948f584b8eed374ddfa49084ee58f1fb352d3d68a6630a202bf25742f8920a"
PANEL_SHA = "38c0b5929bc0c02213ffd66f6c4e7d68924351c3651273a78ce851b5f873de89"
AMENDMENT_FORMAT = "biograph-steward.intact-fidelity-semantic-amendment.v1"


def amended_contract(protocol_path, amendment_path, expected_amendment_sha):
    """Require original bytes, exact acknowledged amendment and pinned evidence."""
    protocol_path, amendment_path = Path(protocol_path), Path(amendment_path)
    if sha(protocol_path) != PROTOCOL_SHA:
        raise ValueError("Original frozen protocol changed.")
    if not expected_amendment_sha or sha(amendment_path) != expected_amendment_sha:
        raise ValueError("Explicit semantic-amendment SHA-256 acknowledgement is required.")
    amendment = json.loads(amendment_path.read_text())
    if (amendment["format"] != AMENDMENT_FORMAT
            or amendment["original_protocol_sha256"] != PROTOCOL_SHA
            or amendment["original_panel_sha256"] != PANEL_SHA
            or amendment["reference_values_accessed_for_amendment"] is not False
            or amendment["replacement"]["path"] != "/field_contract/4/rule"):
        raise ValueError("Amendment does not bind the frozen preparation and allowed field.")
    for source in amendment["evidence"]:
        if sha(ROOT / source["local_path"]) != source["sha256"]:
            raise ValueError("Pinned semantic evidence changed.")
    if sha(__file__) != amendment["replay_guard_sha256"]:
        raise ValueError("Amendment replay guard changed.")
    protocol = json.loads(protocol_path.read_text())
    original = protocol["field_contract"][4]
    replacement = amendment["replacement"]
    if original["group"] != "complex_expansion" or original["rule"] != replacement["original"]:
        raise ValueError("Amendment target does not exactly match the original rule.")
    result = deepcopy(protocol)
    result["field_contract"][4]["rule"] = replacement["corrected"]
    result["effective_contract_amendment_sha256"] = expected_amendment_sha
    result["original_protocol_sha256"] = PROTOCOL_SHA
    return result


def replay(panel_path, expected_panel_sha, amendment_path, expected_amendment_sha):
    if expected_panel_sha != PANEL_SHA:
        raise ValueError("Use the original frozen panel SHA-256.")
    panel = verify_freeze(panel_path, expected_panel_sha)
    result = amended_contract(ROOT / panel["protocol"]["path"], amendment_path,
                              expected_amendment_sha)
    return {"status": "original_preparation_verified_with_semantic_amendment",
            "original_panel_sha256": expected_panel_sha,
            "effective_contract_amendment_sha256": result["effective_contract_amendment_sha256"],
            "reference_rows_opened": False, "evaluation_executed": False,
            "complex_expansion_rule": result["field_contract"][4]["rule"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("panel", "expected-panel-sha256", "amendment", "expected-amendment-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = replay(args.panel, args.expected_panel_sha256, args.amendment,
                    args.expected_amendment_sha256)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
