"""Prospective R1 evaluator transfer with a batch-vs-no-contact candidate.

The frozen protocol is docs/NEXT_RESEARCH_EXPERIMENTS_EN.md. The existing
batch_policy_contrast always fills both policies' caps, so its comparator is
not no-contact. The candidate here bootstraps the *independent customer*
units, reallocates the contact cap on each draw, and compares with no-contact.
It is deliberately unlicensed until known-truth coverage is measured.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.stats import binom

from .policy_comparison import dr_action_scores_with_support, paired_contrast
from .validity_suite import _wilson

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports" / "v4" / "next_evaluator_transfer"
PROTOCOL = ROOT / "docs" / "NEXT_RESEARCH_EXPERIMENTS_EN.md"
SEED = 90371
N_UNITS = 4_000
DECLARED_WORLDS = 2_000
TRUTH_DRAWS = 20_000
COVERAGE_WILSON_FLOOR = 0.92
NULL_PROMOTION_WILSON_CEILING = 0.05
METHOD = "skewness_adjusted_t"
EFFECTIVE_DF_FLOOR = 1.0


@dataclass(frozen=True)
class Cell:
    cell_id: str
    population: str
    policy: str
    effect: str
    assignment: str
    method: str
    status: str
    reason: str | None = None


CELLS = (
    Cell("T1", "independent", "fixed", "null", "variable", METHOD, "IMPLEMENTED"),
    Cell("T2", "independent", "fixed", "rare_heterogeneous", "variable", METHOD, "IMPLEMENTED"),
    Cell(
        "T3",
        "independent",
        "batch_cap_20pct",
        "null",
        "constant_085",
        "paired_reallocation_bootstrap_candidate",
        "IMPLEMENTED_UNVALIDATED",
    ),
    Cell(
        "T4",
        "independent",
        "batch_cap_20pct",
        "rare_heterogeneous",
        "variable",
        "paired_reallocation_bootstrap_candidate",
        "IMPLEMENTED_UNVALIDATED",
    ),
    Cell(
        "T5",
        "two_records_per_customer",
        "customer_batch_cap_20pct",
        "null",
        "cluster_05",
        "customer_cluster_reallocation_bootstrap_candidate",
        "IMPLEMENTED_UNVALIDATED",
    ),
    Cell(
        "T6",
        "two_records_per_customer",
        "customer_batch_cap_20pct",
        "heterogeneous",
        "cluster_05",
        "customer_cluster_reallocation_bootstrap_candidate",
        "IMPLEMENTED_UNVALIDATED",
    ),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _namespace(cell_id: str) -> int:
    return int(hashlib.sha256(cell_id.encode("ascii")).hexdigest()[:8], 16)


def _false_gate_failure_bound(worlds: int) -> dict[str, float | int]:
    """Union bound if six cells truly cover at 95%, before outcomes are drawn."""

    minimum_covered = next(
        (
            count
            for count in range(worlds + 1)
            if _wilson(count, worlds)[0] >= COVERAGE_WILSON_FLOOR
        ),
        None,
    )
    per_cell = (
        1.0 if minimum_covered is None else float(binom.cdf(minimum_covered - 1, worlds, 0.95))
    )
    return {
        "nominal_coverage": 0.95,
        "minimum_covered_to_pass": minimum_covered,
        "one_cell_failure_probability_at_nominal_coverage": per_cell,
        "six_cell_familywise_union_bound": min(1.0, 6 * per_cell),
        "assumption": "Each cell has true independent-world coverage 0.95; union bound needs no cross-cell independence.",
    }


def config_manifest(*, worlds: int, n_units: int, seed: int, resamples: int) -> dict:
    """Declare exact inputs and unsupported cells without drawing outcomes."""

    if worlds < 1 or n_units < 100 or n_units % 2 or resamples < 20:
        raise ValueError("worlds must be positive, n_units even and at least 100, resamples >=20")
    sources = (
        Path(__file__).resolve(),
        PROTOCOL,
        ROOT / "src" / "telco_churn" / "policy_comparison.py",
        ROOT / "src" / "telco_churn" / "validity_suite.py",
    )
    research_lock = ROOT / "locks" / "research.lock.txt"
    return {
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "role": "known_truth_synthetic",
        "data": "generated_in_memory; no real customer data or external inputs",
        "data_sha256": None,
        "split_sha256": None,
        "research_lock_sha256": _sha256(research_lock),
        "planned_outputs": [
            "DRY_RUN_MANIFEST.json",
            "TRANSFER_RESULT.json",
            "TRANSFER_REPORT.md",
            "RUN_RECEIPT.json",
        ],
        "declared_cpu_wall_cap_seconds": 1_800,
        "requested_worlds_per_cell": worlds,
        "declared_worlds_per_cell": DECLARED_WORLDS,
        "n_rows_per_world": n_units,
        "seed": seed,
        "batch_bootstrap_resamples": resamples,
        "rng_key": "[seed, sha256(cell_id)[:8], world_index]",
        "selected_interval": METHOD,
        "effective_df_floor": EFFECTIVE_DF_FLOOR,
        "coverage_wilson_floor": COVERAGE_WILSON_FLOOR,
        "null_promotion_wilson_ceiling": NULL_PROMOTION_WILSON_CEILING,
        "false_coverage_gate_failure_at_nominal": _false_gate_failure_bound(worlds),
        "truth_reference_draws_per_nonnull_batch_cell": TRUTH_DRAWS,
        "target_T1_T2": "fixed_rule_population_reward_contrast",
        "target_T3_T6": "future_batch_population_reward_contrast_vs_no_contact",
        "batch_resampling_unit": "customer; T5/T6 aggregate two records before resampling",
        "batch_interval": "paired percentile bootstrap with full top-K reallocation on each resample",
        "batch_method_status": "unvalidated candidate; not the existing batch_policy_contrast",
        "negative_controls": {
            "wrong_logged_propensity": "PENDING",
            "row_iid_t5_clusters": "PENDING",
            "evaluation_outcome_ranking_leakage": "PENDING",
        },
        "truth_T1": 0.0,
        "truth_T2": 0.0001875,
        "no_promotion": True,
        "source_sha256": {
            str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path) for path in sources
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "cells": [asdict(cell) for cell in CELLS],
    }


def _draw_independent(
    *, n_units: int, cell: Cell, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame, np.ndarray]:
    x1 = rng.integers(0, 2, n_units)
    x2 = rng.integers(0, 2, n_units)
    x3 = rng.uniform(-1.0, 1.0, n_units)
    linear = 1.2 * x3 + 0.7 * x1 - 0.5 * x2
    baseline_event = 0.002 + 0.025 / (1.0 + np.exp(-linear))
    effect = 0.004 * x1 - 0.002 * x2
    if cell.effect == "null":
        effect = np.zeros(n_units)
    elif cell.effect == "rare_heterogeneous":
        baseline_event *= 0.25
        effect *= 0.25
    event_after_action = baseline_event - effect
    if not (
        np.all((baseline_event >= 0) & (baseline_event <= 1))
        and np.all((event_after_action >= 0) & (event_after_action <= 1))
    ):
        raise ValueError("generator produced an event probability outside [0,1]")
    propensity = (
        np.full(n_units, 0.85)
        if cell.assignment == "constant_085"
        else 0.15 + 0.70 / (1.0 + np.exp(-x3))
    )
    treated = rng.random(n_units) < propensity
    event = rng.random(n_units) < (baseline_event - treated * effect)
    reward = 1.0 - event.astype(float)
    action = np.where(treated, "contact", "hold")
    design = pd.DataFrame({"hold": 1.0 - propensity, "contact": propensity})
    oracle_mean = pd.DataFrame(
        {"hold": 1.0 - baseline_event, "contact": 1.0 - baseline_event + effect}
    )
    policy = np.where((x1 == 1) & (x3 > 0), "contact", "hold")
    return reward, action, design, oracle_mean, policy


def _draw_batch(
    *, n_rows: int, cell: Cell, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Return one row per independent customer for the batch evaluator."""

    clustered = cell.population == "two_records_per_customer"
    n_customers = n_rows // 2 if clustered else n_rows
    x1 = rng.integers(0, 2, n_customers)
    x2 = rng.integers(0, 2, n_customers)
    x3 = rng.uniform(-1.0, 1.0, n_customers)
    intercept = rng.uniform(-0.7, 0.7, n_customers) if clustered else 0.0
    linear = 1.2 * x3 + 0.7 * x1 - 0.5 * x2 + intercept
    baseline_event = 0.002 + 0.025 / (1.0 + np.exp(-linear))
    effect = 0.004 * x1 - 0.002 * x2
    if cell.effect == "null":
        effect = np.zeros(n_customers)
    elif cell.effect == "rare_heterogeneous":
        baseline_event *= 0.25
        effect *= 0.25
    if not np.all((baseline_event - effect >= 0) & (baseline_event - effect <= 1)):
        raise ValueError("generator produced an event probability outside [0,1]")
    if cell.assignment == "constant_085":
        propensity = np.full(n_customers, 0.85)
    elif cell.assignment == "cluster_05":
        propensity = np.full(n_customers, 0.5)
    else:
        propensity = 0.15 + 0.70 / (1.0 + np.exp(-x3))
    treated = rng.random(n_customers) < propensity
    event_probability = baseline_event - treated * effect
    if clustered:
        events = rng.random((n_customers, 2)) < event_probability[:, None]
        reward = 1.0 - events.mean(axis=1)
    else:
        reward = 1.0 - (rng.random(n_customers) < event_probability).astype(float)
    action = np.where(treated, "contact", "hold")
    design = pd.DataFrame({"hold": 1.0 - propensity, "contact": propensity})
    oracle_mean = pd.DataFrame(
        {"hold": 1.0 - baseline_event, "contact": 1.0 - baseline_event + effect}
    )
    rank_score = x1 + 0.1 * x3
    return reward, action, design, oracle_mean, rank_score


