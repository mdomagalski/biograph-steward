"""Score one qualified native reference on a fixed design or exact census.

Only a qualified external native-reference adapter can supply labels. A JSONL
file containing AI verdicts is deliberately not an accepted scoring input.
"""
from collections import Counter
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.reference_accuracy import design, estimation, go_reference, cornish

ADAPTERS = {"go_experimental": go_reference, "crc_genomic_cohort": cornish}


def score(packet, reference, output, *, reference_sha256, design_directory=None,
          dispositions=None, disposition_report_sha256=None, reference_kind="go_experimental"):
    design.need(reference_kind in ADAPTERS, "unsupported reference kind; free-form AI labels are not accepted.")
    adapter = ADAPTERS[reference_kind]
    manifest, graph, retained_ids, binding, source_pins = design.source_inputs(
        packet, dispositions, disposition_report_sha256)
    ref, labels = adapter.load_reference(reference, packet, report_sha256=reference_sha256)
    pins = {**source_pins, str(Path(reference).absolute() / "report.json"): reference_sha256,
        **{str(Path(reference).absolute() / name): value for name, value in ref["files"].items()}}
    implementations = {name: sha(ROOT / "tools/reference_accuracy" / name)
                       for name in ("design.py", "estimation.py", Path(adapter.__file__).name, "score.py")}
    if design_directory is None:
        frame, _ = design.frame_for(graph, retained_ids=retained_ids)
        allocation = dict(Counter(row["stratum"] for row in frame))
        strata, sample = design.selected_rows(frame, allocation, 0)
        method = {"mode": "exact_census", "sampling_uncertainty": False,
                  "population_unit": "original stored qualified assertion ID", "disposition_binding": binding}
    else:
        frozen, protocol, frozen_graph, sample = design.load_design(design_directory, packet,
            dispositions=dispositions, disposition_report_sha256=disposition_report_sha256)
        design.need(frozen_graph == graph, "frozen design refers to another original graph.")
        strata = frozen["strata"]
        folder = Path(design_directory).absolute()
        pins.update({str(folder / design.MANIFEST): sha(folder / design.MANIFEST),
                     **{str(folder / name): value for name, value in frozen["files"].items()}})
        method = {"mode": "frozen_stratified_SRSWOR", "sample_id": frozen["sample_id"],
            "design_manifest_file_sha256": sha(folder / design.MANIFEST),
            "protocol_content_sha256": protocol["content_sha256"], "disposition_binding": binding,
            "outside_declared_family_domain_assertions": protocol["outside_domain_assertions"]}
    source_labels = {row["assertion_id"]: row for row in labels}
    scored = []
    for case in sample:
        row = source_labels[case["assertion_id"]]
        design.need(row["assertion_sha256"] == case["assertion_sha256"] and row["family"] == case["family"],
                    "reference label does not bind the exact selected original assertion.")
        scored.append({**case, "verdict": row["verdict"], "axis": row["axis"], "reason": row["reason"],
            "reference_report_content_sha256": ref["content_sha256"],
            "reference_label_sha256": digest(row), "independent_scientific_correctness": "unreviewed"})
    stats = estimation.estimate(strata, sample, scored)
    folder = new_output(output, packet, reference, *([design_directory] if design_directory else []),
                        *([dispositions] if dispositions else []))
    design.write_jsonl(folder / "labels.jsonl", scored)
    write_json(folder / "statistics.json", stats)
    # Re-read all external source and proof bytes after writing results. No
    # success report can survive a concurrent input/reference/code mutation.
    design.need(all(sha(path) == expected for path, expected in pins.items())
         and implementations == {name: sha(ROOT / "tools/reference_accuracy" / name) for name in implementations},
         "source/reference/design or implementation changed during scoring.")
    result = {"format": "biograph-steward.reference-agreement-score.v1", "created_at": utcnow(),
        "packet_id": manifest["packet_id"], "graph_sha256": manifest["graph_sha256"],
        "reference_report_file_sha256": reference_sha256, "reference_axis": adapter.AXIS,
        "reference_kind": reference_kind, "positive_only_reference": True,
        "resolved_only_agreement_ratio_is_accuracy_evidence": False,
        "method": method, "strata": strata, "population_assertions": stats["overall"]["population_units"],
        "sampled_assertions": len(sample), "counts": dict(Counter(row["verdict"] for row in scored)),
        "source_graph_changed": False, "old_audits_reused_or_changed": False,
        "all_independent_scientific_correctness_unreviewed": True,
        "independent_experiments_validated": False, "whole_graph_biological_accuracy_measured": False,
        "prediction_benefit_measured": False, "input_files_sha256": pins,
        "implementation_sha256": implementations, "limitations": adapter.LIMITATIONS,
        "files": {p.name: sha(p) for p in folder.iterdir() if p.is_file()}}
    result["content_sha256"] = digest(result)
    write_json(folder / "report.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("packet", "reference", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--reference-sha256", required=True)
    p.add_argument("--reference-kind", choices=sorted(ADAPTERS), default="go_experimental")
    p.add_argument("--design", type=Path, help="Omit for an exact whole-frame census; no labels are sampled then.")
    p.add_argument("--dispositions", type=Path)
    p.add_argument("--disposition-report-sha256")
    a = p.parse_args()
    print(score(a.packet, a.reference, a.out, reference_sha256=a.reference_sha256,
        design_directory=a.design, dispositions=a.dispositions,
        disposition_report_sha256=a.disposition_report_sha256, reference_kind=a.reference_kind)["content_sha256"])


if __name__ == "__main__":
    main()
