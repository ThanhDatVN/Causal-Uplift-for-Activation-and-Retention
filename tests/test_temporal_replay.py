"""R07: the replay, and the properties that make it a replay rather than a re-score.

The runbook blocked this stage until actions could change future state, so
the tests that matter are the ones that would catch a re-score wearing a
replay's clothes: trajectories must diverge, a strategy must never see a
label that had not matured, and the ledger must reconcile.
"""

from __future__ import annotations

import numpy as np
import pytest

from telco_churn.temporal_replay import (
    CAPACITY_FRACTION,
    DECISION_MONTHS,
    LABEL_DELAY_MONTHS,
    MECHANISMS,
    N_ACCOUNTS,
    RISK_BINS,
    ROLLING_WINDOW,
    STRATEGIES,
    StrategyOutcome,
    TemporalReplayReport,
    _advance,
    _drift,
    _fit_scorer,
    _initial_world,
    _matured,
    _refit_for,
    _score_accounts,
    render_markdown,
    run_temporal_replay,
)


# -- the world -------------------------------------------------------------
def test_a_strategy_can_only_see_the_observable_feature() -> None:
    """A strategy that knew the true risk would have nothing to learn.

    That was the first draft: it read `world.risk` directly, refitting could
    only add noise, and `frozen` won by construction in every mechanism.
    """

    world = _initial_world(np.random.default_rng(1))
    scorer = _fit_scorer([], world.x)
    assert set(scorer) == {"risk_by_bin", "lift"}
    assert len(scorer["risk_by_bin"]) == RISK_BINS


def test_contact_changes_future_state() -> None:
    """Fatigue and attrition, which is what makes a replay necessary."""

    rng = np.random.default_rng(2)
    world = _initial_world(rng)
    contacted = np.zeros(N_ACCOUNTS, dtype=bool)
    contacted[:300] = True
    before_active = int(world.active.sum())
    _advance(world, contacted, rng)
    assert world.prior_offers[:300].sum() == 300
    assert (world.months_since_offer[:300] == 0).all()
    assert int(world.active.sum()) < before_active


def test_repeated_contact_is_worth_less() -> None:
    """Fatigue: the same account contacted again responds less."""

    from telco_churn.temporal_replay import _churn_probability

    world = _initial_world(np.random.default_rng(3))
    contacted = np.ones(N_ACCOUNTS, dtype=bool)
    fresh = _churn_probability(world, contacted).mean()
    world.prior_offers = np.full(N_ACCOUNTS, 3)
    tired = _churn_probability(world, contacted).mean()
    assert tired > fresh, "a fatigued account should churn more despite the offer"


@pytest.mark.parametrize("mechanism", [name for name, _d in MECHANISMS])
def test_every_mechanism_actually_bends_the_world(mechanism: str) -> None:
    rng = np.random.default_rng(4)
    world = _initial_world(rng)
    before = (world.risk_slope, world.risk_base, world.lift_scale)
    for month in range(DECISION_MONTHS):
        _drift(world, month, mechanism, rng)
    assert (world.risk_slope, world.risk_base, world.lift_scale) != before


def test_effect_reversal_really_reverses() -> None:
    """The offer must end up harmful, or the mechanism is mislabelled."""

    rng = np.random.default_rng(5)
    world = _initial_world(rng)
    for month in range(DECISION_MONTHS):
        _drift(world, month, "effect_reversal", rng)
    assert world.lift_scale < 0


# -- label maturation ------------------------------------------------------
def test_a_refit_cannot_read_a_label_that_had_not_arrived() -> None:
    history = [{"month": value} for value in range(-3, 6)]
    visible = _matured(history, month=3, delay=LABEL_DELAY_MONTHS)
    assert all(entry["month"] + LABEL_DELAY_MONTHS < 3 for entry in visible)
    assert max(entry["month"] for entry in visible) == 3 - LABEL_DELAY_MONTHS - 1


def test_a_longer_delay_hides_more() -> None:
    history = [{"month": value} for value in range(-3, 6)]
    assert len(_matured(history, 4, delay=2)) < len(_matured(history, 4, delay=1))


# -- the strategies --------------------------------------------------------
def _history(rng, months=10):
    world = _initial_world(rng)
    out = []
    for month in range(-months, 0):
        contacted = (rng.random(N_ACCOUNTS) < CAPACITY_FRACTION) & world.active
        active = world.active.copy()
        churned, _cf = _advance(world, contacted, rng)
        out.append({"month": month, "contacted": contacted, "churned": churned, "active": active})
    return world, out


def test_frozen_never_refits() -> None:
    rng = np.random.default_rng(6)
    world, history = _history(rng)
    initial = _fit_scorer(history, world.x)
    scorer, refitted = _refit_for("frozen", initial, history, world.x, 5, 1)
    assert refitted is False
    assert scorer is initial


def test_calibration_only_keeps_the_lift_it_was_trained_with() -> None:
    """This is why recalibration cannot fix an effect that has reversed."""

    rng = np.random.default_rng(7)
    world, history = _history(rng)
    initial = {"risk_by_bin": np.full(RISK_BINS, 0.5), "lift": 0.123}
    scorer, refitted = _refit_for("calibration_only", initial, history, world.x, 5, 1)
    assert refitted is True
    assert scorer["lift"] == 0.123
    assert not np.allclose(scorer["risk_by_bin"], initial["risk_by_bin"])