def _batch_population_truth(cell: Cell, n_customers: int) -> float:
    """Expected top-K value for this feature law, including rare low-X1 batches.

    The rank always takes X1=1 first. X2 is independent of that rank, so the
    mean effect is 0.003 for X1=1 and -0.001 for X1=0. The expected number of
    selected X1=1 customers is E[min(Binomial(n, .5), floor(.2*n))].
    """

    if cell.effect == "null":
        return 0.0
    cap = n_customers // 5
    selected_x1 = float(np.sum(binom.sf(np.arange(cap), n_customers, 0.5)))
    selected_x0 = cap - selected_x1
    scale = 0.25 if cell.effect == "rare_heterogeneous" else 1.0
    return scale * (0.003 * selected_x1 - 0.001 * selected_x0) / n_customers


def _batch_truth_reference(
    cell: Cell, n_customers: int, *, seed: int, draws: int = TRUTH_DRAWS
) -> dict[str, float | int]:
    """Independent MC over new batches, cross-checked against exact binomial truth.

    X2 is independent of the top-K ranking; aggregate binomial draws therefore
    reproduce the selected X1 and X2 counts without generating unused features.
    """

    exact = _batch_population_truth(cell, n_customers)
    if cell.effect == "null":
        return {"truth": exact, "mc_truth": exact, "mcse": 0.0, "draws": draws}
    rng = np.random.default_rng([seed, _namespace(cell.cell_id), 2_000_001])
    cap = n_customers // 5
    selected_x1 = np.minimum(rng.binomial(n_customers, 0.5, draws), cap)
    selected_x2 = rng.binomial(cap, 0.5, draws)
    scale = 0.25 if cell.effect == "rare_heterogeneous" else 1.0
    values = scale * (0.004 * selected_x1 - 0.002 * selected_x2) / n_customers
    return {
        "truth": exact,
        "mc_truth": float(values.mean()),
        "mcse": float(values.std(ddof=1) / np.sqrt(draws)),
        "draws": draws,
    }


