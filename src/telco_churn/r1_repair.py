"""Frozen synthetic follow-up for the failed R1 transfer cells.

This tests a fixed-policy paired DR normal interval and a studentized,
customer-level bootstrap that reallocates a 20% batch cap on every draw.
The generator and seeds differ from the inspected T1-T6 experiment. Passing
synthetic cells would not validate a real campaign or a telecom effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.stats import binom, norm

from .policy_comparison import dr_action_scores, paired_contrast
from .validity_suite import _wilson

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports/v4/r1_repair_20261002"
SEED = 884211
N_CUSTOMERS = 2_000
WORLDS = 2_000
RESAMPLES = 299
CAP_FRACTION = 0.20
COVERAGE_WILSON_FLOOR = 0.92
NULL_PROMOTION_WILSON_CEILING = 0.05


@dataclass(frozen=True)
class Cell:
    name: str
    policy: str
    effect: str
    assignment: str
    clustered: bool


CELLS = (
    Cell("F1_fixed_null", "fixed", "null", "constant_085", False),
    Cell("F2_fixed_rare", "fixed", "rare", "variable", False),
    Cell("B1_batch_null", "batch", "null", "constant_085", False),
    Cell("B2_batch_rare", "batch", "rare", "variable", False),
    Cell("C1_cluster_null", "batch", "null", "constant_05", True),
    Cell("C2_cluster_effect", "batch", "effect", "constant_05", True),
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _namespace(name: str) -> int:
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)


def _truth(cell: Cell, n: int) -> float:
    if cell.effect == "null":
        return 0.0
    scale = 0.35 if cell.effect == "rare" else 1.0
    if cell.policy == "fixed":
        return scale * 0.4 * 0.5 * (0.003 - 0.001 * 0.3)
    cap = int(CAP_FRACTION * n)
    # X1=1 ranks before X1=0 for z in [-1,1]; X2 is independent of rank.
    expected_x1 = float(np.sum(binom.sf(np.arange(cap), n, 0.4)))
    return scale * (0.003 * expected_x1 - 0.001 * 0.3 * cap) / n


def _world(cell: Cell, n: int, rng: np.random.Generator) -> dict:
    x1 = rng.binomial(1, 0.4, n)
    x2 = rng.binomial(1, 0.3, n)
    z = rng.uniform(-1.0, 1.0, n)
    base = 0.004 + 0.020 / (1 + np.exp(-(1.1 * z + 0.4 * x1 - 0.3 * x2)))
    scale = 0.35 if cell.effect == "rare" else 1.0
    if cell.effect == "rare":
        base *= scale
    effect = np.zeros(n) if cell.effect == "null" else scale * (0.003 * x1 - 0.001 * x2)
    if not (np.all(base > 0) and np.all(base - effect > 0) and np.all(base < 1)):
        raise ValueError("event probabilities outside (0,1)")
    if cell.assignment == "constant_085":
        e = np.full(n, 0.85)
    elif cell.assignment == "constant_05":
        e = np.full(n, 0.5)
    else:
        e = 0.15 + 0.70 / (1 + np.exp(-z))
    treated = rng.random(n) < e
    event_probability = base - treated * effect
    if cell.clustered:
        # A shared pre-treatment uniform creates strong within-customer
        # outcome dependence. Assignment and the decision unit remain customer.
        common = rng.random(n)
        independent = rng.random((n, 2))
        shared = rng.random(n) < 0.90
        uniforms = np.where(shared[:, None], common[:, None], independent)
        row_rewards = 1.0 - (uniforms < event_probability[:, None]).astype(float)
        reward = row_rewards.mean(axis=1)
    else:
        row_rewards = None
        reward = 1.0 - (rng.random(n) < event_probability).astype(float)
    actions = np.where(treated, "contact", "hold")
    design = pd.DataFrame({"hold": 1 - e, "contact": e})
    oracle = pd.DataFrame({"hold": 1 - base, "contact": 1 - base + effect})
    scores = dr_action_scores(reward, actions, design, oracle)
    rank = x1 + 0.05 * z
    output = {"scores": scores, "rank": rank, "fixed": (x1 == 1) & (z > 0)}
    if row_rewards is not None:
        row_scores = dr_action_scores(
            row_rewards.reshape(-1),
            np.repeat(actions, 2),
            pd.DataFrame({"hold": np.repeat(1 - e, 2), "contact": np.repeat(e, 2)}),
            pd.DataFrame(
                {
                    "hold": np.repeat(1 - base, 2),
                    "contact": np.repeat(1 - base + effect, 2),
                }
            ),
        )
        output["row_effect"] = row_scores.contact.to_numpy() - row_scores.hold.to_numpy()
    return output


def _moments(effect: np.ndarray, rank: np.ndarray) -> tuple[float, float, np.ndarray]:
    n = len(effect)
    cap = int(CAP_FRACTION * n)
    chosen = np.argpartition(-rank, cap - 1)[:cap]
    selected = effect[chosen]
    total = float(selected.sum())
    point = total / n
    variance = max(0.0, (float(np.square(selected).sum()) - total * total / n) / (n - 1))
    return point, float(np.sqrt(variance / n)), chosen


def _studentized_batch(
    effect: np.ndarray, rank: np.ndarray, *, seed: int, resamples: int
) -> tuple[float, float, float, float, int, float, float]:
    n = len(effect)
    cap = int(CAP_FRACTION * n)
    point, se, _ = _moments(effect, rank)
    if not np.isfinite(se) or se <= 0:
        raise ValueError("zero or non-finite original studentizing SE")
    rng = np.random.default_rng(seed)
    boot_point = np.empty(resamples)
    boot_se = np.empty(resamples)
    for start in range(0, resamples, 64):
        stop = min(start + 64, resamples)
        indices = rng.integers(0, n, size=(stop - start, n))
        sampled_rank = rank[indices]
        chosen = np.argpartition(-sampled_rank, cap - 1, axis=1)[:, :cap]
        sampled_effect = np.take_along_axis(effect[indices], chosen, axis=1)
        totals = sampled_effect.sum(axis=1)
        theta = totals / n
        variance = np.maximum(
            0.0, (np.square(sampled_effect).sum(axis=1) - totals * totals / n) / (n - 1)
        )
        boot_point[start:stop] = theta
        boot_se[start:stop] = np.sqrt(variance / n)
    # The numerical floor is declared before validation and recorded.
    floor = max(1e-12, 0.01 * se)
    floored = int(np.sum(boot_se < floor))
    t = (boot_point - point) / np.maximum(boot_se, floor)
    q_low, q_high = np.quantile(t, (0.025, 0.975))
    percentile_low, percentile_high = np.quantile(boot_point, (0.025, 0.975))
    return (
        point,
        float(point - q_high * se),
        float(point - q_low * se),
        se,
        floored,
        float(percentile_low),
        float(percentile_high),
    )


def _normal_interval(contributions: np.ndarray) -> tuple[float, float, float]:
    n = len(contributions)
    point = float(np.mean(contributions))
    se = float(np.std(contributions, ddof=1) / np.sqrt(n))
    radius = float(norm.ppf(0.975) * se)
    return point, point - radius, point + radius


def _bounded_radius(cell: Cell, n: int) -> float:
    """Two-sided 95% bounded-difference radius for oracle DR batch value.

    |Gamma(contact)-Gamma(hold)| <= 1 + 1/min_a e(a|x) = M. Replacing one
    independent customer changes a fixed-rule mean or top-K batch value by
    at most 2M/n. McDiarmid's inequality then gives this radius.
    """

    if cell.assignment == "constant_085":
        minimum_action_probability = 0.15
    elif cell.assignment == "constant_05":
        minimum_action_probability = 0.5
    else:
        minimum_action_probability = 0.15 + 0.70 / (1 + np.exp(1.0))
    bound = 1.0 + 1.0 / minimum_action_probability
    return float(bound * np.sqrt(2 * np.log(2 / 0.05) / n))


def _config(*, worlds: int, n_customers: int, seed: int, resamples: int) -> dict:
    if worlds < 1 or n_customers < 100 or int(CAP_FRACTION * n_customers) < 1 or resamples < 100:
        raise ValueError("invalid simulation size or bootstrap count")
    sources = (
        Path(__file__),
        ROOT / "src/telco_churn/policy_comparison.py",
        ROOT / "src/telco_churn/validity_suite.py",
        ROOT / "docs/R1_REPAIR_DESIGN_EN.md",
    )
    return {
        "protocol": "R1_repair_v1",
        "role": "known_truth_synthetic_validation"
        if (worlds, n_customers, seed, resamples) == (WORLDS, N_CUSTOMERS, SEED, RESAMPLES)
        else "development_only",
        "worlds_per_cell": worlds,
        "n_customers": n_customers,
        "bootstrap_resamples": resamples,
        "seed": seed,
        "rng_key": "[seed, sha256(cell_name)[:8], world_index]; bootstrap adds 99",
        "cells": [asdict(cell) for cell in CELLS],
        "estimands": {
            "fixed": "population value of frozen policy minus no contact",
            "batch": "expected future-batch top-20%-cap value minus no contact",
        },
        "candidate_methods": {
            "fixed": "paired_dr_normal",
            "batch": "studentized_customer_reallocation",
        },
        "reference_methods": {
            "fixed": "previously selected skewness_adjusted_t (descriptive only)",
            "batch": "percentile_customer_reallocation (same draws, descriptive only)",
        },
        "safety_reference": "two-sided McDiarmid bound, M=1+1/min_action_probability, c_i=2M/n",
        "planning_precision_half_width": 0.001,
        "cluster_control": "fixed selected-customer variance, customer vs invalid row-IID; same point and unique-customer cap",
        "studentizing_floor": "max(1e-12, 0.01 * original SE)",
        "coverage_wilson_floor": COVERAGE_WILSON_FLOOR,
        "null_promotion_wilson_ceiling": NULL_PROMOTION_WILSON_CEILING,
        "source_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): _sha(p) for p in sources},
        "research_lock_sha256": _sha(ROOT / "locks/research.lock.txt"),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "confirmation_data_accessed": False,
        "causal_promotion": False,
    }


def _summarize(values: list[tuple[float, float, float]], truth: float, worlds: int) -> dict:
    arr = np.asarray(values, dtype=float)
    valid = np.isfinite(arr).all(axis=1) & (arr[:, 1] <= arr[:, 2])
    covered = int(np.sum(valid & (arr[:, 1] <= truth) & (truth <= arr[:, 2])))
    promoted = int(np.sum(valid & (arr[:, 1] > 0)))
    coverage_interval = _wilson(covered, worlds)
    promotion_interval = _wilson(promoted, worlds)
    widths = arr[valid, 2] - arr[valid, 1]
    return {
        "worlds": worlds,
        "valid_intervals": int(valid.sum()),
        "coverage": covered / worlds,
        "coverage_wilson": coverage_interval,
        "promotion_rate": promoted / worlds,
        "promotion_wilson": promotion_interval,
        "bias": float(np.nanmean(arr[:, 0] - truth)),
        "mean_width": float(np.mean(widths)) if len(widths) else None,
        "median_half_width": float(np.median(widths) / 2) if len(widths) else None,
        "coverage_gate_pass": bool(coverage_interval[0] >= COVERAGE_WILSON_FLOOR),
        "truth_mcse": 0.0,
        "truth_mcse_below_tenth_median_half_width": bool(len(widths) and np.median(widths) > 0),
        "null_promotion_gate_pass": bool(promotion_interval[1] <= NULL_PROMOTION_WILSON_CEILING)
        if truth == 0
        else None,
    }


def run(*, worlds: int, n_customers: int, seed: int, resamples: int) -> dict:
    started = time.perf_counter()
    cells = []
    all_gates = True
    for cell in CELLS:
        namespace = _namespace(cell.name)
        truth = _truth(cell, n_customers)
        observed = []
        reference = []
        bounded = []
        row_control = []
        customer_control = []
        failures = []
        total_floored = 0
        for world_index in range(worlds):
            rng = np.random.default_rng([seed, namespace, world_index])
            try:
                data = _world(cell, n_customers, rng)
                scores = data["scores"]
                if cell.policy == "fixed":
                    action = np.where(data["fixed"], "contact", "hold")
                    contrast = paired_contrast(
                        scores, action, np.full(n_customers, "hold"), interval_method="normal"
                    )
                    result = (contrast.delta, contrast.ci_low, contrast.ci_high)
                    prior = paired_contrast(
                        scores,
                        action,
                        np.full(n_customers, "hold"),
                        interval_method="skewness_adjusted_t",
                        effective_df_floor=1.0,
                    )
                    reference_result = (prior.delta, prior.ci_low, prior.ci_high)
                else:
                    effect = scores.contact.to_numpy() - scores.hold.to_numpy()
                    result_full = _studentized_batch(
                        effect,
                        data["rank"],
                        seed=int(
                            np.random.SeedSequence(
                                [seed, namespace, world_index, 99]
                            ).generate_state(1)[0]
                        ),
                        resamples=resamples,
                    )
                    result = result_full[:3]
                    reference_result = (result_full[0], result_full[5], result_full[6])
                    total_floored += result_full[4]
                    if cell.name == "C1_cluster_null":
                        _, _, chosen = _moments(effect, data["rank"])
                        selected = np.zeros(n_customers, dtype=bool)
                        selected[chosen] = True
                        customer_contribution = np.where(selected, effect, 0.0)
                        row_contribution = np.where(np.repeat(selected, 2), data["row_effect"], 0.0)
                        customer_control.append(_normal_interval(customer_contribution))
                        row_control.append(_normal_interval(row_contribution))
                        if abs(customer_control[-1][0] - row_control[-1][0]) > 1e-12:
                            raise ValueError("cluster control changed the point or cap")
                observed.append(result)
                reference.append(reference_result)
                radius = _bounded_radius(cell, n_customers)
                bounded.append((result[0], result[0] - radius, result[0] + radius))
            except Exception as exc:  # noqa: BLE001 - keep failed worlds in the denominator
                observed.append((float("nan"), float("nan"), float("nan")))
                reference.append((float("nan"), float("nan"), float("nan")))
                bounded.append((float("nan"), float("nan"), float("nan")))
                failures.append({"world": world_index, "error": f"{type(exc).__name__}: {exc}"})
        primary = _summarize(observed, truth, worlds)
        if (
            failures
            or not primary["coverage_gate_pass"]
            or not primary["truth_mcse_below_tenth_median_half_width"]
            or primary["null_promotion_gate_pass"] is False
        ):
            all_gates = False
        item = {
            "cell": asdict(cell),
            "truth": truth,
            "truth_method": "exact Bernoulli ranking/binomial expectation; no Monte Carlo truth error",
            "candidate": primary,
            "historical_reference": _summarize(reference, truth, worlds),
            "bounded_safety_reference": _summarize(bounded, truth, worlds),
            "bounded_half_width_per_1000": 1000 * _bounded_radius(cell, n_customers),
            "bounded_precision_meets_one_per_1000": _bounded_radius(cell, n_customers) <= 0.001,
            "bootstrap_se_floor_count": total_floored,
            "failures": failures,
        }
        if cell.name == "C1_cluster_null":
            customer_summary = _summarize(customer_control, truth, worlds)
            row_summary = _summarize(row_control, truth, worlds)
            discriminates = (
                customer_summary["coverage_wilson"][0] >= COVERAGE_WILSON_FLOOR
                and row_summary["coverage_wilson"][1] < COVERAGE_WILSON_FLOOR
            )
            if not discriminates:
                all_gates = False
            item["cluster_negative_control"] = {
                "customer_fixed_selection": customer_summary,
                "invalid_row_iid_fixed_selection": row_summary,
                "discriminates_at_declared_coverage_floor": discriminates,
                "note": "Variance-only control isolates the resampling unit; it does not validate reallocation coverage.",
            }
        cells.append(item)
    declared = (worlds, n_customers, seed, resamples) == (WORLDS, N_CUSTOMERS, SEED, RESAMPLES)
    return {
        "status": ("ALL_SYNTHETIC_GATES_PASS" if all_gates else "SYNTHETIC_GATE_FAILED")
        if declared
        else "DEVELOPMENT_DIAGNOSTIC",
        "worlds_per_cell": worlds,
        "cells": cells,
        "elapsed_seconds": time.perf_counter() - started,
        "confirmation_data_accessed": False,
        "causal_promotion": False,
        "scope": "Known-truth synthetic designs only; no telecom treatment effect or ROI.",
    }


def _write(path: Path, value: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _report(result: dict) -> str:
    lines = [
        "# R1 evaluator repair: "
        + (
            "development diagnostic"
            if result["status"] == "DEVELOPMENT_DIAGNOSTIC"
            else "unseen synthetic validation"
        ),
        "",
        f"**Status:** `{result['status']}`. No real-data or causal promotion.",
        "",
        "| Cell | Truth | Candidate coverage | Wilson lower | Old-method coverage | Bounded coverage | Bounded half-width / 1k | Failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["cells"]:
        candidate = row["candidate"]
        lines.append(
            f"| {row['cell']['name']} | {row['truth']:+.6f} | "
            f"{candidate['coverage']:.3f} | {candidate['coverage_wilson'][0]:.3f} | "
            f"{row['historical_reference']['coverage']:.3f} | "
            f"{row['bounded_safety_reference']['coverage']:.3f} | "
            f"{row['bounded_half_width_per_1000']:.1f} | "
            f"{len(row['failures'])} |"
        )
    cluster = next(
        row["cluster_negative_control"]
        for row in result["cells"]
        if row["cell"]["name"] == "C1_cluster_null"
    )
    lines += [
        "",
        "The fixed-rule candidate uses the production paired DR normal interval. "
        "The batch candidate resamples whole customers, reallocates the top 20% "
        "on every bootstrap draw, and studentizes by the selected-contribution "
        "standard error. C1 also compares customer and deliberately invalid row-IID "
        "normal intervals for one frozen unique-customer decision set.",
        "",
        f"Cluster control: customer coverage {cluster['customer_fixed_selection']['coverage']:.3f}; "
        f"invalid row-IID coverage {cluster['invalid_row_iid_fixed_selection']['coverage']:.3f}; "
        f"declared discrimination gate `{cluster['discriminates_at_declared_coverage_floor']}`.",
        "",
        "The bounded-difference reference is conservative under this oracle synthetic "
        "design and is reported with its very large half-width. Its coverage is not "
        "a usable campaign decision interval or an alternative promotion path.",
        "",
        "Each cell has a closed-form or exact binomial truth. Failed intervals count "
        "against coverage. This report is a synthetic method check, not evidence of "
        "real campaign benefit or a reason to open the Hillstrom confirmation split.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dry-run", "run"))
    parser.add_argument("--worlds", type=int, default=WORLDS)
    parser.add_argument("--n-customers", type=int, default=N_CUSTOMERS)
    parser.add_argument("--resamples", type=int, default=RESAMPLES)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config = _config(
        worlds=args.worlds, n_customers=args.n_customers, seed=args.seed, resamples=args.resamples
    )
    freeze_path = args.output / "FROZEN_CONFIG.json"
    if args.command == "dry-run":
        if freeze_path.exists():
            parser.error("freeze exists; use a new output directory")
        _write(freeze_path, config)
        print(freeze_path)
        return 0
    if not freeze_path.exists() or json.loads(freeze_path.read_text(encoding="utf-8")) != config:
        parser.error("frozen config missing or source/config/environment changed")
    if (args.output / "RESULT.json").exists():
        parser.error("result exists; use a new output directory")
    manifest = {
        "protocol": config["protocol"],
        "frozen_config_sha256": _sha(freeze_path),
        "command": "run",
        "started_utc": datetime.now(UTC).isoformat(),
        "status": "RUNNING",
    }
    _write(args.output / "RUN_MANIFEST.json", manifest)
    started = time.perf_counter()
    try:
        result = run(
            worlds=args.worlds,
            n_customers=args.n_customers,
            seed=args.seed,
            resamples=args.resamples,
        )
        _write(args.output / "RESULT.json", result)
        _write(args.output / "REPORT.md", _report(result))
        manifest.update(
            {
                "status": "COMPLETE",
                "result_sha256": _sha(args.output / "RESULT.json"),
                "report_sha256": _sha(args.output / "REPORT.md"),
                "study_status": result["status"],
            }
        )
    except Exception as exc:
        manifest.update({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        manifest["elapsed_seconds"] = time.perf_counter() - started
        _write(args.output / "RUN_MANIFEST.json", manifest)
    print(args.output / "REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
