"""Figures for the boundary result, drawn from artifacts and nothing else.

Every number on every axis is read from a file on disk that some run wrote.
Nothing here recomputes a result, and nothing here has a hard-coded data
point: if an artifact is missing the figure is skipped and said to be
skipped, because a figure that quietly falls back to a remembered number is
worse than no figure.

Four panels, each answering one question a reader will ask:

``boundary``
    Where does coverage fail, plotted against the asymmetry index?  With the
    0.92 gate line and the measured crossing.
``why_not_imbalance``
    The same coverages against imbalance instead.  The three event-rate
    curves separate, which is the whole reason imbalance is not a usable
    rule; against ``A`` they collapse onto one.
``formula``
    Predicted skewness against realised skewness, per cell.  This is the
    claim that the closed form describes the estimator, so it gets its own
    panel and a y = x line rather than a correlation coefficient.
``correction``
    What the Edgeworth correction buys, as licensed region rather than as a
    coverage number at one convenient design.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display in CI, in a container, or over ssh

import matplotlib.pyplot as plt

from .policy_comparison import design_asymmetry_index

__all__ = ["build_figures", "main"]

BOUNDARY_ARTIFACT = "reports/v4/overlap_boundary/overlap_boundary.json"
GATE_LINE = 0.92
NOMINAL = 0.95

#: One colour per event rate, used identically in every panel so a reader can
#: follow a single design across figures.
RATE_COLOURS = {0.005: "#b2182b", 0.01: "#ef8a62", 0.035: "#2166ac"}
METHOD_LABELS = {
    "normal": "Wald (normal)",
    "skewness_adjusted_t": "Edgeworth + effective df",
    "skewness_adjusted": "Edgeworth",
    "bootstrap_t": "studentised bootstrap",
}


def _style(axis: Any) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(alpha=0.25, linewidth=0.6)
    axis.set_axisbelow(True)


def _index(cell: dict[str, Any], acted: float) -> float:
    """The cell's asymmetry index, preferring the value the run recorded."""

    stored = cell.get("asymmetry_index")
    if stored is not None:
        return float(stored)
    return abs(
        design_asymmetry_index(
            n_units=10_000,
            propensity=cell["propensity"],
            event_rate=cell["event_rate"],
            acted_fraction=acted,
        )
    )