def _batch_vs_no_contact(
    effect_scores: np.ndarray,
    rank_scores: np.ndarray,
    *,
    resamples: int,
    seed: int,
) -> tuple[float, float, float]:
    """Paired future-batch percentile CI, with contact reallocated every draw.

    The scores are oracle-nuisance DR contact-minus-hold contributions, one per
    *customer*. The baseline has zero contact in every draw. Bootstrap draws
    whole customers with replacement; T5/T6's two observed records have
    already been averaged within customer. Duplicate copies of one customer
    have the same rank and DR contribution, making their boundary order
    immaterial. This is a new unvalidated candidate, not batch_policy_contrast.
    """

    n = len(effect_scores)
    cap = n // 5

    def value_at(index: np.ndarray) -> float:
        ranking = rank_scores[index]
        chosen = np.argpartition(-ranking, cap - 1)[:cap]
        return float(np.sum(effect_scores[index[chosen]]) / n)

    identity = np.arange(n)
    delta = value_at(identity)
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=float)
    for draw in range(resamples):
        draws[draw] = value_at(rng.integers(0, n, n))
    return delta, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def _summarize(
    cell: Cell,
    observations: dict[str, list[tuple[float, float, float]]],
    worlds: int,
    *,
    n_units: int,
    seed: int,
    support: list[tuple[float, float]],
) -> list[dict]:
    if cell.policy == "fixed":
        truth = 0.0 if cell.effect == "null" else 0.0001875
        reference = {"truth": truth, "mc_truth": truth, "mcse": 0.0, "draws": 0}
    else:
        n_customers = n_units // 2 if cell.population == "two_records_per_customer" else n_units
        reference = _batch_truth_reference(cell, n_customers, seed=seed)
        truth = reference["truth"]
    summaries = []
    for label, entries in observations.items():
        result = np.asarray(entries, dtype=float)
        covered = int(np.sum((result[:, 1] <= truth) & (truth <= result[:, 2])))
        promoted = int(np.sum(result[:, 1] > 0))
        c_low, c_high = _wilson(covered, worlds)
        p_low, p_high = _wilson(promoted, worlds)
        summaries.append(
            {
                "cell": cell.cell_id,
                "method": label,
                "population_truth": truth,
                "truth_reference": reference,
                "worlds": worlds,
                "effective_independent_units_per_world": n_customers
                if cell.policy != "fixed"
                else n_units,
                "minimum_logged_action_probability": min(item[0] for item in support),
                "mean_logged_weight_ess_ratio": float(np.mean([item[1] for item in support])),
                "bias": float(np.mean(result[:, 0] - truth)),
                "coverage": covered / worlds,
                "coverage_wilson": [c_low, c_high],
                "promotion_rate": promoted / worlds,
                "promotion_wilson": [p_low, p_high],
                "mean_interval_width": float(np.mean(result[:, 2] - result[:, 1])),
                "truth_mcse_below_tenth_median_half_width": (
                    reference["mcse"] <= 0.1 * float(np.median((result[:, 2] - result[:, 1]) / 2))
                ),
                "coverage_rule_pass": c_low >= COVERAGE_WILSON_FLOOR,
                "null_promotion_rule_pass": (
                    p_high <= NULL_PROMOTION_WILSON_CEILING if cell.effect == "null" else None
                ),
            }
        )
    return summaries


