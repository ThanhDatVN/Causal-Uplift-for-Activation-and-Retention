"""R03 bounded tuning: the grids, the nesting, and the honesty of the search.

The risk in a tuning stage is not that it fails to find a good setting -- it
is that it quietly cheats.  Three ways it could: search more than the runbook
allows, let the inner search see outer labels, or report eight trials when
the allocator could only tell four of them apart.  These tests target those.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.bounded_tuning import (
    GRIDS,
    HGB_GRID,
    INNER_FOLDS,
    LOGISTIC_GRID,
    RIDGE_GRID,
    InnerTrial,
    TunedResult,
    _inner_search,
    render_markdown,
    run_bounded_tuning,
)
from telco_churn.screening import CAPACITY_FRACTION, OUTER_FOLDS


def _cohort(n: int = 900, *, seed: int = 5):
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(
        {
            "recency": rng.integers(1, 12, n).astype(float),
            "log1p_history": rng.normal(5.0, 1.0, n),
            "newbie": rng.integers(0, 2, n).astype(float),
            "channel": rng.choice(["Web", "Phone"], n),
        }
    )
    treatment = rng.integers(0, 2, n)
    probability = np.clip(
        0.10 + 0.08 * (features["recency"].to_numpy() < 6) * treatment, 0.01, 0.95
    )
    reward = (rng.random(n) < probability).astype(float)
    return features, treatment, reward, [f"u{index}" for index in range(n)]


def _run(**overrides):
    features, treatment, reward, ids = overrides.pop("cohort", _cohort())
    kwargs = {
        "dataset": "fixture",
        "propensity": float(np.asarray(treatment).mean()),
        "shortlist": ["M01"],
        "require_gate": False,
    }
    kwargs.update(overrides)
    return run_bounded_tuning(features, treatment, reward, ids, **kwargs)


# -- the declared grids ----------------------------------------------------
def test_every_grid_has_exactly_eight_configurations() -> None:
    """The runbook says eight per family; nine would be a different stage."""

    for candidate_id, grid in GRIDS.items():
        assert len(grid) == 8, candidate_id


def test_the_grids_have_no_duplicate_configurations() -> None:
    for candidate_id, grid in GRIDS.items():
        seen = {tuple(sorted(config.items())) for config in grid}
        assert len(seen) == 8, candidate_id


def test_the_logistic_grid_varies_only_its_penalty() -> None:
    """Varying features here would confound tuning with R04's question."""

    assert all(set(config) == {"C"} for config in LOGISTIC_GRID)


def test_the_hgb_grid_is_the_declared_three_way_factorial() -> None:
    assert {config["max_leaf_nodes"] for config in HGB_GRID} == {15, 31}
    assert {config["min_samples_leaf"] for config in HGB_GRID} == {50, 200}
    assert {config["l2_regularization"] for config in HGB_GRID} == {1.0, 10.0}
    assert {config["learning_rate"] for config in HGB_GRID} == {0.05}
    assert {config["max_iter"] for config in HGB_GRID} == {300}


def test_the_ridge_grid_crosses_alpha_with_shrinkage() -> None:
    assert {config["alpha"] for config in RIDGE_GRID} == {0.1, 1.0, 10.0, 100.0}
    assert {config["shrinkage"] for config in RIDGE_GRID} == {0.5, 1.0}


# -- the bound on the search ----------------------------------------------
def test_a_fourth_family_is_refused() -> None:
    with pytest.raises(ValueError, match="at most three families"):
        _run(shortlist=["M01", "M03", "M05", "M07"])


def test_a_candidate_without_a_declared_grid_is_refused() -> None:
    with pytest.raises(ValueError, match="no declared tuning grid"):
        _run(shortlist=["B02"])


# -- what the search reports ----------------------------------------------
@pytest.fixture(scope="module")
def tuned():
    return _run(shortlist=["M01", "M07"])


def test_each_outer_fold_gets_its_own_inner_search(tuned) -> None:
    for item in tuned.completed:
        assert len(item.chosen_per_fold) == OUTER_FOLDS
        assert len(item.inner_trials) == OUTER_FOLDS
        for fold in item.inner_trials:
            assert len(fold) == 8


def test_the_chosen_configuration_comes_from_the_declared_grid(tuned) -> None:
    for item in tuned.completed:
        allowed = [dict(config) for config in GRIDS[item.candidate_id]]
        for choice in item.chosen_per_fold:
            assert choice in allowed


def test_the_default_is_scored_on_the_same_folds(tuned) -> None:
    """Otherwise 'gain from tuning' would compare different evaluation sets."""

    for item in tuned.completed:
        assert len(item.default_fold_values) == len(item.fold_values) == OUTER_FOLDS


