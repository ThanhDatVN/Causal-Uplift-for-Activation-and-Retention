"""Figures: what they must refuse to draw, and what they must read.

A figure is a claim with a picture attached, so the risk worth testing is not
that matplotlib works -- it is that a panel silently invents a number when
its artifact is missing, stale or says something the caption does not.  These
tests drive the module with artifacts that are absent, incomplete and
contradictory, and check it declines rather than draws.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from telco_churn.figures import BOUNDARY_ARTIFACT, build_figures


def _cell(
    *,
    propensity: float,
    rate: float,
    method: str,
    coverage: float,
    asymmetry: float | None = None,
    skewness: float = 10.0,
) -> dict:
    cell = {
        "propensity": propensity,
        "imbalance": round(abs(propensity - 0.5), 4),
        "event_rate": rate,
        "method": method,
        "worlds": 1000,
        "coverage": coverage,
        "coverage_ci_low": coverage - 0.015,
        "coverage_ci_high": coverage + 0.013,
        "width_ratio": 1.0,
        "mean_score_skewness": skewness,
        "mean_control_events": 40.0,
        "bias": 0.0,
        "mc_se": 0.001,
        "passes": coverage - 0.015 >= 0.92,
    }
    if asymmetry is not None:
        cell["asymmetry_index"] = asymmetry
    return cell


def _write_artifact(root: Path, payload: dict) -> None:
    target = root / BOUNDARY_ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def _payload(*, separates: bool = True, threshold: float = 0.2) -> dict:
    cells = []
    for method in ("normal", "skewness_adjusted_t"):
        for rate in (0.005, 0.01, 0.035):
            for propensity, coverage in ((0.5, 0.950), (0.8, 0.945), (0.95, 0.900)):
                cells.append(
                    _cell(
                        propensity=propensity,
                        rate=rate,
                        method=method,
                        coverage=coverage,
                        asymmetry=abs(1 - 2 * propensity) / 3,
                        skewness=abs(1 - 2 * propensity) * 30,
                    )
                )
    return {
        "study": "overlap_boundary_sweep",
        "worlds_per_cell": 1000,
        "seed": 20260924,
        "n_units": 10_000,
        "acted_fraction": 0.5,
        "cells": cells,
        "boundary_by_asymmetry": {
            method: {
                "method": method,
                "n_cells": 9,
                "n_failing": 3,
                "largest_passing_asymmetry": threshold,
                "smallest_failing_asymmetry": threshold + 0.01,
                "separates": separates,
                "straddling_cells": [],
                "licensed_threshold": threshold if separates else None,
            }
            for method, threshold in (
                ("normal", threshold),
                ("skewness_adjusted_t", threshold * 2.9),
            )
        },
    }


# -- refusing to draw ------------------------------------------------------
def test_no_artifact_draws_nothing_and_says_why(tmp_path) -> None:
    manifest = build_figures(tmp_path, tmp_path / "out")
    assert manifest["figures"] == []
    assert "not on disk" in manifest["skipped"][0]["reason"]


def test_no_artifact_is_not_an_exception(tmp_path) -> None:
    """A missing artifact is an expected state, not a crash."""

    build_figures(tmp_path, tmp_path / "out")  # must not raise


def test_a_sweep_that_licensed_no_threshold_skips_that_panel(tmp_path) -> None:
    """The bar chart claims a licensed region; with none, it must not appear."""

    _write_artifact(tmp_path, _payload(separates=False))
    manifest = build_figures(tmp_path, tmp_path / "out")
    drawn = {entry["figure"] for entry in manifest["figures"]}
    skipped = {entry["figure"] for entry in manifest["skipped"]}
    assert "correction" in skipped
    assert "correction" not in drawn
    assert not (tmp_path / "out/correction.png").exists()


def test_the_other_panels_still_draw_without_a_threshold(tmp_path) -> None:
    _write_artifact(tmp_path, _payload(separates=False))
    manifest = build_figures(tmp_path, tmp_path / "out")
    assert {entry["figure"] for entry in manifest["figures"]} == {
        "boundary",
        "why_not_imbalance",
        "formula",
    }


# -- reading rather than recomputing ---------------------------------------
def test_the_recorded_index_is_preferred_over_recomputing_it(tmp_path) -> None:
    """If a run recorded A, the figure plots that, not its own arithmetic.

    Recomputing would silently paper over a sweep written by a different
    version of the formula, which is exactly the drift worth catching.
    """

    from telco_churn.figures import _index

    cell = _cell(propensity=0.9, rate=0.005, method="normal", coverage=0.9, asymmetry=42.0)
    assert _index(cell, 0.5) == 42.0


def test_a_cell_without_a_recorded_index_falls_back_to_the_formula(tmp_path) -> None:
    from telco_churn.figures import _index

    cell = _cell(propensity=0.9, rate=0.005, method="normal", coverage=0.9)
    assert _index(cell, 0.5) == pytest.approx(0.5333, abs=0.001)


# -- the manifest ----------------------------------------------------------
def test_every_drawn_figure_exists_and_is_not_empty(tmp_path) -> None:
    _write_artifact(tmp_path, _payload())
    manifest = build_figures(tmp_path, tmp_path / "out")
    assert len(manifest["figures"]) == 4
    for entry in manifest["figures"]:
        assert Path(entry["path"]).exists()
        assert entry["bytes"] > 5_000, f"{entry['figure']} looks blank"


def test_the_manifest_names_its_source_and_its_power(tmp_path) -> None:
    _write_artifact(tmp_path, _payload())
    manifest = build_figures(tmp_path, tmp_path / "out")
    assert manifest["source"] == BOUNDARY_ARTIFACT
    assert manifest["worlds_per_cell"] == 1000
    assert manifest["seed"] == 20260924
    assert "constant propensity" in manifest["scope_note"]


def test_every_figure_carries_a_caption(tmp_path) -> None:
    _write_artifact(tmp_path, _payload())
    manifest = build_figures(tmp_path, tmp_path / "out")
    for entry in manifest["figures"]:
        assert entry["caption"].strip(), entry["figure"]


def test_the_manifest_is_written_beside_the_figures(tmp_path) -> None:
    _write_artifact(tmp_path, _payload())
    build_figures(tmp_path, tmp_path / "out")
    saved = json.loads((tmp_path / "out/figures.json").read_text(encoding="utf-8"))
    assert len(saved["figures"]) == 4


def test_redrawing_is_idempotent(tmp_path) -> None:
    _write_artifact(tmp_path, _payload())
    first = build_figures(tmp_path, tmp_path / "out")
    second = build_figures(tmp_path, tmp_path / "out")
    assert [e["figure"] for e in first["figures"]] == [e["figure"] for e in second["figures"]]


def test_a_single_method_sweep_does_not_break_the_panel_layout(tmp_path) -> None:
    """One method means one subplot, which matplotlib does not return as a list."""

    payload = _payload()
    payload["cells"] = [c for c in payload["cells"] if c["method"] == "normal"]
    payload["boundary_by_asymmetry"] = {"normal": payload["boundary_by_asymmetry"]["normal"]}
    _write_artifact(tmp_path, payload)
    manifest = build_figures(tmp_path, tmp_path / "out")
    assert "boundary" in {entry["figure"] for entry in manifest["figures"]}