def run(*, worlds: int, n_units: int, seed: int, resamples: int) -> dict:
    manifest = config_manifest(worlds=worlds, n_units=n_units, seed=seed, resamples=resamples)
    started = time.perf_counter()
    summaries: list[dict] = []
    for cell in CELLS:
        if not cell.status.startswith("IMPLEMENTED"):
            continue
        labels = (
            (("selected_dr", METHOD), ("normal_dr_reference", "normal"))
            if cell.policy == "fixed"
            else (("batch_reallocation_candidate", "percentile"),)
        )
        if cell.cell_id == "T3":
            labels += (("selected_fixed_interval_out_of_domain", METHOD),)
        observations: dict[str, list[tuple[float, float, float]]] = {
            label: [] for label, _ in labels
        }
        support: list[tuple[float, float]] = []
        for world_index in range(worlds):
            rng = np.random.default_rng([seed, _namespace(cell.cell_id), world_index])
            if cell.policy == "fixed":
                reward, action, design, oracle_mean, policy = _draw_independent(
                    n_units=n_units, cell=cell, rng=rng
                )
            else:
                reward, action, design, oracle_mean, rank_score = _draw_batch(
                    n_rows=n_units, cell=cell, rng=rng
                )
            scored = dr_action_scores_with_support(reward, action, design, oracle_mean)
            scores = scored.scores
            support.append((scored.support.min_propensity, scored.support.ess_ratio))
            if cell.policy == "fixed":
                baseline = np.full(n_units, "hold")
                for label, method in labels:
                    contrast = paired_contrast(
                        scores,
                        policy,
                        baseline,
                        interval_method=method,
                        effective_df_floor=EFFECTIVE_DF_FLOOR,
                    )
                    observations[label].append((contrast.delta, contrast.ci_low, contrast.ci_high))
            else:
                treatment_effect_score = scores["contact"].to_numpy() - scores["hold"].to_numpy()
                observations["batch_reallocation_candidate"].append(
                    _batch_vs_no_contact(
                        treatment_effect_score,
                        rank_score,
                        resamples=resamples,
                        seed=int(
                            np.random.SeedSequence(
                                [seed, _namespace(cell.cell_id), world_index, 1]
                            ).generate_state(1)[0]
                        ),
                    )
                )
                if cell.cell_id == "T3":
                    cap = len(rank_score) // 5
                    selected = np.argpartition(-rank_score, cap - 1)[:cap]
                    policy = np.full(len(rank_score), "hold", dtype=object)
                    policy[selected] = "contact"
                    baseline = np.full(len(rank_score), "hold")
                    contrast = paired_contrast(
                        scores,
                        policy,
                        baseline,
                        interval_method=METHOD,
                        effective_df_floor=EFFECTIVE_DF_FLOOR,
                    )
                    observations["selected_fixed_interval_out_of_domain"].append(
                        (contrast.delta, contrast.ci_low, contrast.ci_high)
                    )
        summaries.extend(
            _summarize(cell, observations, worlds, n_units=n_units, seed=seed, support=support)
        )
    return {
        "status": "UNVALIDATED_DIAGNOSTIC" if worlds >= DECLARED_WORLDS else "SMOKE_ONLY",
        "causal_promotion": False,
        "complete_protocol": False,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runtime_seconds": round(time.perf_counter() - started, 2),
        "manifest": manifest,
        "readouts": summaries,
        "failed_intervals": [],
        "negative_controls": manifest["negative_controls"],
        "blocked_cells": [
            asdict(cell) for cell in CELLS if not cell.status.startswith("IMPLEMENTED")
        ],
        "scope_note": (
            "T1/T2 test the selected fixed-rule interval; T3-T6 test a new, unvalidated "
            "no-contact future-batch candidate. Negative controls remain pending. "
            "No real telecom treatment effect or ROI is measured."
        ),
    }


