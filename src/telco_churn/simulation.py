"""Deterministic customer-month simulator for temporal and policy failure probes.

This is not evidence about Orange or any real operator.  Its purpose is to make
otherwise unobservable counterfactuals and post-drift policy regret measurable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SIMULATION_SEED = 20260914
OFFER_COST = 4.0
START_MONTH = "2024-01-01"

TEMPORAL_FEATURES = (
    "region",
    "plan",
    "contract",
    "autopay",
    "tenure_months",
    "monthly_charge",
    "gross_margin_6m",
    "usage_gb_last_month",
    "usage_change_pct",
    "outages_90d",
    "tickets_90d",
    "complaint_last_month",
    "late_payments_90d",
    "price_change_90d",
    "prior_offer_count",
    "months_since_offer",
    "observed_loyalty_score",
)

ORACLE_COLUMNS = (
    "true_control_churn_probability",
    "true_treated_churn_probability",
    "true_cate_prevented_churn",
    "true_net_value",
    "potential_churn_control",
    "potential_churn_treated",
)


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(value, -20, 20)))


def simulate_customer_months(
    *,
    customers: int = 6_000,
    months: int = 18,
    seed: int = SIMULATION_SEED,
) -> pd.DataFrame:
    """Generate active-customer snapshots with randomized retention offers.

    Each row is a decision made at the start of a month. The current treatment
    is assigned after the feature snapshot; churn is observed by month-end.
    Potential outcome probabilities and outcomes are retained only for audits.
    """
    if customers < 500:
        raise ValueError("customers must be at least 500 for stable randomized arms")
    if months < 6:
        raise ValueError("months must be at least 6")
    rng = np.random.default_rng(seed)
    dates = pd.date_range(START_MONTH, periods=months, freq="MS")
    customer_ids = np.array([f"mock-{i:06d}" for i in range(customers)])
    region = rng.choice(["north", "central", "south"], customers, p=[0.30, 0.25, 0.45])
    plan = rng.choice(["mobile", "fiber", "bundle"], customers, p=[0.42, 0.34, 0.24])
    contract = rng.choice(["month_to_month", "annual"], customers, p=[0.67, 0.33])
    autopay = rng.binomial(1, 0.58, customers)
    tenure = rng.integers(1, 61, customers)
    latent_price_sensitivity = rng.beta(2.0, 2.2, customers)
    latent_service_sensitivity = rng.beta(1.8, 2.5, customers)
    latent_loyalty = rng.normal(0, 0.75, customers)
    observed_loyalty = np.clip(50 + 18 * latent_loyalty + rng.normal(0, 8, customers), 0, 100)
    base_price = np.select(
        [plan == "mobile", plan == "fiber", plan == "bundle"], [42.0, 68.0, 91.0]
    )
    monthly_charge = base_price + rng.normal(0, 7, customers)
    usage = np.select(
        [plan == "mobile", plan == "fiber", plan == "bundle"], [18.0, 170.0, 120.0]
    ) * rng.lognormal(0, 0.25, customers)
    usage_change = rng.normal(0, 0.08, customers)
    outages_90d = rng.poisson(0.7, customers)
    tickets_90d = rng.poisson(0.3 + 0.25 * outages_90d, customers)
    complaint = rng.binomial(1, np.clip(0.02 + 0.025 * outages_90d, 0, 0.3))
    late_payments_90d = rng.binomial(2, 0.08 + 0.08 * latent_price_sensitivity)
    price_change_90d = np.zeros(customers, dtype=int)
    prior_offer_count = np.zeros(customers, dtype=int)
    months_since_offer = np.full(customers, 12, dtype=int)
    active = np.ones(customers, dtype=bool)
    frames: list[pd.DataFrame] = []

    for month_index, snapshot_month in enumerate(dates):
        index = np.flatnonzero(active)
        if len(index) == 0:
            break
        post_drift = month_index >= 12
        seasonal = 0.18 * math_sin_month(month_index)
        declining_usage = np.maximum(-usage_change[index], 0)
        relative_price = monthly_charge[index] / base_price[index] - 1
        log_odds = (
            -4.15
            + 0.72 * (contract[index] == "month_to_month")
            - 0.28 * autopay[index]
            + 0.75 * (tenure[index] <= 6)
            + 0.52 * late_payments_90d[index]
            + (0.20 + 0.16 * post_drift) * outages_90d[index]
            + 0.82 * complaint[index]
            + 0.95 * declining_usage
            + 0.62 * price_change_90d[index]
            + 0.95 * latent_price_sensitivity[index] * relative_price
            - 0.48 * latent_loyalty[index]
            + 0.42 * post_drift * (plan[index] == "fiber")
            + seasonal
            + rng.normal(0, 0.18, len(index))
        )
        p0 = np.clip(_sigmoid(log_odds), 0.002, 0.55)
        relative_offer_effect = (
            -0.24
            + 0.82 * latent_price_sensitivity[index]
            + 0.38 * complaint[index]
            + 0.20 * (late_payments_90d[index] > 0)
            + 0.18 * (contract[index] == "month_to_month")
            - 0.30 * (prior_offer_count[index] >= 2)
            - 0.18 * ((complaint[index] == 0) & (p0 < 0.035))
            - 0.28 * post_drift * (plan[index] == "fiber")
        )
        relative_offer_effect = np.clip(relative_offer_effect, -0.40, 0.75)
        p1 = np.clip(p0 * (1 - relative_offer_effect), 0.001, 0.70)
        true_cate = p0 - p1
        treatment = rng.binomial(1, 0.5, len(index))
        draw = rng.random(len(index))
        y0 = (draw < p0).astype(int)
        y1 = (draw < p1).astype(int)
        factual = np.where(treatment == 1, y1, y0)
        margin = np.clip(monthly_charge[index] * 0.62 * 6, 30, None)
        true_net_value = true_cate * margin - OFFER_COST
        frames.append(
            pd.DataFrame(
                {
                    "customer_id": customer_ids[index],
                    "snapshot_month": snapshot_month,
                    "month_index": month_index,
                    "region": region[index],
                    "plan": plan[index],
                    "contract": contract[index],
                    "autopay": autopay[index],
                    "tenure_months": tenure[index],
                    "monthly_charge": monthly_charge[index],
                    "gross_margin_6m": margin,
                    "usage_gb_last_month": usage[index],
                    "usage_change_pct": usage_change[index],
                    "outages_90d": outages_90d[index],
                    "tickets_90d": tickets_90d[index],
                    "complaint_last_month": complaint[index],
                    "late_payments_90d": late_payments_90d[index],
                    "price_change_90d": price_change_90d[index],
                    "prior_offer_count": prior_offer_count[index],
                    "months_since_offer": months_since_offer[index],
                    "observed_loyalty_score": observed_loyalty[index],
                    "treatment": treatment,
                    "treatment_propensity": 0.5,
                    "churn_next_30d": factual,
                    "true_control_churn_probability": p0,
                    "true_treated_churn_probability": p1,
                    "true_cate_prevented_churn": true_cate,
                    "true_net_value": true_net_value,
                    "potential_churn_control": y0,
                    "potential_churn_treated": y1,
                    "post_drift": int(post_drift),
                }
            )
        )

        # Advance only after the point-in-time snapshot and outcome are materialized.
        treated_global = index[treatment == 1]
        prior_offer_count[treated_global] += 1
        months_since_offer[index] += 1
        months_since_offer[treated_global] = 0
        tenure[index] += 1
        regional_outage = 0.25 * ((region[index] == "south") & (month_index % 6 == 4))
        new_outages = rng.poisson(
            np.clip(0.22 + regional_outage + 0.30 * (plan[index] == "fiber") * post_drift, 0, 2)
        )
        outages_90d[index] = np.maximum(0, np.rint(0.65 * outages_90d[index] + new_outages)).astype(
            int
        )
        tickets_90d[index] = rng.poisson(
            np.clip(0.12 + 0.35 * outages_90d[index] * latent_service_sensitivity[index], 0, 3)
        )
        complaint[index] = rng.binomial(
            1,
            np.clip(
                0.012
                + 0.07 * outages_90d[index] * latent_service_sensitivity[index]
                + 0.03 * tickets_90d[index],
                0,
                0.65,
            ),
        )
        late_payments_90d[index] = rng.binomial(
            2, np.clip(0.04 + 0.13 * latent_price_sensitivity[index], 0, 0.45)
        )
        old_usage = usage[index].copy()
        usage[index] *= np.clip(
            1 + rng.normal(-0.006 - 0.025 * complaint[index], 0.07, len(index)), 0.65, 1.3
        )
        usage_change[index] = (usage[index] - old_usage) / np.maximum(old_usage, 1e-3)
        price_change_90d[index] = 0
        if month_index in {8, 12}:
            changed = index[(plan[index] == "fiber") | (rng.random(len(index)) < 0.15)]
            monthly_charge[changed] *= 1.06
            price_change_90d[changed] = 1
        active[index[factual == 1]] = False

    result = pd.concat(frames, ignore_index=True)
    result["snapshot_month"] = pd.to_datetime(result["snapshot_month"])
    return result


def math_sin_month(month_index: int) -> float:
    return float(np.sin(2 * np.pi * month_index / 12))


def simulation_summary(frame: pd.DataFrame) -> dict[str, float | int | str]:
    pre = frame[frame["post_drift"].eq(0)]
    post = frame[frame["post_drift"].eq(1)]
    return {
        "rows": len(frame),
        "unique_customers": int(frame["customer_id"].nunique()),
        "months": int(frame["month_index"].nunique()),
        "factual_churn_rate": float(frame["churn_next_30d"].mean()),
        "treatment_rate": float(frame["treatment"].mean()),
        "true_ate_pre_drift": float(pre["true_cate_prevented_churn"].mean()),
        "true_ate_post_drift": float(post["true_cate_prevented_churn"].mean()),
        "harmful_offer_share_pre_drift": float(pre["true_cate_prevented_churn"].lt(0).mean()),
        "harmful_offer_share_post_drift": float(post["true_cate_prevented_churn"].lt(0).mean()),
        "offer_cost": OFFER_COST,
        "disclaimer": "Synthetic mechanism test only; not external-validity evidence.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=6_000)
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--seed", type=int, default=SIMULATION_SEED)
    parser.add_argument("--output", type=Path, default=Path("data/synthetic/retention_panel.csv"))
    args = parser.parse_args()
    frame = simulate_customer_months(customers=args.customers, months=args.months, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    summary = simulation_summary(frame)
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
