"""R4 nested development comparison. Never scores a confirmation row.

This is a planning analysis on already inspected public datasets. The three
outer fold differences are descriptive, not a population confidence interval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from .allocation import allocate_batch
from .candidates import build_candidate
from .hillstrom_data import (
    CONTROL_ARM, DEFAULT_PATH as HILLSTROM_PATH, EXPECTED_SHA256 as HILLSTROM_SHA,
    POST_TREATMENT_COLUMNS as HILLSTROM_POST, TREATMENT_COLUMN as HILLSTROM_ARM,
    feature_frame as hillstrom_features, make_split as hillstrom_split,
)
from .lenta_data import (
    DEFAULT_PATH as LENTA_PATH, EXPECTED_SHA256 as LENTA_SHA,
    POST_TREATMENT_COLUMNS as LENTA_POST, TREATMENT_COLUMN as LENTA_ARM,
    TREATMENT_GROUP, feature_frame as lenta_features, make_split as lenta_split,
)
from .policy_comparison import dr_action_scores
from .screening import _fold_nuisance

SEED = 20260930
FOLDS = 3
CAP = 0.20
CANDIDATES = ("M01", "M03", "M05", "M07")
SELECTABLE = CANDIDATES[1:]
LENTA_ROWS = 60_000
LENTA_SAMPLE_SEED = 20260921
MARGIN_PER_1000 = 1.0
OUT = Path("reports/v4/learner_comparison")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _validate(features: pd.DataFrame, action: np.ndarray, reward: np.ndarray,
              ids: list[str], forbidden: tuple[str, ...]) -> dict:
    if set(features.columns) & set(forbidden):
        raise ValueError("outcome or post-treatment column leaked into features")
    if len(features) != len(set(ids)) or len(features) != len(action) or len(action) != len(reward):
        raise ValueError("duplicate IDs or unequal frame lengths")
    if set(np.unique(action)) != {0, 1} or set(np.unique(reward)) - {0, 1}:
        raise ValueError("unsupported action or non-binary conversion")
    if features.empty or features.columns.duplicated().any():
        raise ValueError("empty or duplicate feature columns")
    if features.select_dtypes(include=["number"]).replace([np.inf, -np.inf], np.nan).isna().all().any():
        raise ValueError("entirely missing numeric feature")
    return {"n": len(features), "n_features": features.shape[1],
            "arm_counts": {str(k): int(v) for k, v in Counter(action).items()},
            "events_by_arm": {str(k): int(reward[action == k].sum()) for k in (0, 1)},
            "missing_feature_cells": int(features.isna().sum().sum())}


def load_domain(root: Path, domain: str, *, outcomes: bool) -> dict:
    """Split before selecting labels; labels are accessed on development only.

    CSV parsing still reads full raw bytes, so the holdout is procedural rather
    than cryptographically sealed. No confirmation label is indexed or scored.
    """
    if domain.startswith("hillstrom_"):
        path = root / HILLSTROM_PATH
        if sha(path) != HILLSTROM_SHA:
            raise ValueError("Hillstrom raw SHA mismatch")
        frame = pd.read_csv(path).reset_index(drop=False).rename(columns={"index": "row_id"})
        split = hillstrom_split(frame)
        arm_name = "Mens E-Mail" if domain == "hillstrom_mens" else "Womens E-Mail"
        dev = frame.loc[(split == "development") & frame[HILLSTROM_ARM].isin((CONTROL_ARM, arm_name))].copy()
        features = hillstrom_features(dev).reset_index(drop=True)
        action = (dev[HILLSTROM_ARM] == arm_name).astype(int).to_numpy()
        reward = dev["conversion"].astype(int).to_numpy() if outcomes else None
        ids = dev.row_id.astype(str).tolist()
        forbidden = (*HILLSTROM_POST, HILLSTROM_ARM, "row_id")
        e = 0.5  # equal three-arm source design, conditional on two arms
        probability_note = "source-declared equal three-arm assignment; conditional e=1/2"
        role_counts = {str(k): int(v) for k, v in split.value_counts().items()}
    elif domain == "lenta_sms":
        path = root / LENTA_PATH
        if sha(path) != LENTA_SHA:
            raise ValueError("Lenta raw SHA mismatch")
        frame = pd.read_csv(path, compression="infer", low_memory=False)
        frame.insert(0, "row_id", [f"lenta-{i:07d}" for i in range(len(frame))])
        split = lenta_split(frame)
        dev = frame.loc[split == "development"].reset_index(drop=True)
        if LENTA_ROWS < len(dev):
            take = np.sort(np.random.default_rng(LENTA_SAMPLE_SEED).choice(len(dev), LENTA_ROWS, replace=False))
            dev = dev.iloc[take].reset_index(drop=True)
        features = lenta_features(dev).reset_index(drop=True)
        action = (dev[LENTA_ARM].astype(str) == TREATMENT_GROUP).astype(int).to_numpy()
        reward = dev["response_att"].astype(int).to_numpy() if outcomes else None
        ids = dev.row_id.astype(str).tolist()
        forbidden = (*LENTA_POST, LENTA_ARM, "row_id")
        e = 0.75  # working assumption, not a verified design-provided probability
        probability_note = "ASSUMED_PROPENSITY: working e=0.75 from observed approximately 3:1 assignment; exact randomizer record unavailable"
        role_counts = {str(k): int(v) for k, v in split.value_counts().items()}
    else:
        raise ValueError(f"unknown domain {domain}")
    if set(features.columns) & set(forbidden):
        raise ValueError("post-treatment feature leakage")
    if len(ids) != len(set(ids)) or not len(features):
        raise ValueError("invalid IDs or empty development frame")
    return {"features": features, "action": action, "reward": reward, "ids": ids,
            "propensity": e, "propensity_note": probability_note, "roles": role_counts,
            "raw_sha256": sha(path), "split_id_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
            "forbidden": forbidden, "path": str(path)}


def _folds(action: np.ndarray, reward: np.ndarray, seed: int):
    strata = action * 2 + reward
    counts = Counter(strata)
    if min(counts.values()) < FOLDS:
        raise ValueError(f"insufficient arm/outcome support for 3 folds: {counts}")
    return list(StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=seed).split(np.zeros(len(action)), strata))


def _fit_score(candidate_id: str, x_train: pd.DataFrame, a_train: np.ndarray,
               y_train: np.ndarray, x_eval: pd.DataFrame, propensity: float,
               seed: int) -> tuple[np.ndarray, float, int]:
    started = time.perf_counter()
    model = build_candidate(candidate_id, seed=seed)
    model.fit(x_train, a_train, y_train, propensity=propensity)
    score = model.score(x_eval)
    # M07 uses 3x2 nuisance logistics + ridge; other models fit 1 or 2.
    fit_count = {"M01": 1, "M03": 1, "M05": 2, "M07": 7}[candidate_id]
    return score, time.perf_counter() - started, fit_count


def _evaluate(score: np.ndarray, ids: list[str], action: np.ndarray,
              reward: np.ndarray, mu0: np.ndarray, mu1: np.ndarray,
              propensity: float) -> dict:
    allocated = allocate_batch(ids, score, fraction=CAP, require_positive=True)
    selected = allocated.frame.selected.to_numpy(dtype=bool)
    logged = np.where(action == 1, "contact", "hold")
    design = pd.DataFrame({"hold": np.full(len(ids), 1 - propensity),
                           "contact": np.full(len(ids), propensity)})
    nuisance = pd.DataFrame({"hold": mu0, "contact": mu1})
    dr = dr_action_scores(reward, logged, design, nuisance)
    no_contact = float(dr.hold.mean())
    policy = float(np.where(selected, dr.contact, dr.hold).mean())
    return {"incremental_per_1000": 1000 * (policy - no_contact),
            "policy_conversion_per_1000": 1000 * policy,
            "no_contact_conversion_per_1000": 1000 * no_contact,
            "selected": int(selected.sum()), "capacity": int(allocated.capacity),
            "selected_id_set": set(np.asarray(ids)[selected])}


def _one_domain(domain: str, data: dict) -> dict:
    x, a, y, ids, e = (data[k] for k in ("features", "action", "reward", "ids", "propensity"))
    checks = _validate(x, a, y, ids, data["forbidden"])
    outer = _folds(a, y, SEED)
    result = {"domain": domain, "evidence_role": ("primary_development" if domain == "hillstrom_mens"
                                                   else "sensitivity_development" if domain == "hillstrom_womens"
                                                   else "exploratory_assumed_propensity"),
              "checks": checks, "propensity": e,
              "propensity_note": data["propensity_note"], "roles": data["roles"],
              "raw_sha256": data["raw_sha256"], "development_id_sha256": data["split_id_sha256"],
              "folds": [], "failures": []}
    for outer_i, (train_idx, eval_idx) in enumerate(outer):
        began = time.perf_counter()
        inner = _folds(a[train_idx], y[train_idx], SEED + 100 + outer_i)
        inner_values = {k: [] for k in SELECTABLE}
        inner_cost = {k: {"fits": 0, "fit_seconds": 0.0} for k in SELECTABLE}
        for inner_i, (it, iv) in enumerate(inner):
            train = train_idx[it]
            valid = train_idx[iv]
            mu0, mu1 = _fold_nuisance(x.iloc[train], a[train], y[train], x.iloc[valid], SEED + 200 + outer_i * 10 + inner_i)
            for candidate_id in SELECTABLE:
                try:
                    scores, seconds, count = _fit_score(candidate_id, x.iloc[train], a[train], y[train], x.iloc[valid], e, SEED + 300 + outer_i * 10 + inner_i)
                    value = _evaluate(scores, [ids[j] for j in valid], a[valid], y[valid], mu0, mu1, e)
                    inner_values[candidate_id].append(value["incremental_per_1000"])
                    inner_cost[candidate_id]["fits"] += count
                    inner_cost[candidate_id]["fit_seconds"] += seconds
                except Exception as exc:  # every failed cell remains visible
                    result["failures"].append({"outer": outer_i, "inner": inner_i, "candidate": candidate_id,
                                               "error": f"{type(exc).__name__}: {exc}"})
        eligible = [k for k in SELECTABLE if len(inner_values[k]) == FOLDS]
        winner = max(eligible, key=lambda k: (float(np.mean(inner_values[k])), -SELECTABLE.index(k))) if eligible else None
        mu0, mu1 = _fold_nuisance(x.iloc[train_idx], a[train_idx], y[train_idx], x.iloc[eval_idx], SEED + 400 + outer_i)
        outer_rows = {}
        selected_sets = {}
        for candidate_id in CANDIDATES:
            try:
                scores, seconds, count = _fit_score(candidate_id, x.iloc[train_idx], a[train_idx], y[train_idx], x.iloc[eval_idx], e, SEED + 500 + outer_i)
                value = _evaluate(scores, [ids[j] for j in eval_idx], a[eval_idx], y[eval_idx], mu0, mu1, e)
                selected_sets[candidate_id] = value.pop("selected_id_set")
                outer_rows[candidate_id] = {**value, "fit_seconds": seconds, "internal_fits": count,
                                             "status": "COMPLETE"}
            except Exception as exc:
                outer_rows[candidate_id] = {"status": "FIT_FAILED", "error": f"{type(exc).__name__}: {exc}"}
                result["failures"].append({"outer": outer_i, "candidate": candidate_id,
                                           "error": outer_rows[candidate_id]["error"]})
        selected = outer_rows.get(winner, {}) if winner else {}
        baseline = outer_rows["M01"]
        delta = (selected["incremental_per_1000"] - baseline["incremental_per_1000"]
                 if selected.get("status") == baseline.get("status") == "COMPLETE" else None)
        disagreement = (len(selected_sets[winner] ^ selected_sets["M01"]) / len(eval_idx)
                        if winner in selected_sets and "M01" in selected_sets else None)
        result["folds"].append({"outer": outer_i, "n_train": len(train_idx), "n_eval": len(eval_idx),
                                "train_events_by_arm": {str(k): int(y[train_idx][a[train_idx] == k].sum()) for k in (0, 1)},
                                "eval_events_by_arm": {str(k): int(y[eval_idx][a[eval_idx] == k].sum()) for k in (0, 1)},
                                "inner_values_per_1000": inner_values, "inner_cost": inner_cost,
                                "inner_selected": winner, "outer_values": outer_rows,
                                "selected_delta_vs_m01_per_1000": delta,
                                "disagreement_fraction": disagreement,
                                "elapsed_seconds": time.perf_counter() - began})
    deltas = [f["selected_delta_vs_m01_per_1000"] for f in result["folds"]]
    complete = len(deltas) == FOLDS and all(v is not None for v in deltas)
    result["status"] = "COMPLETE_DEVELOPMENT" if complete else "INCOMPLETE"
    result["mean_delta_per_1000"] = float(np.mean(deltas)) if complete else None
    result["fold_range_per_1000"] = [float(min(deltas)), float(max(deltas))] if complete else None
    result["selected_recipes"] = [f["inner_selected"] for f in result["folds"]]
    result["planning_margin_per_1000"] = MARGIN_PER_1000
    result["development_priority"] = ("FURTHER_STUDY_ONLY" if complete and result["mean_delta_per_1000"] > MARGIN_PER_1000
                                      and len(set(result["selected_recipes"])) == 1 else "RETAIN_M01_FOR_SCOPE")
    if domain == "lenta_sms":
        result["development_priority"] = "EXPLORATORY_ONLY_ASSUMED_PROPENSITY"
    return result


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dry-run", "run"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    started = time.perf_counter()
    domains = ("hillstrom_mens", "hillstrom_womens", "lenta_sms")
    manifest = {"protocol": "R4_learner_v1_amendment_1", "command": args.command,
                "created_utc": datetime.now(UTC).isoformat(), "seed": SEED,
                "folds": {"outer": FOLDS, "inner": FOLDS}, "capacity_fraction": CAP,
                "candidates": {"fixed": "M01", "inner_select": list(SELECTABLE)},
                "margin_per_1000": MARGIN_PER_1000, "lenta_subsample_rows": LENTA_ROWS,
                "lenta_subsample_seed": LENTA_SAMPLE_SEED,
                "source_sha256": sha(Path(__file__)), "domains": {},
                "confirmation_labels_accessed": False,
                "holdout_limitation": "Raw CSV parser loads full files; holdout exclusion is procedural, not cryptographic.",
                "evidence_scope": "inspected public development data; Lenta exploratory with assumed propensity; no domain pooling, independent confirmation or telecom uplift/ROI"}
    for domain in domains:
        data = load_domain(args.root, domain, outcomes=args.command == "run")
        manifest["domains"][domain] = {"evidence_role": ("primary_development" if domain == "hillstrom_mens"
                                                    else "sensitivity_development" if domain == "hillstrom_womens"
                                                    else "exploratory_assumed_propensity"),
                                        "n_development": len(data["features"]),
                                        "roles": data["roles"], "raw_sha256": data["raw_sha256"],
                                        "development_id_sha256": data["split_id_sha256"],
                                        "features": list(data["features"].columns),
                                        "propensity": data["propensity"],
                                        "propensity_note": data["propensity_note"]}
        if args.command == "run":
            manifest["domains"][domain]["result_path"] = f"{domain}.json"
    manifest["elapsed_seconds"] = time.perf_counter() - started
    _write(args.output / "RUN_MANIFEST.json", manifest)
    if args.command == "dry-run":
        print(args.output / "RUN_MANIFEST.json")
        return 0
    for domain in domains:
        data = load_domain(args.root, domain, outcomes=True)
        outcome = _one_domain(domain, data)
        _write(args.output / f"{domain}.json", outcome)
        print(f"{domain}: {outcome['status']} mean delta {outcome['mean_delta_per_1000']} per 1000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
