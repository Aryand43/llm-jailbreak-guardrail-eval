#!/usr/bin/env python3
"""Illustrative bound analysis on the NeurIPS submission's Table 1 aggregate rates.

NOT an ACL result. Table 1 gives only aggregate rates (N = 120) at q in {1, 4, 16, 64}, with no
prompt-level logs, so this script resamples each rate as Binomial(120, rho) / 120 in place of
the prompt-level cluster bootstrap that real runs use. Its purpose is to show the figures and
the decomposition the methodology produces, using numbers the group has already seen.

    .venv/bin/python scripts/demo_neurips_table.py   ->  figures/demo_*.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from harmfloor import bounds as b
from harmfloor import plots

N = 120
QS = [1, 4, 16, 64]
# neurips.tex Table 1 (tab:harm-rates): no-filter rate, then each filter at q = 1, 4, 16, 64
TABLE1 = {
    "LLaMA-3.2 3B": {"none": 0.52, "black-box": [0.42, 0.33, 0.28, 0.26], "white-box": [0.45, 0.36, 0.31, 0.29],
                     "sq": [0.44, 0.35, 0.30, 0.27], "guardrail": [0.38, 0.30, 0.24, 0.22]},
    "Nemotron 70B": {"none": 0.41, "black-box": [0.31, 0.22, 0.18, 0.15], "white-box": [0.33, 0.25, 0.21, 0.19],
                     "sq": [0.32, 0.24, 0.20, 0.17], "guardrail": [0.27, 0.19, 0.14, 0.12]},
    "Nemotron 253B": {"none": 0.35, "black-box": [0.24, 0.16, 0.12, 0.09], "white-box": [0.27, 0.19, 0.15, 0.12],
                      "sq": [0.25, 0.17, 0.13, 0.10], "guardrail": [0.20, 0.13, 0.09, 0.07]},
}
OUT = Path(__file__).resolve().parents[1] / "figures"


def parametric_estimate(u: float, rho: list[float], n_boot: int = 2000, seed: int = 0) -> b.BoundEstimate:
    rng = np.random.default_rng(seed)
    rho = np.asarray(rho)
    fit = b.fit_floor(QS, rho)
    us, Ls, rmax = [], [], []
    for _ in range(n_boot):
        rb = rng.binomial(N, rho) / N
        us.append(rng.binomial(N, u) / N)
        Ls.append(b.fit_floor(QS, rb).L)
        rmax.append(rb[-1])
    ci = lambda a: (float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5)))
    return b.BoundEstimate(u, ci(us), rho, fit, ci(Ls), ci(rmax), float(np.mean(np.asarray(Ls) < 1e-3)))


def main() -> None:
    plots.style()
    OUT.mkdir(exist_ok=True)
    # headline cell per model: the strongest filter (layered guardrail), as in the NeurIPS RQ3 floor
    est = {m: parametric_estimate(r["none"], r["guardrail"]) for m, r in TABLE1.items()}

    print(f"{'model':15} {'filter':10} {'U':>5} {'rho64':>6} {'L':>6} {'L 95% CI':>14} {'alpha':>6} {'P(L=0)':>7}")
    for m, rows in TABLE1.items():
        for f in ("black-box", "white-box", "sq", "guardrail"):
            e = parametric_estimate(rows["none"], rows[f], n_boot=500)
            print(f"{m:15} {f:10} {e.ceiling:5.2f} {e.rho[-1]:6.2f} {e.floor:6.3f} "
                  f"[{e.floor_ci[0]:.3f}, {e.floor_ci[1]:.3f}] {e.fit.alpha:6.2f} {e.frac_zero_floor:7.2f}")

    fig, axes = plt.subplots(1, 3, figsize=(9, 2.8), sharey=True)
    plots.bound_bands(axes, est, QS)
    fig.suptitle("Illustrative: layered guardrail, NeurIPS Table 1 rates refit (not ACL results)", color=plots.INK_2, fontsize=8, y=1.06)
    fig.savefig(OUT / "demo_bound_bands.png")

    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    plots.bound_map(ax, est)
    ax.set_title("Illustrative bound map (NeurIPS Table 1 rates)", color=plots.INK_2, fontsize=8)
    fig.savefig(OUT / "demo_bound_map.png")

    dec = {m: b.BoundDecomposition(e.ceiling, e.rho[-1], e.floor) for m, e in est.items()}
    fig, ax = plt.subplots(figsize=(5.4, 1.9))
    plots.decomposition(ax, dec)
    fig.savefig(OUT / "demo_decomposition.png")
    for m, d in dec.items():
        print(f"{m:15} removed={d.removed:.2f} reducible={d.reducible:.2f} irreducible={d.irreducible:.2f} "
              f"position={d.position:.2f} irreducible_share={d.irreducible_share:.2f}")


if __name__ == "__main__":
    main()