def _render_report(payload: dict) -> str:
    lines = [
        "# R1 next evaluator transfer - development diagnostic",
        "",
        f"**Status:** `{payload['status']}`. Causal promotion: **no**. "
        "The batch and cluster bootstrap is a new candidate, not an already licensed method.",
        "",
        "The fixed-rule T1/T2 results target population reward contrast and use "
        "oracle nuisance means and logged assignment probabilities. All outcomes "
        "are generated. The chosen interval had been selected after earlier work; "
        "this run cannot turn it into an independently licensed real-data evaluator.",
        "",
        "| Cell | Method | Truth | Bias | Coverage | Wilson lower | Null promotion (Wilson upper) | Mean width | MCSE |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["readouts"]:
        lines.append(
            f"| {item['cell']} | {item['method']} | {item['population_truth']:+.6f} | "
            f"{item['bias']:+.6f} | {item['coverage']:.3f} | "
            f"{item['coverage_wilson'][0]:.3f} | {item['promotion_rate']:.3f} "
            f"({item['promotion_wilson'][1]:.3f}) | "
            f"{item['mean_interval_width']:.6f} | "
            f"{item['truth_reference']['mcse']:.2g} |"
        )
    lines.extend(
        [
            "",
            "## Method and scope",
            "",
            "The current `batch_policy_contrast` fills the cap for both policies. "
            "This runner instead compares a capped policy against no-contact. It "
            "resamples customers and recalculates top-K within each draw; T5/T6 "
            "aggregate two records before scoring and bootstrap whole customers. "
            "The interval is percentile bootstrap. Its support and coverage must be "
            "validated for this DGP; an old V08 pass cannot be transferred by name.",
            "",
            "The dry-run manifest and machine-readable results record all six cell "
            "statuses. The declared wrong-propensity, row-IID-cluster, and "
            "outcome-leakage negative controls remain to be executed. Until then "
            "the full protocol is incomplete even if every coverage gate passes. No uplift "
            "or ROI claim follows from this synthetic diagnostic.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=DECLARED_WORLDS)
    parser.add_argument("--n-units", type=int, default=N_UNITS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--bootstrap-resamples", type=int, default=600)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        payload = config_manifest(
            worlds=args.worlds,
            n_units=args.n_units,
            seed=args.seed,
            resamples=args.bootstrap_resamples,
        )
        path = args.output_dir / "DRY_RUN_MANIFEST.json"
        path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
        print(f"{path}: 2 fixed-rule methods, 4 unvalidated batch candidates; no outcomes drawn")
        return 0
    if args.worlds >= DECLARED_WORLDS:
        dry_run_path = args.output_dir / "DRY_RUN_MANIFEST.json"
        if not dry_run_path.exists():
            parser.error("declared-size run requires a frozen DRY_RUN_MANIFEST.json")
        frozen = json.loads(dry_run_path.read_text(encoding="utf-8"))
        current = config_manifest(
            worlds=args.worlds,
            n_units=args.n_units,
            seed=args.seed,
            resamples=args.bootstrap_resamples,
        )
        if frozen != current:
            parser.error("frozen dry-run manifest differs from current config or source hashes")
    payload = run(
        worlds=args.worlds, n_units=args.n_units, seed=args.seed, resamples=args.bootstrap_resamples
    )
    result_path = args.output_dir / "TRANSFER_RESULT.json"
    report_path = args.output_dir / "TRANSFER_REPORT.md"
    result_path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    report_path.write_text(_render_report(payload), encoding="utf-8")
    receipt = {
        "command": sys.argv,
        "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runtime_seconds": payload["runtime_seconds"],
        "result_sha256": _sha256(result_path),
        "report_sha256": _sha256(report_path),
        "pre_run_manifest_sha256": _sha256(args.output_dir / "DRY_RUN_MANIFEST.json")
        if (args.output_dir / "DRY_RUN_MANIFEST.json").exists()
        else None,
    }
    (args.output_dir / "RUN_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(f"{result_path}: {payload['status']}; {len(payload['blocked_cells'])} blocked cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
