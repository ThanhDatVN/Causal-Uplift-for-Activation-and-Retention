"""R4 synthetic, known-truth comparison of feasible ranking and exact allocation.

The two rules see the same frozen M07 score and the same observed features.
Oracle probabilities are used only after decisions are fixed. This is a
synthetic method study, not an estimate of telecom treatment effect or ROI.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from .allocation import allocate_batch, capacity_limit
from .candidates import build_candidate

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports" / "v4" / "exact_allocator_study"
PROTOCOL = ROOT / "docs" / "NEXT_RESEARCH_EXPERIMENTS_EN.md"
LOCK = ROOT / "locks" / "research.lock.txt"
SEED_BASE = 840_000
MECHANISMS = ("aligned", "opposed", "sharp_null")
WORLDS = 30
TRAIN_UNITS = 10_000
SELECTION_UNITS = 5_000
BATCHES = 50
BATCH_SIZE = 20
CONTACT_FRACTION = 0.20
CONTACT_CAP = capacity_limit(BATCH_SIZE, CONTACT_FRACTION)
MONEY_CENTS = 200
VALUE_PER_EVENT = 100.0
PRACTICAL_MARGIN = 1.0


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _features(rng: np.random.Generator, n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "X1": rng.binomial(1, 0.5, n),
            "X2": rng.binomial(1, 0.5, n),
            "Z": rng.normal(0, 1, n),
        }
    )


def _probabilities(features: pd.DataFrame, mechanism: str) -> tuple[np.ndarray, np.ndarray]:
    x1 = features["X1"].to_numpy(dtype=float)
    z = features["Z"].to_numpy(dtype=float)
    p0 = 0.01 + 0.05 / (1 + np.exp(-(0.8 * (2 * x1 - 1) + 0.5 * z)))
    direction = {"aligned": 1.0, "opposed": -1.0, "sharp_null": 0.0}[mechanism]
    tau = direction * 0.01 * (2 * x1 - 1)
    p1 = p0 - tau
    if not ((p0 >= 0).all() and (p1 >= 0).all() and (p1 <= 1).all()):
        raise ValueError("generator produced an invalid probability")
    return p0, tau


def _cost_cents(features: pd.DataFrame) -> np.ndarray:
    return np.where(features["X2"].to_numpy(dtype=int) == 0, 20, 120)


def feasible_rank(
    ids: np.ndarray, predicted_net: np.ndarray, cost_cents: np.ndarray, *, money_cents: int
) -> np.ndarray:
    """Rank by positive predicted net, skipping candidates that do not fit."""
    ranked = allocate_batch(ids, predicted_net, fraction=CONTACT_FRACTION)
    order = np.argsort(ranked.frame["rank"].to_numpy())
    chosen = np.zeros(len(ids), dtype=bool)
    remaining = money_cents
    for index in order:
        if chosen.sum() >= ranked.capacity:
            break
        if predicted_net[index] <= 0:
            break
        if cost_cents[index] <= remaining:
            chosen[index] = True
            remaining -= int(cost_cents[index])
    return chosen


def exact_allocate(
    ids: np.ndarray, predicted_net: np.ndarray, cost_cents: np.ndarray, *, money_cents: int
) -> np.ndarray:
    """Exact two-price solver: for each price, only its top-k prefix can be optimal.

    Exhaustively enumerate feasible counts by price; ties use sorted unit IDs.
    This is exact for the protocol's two fixed prices and any nonnegative cap.
    """
    cap = capacity_limit(len(ids), CONTACT_FRACTION)
    groups: list[list[int]] = []
    for price in sorted(set(cost_cents.tolist())):
        indices = [i for i in range(len(ids)) if cost_cents[i] == price and predicted_net[i] > 0]
        indices.sort(key=lambda i: (-predicted_net[i], str(ids[i])))
        groups.append(indices[:cap])
    if len(groups) > 2:
        raise ValueError("exact solver protocol supports at most two observed price groups")
    if len(groups) == 1:
        groups.append([])  # A homogeneous-price control is still exactly solvable.
    best_value = 0.0
    best_ids: tuple[str, ...] = ()
    best_indices: tuple[int, ...] = ()
    left, right = groups
    for nl in range(len(left) + 1):
        for nr in range(len(right) + 1):
            indices = tuple(left[:nl] + right[:nr])
            if len(indices) > cap or sum(int(cost_cents[i]) for i in indices) > money_cents:
                continue
            objective = float(sum(predicted_net[i] for i in indices))
            id_key = tuple(sorted(str(ids[i]) for i in indices))
            if objective > best_value + 1e-12 or (
                abs(objective - best_value) <= 1e-12 and id_key < best_ids
            ):
                best_value, best_ids, best_indices = objective, id_key, indices
    chosen = np.zeros(len(ids), dtype=bool)
    chosen[list(best_indices)] = True
    return chosen


def _brute_force(ids: np.ndarray, net: np.ndarray, cost: np.ndarray, money: int) -> float:
    best = 0.0
    for size in range(capacity_limit(len(ids), CONTACT_FRACTION) + 1):
        for indices in itertools.combinations(range(len(ids)), size):
            if sum(int(cost[i]) for i in indices) <= money:
                best = max(best, float(sum(net[i] for i in indices)))
    return best


def mechanical_controls() -> dict[str, bool]:
    """One integrated algorithm check, including a brute-force reference."""
    ids = np.array([f"c{i:02}" for i in range(10)])
    score = np.array([1.8, 1.7, 1.6, 1.5, 1.4, 1.3, -0.1, 0.0, 0.2, 0.3])
    prices = np.array([120, 120, 120, 20, 20, 20, 20, 120, 20, 20])
    exact = exact_allocate(ids, score, prices, money_cents=200)
    controls = {
        "brute_force_optimality": math.isclose(
            float(score[exact].sum()), _brute_force(ids, score, prices, 200), abs_tol=1e-12
        ),
        "zero_money_no_contact": not exact_allocate(ids, score, prices, money_cents=0).any(),
        "all_negative_no_contact": not exact_allocate(
            ids, -np.ones(10), prices, money_cents=200
        ).any(),
        "tie_order_invariant": bool(
            np.array_equal(
                np.sort(ids[exact_allocate(ids, np.ones(10), prices, money_cents=200)]),
                np.sort(
                    ids[::-1][exact_allocate(ids[::-1], np.ones(10), prices[::-1], money_cents=200)]
                ),
            )
        ),
        "infeasible_action_skipped": not exact_allocate(
            ids, score, np.full(10, 120), money_cents=20
        ).any(),
        "homogeneous_cost_equivalence": bool(
            np.array_equal(
                feasible_rank(ids, score, np.full(10, 20), money_cents=200),
                exact_allocate(ids, score, np.full(10, 20), money_cents=200),
            )
        ),
    }
    # A second exhaustive tiny fixture checks that 2-price enumeration handles
    # a different cap and two positive price groups.
    tiny_ids = ids[:5]
    tiny_scores = score[:5]
    tiny_prices = prices[:5]
    tiny = exact_allocate(tiny_ids, tiny_scores, tiny_prices, money_cents=200)
    controls["second_brute_force_optimality"] = math.isclose(
        float(tiny_scores[tiny].sum()),
        _brute_force(tiny_ids, tiny_scores, tiny_prices, 200),
        abs_tol=1e-12,
    )
    if not all(controls.values()):
        raise AssertionError(f"mechanical allocator control failed: {controls}")
    return controls


def _config() -> dict[str, object]:
    return {
        "protocol_revision": "R4-allocation-small-batch-v1",
        "role": "new_known_truth_synthetic_worlds",
        "mechanisms": list(MECHANISMS),
        "worlds_per_mechanism": WORLDS,
        "train_units": TRAIN_UNITS,
        "selection_units_reserved_unused": SELECTION_UNITS,
        "evaluation_batches": BATCHES,
        "evaluation_batch_size": BATCH_SIZE,
        "contact_fraction": CONTACT_FRACTION,
        "hard_contacts_per_batch": CONTACT_CAP,
        "money_cap_cents": MONEY_CENTS,
        "cost_cents_by_X2": {"0": 20, "1": 120},
        "constraint_geometry": (
            "Two expensive contacts cost 240 > 200; one expensive plus three cheap "
            "costs 180 <= 200. Thus the rank-with-skip rule and the exact solver "
            "must agree for every batch with positive scores under this revision."
        ),
        "value_per_prevented_event": VALUE_PER_EVENT,
        "score_recipe": "M07 DR-Ridge, alpha=10, 3-fold cross-fitted logistic nuisances, e=0.5",
        "generator": "R04 V03 p0; tau=+/-0.01(2X1-1) or sharp null; X1/X2 binary, Z normal",
        "primary_contrast": "exact minus feasible rank; paired true expected net CU per 1000 eligible",
        "interval": "two-sided 95% Student t across 30 independent world differences",
        "practical_margin_opposed_CU_per_1000": PRACTICAL_MARGIN,
        "seed_namespace": {
            "base": SEED_BASE,
            "world": "base + mechanism_index*10000 + world_index*10",
            "train_features": "+1",
            "train_assignment_and_outcome": "+2",
            "selection_features": "+3",
            "evaluation_features": "+4",
            "model": "+5",
        },
        "expected_outputs": [
            "WORLD_RESULTS.csv",
            "RESULT.json",
            "ALLOCATOR_STUDY.md",
            "RUN_MANIFEST.json",
        ],
        "resource_cap": "90 model fits; 4500 paired 20-unit batches; CPU only",
        "external_data_and_splits": "none; independent generated train/selection/evaluation roles",
    }


def _dry_manifest() -> dict[str, object]:
    source = Path(__file__).resolve()
    return {
        "status": "DRY_RUN_FROZEN_NO_EVALUATION_OUTCOMES_READ",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "config": _config(),
        "source_sha256": _sha(source),
        "protocol_sha256": _sha(PROTOCOL),
        "research_lock_sha256": _sha(LOCK),
        "python_version": sys.version,
        "package_versions": {
            package: version(package) for package in ("numpy", "pandas", "scipy", "scikit-learn")
        },
        "schema_checks": {
            "disjoint_role_seed_namespaces": True,
            "known_design_propensity": 0.5,
            "oracle_only_for_post_decision_evaluation": True,
            "contact_cap": CONTACT_CAP,
            "costs_integer_cents": True,
        },
    }


def _world(mechanism: str, mechanism_index: int, world_index: int) -> dict[str, object]:
    seed = SEED_BASE + mechanism_index * 10_000 + world_index * 10
    training = _features(np.random.default_rng(seed + 1), TRAIN_UNITS)
    p0, tau = _probabilities(training, mechanism)
    draw_rng = np.random.default_rng(seed + 2)
    arm = draw_rng.binomial(1, 0.5, TRAIN_UNITS)
    # Observed reward is non-event, so its treatment contrast is +tau.
    outcome = draw_rng.binomial(1, np.where(arm == 1, p0 - tau, p0))
    reward = 1 - outcome
    # Reserved, role-isolated selection frame; no selection or outcome access.
    selection = _features(np.random.default_rng(seed + 3), SELECTION_UNITS)
    if len(selection) != SELECTION_UNITS:
        raise AssertionError("selection role size changed")
    evaluation = _features(np.random.default_rng(seed + 4), BATCHES * BATCH_SIZE)
    _, true_tau = _probabilities(evaluation, mechanism)
    model_start = time.perf_counter()
    model = build_candidate("M07", seed=seed + 5).fit(training, arm, reward, propensity=0.5)
    fit_seconds = time.perf_counter() - model_start
    score = model.score(evaluation)
    cost = _cost_cents(evaluation)
    predicted_net = VALUE_PER_EVENT * score - cost / 100.0
    true_net = VALUE_PER_EVENT * true_tau - cost / 100.0
    values = {"rank": 0.0, "exact": 0.0}
    predicted = {"rank": 0.0, "exact": 0.0}
    contacts = {"rank": 0, "exact": 0}
    unused = {"rank": 0, "exact": 0}
    disagreement = 0
    violations = 0
    rank_objective_excess_max = 0.0
    allocation_start = time.perf_counter()
    for batch in range(BATCHES):
        lo, hi = batch * BATCH_SIZE, (batch + 1) * BATCH_SIZE
        ids = np.array([f"{mechanism}-{world_index:02}-{i:04}" for i in range(lo, hi)])
        net_slice = predicted_net[lo:hi]
        cost_slice = cost[lo:hi]
        selections = {
            "rank": feasible_rank(ids, net_slice, cost_slice, money_cents=MONEY_CENTS),
            "exact": exact_allocate(ids, net_slice, cost_slice, money_cents=MONEY_CENTS),
        }
        rank_objective_excess_max = max(
            rank_objective_excess_max,
            float(net_slice[selections["rank"]].sum() - net_slice[selections["exact"]].sum()),
        )
        disagreement += int(np.sum(selections["rank"] != selections["exact"]))
        for method, selected in selections.items():
            spent = int(cost_slice[selected].sum())
            count = int(selected.sum())
            violations += int(count > CONTACT_CAP or spent > MONEY_CENTS)
            contacts[method] += count
            unused[method] += CONTACT_CAP - count
            values[method] += float(true_net[lo:hi][selected].sum())
            predicted[method] += float(net_slice[selected].sum())
    allocation_seconds = time.perf_counter() - allocation_start
    if violations or rank_objective_excess_max > 1e-9:
        raise AssertionError("constraint violation or exact objective below feasible rank")
    return {
        "mechanism": mechanism,
        "world": world_index,
        "seed": seed,
        "train_events": int(outcome.sum()),
        "rank_true_CU_per_1000": values["rank"],
        "exact_true_CU_per_1000": values["exact"],
        "paired_delta_CU_per_1000": values["exact"] - values["rank"],
        "rank_predicted_CU_per_1000": predicted["rank"],
        "exact_predicted_CU_per_1000": predicted["exact"],
        "rank_contacts": contacts["rank"],
        "exact_contacts": contacts["exact"],
        "rank_unused_slots": unused["rank"],
        "exact_unused_slots": unused["exact"],
        "disagreement_fraction": disagreement / (BATCHES * BATCH_SIZE),
        "constraint_violations": violations,
        "rank_objective_excess_max": max(0.0, rank_objective_excess_max),
        "fit_seconds": fit_seconds,
        "allocation_seconds": allocation_seconds,
    }


def _summarize(worlds: pd.DataFrame) -> dict[str, object]:
    output: dict[str, object] = {}
    for mechanism in MECHANISMS:
        part = worlds.loc[worlds["mechanism"] == mechanism]
        delta = part["paired_delta_CU_per_1000"].to_numpy(dtype=float)
        n = len(delta)
        mean = float(delta.mean())
        se = float(delta.std(ddof=1) / np.sqrt(n))
        half = float(student_t.ppf(0.975, n - 1) * se)
        output[mechanism] = {
            "independent_worlds": n,
            "mean_delta_CU_per_1000": mean,
            "mcse_CU_per_1000": se,
            "ci95_CU_per_1000": [mean - half, mean + half],
            "mean_rank_true_CU_per_1000": float(part["rank_true_CU_per_1000"].mean()),
            "mean_exact_true_CU_per_1000": float(part["exact_true_CU_per_1000"].mean()),
            "mean_disagreement_fraction": float(part["disagreement_fraction"].mean()),
            "total_rank_unused_slots": int(part["rank_unused_slots"].sum()),
            "total_exact_unused_slots": int(part["exact_unused_slots"].sum()),
            "total_constraint_violations": int(part["constraint_violations"].sum()),
            "max_rank_objective_excess": float(part["rank_objective_excess_max"].max()),
            "mean_fit_seconds": float(part["fit_seconds"].mean()),
            "mean_allocation_seconds": float(part["allocation_seconds"].mean()),
        }
    opposed = output["opposed"]
    null = output["sharp_null"]
    output["decision"] = (
        "CARRY_EXACT_FOR_SYNTHETIC_FOLLOWUP"
        if opposed["ci95_CU_per_1000"][0] > PRACTICAL_MARGIN
        and opposed["total_constraint_violations"] == 0
        and null["ci95_CU_per_1000"][0] <= 0
        else "RETAIN_FEASIBLE_RANK_OR_INCONCLUSIVE"
    )
    return output


def _report(summary: dict[str, object], runtime: float) -> str:
    lines = [
        "# R4 exact allocator: known-truth synthetic comparison",
        "",
        "**Role:** synthetic method study; no telecom uplift or ROI claim.",
        f"**Run:** 90 independent worlds, 4,500 paired batches, {runtime:.1f} CPU wall seconds.",
        "",
        "M07 DR-Ridge was fitted independently in each world on 10,000 randomized training units. "
        "The 5,000-unit selection role was reserved and unused. Each allocator saw identical frozen "
        "scores and costs on 50 new batches of 20 units. Oracle probabilities were read only after "
        "decisions. Value is true expected synthetic net currency per 1,000 eligible units, "
        "with 100 currency units per prevented adverse event and assumed contact prices 0.2/1.2.",
        "",
        "| Mechanism | Exact minus rank | 95% world-t interval | MCSE | Disagreement | Violations |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mechanism in MECHANISMS:
        row = summary[mechanism]
        lo, hi = row["ci95_CU_per_1000"]
        lines.append(
            f"| {mechanism} | {row['mean_delta_CU_per_1000']:.3f} | "
            f"[{lo:.3f}, {hi:.3f}] | {row['mcse_CU_per_1000']:.3f} | "
            f"{row['mean_disagreement_fraction']:.3%} | {row['total_constraint_violations']} |"
        )
    lines.extend(
        [
            "",
            f"**Predeclared decision:** `{summary['decision']}`. The practical margin is 1 synthetic "
            "currency unit per 1,000 eligible customers in the opposed mechanism. The sharp-null "
            "mechanism is a negative control and must not be promoted as a gain.",
            "",
            "The exact two-price solver maximizes the same predicted objective as the feasible rank "
            "rule under four contacts and a 2-unit money cap. Algorithmic controls include brute-force "
            "optimality on tiny batches, homogeneous prices, zero money, all-negative scores, ties, "
            "and infeasible actions. Under these particular constraints two expensive contacts "
            "exceed the money cap, while one expensive plus three cheap contacts fits. Sorting "
            "by positive net score and skipping unaffordable expensive contacts is therefore "
            "already exact: each feasible top-four set can contain at most one expensive contact. "
            "The exhaustive two-price count search has a zero solver gap by construction. "
            "Both policies have zero recorded hard-cap violations. The table above is the "
            "primary readout; exact and rank cannot separate in this frozen constraint geometry.",
            "",
            "**Limits:** 30 worlds per mechanism give a descriptive t interval for this generator. "
            "They do not validate interval coverage, other cost grids, a real customer's offer response, "
            "or a deployed economic return. The synthetic price and value scale are assumptions. "
            "The comparison is conditional on M07 and this frozen generator. The current cost "
            "geometry cannot distinguish the two allocators. A 1.2-unit cap with these same "
            "prices could create a real tradeoff between one expensive and several cheap "
            "contacts, but it is only a prospective design suggestion, not a result here. "
            "It requires a new frozen protocol and new worlds.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    freeze_path = output / "DRY_RUN_MANIFEST.json"
    if args.dry_run:
        if freeze_path.exists():
            raise FileExistsError(f"freeze already exists: {freeze_path}")
        freeze_path.write_text(json.dumps(_dry_manifest(), indent=2) + "\n", encoding="utf-8")
        print(f"Frozen dry-run manifest: {freeze_path}")
        return
    if not freeze_path.exists():
        raise FileNotFoundError("run --dry-run first; freeze the protocol before evaluation")
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    current = _dry_manifest()
    for key in (
        "config",
        "source_sha256",
        "protocol_sha256",
        "research_lock_sha256",
        "python_version",
        "package_versions",
        "schema_checks",
    ):
        if frozen[key] != current[key]:
            raise RuntimeError(
                f"dry-run freeze mismatch in {key}; create a new revision/output directory"
            )
    controls = mechanical_controls()
    start = time.perf_counter()
    rows = [
        _world(mechanism, mi, wi) for mi, mechanism in enumerate(MECHANISMS) for wi in range(WORLDS)
    ]
    runtime = time.perf_counter() - start
    worlds = pd.DataFrame(rows)
    summary = _summarize(worlds)
    worlds_path = output / "WORLD_RESULTS.csv"
    result_path = output / "RESULT.json"
    report_path = output / "ALLOCATOR_STUDY.md"
    worlds.to_csv(worlds_path, index=False)
    result_path.write_text(
        json.dumps({"summary": summary, "mechanical_controls": controls}, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_report(summary, runtime), encoding="utf-8")
    manifest = {
        "status": "COMPLETED",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "dry_run_manifest_sha256": _sha(freeze_path),
        "config": frozen["config"],
        "source_sha256": frozen["source_sha256"],
        "protocol_sha256": frozen["protocol_sha256"],
        "research_lock_sha256": frozen["research_lock_sha256"],
        "runtime_seconds": runtime,
        "command": " ".join(sys.argv),
        "completed_worlds": len(worlds),
        "failed_worlds": [],
        "outputs_sha256": {
            path.name: _sha(path) for path in (worlds_path, result_path, report_path)
        },
        "evidence_scope": "known-truth synthetic method study only; causal release tier unchanged",
    }
    (output / "RUN_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(report_path)
    print(summary["decision"])


if __name__ == "__main__":
    main()
