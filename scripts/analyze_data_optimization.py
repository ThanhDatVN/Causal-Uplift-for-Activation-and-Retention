"""Turn EDA and OOF screening artifacts into an auditable optimization decision.

This script does not fit a model and never reads a confirmation split.  It joins
the preregistered problem statements, full-data EDA evidence, two development OOF
seeds, and paired bootstrap output into two compact decision artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metric(aggregate: pd.DataFrame, model: str, column: str) -> float:
    rows = aggregate.loc[aggregate["model"] == model, column]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one row for {model!r}, found {len(rows)}")
    return float(rows.iloc[0])


def _seed_metric(ranking: pd.DataFrame, model: str, seed: int) -> float:
    rows = ranking.loc[
        (ranking["model"] == model) & (ranking["fold_seed"] == seed),
        "policy_area_dr",
    ]
    if len(rows) != 1:
        raise ValueError(f"Expected one {model!r} result for seed {seed}")
    return float(rows.iloc[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comparison-dir",
        type=Path,
        default=REPO / "output" / "improvement" / "data_opt_comparison",
    )
    parser.add_argument(
        "--eda-dir",
        type=Path,
        default=REPO / "output" / "eda",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=REPO / "configs" / "data_optimization_protocol_v1.json",
    )
    parser.add_argument(
        "--screen-dir",
        type=Path,
        action="append",
        default=None,
        help="Two OOF screen directories. Defaults to seeds 101 and 202.",
    )
    args = parser.parse_args()

    screen_dirs = args.screen_dir or [
        REPO / "output" / "improvement" / "data_opt_screen_seed101",
        REPO / "output" / "improvement" / "data_opt_screen_seed202",
    ]
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    eda = json.loads((args.eda_dir / "run_manifest.json").read_text(encoding="utf-8"))
    aggregate_path = args.comparison_dir / "candidate_aggregate.csv"
    ranking_path = args.comparison_dir / "candidate_ranking.csv"
    paired_path = args.comparison_dir / "paired_comparisons.csv"
    advance_path = args.comparison_dir / "advancement_decision.csv"
    aggregate = pd.read_csv(aggregate_path)
    ranking = pd.read_csv(ranking_path)
    paired = pd.read_csv(paired_path)
    advancement = pd.read_csv(advance_path)
    manifests = [
        json.loads((path / "run_manifest.json").read_text(encoding="utf-8"))
        for path in screen_dirs
    ]

    expected_seeds = sorted(protocol["cross_fitting"][key] for key in (
        "primary_fold_seed",
        "secondary_fold_seed",
    ))
    observed_seeds = sorted(int(item["fold_seed"]) for item in manifests)
    if observed_seeds != expected_seeds:
        raise ValueError(f"Fold seeds {observed_seeds} do not match protocol {expected_seeds}")
    if any(item["protocol_id"] != protocol["protocol_id"] for item in manifests):
        raise ValueError("Screen artifact protocol_id mismatch")

    response_mean = _metric(aggregate, "Response", "policy_area_dr_mean")
    sentinel_mean = _metric(aggregate, "Response-Sentinel", "policy_area_dr_mean")
    funnel_mean = _metric(aggregate, "Funnel-S", "policy_area_dr_mean")
    funnel_sentinel_mean = _metric(
        aggregate,
        "Funnel-S-Sentinel",
        "policy_area_dr_mean",
    )
    s_mean = _metric(aggregate, "S-Under7", "policy_area_dr_mean")
    s_sentinel_mean = _metric(
        aggregate,
        "S-Sentinel-Under7",
        "policy_area_dr_mean",
    )
    qagg_mean = _metric(aggregate, "Ensemble-QAgg", "policy_area_dr_mean")
    paired_row = paired.loc[
        (paired["model_a"] == "Response-Sentinel")
        & (paired["model_b"] == "Response")
    ].iloc[0]
    advance_row = advancement.loc[
        advancement["model"] == "Response-Sentinel"
    ].iloc[0]

    sentinel_seed_values = {
        str(seed): {
            "response": _seed_metric(ranking, "Response", seed),
            "challenger": _seed_metric(ranking, "Response-Sentinel", seed),
        }
        for seed in expected_seeds
    }
    for values in sentinel_seed_values.values():
        values["difference"] = values["challenger"] - values["response"]

    structure = eda["structure"]
    dominance = eda["prognostic_dominance"]
    rows = [
        {
            "problem_id": "rare_conversion",
            "evidence_before": (
                "conversion_rate=0.2917%; development control positives=1625"
            ),
            "intervention": "factor P(conversion) through auxiliary visit outcome",
            "models": "Funnel-S; Funnel-S-Sentinel",
            "mean_policy_area_delta_vs_response": max(
                funnel_mean,
                funnel_sentinel_mean,
            ) - response_mean,
            "verdict": "rejected_at_screen",
            "next_action": (
                "Do not use funnel for conversion policy; collect more control "
                "conversions or a new randomized campaign."
            ),
        },
        {
            "problem_id": "sentinel_structure",
            "evidence_before": (
                f"{structure['n_distinct_sentinel_patterns']} patterns; "
                "6/12 features have mode_share>0.9"
            ),
            "intervention": "fold-local sentinel flags and sentinel count",
            "models": "Response-Sentinel; S-Sentinel-Under7",
            "mean_policy_area_delta_vs_response": sentinel_mean - response_mean,
            "verdict": "advance_not_promote",
            "next_action": "Evaluate Response-Sentinel in a new randomized confirmation campaign.",
        },
        {
            "problem_id": "prognostic_dominance",
            "evidence_before": (
                "corr(p0,tau)="
                f"{dominance['feature_bins']['pearson_r']:.6f}; "
                "Response is the frozen reference"
            ),
            "intervention": "require every fold seed to beat Response",
            "models": "all challengers vs Response",
            "mean_policy_area_delta_vs_response": sentinel_mean - response_mean,
            "verdict": "champion_held",
            "next_action": "Keep Response until paired confirmation CI is strictly above zero.",
        },
        {
            "problem_id": "metric_disagreement",
            "evidence_before": "DR-risk ensembles can prefer models with weaker policy value",
            "intervention": "policy_area_dr primary; Qini and DR risk secondary",
            "models": "Ensemble-QAgg vs Response",
            "mean_policy_area_delta_vs_response": qagg_mean - response_mean,
            "verdict": "primary_metric_guard_worked",
            "next_action": "Do not promote by DR risk or Qini alone.",
        },
    ]
    resolution = pd.DataFrame(rows)
    resolution.to_csv(args.comparison_dir / "problem_resolution.csv", index=False)

    decision = {
        "protocol_id": protocol["protocol_id"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_scope": {
            "stage": "development_oof_screen",
            "confirmation_read": False,
            "pool_fraction": manifests[0]["pool_fraction"],
            "n_rows": manifests[0]["arm_counts"]["n_rows"],
            "n_conversion_control": manifests[0]["arm_counts"][
                "n_conversion_control"
            ],
            "fold_seeds": expected_seeds,
            "primary_seed_bootstrap_replicates": int(paired_row["n_boot"]),
        },
        "current_champion": "Response",
        "screening_winner": "Response-Sentinel",
        "advances_to_new_confirmation": bool(advance_row["advance"]),
        "promoted": False,
        "promotion_decision": "hold_response_champion",
        "metrics": {
            "response_policy_area_dr_mean": response_mean,
            "response_sentinel_policy_area_dr_mean": sentinel_mean,
            "mean_difference": sentinel_mean - response_mean,
            "relative_difference": (sentinel_mean - response_mean) / response_mean,
            "per_seed": sentinel_seed_values,
            "primary_seed_paired_ci_95": [
                float(paired_row["policy_area_ci_low"]),
                float(paired_row["policy_area_ci_high"]),
            ],
            "primary_seed_probability_positive": float(
                paired_row["policy_area_probability_positive"]
            ),
            "funnel_best_mean_difference_vs_response": max(
                funnel_mean,
                funnel_sentinel_mean,
            ) - response_mean,
            "s_sentinel_difference_vs_s": s_sentinel_mean - s_mean,
            "qagg_difference_vs_response": qagg_mean - response_mean,
        },
        "decision_reasons": [
            "Response-Sentinel beats Response by point estimate on both registered fold seeds.",
            "The observed mean gain is small and the paired 95% interval crosses zero.",
            "The protocol requires a new randomized confirmation campaign for promotion.",
            "No previously observed Sprint 2 confirmation data were used for this decision.",
        ],
        "next_step": (
            "Freeze Response-Sentinel as the sole advancing challenger and score it "
            "against Response on a new randomized confirmation campaign."
        ),
        "input_sha256": {
            str(path.relative_to(REPO)): _sha256(path)
            for path in (
                args.protocol,
                args.eda_dir / "run_manifest.json",
                aggregate_path,
                ranking_path,
                paired_path,
                advance_path,
                *(path / "run_manifest.json" for path in screen_dirs),
            )
        },
    }
    (args.comparison_dir / "optimization_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(resolution.to_string(index=False), flush=True)
    print(
        "[decision] hold Response; advance Response-Sentinel to new confirmation",
        flush=True,
    )


if __name__ == "__main__":
    main()
