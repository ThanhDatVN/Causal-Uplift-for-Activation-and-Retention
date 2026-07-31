"""Build bootstrap intervals for the frozen Response top-k budget curve."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.paths import OUTPUT_DIR
from src.policy import (
    bootstrap_policy_values,
    doubly_robust_effect_signal,
    ipw_effect_signal,
    top_budget_policy,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sprint2-dir",
        type=Path,
        default=OUTPUT_DIR / "sprint2",
    )
    parser.add_argument("--budgets", default="0,0.01,0.05,0.10,0.20,0.30")
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    budgets = [float(value) for value in args.budgets.split(",")]
    frozen = np.load(args.sprint2_dir / "confirmation_predictions.npz")
    manifest = json.loads(
        (args.sprint2_dir / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    propensity = float(manifest["evaluation"]["propensity"])
    y = frozen["conversion"]
    t = frozen["treatment"]
    response = frozen["response_score"]
    ipw_signal = ipw_effect_signal(y, t, propensity=propensity)
    dr_signal = doubly_robust_effect_signal(
        y,
        t,
        frozen["mu0_local_exact"],
        frozen["mu1_local_exact"],
        propensity=propensity,
    )
    policies = [top_budget_policy(response, budget) for budget in budgets]
    contributions = np.column_stack(
        [policy * dr_signal for policy in policies]
    )
    bootstrap = bootstrap_policy_values(
        contributions,
        n_boot=args.n_boot,
        seed=args.seed,
    )

    rows = []
    for index, (budget, policy) in enumerate(zip(budgets, policies)):
        target_fraction = float(np.mean(policy))
        gross_dr = float(bootstrap["mean"][index])
        gross_ipw = float(np.mean(policy * ipw_signal))
        rows.append(
            {
                "run_id": manifest["run_id"],
                "policy": "Response top-k",
                "budget_fraction": budget,
                "target_fraction": target_fraction,
                "gross_incremental_conversions_per_customer_dr": gross_dr,
                "gross_dr_ci_low": float(bootstrap["ci_low"][index]),
                "gross_dr_ci_high": float(bootstrap["ci_high"][index]),
                "gross_incremental_conversions_per_customer_ipw": gross_ipw,
                "break_even_contact_cost_per_target_conversion_equivalent": (
                    gross_dr / target_fraction if target_fraction > 0 else None
                ),
                "n_boot": args.n_boot,
                "monetary_outcome_available": False,
            }
        )
    output = args.sprint2_dir / "policy_budget_curve.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    print(f"[write] {output}")


if __name__ == "__main__":
    main()
