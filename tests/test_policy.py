import numpy as np

from telco_churn.policy import Scenario, break_even_save_rate, expected_value, plan_campaign


def test_expected_value_and_break_even_are_consistent() -> None:
    scenario = Scenario("test", 0.2, 0.5, 10.0, 6)
    value = expected_value([0.5], [100], scenario)
    break_even = break_even_save_rate([0.5], [100], scenario)
    assert value[0] == 20.0
    assert np.isclose(break_even[0], 1 / 15)


def test_campaign_respects_capacity_and_positive_value() -> None:
    scenario = Scenario("test", 0.1, 0.5, 10.0, 6)
    plan = plan_campaign(
        ["a", "b", "c", "d"],
        [0.9, 0.8, 0.2, 0.1],
        [100, 100, 100, 100],
        scenario,
        budget_fraction=0.5,
    )
    selected = plan[plan["selected"]]
    assert selected["customer_id"].tolist() == ["a", "b"]
    assert (selected["simulated_expected_value"] > 0).all()


def test_fractional_and_money_caps_are_hard_constraints() -> None:
    scenario = Scenario("test", 0.2, 0.5, 10.0, 6)
    args = (["a", "b", "c", "d", "e"], [0.9] * 5, [100] * 5, scenario)
    one_slot = plan_campaign(*args, budget_fraction=0.39)
    assert one_slot.loc[one_slot["selected"], "customer_id"].tolist() == ["a"]
    assert one_slot.loc[one_slot["customer_id"] == "b", "reason"].item() == "contact_cap_reached"
    no_slot = plan_campaign(*args, budget_fraction=0.1)
    assert no_slot["selected"].sum() == 0
    cost_limited = plan_campaign(*args, budget_fraction=1, max_total_cost=25)
    assert cost_limited.loc[cost_limited["selected"], "customer_id"].tolist() == ["a", "b"]
    assert (
        cost_limited.loc[cost_limited["customer_id"] == "c", "reason"].item() == "cost_cap_reached"
    )


def test_rank_and_decision_survive_input_reordering() -> None:
    scenario = Scenario("test", 0.2, 0.5, 10.0, 6)
    left = plan_campaign(["b", "a", "c"], [0.7] * 3, [100] * 3, scenario, budget_fraction=0.34)
    right = plan_campaign(["c", "b", "a"], [0.7] * 3, [100] * 3, scenario, budget_fraction=0.34)
    assert left.loc[left["selected"], "customer_id"].tolist() == ["a"]
    assert left[["customer_id", "rank", "reason"]].to_dict("records") == right[
        ["customer_id", "rank", "reason"]
    ].to_dict("records")


def test_ineligible_high_value_customer_is_never_selected() -> None:
    scenario = Scenario("test", 0.2, 0.5, 0.0, 6)
    plan = plan_campaign(
        ["high", "low"],
        [0.9, 0.2],
        [100, 100],
        scenario,
        budget_fraction=0.5,
        eligible=[False, True],
    )
    assert plan.loc[plan["selected"], "customer_id"].tolist() == ["low"]
    assert plan.loc[plan["customer_id"] == "high", "reason"].item() == "not_eligible"
