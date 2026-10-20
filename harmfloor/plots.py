"""Paper figures for the bound analysis (static matplotlib, print-safe).

bound_bands:    rho(q) per model with the fitted floor L and ceiling U (results §5.1)
bound_map:      one dot per model at (ceiling U, floor L); Terry's model-dots view (§5.4)
decomposition:  stacked removed / reducible / irreducible bars per model (§5.4)
floor_heatmap:  floor L for models x attack families, the taxonomy cross (§5.2)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np

from harmfloor.bounds import BoundDecomposition, BoundEstimate

# Reference categorical order (dataviz palette, light mode). Scatter / small multiples
# validate for the first three slots only; past three, facet or fold into "Other".
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK_2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
SEGMENTS = {"removed": "#d9d8d4", "reducible": "#9cc1ee", "irreducible": "#1c5cab"}


def style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK_2,
            "axes.titlesize": 9,
            "axes.titlecolor": INK,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
        }
    )


def bound_bands(
    ax_row: Sequence[plt.Axes],
    estimates: Mapping[str, BoundEstimate],
    qs: Sequence[int],
) -> None:
    """One panel per model: observed rho(q), fitted curve, floor band and ceiling."""
    qs = np.asarray(qs, float)
    qq = np.geomspace(qs.min(), qs.max() * 4, 200)
    for i, (ax, (name, est)) in enumerate(zip(ax_row, estimates.items())):
        c = SERIES[i]
        ax.axhline(est.ceiling, color=MUTED, lw=1, ls="--")
        ax.text(qq[-1], est.ceiling, " U", va="center", color=INK_2)
        ax.axhspan(*est.floor_ci, color=c, alpha=0.12, lw=0)
        ax.axhline(est.floor, color=c, lw=1)
        ax.text(qq[-1], est.floor, " L", va="center", color=INK_2)
        ax.plot(qq, est.fit.predict(qq), color=c, lw=2)
        ax.plot(qs, est.rho, "o", ms=5, color=c, mec="white", mew=1.5)
        ax.set_xscale("log", base=2)
        ax.set_title(name)
        ax.set_xlabel("filter budget q")
        ax.set_ylim(0, None)
    ax_row[0].set_ylabel("harmful rate ρ(q)")


def bound_map(ax: plt.Axes, estimates: Mapping[str, BoundEstimate]) -> None:
    """Each model at (U, L). The diagonal is 'filtering removes nothing'; L = 0 is full
    mitigation, which the theory says bounded filters cannot reach."""
    hi = max(e.ceiling_ci[1] for e in estimates.values()) * 1.15
    ax.plot([0, hi], [0, hi], color=MUTED, lw=1, ls="--")
    top = hi * 0.6
    ax.text(top * 0.93, top * 0.93, "defense removes nothing  ", ha="right", va="bottom", color=INK_2,
            rotation=45, rotation_mode="anchor", transform_rotates_text=True)
    ax.axhline(0, color=INK_2, lw=1)
    ax.text(hi * 0.98, -hi * 0.005, "L = 0: full mitigation (theory: unreachable)", color=INK_2, va="top", ha="right", fontsize=8)
    for i, (name, e) in enumerate(estimates.items()):
        ax.errorbar(
            e.ceiling,
            e.floor,
            xerr=[[e.ceiling - e.ceiling_ci[0]], [e.ceiling_ci[1] - e.ceiling]],
            yerr=[[e.floor - e.floor_ci[0]], [e.floor_ci[1] - e.floor]],
            fmt="o",
            ms=8,
            color=SERIES[i],
            mec="white",
            mew=2,
            elinewidth=1,
            capsize=0,
            label=name,
        )
        ax.annotate(name, (e.ceiling, e.floor), xytext=(6, 6), textcoords="offset points", color=INK)
    ax.set_xlim(0, hi)
    ax.set_ylim(-hi * 0.06, top)
    ax.set_xlabel("ceiling U (unfiltered harmful rate)")
    ax.set_ylabel("floor L (fitted asymptote)")
    ax.legend(loc="upper left")


def decomposition(ax: plt.Axes, decomps: Mapping[str, BoundDecomposition]) -> None:
    names = list(decomps)
    y = np.arange(len(names))
    left = np.zeros(len(names))
    for seg in ("irreducible", "reducible", "removed"):
        w = np.array([max(getattr(decomps[n], seg), 0.0) for n in names])
        ax.barh(y, w, left=left, height=0.55, color=SEGMENTS[seg], edgecolor="white", linewidth=2, label=seg)
        for yi, (l, wi) in enumerate(zip(left, w)):
            if wi > 0.03:
                ax.text(l + wi / 2, yi, f"{wi:.2f}", ha="center", va="center",
                        color="white" if seg == "irreducible" else INK, fontsize=8)
        left += w
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlabel("share of prompts (sums to ceiling U)")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))


def floor_heatmap(ax: plt.Axes, floors: np.ndarray, models: Sequence[str], families: Sequence[str],
                  significant: np.ndarray | None = None) -> None:
    """Floor L for models (rows) x attack families (columns). Sequential single hue.
    Cells whose floor lower CI does not exceed 0 are hatched: those are counter-evidence to H1."""
    im = ax.imshow(floors, cmap="Blues", vmin=0, aspect="auto")
    ax.set_xticks(range(len(families)), families, rotation=30, ha="right")
    ax.set_yticks(range(len(models)), models)
    ax.grid(False)
    for (r, c), v in np.ndenumerate(floors):
        ax.text(c, r, f"{v:.2f}", ha="center", va="center", color="white" if v > floors.max() * 0.6 else INK, fontsize=8)
        if significant is not None and not significant[r, c]:
            ax.add_patch(plt.Rectangle((c - 0.5, r - 0.5), 1, 1, fill=False, hatch="///", ec=MUTED, lw=0))
    plt.colorbar(im, ax=ax, label="floor L", shrink=0.8)
