"""Prospective R1 negative controls; separate from candidate coverage gates.

Run ``--dry-run`` before the first outcome draw. The frozen manifest binds this
script and the R1 producer to the fixed 500-world, 300-bootstrap control suite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from telco_churn.next_evaluator_transfer import (
    CELLS,
    _batch_vs_no_contact,
    _draw_batch,
)
from telco_churn.policy_comparison import dr_action_scores
from telco_churn.validity_suite import _wilson

OUTPUT = Path(__file__).resolve().parent
WORLDS = 500
RESAMPLES = 300
N_ROWS = 4_000
SEED = 53109


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest() -> dict:
    return {
        "role": "synthetic_negative_controls_only",
        "source_hashes": {
            str(Path(__file__).relative_to(ROOT)).replace("\\", "/"): _sha(Path(__file__)),
            "src/telco_churn/next_evaluator_transfer.py": _sha(
                ROOT / "src/telco_churn/next_evaluator_transfer.py"
            ),
            "src/telco_churn/policy_comparison.py": _sha(
                ROOT / "src/telco_churn/policy_comparison.py"
            ),
        },
        "worlds_per_stochastic_control": WORLDS,
        "bootstrap_resamples": RESAMPLES,
        "rows_per_world": N_ROWS,
        "independent_customers_T5": N_ROWS // 2,
        "seed": SEED,
        "rng_namespaces": {
            "T5_cluster": "[seed, 5, world_index]",
            "T3_leakage": "[seed, 3, world_index]",
            "bootstrap": "[seed, cell_number, world_index, variant_number]",
        },
        "controls": {
            "wrong_logged_propensity": "Inject e=0.50 where generator logged e=0.85; control-harness provenance guard must reject. Production scoring cannot independently prove a self-declared probability is true.",
            "row_iid_T5": "Compare customer bootstrap to deliberately invalid row-IID bootstrap under two records and one assignment per customer; truth is zero.",
            "outcome_leakage_T3": "Compare clean pre-treatment rank to forbidden rank built from evaluation DR score; truth is zero and leakage guard must reject.",
        },
        "planned_outputs": [
            "NEGATIVE_CONTROL_PROTOCOL.json",
            "NEGATIVE_CONTROL_RESULT.json",
            "NEGATIVE_CONTROL_REPORT.md",
            "NEGATIVE_CONTROL_RECEIPT.json",
        ],
        "promotion": False,
        "relation_to_R1": "Separate negative controls; do not retroactively change the frozen R1 coverage study.",
    }


def _interval_summary(values: list[tuple[float, float, float]]) -> dict:
    result = np.asarray(values)
    covered = int(np.sum((result[:, 1] <= 0) & (0 <= result[:, 2])))
    promoted = int(np.sum(result[:, 1] > 0))
    return {
        "worlds": len(result),
        "truth": 0.0,
        "mean_point_bias": float(np.mean(result[:, 0])),
        "coverage": covered / len(result),
        "coverage_wilson": _wilson(covered, len(result)),
        "positive_lower_bound_rate": promoted / len(result),
        "positive_lower_bound_wilson": _wilson(promoted, len(result)),
        "mean_interval_width": float(np.mean(result[:, 2] - result[:, 1])),
    }


def _cluster_world(
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    customers = N_ROWS // 2
    x1 = rng.integers(0, 2, customers)
    x2 = rng.integers(0, 2, customers)
    x3 = rng.uniform(-1, 1, customers)
    intercept = rng.uniform(-0.7, 0.7, customers)
    linear = 1.2 * x3 + 0.7 * x1 - 0.5 * x2 + intercept
    baseline_event = 0.002 + 0.025 / (1 + np.exp(-linear))
    treated = rng.random(customers) < 0.5
    events = rng.random((customers, 2)) < baseline_event[:, None]
    row_reward = 1.0 - events.astype(float).reshape(-1)
    customer_reward = row_reward.reshape(customers, 2).mean(axis=1)
    customer_action = np.where(treated, "contact", "hold")
    customer_design = pd.DataFrame(
        {"hold": np.full(customers, 0.5), "contact": np.full(customers, 0.5)}
    )
    customer_oracle = pd.DataFrame({"hold": 1.0 - baseline_event, "contact": 1.0 - baseline_event})
    customer_scores = dr_action_scores(
        customer_reward, customer_action, customer_design, customer_oracle
    )
    row_scores = dr_action_scores(
        row_reward,
        np.repeat(customer_action, 2),
        pd.DataFrame({"hold": np.full(N_ROWS, 0.5), "contact": np.full(N_ROWS, 0.5)}),
        pd.DataFrame(
            {
                "hold": np.repeat(1.0 - baseline_event, 2),
                "contact": np.repeat(1.0 - baseline_event, 2),
            }
        ),
    )
    ranking = x1 + 0.1 * x3
    return (
        customer_scores["contact"].to_numpy() - customer_scores["hold"].to_numpy(),
        ranking,
        row_scores["contact"].to_numpy() - row_scores["hold"].to_numpy(),
        np.repeat(ranking, 2),
    )


def _guard_propensity(expected: pd.DataFrame, claimed: pd.DataFrame) -> None:
    if not np.array_equal(expected.to_numpy(), claimed.to_numpy()):
        raise ValueError(
            "design-provenance mismatch: claimed probabilities differ from generator log"
        )


def _guard_rank_features(feature_names: set[str]) -> None:
    forbidden = {"reward", "evaluation_outcome", "dr_effect_score"}
    if feature_names & forbidden:
        raise ValueError("policy-rank provenance mismatch: evaluation outcome used in ranking")


def run() -> dict:
    started = time.perf_counter()
    cell3 = next(cell for cell in CELLS if cell.cell_id == "T3")
    expected = pd.DataFrame({"hold": np.full(N_ROWS, 0.15), "contact": np.full(N_ROWS, 0.85)})
    injected = pd.DataFrame({"hold": np.full(N_ROWS, 0.5), "contact": np.full(N_ROWS, 0.5)})
    try:
        _guard_propensity(expected, injected)
    except ValueError as error:
        wrong_propensity = {
            "status": "REJECTED_BY_CONTROL_HARNESS",
            "reason": str(error),
            "mismatched_rows": N_ROWS,
            "production_api_has_independent_design_provenance": False,
        }
    else:
        wrong_propensity = {"status": "FAILED_TO_REJECT"}
    try:
        _guard_rank_features({"x1", "dr_effect_score"})
    except ValueError as error:
        leakage_guard = {"status": "REJECTED_BY_CONTROL_HARNESS", "reason": str(error)}
    else:
        leakage_guard = {"status": "FAILED_TO_REJECT"}

    observations: dict[str, list[tuple[float, float, float]]] = {
        "T5_customer_cluster_bootstrap": [],
        "T5_invalid_row_iid_bootstrap": [],
        "T3_clean_feature_rank": [],
        "T3_forbidden_outcome_rank": [],
    }
    point_mismatch = 0
    for world in range(WORLDS):
        rng5 = np.random.default_rng([SEED, 5, world])
        customer_effect, customer_rank, row_effect, row_rank = _cluster_world(rng5)
        customer_result = _batch_vs_no_contact(
            customer_effect,
            customer_rank,
            resamples=RESAMPLES,
            seed=int(np.random.SeedSequence([SEED, 5, world, 1]).generate_state(1)[0]),
        )
        row_result = _batch_vs_no_contact(
            row_effect,
            row_rank,
            resamples=RESAMPLES,
            seed=int(np.random.SeedSequence([SEED, 5, world, 2]).generate_state(1)[0]),
        )
        observations["T5_customer_cluster_bootstrap"].append(customer_result)
        observations["T5_invalid_row_iid_bootstrap"].append(row_result)
        point_mismatch += abs(customer_result[0] - row_result[0]) > 1e-12

        rng3 = np.random.default_rng([SEED, 3, world])
        reward, action, design, oracle, clean_rank = _draw_batch(
            n_rows=N_ROWS, cell=cell3, rng=rng3
        )
        scores = dr_action_scores(reward, action, design, oracle)
        effect = scores["contact"].to_numpy() - scores["hold"].to_numpy()
        observations["T3_clean_feature_rank"].append(
            _batch_vs_no_contact(
                effect,
                clean_rank,
                resamples=RESAMPLES,
                seed=int(np.random.SeedSequence([SEED, 3, world, 1]).generate_state(1)[0]),
            )
        )
        observations["T3_forbidden_outcome_rank"].append(
            _batch_vs_no_contact(
                effect,
                effect,
                resamples=RESAMPLES,
                seed=int(np.random.SeedSequence([SEED, 3, world, 2]).generate_state(1)[0]),
            )
        )
    return {
        "status": "NEGATIVE_CONTROLS_ONLY",
        "promotion": False,
        "runtime_seconds": round(time.perf_counter() - started, 2),
        "wrong_logged_propensity": wrong_propensity,
        "leakage_guard": leakage_guard,
        "T5_point_estimate_mismatch_worlds": int(point_mismatch),
        "readouts": {key: _interval_summary(value) for key, value in observations.items()},
        "scope": "Intentional violations. No real telecom effect or licensed interval follows.",
    }


def report(result: dict) -> str:
    lines = [
        "# R1 negative controls - separate synthetic suite",
        "",
        "**Status:** negative controls only; no method promotion. The suite uses 500 "
        "worlds per stochastic control, 4,000 rows, and 300 bootstrap resamples.",
        "",
        f"Wrong logged propensity: **{result['wrong_logged_propensity']['status']}**. "
        "The check is inside this harness; the production score API cannot verify "
        "a self-declared design probability against an external assignment log.",
        "",
        f"Outcome-derived ranking provenance: **{result['leakage_guard']['status']}**. "
        "The forbidden rank is evaluated below only to expose its statistical failure.",
        "",
        "| Control | Coverage | Wilson lower | Positive lower bound | Wilson upper | Mean bias | Mean width |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in result["readouts"].items():
        lines.append(
            f"| {name} | {item['coverage']:.3f} | {item['coverage_wilson'][0]:.3f} | "
            f"{item['positive_lower_bound_rate']:.3f} | "
            f"{item['positive_lower_bound_wilson'][1]:.3f} | "
            f"{item['mean_point_bias']:+.6f} | {item['mean_interval_width']:.6f} |"
        )
    lines += [
        "",
        "The row-IID bootstrap deliberately treats correlated records as "
        "independent. The customer bootstrap resamples the actual decision "
        "units. Both use the same null generator; their comparison is a "
        "diagnostic, not another candidate-search round. The outcome-rank "
        "control reads the evaluation scores when choosing contacts, violating "
        "the pre-treatment policy contract.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    protocol_path = OUTPUT / "NEGATIVE_CONTROL_PROTOCOL.json"
    if args.dry_run:
        protocol_path.write_text(json.dumps(manifest(), indent=2), encoding="utf-8")
        print(f"{protocol_path}: frozen; no outcomes drawn")
        return 0
    if (
        not protocol_path.exists()
        or json.loads(protocol_path.read_text(encoding="utf-8")) != manifest()
    ):
        parser.error("freeze an identical negative-control protocol with --dry-run first")
    result = run()
    result_path = OUTPUT / "NEGATIVE_CONTROL_RESULT.json"
    report_path = OUTPUT / "NEGATIVE_CONTROL_REPORT.md"
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    report_path.write_text(report(result), encoding="utf-8")
    receipt = {
        "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "protocol_sha256": _sha(protocol_path),
        "result_sha256": _sha(result_path),
        "report_sha256": _sha(report_path),
        "runtime_seconds": result["runtime_seconds"],
    }
    (OUTPUT / "NEGATIVE_CONTROL_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(f"{result_path}: {result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
