"""R04: the factorial, the caching, and the null fixture that guards it.

The interesting risk is not that a main effect is mis-estimated -- it is that
the pipeline has a bug which shows up as a factor effect.  The declared null
fixture exists for exactly that, so most of these tests are about whether it
can actually catch one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from telco_churn.component_factorial import (
    CHANNEL_COST,
    COST_REGIMES,
    FACTORS,
    HOMOGENEOUS_COST,
    INTERACTIONS,
    CellResult,
    FactorialReport,
    _allocate,
    _contact_cost,
    add_interactions,
    render_markdown,
    run_factorial,
)
from telco_churn.screening import OUTER_FOLDS


def _cohort(n: int = 900, *, seed: int = 5):
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(
        {
            "recency": rng.integers(1, 12, n).astype(float),
            "log1p_history": rng.normal(5.0, 1.0, n),
            "mens": rng.integers(0, 2, n).astype(float),
            "womens": rng.integers(0, 2, n).astype(float),
            "newbie": rng.integers(0, 2, n).astype(float),
            "channel": rng.choice(["Web", "Phone", "Multichannel"], n),
        }
    )
    treatment = rng.integers(0, 2, n)
    probability = np.clip(
        0.10 + 0.08 * (features["recency"].to_numpy() < 6) * treatment, 0.01, 0.95
    )
    reward = (rng.random(n) < probability).astype(float)
    return features, treatment, reward, [f"u{index}" for index in range(n)]


# -- the representation factor --------------------------------------------
def test_the_declared_interactions_are_the_four_from_the_runbook() -> None:
    assert set(INTERACTIONS) == {
        ("log1p_history", "recency"),
        ("log1p_history", "newbie"),
        ("recency", "newbie"),
        ("mens", "womens"),
    }


def test_adding_interactions_adds_exactly_four_columns() -> None:
    features, *_ = _cohort(100)
    augmented = add_interactions(features)
    added = set(augmented.columns) - set(features.columns)
    assert len(added) == 4
    assert set(features.columns) <= set(augmented.columns), "base features are kept"


def test_an_interaction_is_the_product_of_its_two_columns() -> None:
    features, *_ = _cohort(100)
    augmented = add_interactions(features)
    expected = features["recency"].to_numpy() * features["newbie"].to_numpy()
    assert augmented["recency_x_newbie"].to_numpy() == pytest.approx(expected)


def test_a_missing_column_is_an_error_not_a_skipped_interaction() -> None:
    """A factorial that silently drops a level is not a factorial."""

    features, *_ = _cohort(100)
    with pytest.raises(ValueError, match="needs column 'mens'"):
        add_interactions(features.drop(columns=["mens"]))


# -- the cost regimes ------------------------------------------------------
def test_the_homogeneous_cost_is_one_number_for_everyone() -> None:
    features, *_ = _cohort(200)
    cost = _contact_cost(features, "homogeneous")
    assert set(np.unique(cost)) == {HOMOGENEOUS_COST}


def test_the_heterogeneous_cost_follows_the_channel() -> None:
    features, *_ = _cohort(200)
    cost = _contact_cost(features, "heterogeneous")
    for channel, price in CHANNEL_COST.items():
        rows = features["channel"].to_numpy() == channel
        if rows.any():
            assert set(np.unique(cost[rows])) == {price}


def test_an_unknown_channel_falls_back_rather_than_crashing() -> None:
    features, *_ = _cohort(50)
    features.loc[0, "channel"] = "Carrier Pigeon"
    assert _contact_cost(features, "heterogeneous")[0] == HOMOGENEOUS_COST


# -- the null fixture ------------------------------------------------------
def test_a_constant_cost_cannot_change_a_rank_allocation() -> None:
    """The mechanism behind the null fixture, checked directly."""

    rng = np.random.default_rng(1)
    scores = rng.normal(size=400)
    ids = [f"u{index}" for index in range(400)]
    flat = np.full(400, HOMOGENEOUS_COST)
    by_rank = _allocate(scores, ids, flat, allocator="rank")
    by_value = _allocate(scores, ids, flat, allocator="net_value")
    assert (by_rank == by_value).all()


def test_a_varying_cost_does_change_it() -> None:
    """Otherwise the heterogeneous regime would be a second null fixture."""

    rng = np.random.default_rng(1)
    scores = rng.normal(size=400) * 0.001
    ids = [f"u{index}" for index in range(400)]
    varying = rng.choice(list(CHANNEL_COST.values()), size=400)
    by_rank = _allocate(scores, ids, varying, allocator="rank")
    by_value = _allocate(scores, ids, varying, allocator="net_value")
    assert (by_rank != by_value).any()


def test_the_fixture_reports_broken_when_allocations_diverge() -> None:
    """It must be able to say no, or it guards nothing."""

    report = FactorialReport(
        dataset="fixture",
        started_at="now",
        gate_detail="n/a",
        n_units=10,
        n_events=1,
        propensity=0.5,
    )
    report.cells = [
        CellResult("base", "ridge", "rank", "homogeneous", [0.1], ["a,b"]),
        CellResult("base", "ridge", "net_value", "homogeneous", [0.2], ["a,c"]),
    ]
    verdict = report.null_fixture_held()
    assert verdict["held"] is False
    assert verdict["mismatched_cells"]


def test_the_fixture_holds_when_allocations_match() -> None:
    report = FactorialReport(
        dataset="fixture",
        started_at="now",
        gate_detail="n/a",
        n_units=10,
        n_events=1,
        propensity=0.5,
    )
    report.cells = [
        CellResult("base", "ridge", "rank", "homogeneous", [0.1], ["a,b"]),
        CellResult("base", "ridge", "net_value", "homogeneous", [0.1], ["a,b"]),
    ]
    assert report.null_fixture_held()["held"] is True


# -- the run ---------------------------------------------------------------
@pytest.fixture(scope="module")
def factorial():
    features, treatment, reward, ids = _cohort()
    return run_factorial(
        features,
        treatment,
        reward,
        ids,
        dataset="fixture",
        propensity=float(treatment.mean()),
        require_gate=False,
    )


def test_every_cell_of_the_factorial_is_scored(factorial) -> None:
    expected = 2 * 2 * 2 * len(COST_REGIMES)
    assert len(factorial.cells) == expected
    for cell in factorial.cells:
        assert len(cell.fold_values) == OUTER_FOLDS


def test_the_allocator_factor_costs_no_extra_effect_fits(factorial) -> None:
    """Four fits per fold, not eight: both allocators read the same scores."""

    assert factorial.effect_fits == 4 * OUTER_FOLDS


def test_the_null_fixture_holds_on_a_real_run(factorial) -> None:
    assert factorial.null_fixture_held()["held"] is True


def test_the_allocator_effect_is_exactly_zero_under_a_flat_cost(factorial) -> None:
    effect = factorial.main_effects("homogeneous")["allocator"]
    assert effect["mean_effect"] == pytest.approx(0.0, abs=1e-15)


def test_main_effects_are_paired_across_folds(factorial) -> None:
    for regime in COST_REGIMES:
        for effect in factorial.main_effects(regime).values():
            # Four cells hold the other two factors fixed, three folds each.
            assert effect["n_paired_readouts"] == 4 * OUTER_FOLDS


def test_the_report_declares_its_costs_as_assumed(factorial) -> None:
    payload = factorial.to_dict()
    assert "assumed" in payload["cost_source"]
    assert payload["protocol"]["split"].startswith("development only")
    assert set(payload["protocol"]["factors"]) == set(FACTORS)


def test_the_markdown_names_both_regimes_and_the_fixture(factorial) -> None:
    rendered = render_markdown(factorial)
    for regime in COST_REGIMES:
        assert regime in rendered
    assert "null fixture" in rendered.lower()
    assert "assumed" in rendered
