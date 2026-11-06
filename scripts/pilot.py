#!/usr/bin/env python3
"""Run the pilot one stage at a time (each stage loads one model, so run them as separate processes).

    uv run python scripts/pilot.py build
    uv run python scripts/pilot.py generate --backend vllm
    uv run python scripts/pilot.py guard    --backend vllm
    uv run python scripts/pilot.py judge    --backend vllm
    uv run python scripts/pilot.py analyze

Dry run on a laptop, no model needed:  uv run python scripts/pilot.py all --backend fake --run-dir runs/dry
"""

import argparse
import json
from pathlib import Path

import yaml

from harmfloor.run import stages
from harmfloor.run.backend import make_backend

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["build", "generate", "guard", "judge", "analyze", "all"])
    ap.add_argument("--config", default=str(ROOT / "configs" / "pilot.yaml"))
    ap.add_argument("--backend", choices=["vllm", "fake"], default="vllm")
    ap.add_argument("--run-dir", help="overrides run_dir in the config")
    ap.add_argument("--n", type=int, help="override pool size (e.g. 8 for a quick smoke test)")
    a = ap.parse_args()

    cfg = yaml.safe_load(Path(a.config).read_text())
    run = ROOT / (a.run_dir or cfg["run_dir"])
    n = a.n or cfg["n"]
    # A fake run gets fake model names, so its files can never be mistaken for real results.
    target = cfg["target"] if a.backend == "vllm" else "fake-target"
    guard_model = cfg["guard"]["model"] if a.backend == "vllm" else "fake-guard"
    judge_model = cfg["judge"]["model"] if a.backend == "vllm" else "fake-judge"
    todo = ["build", "generate", "guard", "judge", "analyze"] if a.stage == "all" else [a.stage]

    for stage in todo:
        print(f"== {stage}")
        if stage == "build":
            print(stages.build(run, cfg["sources"], cfg["benign_per_source"]))
        elif stage == "generate":
            print(stages.generate(run, make_backend(a.backend, target, cfg["vllm"]), n=n,
                                  decoding=cfg["decoding"]), "samples")
        elif stage == "guard":
            print(stages.guard(run, make_backend(a.backend, guard_model, cfg["vllm"]), cfg["guard"]["name"]),
                  "guard scores")
        elif stage == "judge":
            print(stages.judge(run, make_backend(a.backend, judge_model, cfg["vllm"]), cfg["judge"]["name"],
                               threshold=cfg["judge"]["harmful_threshold"]), "labels")
        else:
            res = stages.analyze(run, model=target, guard_name=cfg["guard"]["name"],
                                 judge_name=cfg["judge"]["name"], budgets=cfg["budgets"],
                                 max_fprs=cfg["max_fpr"], n_boot=cfg["n_boot"])
            for setting, cells in res["cells"].items():
                for fam, c in cells.items():
                    print(f"{setting:9} {fam:11} prompts={c['prompts']:3d} U={c['ceiling']:.3f} "
                          f"rho_max={list(c['rho'].values())[-1]:.3f} L={c['floor']:.3f} "
                          f"model_free_positive={c['model_free_positive']}")
            print(f"results: {run / 'results.json'}")


if __name__ == "__main__":
    main()
