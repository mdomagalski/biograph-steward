"""Prepare explicit consumed-development examples; never call a hosted service."""
import argparse
import json
from pathlib import Path

from biograph_steward.support_comparator import prepare_comparator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selections", type=Path, required=True,
                        help="JSON list of run, assertion_id and consumed_development_reason")
    parser.add_argument("--upstream", type=Path, required=True,
                        help="Downloaded pinned OptimusKG source and LICENSE folder")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare_comparator(json.loads(args.selections.read_text()), args.output, args.upstream)
    print(json.dumps({k: report[k] for k in ("status", "case_count", "unique_query_count", "hosted_model_calls")}, indent=2))


if __name__ == "__main__":
    main()
