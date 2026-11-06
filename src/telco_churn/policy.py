"""Budget-constrained retention policy and explicitly simulated business value."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .allocation import capacity_limit


@dataclass(frozen=True)
class Scenario:
    name: str
    save_rate: float
    gross_margin_rate: float
    contact_offer_cost: float
    horizon_months: int = 6

    def validate(self) -> None:
        if not all(
            math.isfinite(value)
            for value in (self.save_rate, self.gross_margin_rate, self.contact_offer_cost)
        ):
            raise ValueError("scenario rates and cost must be finite")
        if not 0 <= self.save_rate <= 1:
            raise ValueError("save_rate must be in [0, 1]")
        if not 0 <= self.gross_margin_rate <= 1:
            raise ValueError("gross_margin_rate must be in [0, 1]")
        if self.contact_offer_cost < 0 or self.horizon_months <= 0:
            raise ValueError("cost must be non-negative and horizon_months positive")


DEFAULT_SCENARIOS = (
    Scenario("conservative", save_rate=0.05, gross_margin_rate=0.40, contact_offer_cost=20.0),
    Scenario("base", save_rate=0.10, gross_margin_rate=0.60, contact_offer_cost=15.0),
    Scenario("optimistic", save_rate=0.20, gross_margin_rate=0.70, contact_offer_cost=10.0),
)


def expected_value(
    churn_probability: Iterable[float], monthly_charges: Iterable[float], scenario: Scenario
) -> np.ndarray:
    scenario.validate()
    probability = np.asarray(churn_probability, dtype=float)
    charges = np.asarray(monthly_charges, dtype=float)
    if probability.shape != charges.shape:
        raise ValueError("probability and monthly_charges must have equal shape")
    if (
        not np.isfinite(probability).all()
        or not np.isfinite(charges).all()
        or ((probability < 0) | (probability > 1)).any()
        or (charges < 0).any()
    ):
        raise ValueError("probabilities must be in [0,1] and charges non-negative")
    margin_at_risk = charges * scenario.horizon_months * scenario.gross_margin_rate
    return probability * scenario.save_rate * margin_at_risk - scenario.contact_offer_cost


def break_even_save_rate(
    churn_probability: Iterable[float], monthly_charges: Iterable[float], scenario: Scenario
) -> np.ndarray:
    scenario.validate()
    probability = np.asarray(churn_probability, dtype=float)
    charges = np.asarray(monthly_charges, dtype=float)
    denominator = probability * charges * scenario.horizon_months * scenario.gross_margin_rate
    return np.divide(
        scenario.contact_offer_cost,
        denominator,
        out=np.full_like(denominator, np.inf, dtype=float),
        where=denominator > 0,
    )


def plan_campaign(
    customer_ids: Iterable[str],
    churn_probability: Iterable[float],
    monthly_charges: Iterable[float],
    scenario: Scenario,
    *,
    budget_fraction: float,
    max_total_cost: float | None = None,
    eligible: Iterable[bool] | None = None,
) -> pd.DataFrame:
    if not 0 < budget_fraction <= 1:
        raise ValueError("budget_fraction must be in (0, 1]")
    if max_total_cost is not None and (not math.isfinite(max_total_cost) or max_total_cost < 0):
        raise ValueError("max_total_cost must be finite and non-negative")
    ids = np.asarray(customer_ids, dtype=str)
    probability = np.asarray(churn_probability, dtype=float)
    charges = np.asarray(monthly_charges, dtype=float)
    values = expected_value(probability, charges, scenario)
    break_even = break_even_save_rate(probability, charges, scenario)
    if not (ids.size == probability.size == charges.size):
        raise ValueError("campaign arrays must have equal length")
    eligibility = (
        np.ones(ids.size, dtype=bool)
        if eligible is None
        else np.asarray(list(eligible), dtype=bool)
    )
    if eligibility.size != ids.size:
        raise ValueError("eligible must have one entry per customer")
    contact_limit = capacity_limit(ids.size, budget_fraction)
    cost_limit = (
        math.floor(max_total_cost / scenario.contact_offer_cost)
        if max_total_cost is not None and scenario.contact_offer_cost > 0
        else ids.size
    )
    limit = min(contact_limit, cost_limit)
    order = np.lexsort((ids, -probability, -values))
    eligible_order = [index for index in order if eligibility[index] and values[index] > 0]
    selected = set(eligible_order[:limit])
    ranks = np.empty(ids.size, dtype=int)
    ranks[order] = np.arange(1, ids.size + 1)
    reasons = [
        "selected"
        if index in selected
        else "not_eligible"
        if not eligibility[index]
        else "non_positive_value"
        if values[index] <= 0
        else "cost_cap_reached"
        if cost_limit < contact_limit and ranks[index] > cost_limit
        else "contact_cap_reached"
        for index in range(ids.size)
    ]
    result = pd.DataFrame(
        {
            "customer_id": ids,
            "risk_30d": probability,
            "monthly_charges": charges,
            "simulated_expected_value": values,
            "break_even_save_rate": break_even,
            "selected": [index in selected for index in range(ids.size)],
            "reason": reasons,
            "scenario": scenario.name,
            "rank": ranks,
        }
    )
    return result.sort_values("rank")


def scenario_summary(
    customer_ids: Iterable[str],
    churn_probability: Iterable[float],
    monthly_charges: Iterable[float],
    *,
    budget_fraction: float = 0.10,
    scenarios: Iterable[Scenario] = DEFAULT_SCENARIOS,
) -> pd.DataFrame:
    rows = []
    for scenario in scenarios:
        plan = plan_campaign(
            customer_ids,
            churn_probability,
            monthly_charges,
            scenario,
            budget_fraction=budget_fraction,
        )
        selected = plan[plan["selected"]]
        rows.append(
            {
                **asdict(scenario),
                "budget_fraction": budget_fraction,
                "selected_customers": len(selected),
                "budget_capacity": capacity_limit(len(plan), budget_fraction),
                "budget_utilization": len(selected) / capacity_limit(len(plan), budget_fraction)
                if capacity_limit(len(plan), budget_fraction)
                else 0.0,
                "simulated_total_expected_value": selected["simulated_expected_value"].sum(),
                "mean_selected_risk": selected["risk_30d"].mean() if len(selected) else math.nan,
            }
        )
    return pd.DataFrame(rows)
