"""Rebuild the frozen Sprint 2 main policy comparison with paired bootstrap."""

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
    cost_aware_policy,
    doubly_robust_effect_signal,
    ipw_effect_signal,
    policy_value_from_signal,
    top_budget_policy,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sprint2-dir",
        type=Path,
        default=OUTPUT_DIR / "sprint2",
    )
    parser.add_argument("--budget", type=float, default=0.10)
    parser.add_argument("--cost", type=float, default=0.0005)
    parser.add_argument("--value-per-conversion", type=float, default=1.0)
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    frozen = np.load(args.sprint2_dir / "confirmation_predictions.npz")
    manifest_path = args.sprint2_dir / "protocol_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    propensity = float(manifest["evaluation"]["propensity"])
    y, t = frozen["conversion"], frozen["treatment"]
    ipw_signal = ipw_effect_signal(y, t, propensity=propensity)
    dr_signal = doubly_robust_effect_signal(
        y,
        t,
        frozen["mu0_local_exact"],
        frozen["mu1_local_exact"],
        propensity=propensity,
    )
    rng = np.random.default_rng(args.seed)
    policies = {
        "Treat none": np.zeros(len(y), dtype="int8"),
        "Random top-k": top_budget_policy(rng.random(len(y)), args.budget),
        "Response top-k": top_budget_policy(
            frozen["response_score"],
            args.budget,
        ),
        "X-Renormalized top-k": top_budget_policy(
            frozen["x_renormalized"],
            args.budget,
        ),
        "X-Calibrated top-k": top_budget_policy(
            frozen["x_calibrated"],
            args.budget,
        ),
        "T-LocalExact top-k": top_budget_policy(
            frozen["t_local_exact"],
            args.budget,
        ),
        "X-Calibrated cost-aware": cost_aware_policy(
            frozen["x_calibrated"],
            args.budget,
            args.value_per_conversion,
            args.cost,
        ),
    }
    names = list(policies)
    contributions = np.column_stack(
        [
            policy * (args.value_per_conversion * dr_signal - args.cost)
            for policy in policies.values()
        ]
    )
    bootstrap = bootstrap_policy_values(
        contributions,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    random_index = names.index("Random top-k")
    rows = []
    for index, (name, policy) in enumerate(policies.items()):
        difference = (
            bootstrap["draws"][:, index]
            - bootstrap["draws"][:, random_index]
        )
        rows.append(
            {
                "run_id": manifest["run_id"],
                "policy": name,
                "budget_fraction": args.budget,
                "contact_cost_assumption": args.cost,
                "value_per_conversion_assumption": args.value_per_conversion,
                "target_fraction": float(np.mean(policy)),
                "ipw_net_scenario_value_per_customer": policy_value_from_signal(
                    policy,
                    ipw_signal,
                    args.value_per_conversion,
                    args.cost,
                ),
                "dr_net_scenario_value_per_customer": bootstrap["mean"][index],
                "dr_ci_low": bootstrap["ci_low"][index],
                "dr_ci_high": bootstrap["ci_high"][index],
                "dr_delta_vs_random": (
                    bootstrap["mean"][index]
                    - bootstrap["mean"][random_index]
                ),
                "dr_delta_vs_random_ci_low": np.quantile(difference, 0.025),
                "dr_delta_vs_random_ci_high": np.quantile(difference, 0.975),
                "n_boot": args.n_boot,
                "is_monetary_observation": False,
            }
        )
    output = args.sprint2_dir / "policy_value_comparison.csv"
    pd.DataFrame(rows).to_csv(output, index=False)

    manifest["evaluation"]["n_boot"] = args.n_boot
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {output}")
    print(f"[update] {manifest_path} n_boot={args.n_boot}")


if __name__ == "__main__":
    main()
