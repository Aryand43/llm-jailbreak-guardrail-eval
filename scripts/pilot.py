#!/usr/bin/env python3
"""Run the pilot one stage at a time (each stage loads one model, so run them as separate processes).

    uv run python scripts/pilot.py build
    uv run python scripts/pilot.py generate --backend vllm
    uv run python scripts/pilot.py guard    --backend vllm
    uv run python scripts/pilot.py translate --backend vllm   (only if the config has `languages`)
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
from harmfloor.run.translate import make_translator

ROOT = Path(__file__).resolve().parents[1]


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(path: Path) -> dict:
    """A config may say `extends: other.yaml` and override only what differs (ablation configs)."""
    cfg = yaml.safe_load(path.read_text())
    if "extends" in cfg:
        cfg = _merge(load_config(path.parent / cfg.pop("extends")), cfg)
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["build", "generate", "guard", "translate", "judge", "analyze", "all"])
    ap.add_argument("--config", default=str(ROOT / "configs" / "pilot.yaml"))
    ap.add_argument("--backend", choices=["vllm", "fake"], default="vllm")
    ap.add_argument("--run-dir", help="overrides run_dir in the config")
    ap.add_argument("--n", type=int, help="override pool size (e.g. 8 for a quick smoke test)")
    ap.add_argument("--limit", type=int, help="build: keep this many items per role/family (smoke test)")
    ap.add_argument("--tag", help="analyze: suffix for the results file (ablations)")
    ap.add_argument("--calibrate-on", choices=["single_turn", "dialogues"],
                    help="analyze: set thresholds on single-turn benign prompts or held-out benign dialogues")
    ap.add_argument("--permute-labels", action="store_true", help="analyze: shuffle harm labels within each pool")
    a = ap.parse_args()

    cfg = load_config(Path(a.config))
    run = ROOT / (a.run_dir or cfg["run_dir"])
    n = a.n or cfg["n"]
    # A fake run gets fake model names, so its files can never be mistaken for real results.
    target = cfg["target"] if a.backend == "vllm" else "fake-target"
    guard_model = cfg["guard"]["model"] if a.backend == "vllm" else "fake-guard"
    judge_model = cfg["judge"]["model"] if a.backend == "vllm" else "fake-judge"
    todo = ["build", "generate", "guard", "translate", "judge", "analyze"] if a.stage == "all" else [a.stage]

    for stage in todo:
        print(f"== {stage}")
        if stage == "build":
            print(stages.build(run, cfg["sources"], cfg["benign_per_source"], limit=a.limit,
                               languages=cfg.get("languages")))
        elif stage == "generate":
            print(stages.generate(run, make_backend(a.backend, target, cfg["vllm"]), n=n,
                                  decoding=cfg["decoding"]), "samples")
        elif stage == "guard":
            engine = {**cfg["vllm"], **cfg["guard"].get("vllm", {})}  # e.g. quantization for a larger guard
            print(stages.guard(run, make_backend(a.backend, guard_model, engine), cfg["guard"]["name"],
                               context=cfg["guard"].get("context", "final")), "guard scores")
        elif stage == "translate":
            if not set(cfg.get("languages") or []) - {"en"}:
                print("no non-English items in this config; nothing to translate")
                continue
            tr = make_translator(a.backend, cfg.get("translate", {}).get("model"))
            print(stages.translate(run, tr, model=target), "translation rows")
        elif stage == "judge":
            engine = {**cfg["vllm"], **cfg["judge"].get("vllm", {})}
            print(stages.judge(run, make_backend(a.backend, judge_model, engine), cfg["judge"]["name"],
                               threshold=cfg["judge"]["harmful_threshold"],
                               use_translation=cfg["judge"].get("use_translation", True),
                               fold_system=cfg["judge"].get("fold_system", False),
                               max_tokens=cfg["judge"].get("max_tokens", 32)), "labels")
        else:
            for group_by in cfg.get("group_by", ["attack_family"]):
                res = stages.analyze(run, model=target, guard_name=cfg["guard"]["name"],
                                     judge_name=cfg["judge"]["name"], budgets=cfg["budgets"],
                                     max_fprs=cfg["max_fpr"], n_boot=cfg["n_boot"], group_by=group_by,
                                     calibrate_on=a.calibrate_on or cfg.get("calibrate_on", "single_turn"),
                                     permute_labels=a.permute_labels, tag=a.tag or cfg.get("tag"))
                for setting, cells in res["cells"].items():
                    for grp, c in cells.items():
                        print(f"{setting:9} {grp:40} prompts={c['prompts']:3d} U={c['ceiling']:.3f} "
                              f"rho_max={list(c['rho'].values())[-1]:.3f} L={c['floor']:.3f} "
                              f"model_free_positive={c['model_free_positive']}")
                print(f"results: {run / stages.results_name(group_by, a.tag or cfg.get('tag'))}")


if __name__ == "__main__":
    main()
