"""Plot the frozen R1 transfer readout without changing its decisions."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "reports/v4/next_evaluator_transfer/TRANSFER_RESULT.json"
OUTPUT = Path(__file__).with_name("R1_COVERAGE.png")


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    cells = [
        row
        for row in payload["readouts"]
        if row["method"] in {"selected_dr", "batch_reallocation_candidate"}
    ]
    cells.sort(key=lambda row: row["cell"])
    labels = [row["cell"] for row in cells]
    coverage = np.array([row["coverage"] for row in cells])
    low = np.array([row["coverage_wilson"][0] for row in cells])
    high = np.array([row["coverage_wilson"][1] for row in cells])
    passed = low >= 0.92
    colors = ["#176a56" if ok else "#bb6131" for ok in passed]

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=170)
    y = np.arange(len(cells))[::-1]
    ax.axvspan(0, 0.92, color="#fbefe8", zorder=0)
    ax.axvline(0.92, color="#bb6131", linestyle="--", linewidth=1.2)
    ax.axvline(0.95, color="#718880", linestyle=":", linewidth=1.2)
    for i, row in enumerate(cells):
        ax.errorbar(
            coverage[i],
            y[i],
            xerr=[[coverage[i] - low[i]], [high[i] - coverage[i]]],
            fmt="o",
            color=colors[i],
            ecolor=colors[i],
            capsize=3,
            markersize=7,
            linewidth=1.5,
        )
        ax.text(high[i] + 0.006, y[i], f"{coverage[i]:.3f}", va="center", fontsize=9)
    ax.set_yticks(y, labels)
    ax.set_xlim(0.78, 1.01)
    ax.set_xlabel("Empirical coverage of 95% interval; error bars: 95% Wilson bounds")
    fig.suptitle(
        "R1 transfer: three cells fail the predeclared coverage gate",
        x=0.06,
        y=0.985,
        ha="left",
        fontsize=14,
    )
    fig.text(
        0.06,
        0.925,
        "2,000 synthetic worlds per cell  •  Pass requires Wilson lower bound ≥ 0.92",
        fontsize=9,
        color="#3d5b51",
    )
    ax.grid(axis="x", color="#d7e2dd", linewidth=0.7)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    fig.text(
        0.01,
        0.01,
        "T1–T2: selected fixed-rule DR interval. T3–T6: new unvalidated batch bootstrap. "
        "Synthetic method study; no telecom effect.",
        fontsize=8,
        color="#52675e",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.89))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
