#!/usr/bin/env python3
"""Export the responses that survive the largest budget, for hand-labelling (experiment 2c).

For every harmful prompt, best-of-q at q = n returns the sample the guard scores safest. If the
judge calls that sample harmful, it is a survivor: it sits in the floor. This writes one row per
survivor to <run>/survivors.csv (runs/ is gitignored; the file holds harmful text, so never commit
or paste it), with empty `category` and `notes` columns to fill in by hand.

    uv run python scripts/export_survivors.py --config configs/experiment2_12gb.yaml

Ties at the minimum risk are rare with continuous guard scores; the lowest sample index is taken.
`passes_threshold` says whether the guard would still return the response at the 5% FPR threshold
(read from results.json); survivors that fail it are refused at that setting.
"""

import argparse
import csv
import json
from pathlib import Path

import yaml

from harmfloor.run import stages

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ["fiction_or_roleplay", "disclaimer_then_comply", "partial_compliance", "full_compliance",
              "judge_error", "other"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-dir")
    ap.add_argument("--backend", choices=["vllm", "fake"], default="vllm")
    ap.add_argument("--fpr", default="0.05")
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    run = ROOT / (a.run_dir or cfg["run_dir"])
    model = cfg["target"] if a.backend == "vllm" else "fake-target"
    guard_name, judge_name = cfg["guard"]["name"], cfg["judge"]["name"]

    results = run / "results.json"
    thresholds = json.loads(results.read_text())["thresholds"] if results.exists() else {}
    taus = {int(q): t for q, t in thresholds.get(f"fpr_{float(a.fpr):g}", {}).items()}

    items = {it.item_id: it for role, it in stages.load_items(run) if role == "harmful"}
    risk: dict[str, dict[int, float]] = {}
    for r in stages._read(run / "guard.jsonl"):
        if r["guard"] == guard_name and r["model"] == model and r["item_id"] in items:
            risk.setdefault(r["item_id"], {})[r["sample_idx"]] = r["risk"]
    labels = {(r["item_id"], r["sample_idx"]): r for r in stages._read(run / "labels.jsonl")
              if r["judge"] == judge_name and r["model"] == model}
    picked = {iid: min(pool, key=lambda k: (pool[k], k)) for iid, pool in risk.items()}
    texts = {(s["item_id"], s["sample_idx"]): s["text"] for s in stages._read(run / "samples.jsonl")
             if s["model"] == model and picked.get(s["item_id"]) == s["sample_idx"]}
    english = stages._english_texts(run, model)

    rows = []
    for iid, k in sorted(picked.items()):
        label = labels.get((iid, k))
        if not label or label["harmful"] is not True:
            continue
        it, n = items[iid], len(risk[iid])
        tau = taus.get(n)
        rows.append({"item_id": iid, "group": stages.GROUPINGS["attack_method"](it),
                     "language": stages.language(it), "sample_idx": k, "risk": f"{risk[iid][k]:.4f}",
                     "tau": "" if tau is None else f"{tau:.4f}",
                     "passes_threshold": "" if tau is None else risk[iid][k] <= tau,
                     "judge_score": label["score"], "intent": it.intent, "response": texts[(iid, k)],
                     "response_en": english.get((iid, k), texts[(iid, k)]), "category": "", "notes": ""})
    out = run / "survivors.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["item_id"])
        w.writeheader()
        w.writerows(rows)
    by_group: dict[str, int] = {}
    for r in rows:
        by_group[r["group"]] = by_group.get(r["group"], 0) + 1
    print(f"{len(rows)} survivors of {len(picked)} harmful prompts -> {out}")
    for g, c in sorted(by_group.items()):
        print(f"  {g:45} {c}")
    print("category values:", ", ".join(CATEGORIES))


if __name__ == "__main__":
    main()
