#!/usr/bin/env python3
"""Harm vs guardrail budget for a pilot run, from its results.json (numbers only).

    uv run python scripts/plot_pilot.py results/pilot-12gb/results.json --setting fpr_0.05
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

SERIES = {"multi_turn": ("#eb6834", "Multi-turn attacks"), "direct": ("#2a78d6", "Direct requests")}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--setting", default="fpr_0.05")
    ap.add_argument("--out")
    a = ap.parse_args()
    res = json.loads(Path(a.results).read_text())
    cells = res["cells"][a.setting]
    qs = res["budgets"]
    xs = list(range(len(qs) + 1))  # position 0 = no guardrail (ceiling)
    labels = ["none"] + [str(q) for q in qs]

    plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#8a8984", "xtick.color": INK2, "ytick.color": INK2})
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.grid(axis="y", color=GRID, lw=0.8)
    for family, (color, name) in SERIES.items():
        c = cells.get(family)
        if not c:
            continue
        ys = [100 * c["ceiling"]] + [100 * c["rho"][str(q)] for q in qs]
        ax.plot(xs, ys, color=color, lw=2.2, marker="o", ms=6, mec="white", mew=1.5, zorder=3,
                label=f"{name} ({c['prompts']} prompts)")
        if c["asymptote_positive"]:
            lo, hi = (100 * v for v in c["floor_ci"])
            ax.plot([xs[1], xs[-1] + 0.4], [100 * c["floor"]] * 2, color=color, ls="--", lw=1.2, zorder=2)
            ax.text(xs[-1] + 0.5, 100 * c["floor"], f"floor ≈ {100 * c['floor']:.0f}%\n(95% CI {lo:.0f}–{hi:.0f}%)",
                    color=INK, va="center", fontsize=9.3)
        ax.text(xs[0] - 0.15, ys[0], f"{ys[0]:.0f}%", color=INK, va="center", ha="right", fontsize=9.5)
    ax.set_xticks(xs, labels)
    ax.set_xlim(-0.7, xs[-1] + 2.3)
    ax.set_ylim(0, None)
    ax.set_xlabel("Guardrail budget q (responses the guardrail compares)", color=INK2)
    ax.set_ylabel("Harmful responses (%)", color=INK2)
    ax.legend(frameon=False, loc="upper right")
    fpr = a.setting.replace("fpr_", "")
    fig.text(0.01, -0.07, f"Pilot, raw judge rates: Llama-3.1-8B (4-bit), Llama Guard 3 1B best-of-q at {float(fpr):.0%} "
             f"false positives,\nQwen2.5-7B judge (not yet checked against human labels). Floor = fitted level harm settles at.",
             fontsize=8.3, color=INK2)
    out = Path(a.out) if a.out else Path(a.results).with_name(f"harm_vs_budget_{a.setting}.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print(out)


if __name__ == "__main__":
    main()
