#!/usr/bin/env python3
"""Exercise upstream graph learners on bundled Nations data, validation only.

This is an engineering smoke check, not a biomedical benchmark. It deliberately
has no option to load our graph, experimental relationship labels, or a model
checkpoint. See docs/literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import traceback
from datetime import datetime, timezone
from importlib.metadata import distributions, version
from pathlib import Path


COMMON = {
    "dataset": "Nations",
    "device": "cpu",
    "random_seed": 42,
    "training_loop": "sLCWA",
    "training_kwargs": {"num_epochs": 2, "batch_size": 128},
    "negative_sampler": "basic",
    "negative_sampler_kwargs": {
        "num_negs_per_pos": 1,
        "filtered": True,
        "filterer": "python-set",
    },
    "evaluator": "RankBasedEvaluator",
    "evaluator_kwargs": {"filtered": True},
    "evaluation_kwargs": {"batch_size": 32},
    "use_testing_data": False,
    "use_tqdm": False,
}
MODELS = {
    "ComplEx": {"embedding_dim": 16},
    "RGCN": {
        "embedding_dim": 16,
        "num_layers": 1,
        "decomposition": "bases",
        "decomposition_kwargs": {"num_bases": 2},
    },
}


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    try:
        for name, expected in {"pykeen": "1.11.1", "torch": "2.6.0"}.items():
            if version(name) != expected:
                raise RuntimeError(f"Expected {name}=={expected}; found {version(name)}")

        from pykeen.pipeline import pipeline

        write_json(args.output_dir / "manifest.json", {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "purpose": "engineering_feasibility_only",
            "python": platform.python_version(),
            "platform": platform.platform(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "packages": {item.metadata["Name"]: item.version for item in distributions()},
            "common_configuration": COMMON,
            "model_configurations": MODELS,
            "evaluation_partition": "validation",
            "biomedical_inputs_used": False,
            "note": "Nations loader may load its test file; test outcomes are not evaluated.",
        })
        for model_name, model_kwargs in MODELS.items():
            result = pipeline(
                model=model_name,
                model_kwargs=copy.deepcopy(model_kwargs),
                **copy.deepcopy(COMMON),
            )
            metrics = {
                name: float(result.metric_results.get_metric(name))
                for name in ("both.realistic.inverse_harmonic_mean_rank", "both.realistic.hits_at_10")
            }
            losses = [float(value) for value in result.losses]
            if len(losses) != 2 or not all(math.isfinite(value) for value in [*losses, *metrics.values()]):
                raise RuntimeError(f"{model_name}: incomplete training or non-finite output")
            write_json(args.output_dir / f"{model_name.lower()}.json", {
                "model": model_name,
                "status": "passed",
                "device": str(result.model.device),
                "training_triples": result.training.num_triples,
                "training_entities": result.training.num_entities,
                "training_relations": result.training.num_relations,
                "losses": losses,
                "validation_metrics": metrics,
                "training_seconds": result.train_seconds,
                "evaluation_seconds": result.evaluate_seconds,
            })
            print(f"{model_name}: passed (CPU, Nations, 2 epochs, validation only)", flush=True)
    except Exception as error:
        write_json(args.output_dir / "failure.json", {
            "status": "failed",
            "error": str(error),
            "traceback": traceback.format_exc(),
        })
        raise


if __name__ == "__main__":
    main()