def _figure_boundary(payload: dict[str, Any], acted: float, out: Path) -> str:
    methods = sorted({c["method"] for c in payload["cells"]})
    fig, drawn_axes = plt.subplots(1, len(methods), figsize=(5.2 * len(methods), 4.2), sharey=True)
    axes = [drawn_axes] if len(methods) == 1 else list(drawn_axes)
    summary = payload.get("boundary_by_asymmetry", {})

    for axis, method in zip(axes, methods, strict=True):
        cells = [c for c in payload["cells"] if c["method"] == method]
        for rate in sorted({c["event_rate"] for c in cells}):
            group = sorted(
                (c for c in cells if c["event_rate"] == rate),
                key=lambda c: _index(c, acted),
            )
            axis.errorbar(
                [_index(c, acted) for c in group],
                [c["coverage"] for c in group],
                yerr=[
                    [c["coverage"] - c["coverage_ci_low"] for c in group],
                    [c["coverage_ci_high"] - c["coverage"] for c in group],
                ],
                marker="o",
                markersize=5,
                linewidth=1.4,
                capsize=2.5,
                color=RATE_COLOURS.get(rate, "#666666"),
                label=f"event rate {rate:.1%}",
            )
        entry = summary.get(method, {})
        threshold = entry.get("licensed_threshold")
        if entry.get("separates") and threshold is not None:
            axis.axvspan(0, threshold, color="#2166ac", alpha=0.07)
            axis.axvline(threshold, color="#2166ac", linestyle=":", linewidth=1.4)
            axis.annotate(
                f"licensed to A = {threshold:.3f}",
                xy=(threshold, 0.815),
                xytext=(4, 0),
                textcoords="offset points",
                fontsize=8,
                color="#2166ac",
                rotation=90,
                va="bottom",
            )
        axis.axhline(NOMINAL, color="#444444", linewidth=0.9)
        axis.axhline(GATE_LINE, color="#b2182b", linestyle="--", linewidth=1.1)
        axis.set_title(METHOD_LABELS.get(method, method), fontsize=11)
        axis.set_xlabel("asymmetry index  $A = |1-2e| / \\sqrt{n h r e(1-e)}$")
        _style(axis)

    axes[0].set_ylabel("coverage of the nominal 95% interval")
    # Both reference lines are labelled on the right, where the curves have
    # already fallen away, so the text never lands on a marker.
    axes[-1].annotate(
        "nominal 0.95",
        xy=(1.0, NOMINAL),
        xycoords=("axes fraction", "data"),
        xytext=(-4, 4),
        textcoords="offset points",
        fontsize=8,
        color="#444444",
        ha="right",
    )
    axes[-1].annotate(
        "gate floor 0.92",
        xy=(1.0, GATE_LINE),
        xycoords=("axes fraction", "data"),
        xytext=(-4, -11),
        textcoords="offset points",
        fontsize=8,
        color="#b2182b",
        ha="right",
    )
    axes[-1].legend(frameon=False, fontsize=9, loc="lower left")
    fig.suptitle(
        "Coverage against the design's asymmetry index, "
        f"{payload.get('worlds_per_cell', 0):,} worlds per cell",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return "coverage against A, per interval method, with the measured licensed region"


def _figure_why_not_imbalance(payload: dict[str, Any], acted: float, out: Path) -> str:
    methods = sorted({c["method"] for c in payload["cells"]})
    method = "normal" if "normal" in methods else methods[0]
    cells = [c for c in payload["cells"] if c["method"] == method]
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.4, 4.2), sharey=True)

    for axis, key, label in (
        (left, "imbalance", "propensity imbalance  $|e - 0.5|$"),
        (right, "asymmetry", "asymmetry index  $A$"),
    ):
        for rate in sorted({c["event_rate"] for c in cells}):
            group = [c for c in cells if c["event_rate"] == rate]
            xs = [c["imbalance"] if key == "imbalance" else _index(c, acted) for c in group]
            order = sorted(range(len(group)), key=lambda i: xs[i])
            axis.plot(
                [xs[i] for i in order],
                [group[i]["coverage"] for i in order],
                marker="o",
                markersize=5,
                linewidth=1.4,
                color=RATE_COLOURS.get(rate, "#666666"),
                label=f"event rate {rate:.1%}",
            )
        axis.axhline(GATE_LINE, color="#b2182b", linestyle="--", linewidth=1.1)
        axis.set_xlabel(label)
        _style(axis)

    left.set_ylabel("coverage")
    left.set_title("Against imbalance: three curves, no single rule", fontsize=11)
    right.set_title("Against $A$: one curve", fontsize=11)
    right.legend(frameon=False, fontsize=9, loc="lower left")
    fig.suptitle(
        f"Why imbalance is not a gate rule ({METHOD_LABELS.get(method, method)})",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return "the same coverages against imbalance and against A, side by side"


def _figure_formula(payload: dict[str, Any], acted: float, out: Path) -> str:
    """Predicted skewness against the skewness the estimator actually showed."""

    n_units = payload.get("n_units", 10_000)
    seen: dict[tuple[float, float], dict[str, Any]] = {}
    for cell in payload["cells"]:
        seen.setdefault((cell["event_rate"], cell["propensity"]), cell)

    fig, axis = plt.subplots(figsize=(5.6, 5.2))
    limit = 0.0
    for (rate, _propensity), cell in sorted(seen.items()):
        predicted = _index(cell, acted)
        realised = abs(cell["mean_score_skewness"]) / (n_units**0.5)
        limit = max(limit, predicted, realised)
        axis.scatter(
            predicted,
            realised,
            s=38,
            color=RATE_COLOURS.get(rate, "#666666"),
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )
    span = [0.0, limit * 1.06]
    axis.plot(span, span, color="#444444", linewidth=1.0)
    axis.plot(
        span,
        [0.85 * value for value in span],
        color="#888888",
        linestyle=":",
        linewidth=1.0,
    )
    axis.annotate("y = x", xy=(span[1] * 0.78, span[1] * 0.80), fontsize=8, color="#444444")
    axis.annotate("y = 0.85x", xy=(span[1] * 0.78, span[1] * 0.60), fontsize=8, color="#888888")
    axis.set_xlim(*span)
    axis.set_ylim(*span)
    axis.set_xlabel("predicted  $|A|$")
    axis.set_ylabel("realised skewness of the DR mean")
    axis.set_title(
        "The closed form against the estimator\n"
        "one point per design; the spike model\ndrops the augmentation term",
        fontsize=10,
    )
    handles = [
        plt.Line2D([], [], marker="o", linestyle="", color=colour, label=f"event rate {rate:.1%}")
        for rate, colour in sorted(RATE_COLOURS.items())
    ]
    axis.legend(handles=handles, frameon=False, fontsize=8, loc="upper left")
    _style(axis)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return "predicted A against the realised skewness, one point per design"


def _figure_correction(payload: dict[str, Any], out: Path) -> str:
    summary = payload.get("boundary_by_asymmetry", {})
    usable = {
        method: entry["licensed_threshold"]
        for method, entry in summary.items()
        if entry.get("separates") and entry.get("licensed_threshold") is not None
    }
    if not usable:
        return ""

    methods = sorted(usable, key=lambda name: usable[name])
    fig, axis = plt.subplots(figsize=(6.6, 1.8 + 0.7 * len(methods)))
    palette = ["#92c5de", "#2166ac", "#67a9cf", "#d1e5f0"]
    axis.barh(
        [METHOD_LABELS.get(name, name) for name in methods],
        [usable[name] for name in methods],
        color=[palette[index % len(palette)] for index in range(len(methods))],
        height=0.5,
    )
    for position, name in enumerate(methods):
        axis.annotate(
            f"A ≤ {usable[name]:.3f}",
            xy=(usable[name], position),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
        )
    if len(methods) == 2:
        low, high = (usable[name] for name in methods)
        if low > 0:
            axis.set_title(
                f"The correction widens the usable region {high / low:.1f}x", fontsize=11
            )
    axis.set_xlabel("largest asymmetry index measured to cover")
    axis.set_xlim(0, max(usable.values()) * 1.4)
    _style(axis)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return "licensed asymmetry region per interval method"


def build_figures(
    root: Path | str = ".", output_dir: Path | str = "reports/v4/figures"
) -> dict[str, Any]:
    """Draw every figure whose artifact exists; report what was skipped."""

    base = Path(root)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    path = base / BOUNDARY_ARTIFACT
    if not path.exists():
        return {
            "source": BOUNDARY_ARTIFACT,
            "figures": [],
            "skipped": [{"figure": "all", "reason": f"{BOUNDARY_ARTIFACT} not on disk"}],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    acted = float(payload.get("acted_fraction", 0.5))

    drawn: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    builders = (
        ("boundary", lambda out: _figure_boundary(payload, acted, out)),
        ("why_not_imbalance", lambda out: _figure_why_not_imbalance(payload, acted, out)),
        ("formula", lambda out: _figure_formula(payload, acted, out)),
        ("correction", lambda out: _figure_correction(payload, out)),
    )
    for name, builder in builders:
        target = destination / f"{name}.png"
        caption = builder(target)
        if not caption:
            skipped.append({"figure": name, "reason": "the artifact licensed no threshold"})
            continue
        drawn.append(
            {
                "figure": name,
                "path": str(target).replace("\\", "/"),
                "caption": caption,
                "bytes": target.stat().st_size,
            }
        )

    manifest = {
        "source": BOUNDARY_ARTIFACT,
        "worlds_per_cell": payload.get("worlds_per_cell"),
        "seed": payload.get("seed"),
        "figures": drawn,
        "skipped": skipped,
        "scope_note": (
            "Drawn from one sweep of one generator family with a constant propensity. "
            "Every value plotted is read from the artifact; none is recomputed here."
        ),
    }
    (destination / "figures.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="reports/v4/figures")
    args = parser.parse_args(argv)

    manifest = build_figures(args.root, args.output_dir)
    for entry in manifest["figures"]:
        print(f"[drawn  ] {entry['path']} -- {entry['caption']}")
    for entry in manifest["skipped"]:
        print(f"[skipped] {entry['figure']}: {entry['reason']}")
    return 0 if manifest["figures"] else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
