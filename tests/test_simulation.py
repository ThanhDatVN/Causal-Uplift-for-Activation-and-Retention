import pandas as pd

from telco_churn.simulation import ORACLE_COLUMNS, TEMPORAL_FEATURES, simulate_customer_months
from telco_churn.temporal_lab import population_stability_index, validate_point_in_time_schema


def test_simulator_is_reproducible_and_point_in_time_safe() -> None:
    first = simulate_customer_months(customers=500, months=6, seed=123)
    second = simulate_customer_months(customers=500, months=6, seed=123)

    pd.testing.assert_frame_equal(first, second)
    validate_point_in_time_schema(first)
    assert not set(ORACLE_COLUMNS).intersection(TEMPORAL_FEATURES)
    assert "treatment" not in TEMPORAL_FEATURES
    assert first["treatment_propensity"].eq(0.5).all()


def test_churned_customer_leaves_following_risk_sets() -> None:
    frame = simulate_customer_months(customers=500, months=6, seed=321)
    churned = frame[frame["churn_next_30d"].eq(1)]
    for row in churned.itertuples():
        later = frame[
            frame["customer_id"].eq(row.customer_id) & frame["month_index"].gt(row.month_index)
        ]
        assert later.empty


def test_psi_is_zero_for_identical_distribution() -> None:
    series = pd.Series(range(100))
    assert population_stability_index(series, series) == 0.0