def test_fold_to_fold_instability_is_reported_not_averaged(tuned) -> None:
    for item in tuned.completed:
        assert isinstance(item.configuration_stable, bool)
    assert "configuration_stable" in tuned.to_dict()["results"][0]


def test_a_failed_configuration_is_recorded_rather_than_dropped() -> None:
    """One unfittable setting must not quietly improve the survivors' average."""

    features, treatment, reward, ids = _cohort(600)
    grid = ({"C": 0.1}, {"C": 1.0}, {"not_a_hyperparameter": 1})
    chosen, trials, _fits = _inner_search(
        features,
        np.asarray(treatment),
        np.asarray(reward, dtype=float),
        ids,
        candidate_id="M01",
        grid=grid,
        propensity=float(np.asarray(treatment).mean()),
        seed=1,
    )
    broken = trials[-1]
    assert broken.inner_value == float("-inf")
    assert "not_a_hyperparameter" in broken.error
    assert chosen in ({"C": 0.1}, {"C": 1.0}), "a broken setting must not be chosen"


def test_a_grid_where_everything_fails_is_a_failure_not_a_silent_default() -> None:
    features, treatment, reward, ids = _cohort(400)
    with pytest.raises(RuntimeError, match="every configuration"):
        _inner_search(
            features,
            np.asarray(treatment),
            np.asarray(reward, dtype=float),
            ids,
            candidate_id="M01",
            grid=({"nonsense": 1}, {"also_nonsense": 2}),
            propensity=float(np.asarray(treatment).mean()),
            seed=1,
        )


def test_the_whole_stage_records_a_failed_candidate_and_carries_on(monkeypatch) -> None:
    """One family that cannot be tuned must not take the report down with it."""

    monkeypatch.setitem(GRIDS, "M01", ({"nonsense": 1},))
    report = _run(shortlist=["M01"])
    item = report.results[0]
    assert item.status == "TUNING_FAILED"
    assert item.error
    assert item.candidate_id in render_markdown(report)


# -- the degeneracy diagnostic --------------------------------------------
def test_a_grid_dimension_the_allocator_cannot_see_is_reported(tuned) -> None:
    """Shrinking a score toward a constant cannot change a rank allocation.

    `shrinkage` is an affine transform of the score, and the allocator ranks,
    so half the DR-Ridge grid contacts exactly the same accounts as the other
    half.  Reporting eight trials would overstate the search, so the stage
    counts how many distinct allocations the grid actually produced.
    """

    ridge = next(item for item in tuned.completed if item.candidate_id == "M07")
    assert ridge.grid_is_degenerate is True
    assert min(ridge.distinct_configurations_searched) < 8
    assert "M07" in tuned.to_dict()["degenerate_grids"]


def test_a_grid_that_does_separate_is_not_flagged() -> None:
    result = TunedResult(candidate_id="M01", family="outcome_ranking")
    result.inner_trials = [
        [
            InnerTrial(
                configuration={"C": value},
                inner_value=0.1,
                folds_scored=INNER_FOLDS,
                allocation_signature=f"sig{index}",
            )
            for index, value in enumerate(range(8))
        ]
    ]
    assert result.grid_is_degenerate is False
    assert result.distinct_configurations_searched == [8]


def test_configurations_with_the_same_signature_count_once() -> None:
    result = TunedResult(candidate_id="M07", family="dr_learner")
    result.inner_trials = [
        [
            InnerTrial(
                configuration={"alpha": 1.0, "shrinkage": shrink},
                inner_value=0.1,
                folds_scored=INNER_FOLDS,
                allocation_signature="identical",
            )
            for shrink in (0.5, 1.0)
        ]
    ]
    assert result.distinct_configurations_searched == [1]
    assert result.grid_is_degenerate is True


# -- the protocol the artifact must record --------------------------------
def test_the_report_records_the_nesting_and_the_split(tuned) -> None:
    payload = tuned.to_dict()
    assert payload["protocol"]["inner_folds"] == INNER_FOLDS
    assert payload["protocol"]["outer_folds"] == OUTER_FOLDS
    assert payload["protocol"]["capacity_fraction"] == CAPACITY_FRACTION
    assert payload["protocol"]["split"].startswith("development only")
    assert "not a confirmation" in payload["scope_note"]


def test_the_fit_count_is_reported_so_the_budget_is_auditable(tuned) -> None:
    assert tuned.fits > 8 * INNER_FOLDS
    assert tuned.to_dict()["candidate_fits"] == tuned.fits


def test_the_markdown_names_the_gain_and_the_instability(tuned) -> None:
    rendered = render_markdown(tuned)
    assert "gain from tuning" in rendered
    assert "distinct configs" in rendered
    for item in tuned.results:
        assert item.candidate_id in rendered
