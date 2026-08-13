"""Build a reproducible causal-foundation retrospective from frozen OOF artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.policy_evaluation import dr_policy_value_curve


RESERVED_KEYS = {
    "source_index",
    "treatment",
    "outcome",
    "dr_signal",
    "adjusted_signal",
    "mu0",
    "mu1",
}


DEFAULT_PROTOCOL = Path("configs/causal_foundation_protocol_v1.json")
DEFAULT_SCREEN_RUNS = {
    101: Path("output/improvement/causal_foundation_screen_seed101"),
    202: Path("output/improvement/causal_foundation_screen_seed202"),
}
DEFAULT_FULL_RUNS = {
    101: Path("output/improvement/causal_foundation_finalist_seed101"),
    202: Path("output/improvement/causal_foundation_finalist_seed202"),
}


def stability_label(deltas: list[float]) -> str:
    """Classify point-estimate behavior without using secondary metrics to override it."""
    if deltas and all(value > 0 for value in deltas):
        return "beats_reference_on_every_fold_seed"
    if deltas and all(value <= 0 for value in deltas):
        return "systematic_policy_area_regression"
    return "fold_seed_instability"


def _read_stage(run_dirs: dict[int, Path], reference: str) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    metric_rows = []
    budget_rows = []
    manifests = []
    for fold_seed, run_dir in run_dirs.items():
        metrics = pd.read_csv(run_dir / "oof_metrics.csv")
        metrics["fold_seed"] = fold_seed
        metric_rows.append(metrics)
        manifest = json.loads(
            (run_dir / "run_manifest.json").read_text(encoding="utf-8")
        )
        curve_path = run_dir / "budget_value_curve.csv"
        if curve_path.exists():
            curve = pd.read_csv(curve_path)
        else:
            curve_rows = []
            with np.load(run_dir / "oof_scores.npz") as payload:
                for model in sorted(set(payload.files) - RESERVED_KEYS):
                    values = dr_policy_value_curve(
                        payload["dr_signal"],
                        payload[model],
                        budgets=manifest["budget_grid"],
                    )["gross_value_per_customer"]
                    for budget, value in zip(
                        manifest["budget_grid"],
                        values,
                        strict=True,
                    ):
                        curve_rows.append(
                            {
                                "model": model,
                                "budget_fraction": budget,
                                "gross_value_per_customer": value,
                            }
                        )
            curve = pd.DataFrame(curve_rows)
        curve = curve.loc[~curve["model"].str.startswith("Expected random")].copy()
        reference_curve = curve.loc[
            curve["model"] == reference,
            ["budget_fraction", "gross_value_per_customer"],
        ].rename(columns={"gross_value_per_customer": "reference_value"})
        curve = curve.merge(reference_curve, on="budget_fraction", validate="many_to_one")
        curve["policy_value_delta_vs_response"] = (
            curve["gross_value_per_customer"] - curve["reference_value"]
        )
        curve["fold_seed"] = fold_seed
        budget_rows.append(curve)
        manifests.append(manifest)
    return (
        pd.concat(metric_rows, ignore_index=True),
        pd.concat(budget_rows, ignore_index=True),
        manifests,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/improvement/causal_foundation_analysis"),
    )
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    hypotheses = {item["name"]: item["hypothesis"] for item in protocol["candidates"]}
    families = {item["name"]: item["family"] for item in protocol["candidates"]}
    reference = protocol["selection_rule"]["advance_reference"]

    screen_metrics, screen_budgets, screen_manifests = _read_stage(
        DEFAULT_SCREEN_RUNS,
        reference,
    )
    full_metrics, full_budgets, full_manifests = _read_stage(
        DEFAULT_FULL_RUNS,
        reference,
    )
    reference_screen = screen_metrics.loc[
        screen_metrics["candidate"] == reference,
        ["fold_seed", "policy_area_dr"],
    ].rename(columns={"policy_area_dr": "reference_policy_area_dr"})
    screen = screen_metrics.merge(reference_screen, on="fold_seed", validate="many_to_one")
    screen["policy_area_delta_vs_response"] = (
        screen["policy_area_dr"] - screen["reference_policy_area_dr"]
    )

    full_reference = full_metrics.loc[
        full_metrics["candidate"] == reference,
        ["fold_seed", "policy_area_dr"],
    ].rename(columns={"policy_area_dr": "full_reference_policy_area_dr"})
    full = full_metrics.merge(full_reference, on="fold_seed", validate="many_to_one")
    full["full_policy_area_delta_vs_response"] = (
        full["policy_area_dr"] - full["full_reference_policy_area_dr"]
    )

    rows = []
    for candidate in hypotheses:
        if candidate == reference:
            continue
        candidate_screen = screen.loc[screen["candidate"] == candidate].sort_values("fold_seed")
        deltas = candidate_screen["policy_area_delta_vs_response"].astype(float).tolist()
        budget = screen_budgets.loc[screen_budgets["model"] == candidate]
        low_budget = budget.loc[budget["budget_fraction"] <= 0.02]
        candidate_full = full.loc[full["candidate"] == candidate].sort_values("fold_seed")
        full_deltas = candidate_full["full_policy_area_delta_vs_response"].astype(float).tolist()
        rows.append(
            {
                "candidate": candidate,
                "family": families[candidate],
                "hypothesis": hypotheses[candidate],
                "screen_seed101_delta": deltas[0] if len(deltas) > 0 else np.nan,
                "screen_seed202_delta": deltas[1] if len(deltas) > 1 else np.nan,
                "screen_mean_delta": float(np.mean(deltas)) if deltas else np.nan,
                "screen_min_delta": float(np.min(deltas)) if deltas else np.nan,
                "screen_stability": stability_label(deltas),
                "screen_low_budget_wins": int(
                    (low_budget["policy_value_delta_vs_response"] > 0).sum()
                ),
                "screen_low_budget_comparisons": len(low_budget),
                "full_seed101_delta": full_deltas[0] if len(full_deltas) > 0 else np.nan,
                "full_seed202_delta": full_deltas[1] if len(full_deltas) > 1 else np.nan,
                "full_stability": stability_label(full_deltas) if full_deltas else "not_advanced",
                "final_decision": (
                    "retain_response"
                    if not full_deltas or not all(value > 0 for value in full_deltas)
                    else "requires_new_randomized_confirmation"
                ),
            }
        )
    outcomes = pd.DataFrame(rows)

    all_manifests = screen_manifests + full_manifests
    source_hashes = {item["development_index_sha256"] for item in all_manifests}
    summary = {
        "protocol_id": protocol["protocol_id"],
        "reference": reference,
        "screen_n_rows": screen_manifests[0]["arm_counts"]["n_rows"],
        "screen_control_conversions": screen_manifests[0]["arm_counts"][
            "n_conversion_control"
        ],
        "full_n_rows": full_manifests[0]["arm_counts"]["n_rows"],
        "full_control_conversions": full_manifests[0]["arm_counts"][
            "n_conversion_control"
        ],
        "screen_advancing_candidates": outcomes.loc[
            outcomes["screen_stability"] == "beats_reference_on_every_fold_seed",
            "candidate",
        ].tolist(),
        "causal_candidates_advancing": outcomes.loc[
            (outcomes["family"] != "response")
            & (outcomes["screen_stability"] == "beats_reference_on_every_fold_seed"),
            "candidate",
        ].tolist(),
        "full_advancing_candidates": outcomes.loc[
            outcomes["full_stability"] == "beats_reference_on_every_fold_seed",
            "candidate",
        ].tolist(),
        "decision": "retain_response",
        "new_randomized_confirmation_required_for_promotion": True,
        "sprint2_confirmation_read": False,
        "causal_forest_executed": False,
        "all_stage_source_hashes": sorted(source_hashes),
        "resource_gate_passed_for_completed_runs": all(
            item["resource_gate_passed"] for item in all_manifests
        ),
        "protocol_amendments": protocol.get("protocol_amendments", []),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outcomes.to_csv(args.output_dir / "hypothesis_outcomes.csv", index=False)
    pd.concat(
        [
            screen_budgets.assign(stage="screen"),
            full_budgets.assign(stage="finalist"),
        ],
        ignore_index=True,
    ).to_csv(args.output_dir / "budget_deltas.csv", index=False)
    (args.output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(outcomes.to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