def test_full_expanding_refits_both_parts() -> None:
    rng = np.random.default_rng(8)
    world, history = _history(rng)
    initial = {"risk_by_bin": np.full(RISK_BINS, 0.5), "lift": 0.123}
    scorer, refitted = _refit_for("full_expanding", initial, history, world.x, 5, 1)
    assert refitted is True
    assert scorer["lift"] != 0.123


def test_rolling_uses_a_shorter_window_than_expanding() -> None:
    rng = np.random.default_rng(9)
    world, history = _history(rng, months=2)
    for month in range(10):
        history.append(
            {
                "month": month,
                "contacted": np.zeros(N_ACCOUNTS, dtype=bool),
                "churned": np.zeros(N_ACCOUNTS, dtype=bool),
                "active": np.ones(N_ACCOUNTS, dtype=bool),
            }
        )
    initial = _fit_scorer(history[:2], world.x)
    rolling, _r = _refit_for("rolling_6", initial, history, world.x, 9, 1)
    expanding, _e = _refit_for("full_expanding", initial, history, world.x, 9, 1)
    assert not np.allclose(rolling["risk_by_bin"], expanding["risk_by_bin"])


def test_an_unknown_strategy_is_refused() -> None:
    rng = np.random.default_rng(10)
    world, history = _history(rng)
    with pytest.raises(ValueError, match="unknown strategy"):
        _refit_for(
            "vibes", {"risk_by_bin": np.zeros(RISK_BINS), "lift": 0.0}, history, world.x, 5, 1
        )


def test_the_score_uses_both_parts_of_the_belief() -> None:
    scorer = {"risk_by_bin": np.linspace(0.01, 0.2, RISK_BINS), "lift": 0.5}
    x = np.linspace(0, 0.999, 50)
    scores = _score_accounts(scorer, x)
    assert scores[0] < scores[-1], "higher believed risk should score higher"
    doubled = _score_accounts({**scorer, "lift": 1.0}, x)
    assert np.allclose(doubled, 2 * scores)


# -- the replay ------------------------------------------------------------
@pytest.fixture(scope="module")
def replayed():
    return run_temporal_replay(worlds=6, seed=13)


def test_every_strategy_is_replayed_in_every_mechanism(replayed) -> None:
    seen = {(item.mechanism, item.strategy) for item in replayed.outcomes}
    assert seen == {
        (mechanism, strategy) for mechanism, _d in MECHANISMS for strategy in STRATEGIES
    }


def test_trajectories_diverge_between_strategies(replayed) -> None:
    """If two strategies scored identically on every world it is a re-score."""

    for mechanism, _d in MECHANISMS:
        totals = {
            strategy: [
                item.prevented_churn
                for item in replayed.outcomes
                if item.mechanism == mechanism and item.strategy == strategy
            ]
            for strategy in STRATEGIES
        }
        assert totals["rolling_6"] != totals["frozen"], mechanism


def test_the_ledger_reconciles(replayed) -> None:
    assert replayed.to_dict()["ledger_balanced"] is True
    assert replayed.to_dict()["unbalanced_runs"] == []


def test_only_frozen_reports_no_refits(replayed) -> None:
    for item in replayed.outcomes:
        if item.strategy == "frozen":
            assert item.refits == 0
        else:
            assert item.refits > 0


def test_the_late_window_is_reported_beside_the_whole_horizon(replayed) -> None:
    """The total hides the degradation; the late window is where it shows."""

    for row in replayed.summary():
        assert "mean_late_prevented_churn" in row
        assert "late_vs_frozen" in row
    for item in replayed.outcomes:
        assert len(item.monthly_prevented) == DECISION_MONTHS


def test_frozen_is_its_own_zero(replayed) -> None:
    for row in replayed.summary():
        if row["strategy"] == "frozen":
            assert row["vs_frozen"] == pytest.approx(0.0, abs=1e-12)
            assert row["late_vs_frozen"] == pytest.approx(0.0, abs=1e-12)


def test_calibration_only_cannot_rescue_a_reversed_effect(replayed) -> None:
    """The runbook's point, measured: recalibration is not an effect fix."""

    rows = {
        row["strategy"]: row for row in replayed.summary() if row["mechanism"] == "effect_reversal"
    }
    assert abs(rows["calibration_only"]["late_vs_frozen"]) < 1.0
    assert rows["full_expanding"]["late_vs_frozen"] > 1.0


def test_the_scope_note_reports_the_count_that_actually_ran(replayed) -> None:
    assert "6 worlds per mechanism" in replayed.to_dict()["scope_note"]


def test_the_markdown_names_the_replay_and_the_ledger(replayed) -> None:
    rendered = render_markdown(replayed)
    assert "own trajectory" in rendered
    assert "Ledger reconciliation" in rendered
    assert "late" in rendered.lower()


def test_an_unbalanced_run_is_named_rather_than_hidden() -> None:
    report = TemporalReplayReport(worlds_per_mechanism=1, seed=1, started_at="now")
    report.outcomes = [
        StrategyOutcome(
            mechanism="covariate_shift",
            strategy="frozen",
            world=0,
            prevented_churn=1.0,
            contacts=10,
            refits=0,
            ledger_balanced=False,
            monthly_prevented=[1.0],
        )
    ]
    payload = report.to_dict()
    assert payload["ledger_balanced"] is False
    assert payload["unbalanced_runs"] == ["covariate_shift:frozen:0"]


def test_the_rolling_window_is_the_declared_length() -> None:
    assert ROLLING_WINDOW == 6
