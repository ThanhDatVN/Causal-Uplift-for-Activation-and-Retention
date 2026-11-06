"""Assignment-integrity diagnostics for a pooled campaign dataset (session 3).

Finding F01 of the V3 review showed that two Orange covariates are strongly
associated with the treatment indicator, and named the test that was missing:
the dataset paper checked treatment predictability with Hamming loss at a 0.5
threshold, which cannot detect dependence when treatment is the majority class
in every subgroup.  This module runs the stronger check --- cross-fitted
out-of-fold ROC-AUC and log-loss for predicting treatment from pre-treatment
covariates, with a permutation test for the null of no dependence --- and
reports the positivity diagnostics that follow from the fitted ``e(X)``.

What a rejection here does and does not mean:

* It **does** mean a constant propensity taken from the observed treatment share
  is not a design probability, and that inverse-probability weights built from
  it are not justified by randomization alone.
* It **does not** identify which mechanism produced the dependence.  Without
  campaign and customer identifiers, campaign-level variation in treatment rates
  across different populations, post-randomization preselection, a covariate
  that is not truly pre-treatment, and non-uniform assignment all produce the
  same pooled signature.  Rows are also not independent if customers repeat, so
  the permutation null is a pooled-IID null, not the design's own null.

The honest consequence is the one the plan already anticipated: keep the dataset
as a conditional benchmark and a subject for sensitivity analysis, and do not
promote a causal claim from it.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from .uplift import ModelKind, make_outcome_model

__all__ = ["audit_assignment", "cross_fitted_propensity", "main"]

#: Minimum action propensity thresholds screened in E21.
SUPPORT_THRESHOLDS: tuple[float, ...] = (0.025, 0.05, 0.10)


def cross_fitted_propensity(
    features: pd.DataFrame,
    treatment: np.ndarray,
    *,
    folds: int = 3,
    seed: int = 20260920,
    kind: ModelKind = "logistic",
) -> np.ndarray:
    """Out-of-fold ``P(T = 1 | X)``.

    Cross-fitting matters here: an in-sample fit would show apparent
    predictability for any flexible model, including under perfect
    randomization.
    """

    treatment = np.asarray(treatment, dtype=int)
    scores = np.zeros(len(features), dtype=float)
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for index, (train, valid) in enumerate(splitter.split(features, treatment)):
        model = make_outcome_model(kind, features, seed=seed + 10 * index)
        model.fit(features.iloc[train], treatment[train])
        scores[valid] = model.predict_proba(features.iloc[valid])[:, 1]
    return scores


def _effective_sample_size(treatment: np.ndarray, propensity: np.ndarray) -> float:
    e = np.clip(propensity, 1e-6, 1 - 1e-6)
    weights = np.where(treatment == 1, 1.0 / e, 1.0 / (1.0 - e))
    return float(weights.sum() ** 2 / np.square(weights).sum())


def _support_report(treatment: np.ndarray, propensity: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    for threshold in SUPPORT_THRESHOLDS:
        # A unit lacks support for the arm it did not receive when the estimated
        # probability of that arm falls below the threshold.
        control_unsupported = (treatment == 0) & (1.0 - propensity < threshold)
        treated_unsupported = (treatment == 1) & (propensity < threshold)
        outside = control_unsupported | treated_unsupported
        rows.append(
            {
                "min_action_propensity": threshold,
                "n_outside_support": int(outside.sum()),
                "share_outside_support": float(outside.mean()),
            }
        )
    return rows


def audit_assignment(
    features: pd.DataFrame,
    treatment: np.ndarray,
    *,
    folds: int = 3,
    permutations: int = 100,
    seed: int = 20260920,
    kind: ModelKind = "logistic",
) -> dict[str, Any]:
    """Cross-fitted treatment predictability with a permutation null.

    Each permutation refits the whole cross-fitted pipeline on shuffled
    treatment labels, so the null distribution reflects the same estimator and
    the same amount of fitting flexibility as the observed statistic.
    """

    treatment = np.asarray(treatment, dtype=int)
    if set(np.unique(treatment)) - {0, 1}:
        raise ValueError("treatment must be binary 0/1")
    if len(features) != len(treatment):
        raise ValueError("features and treatment must have the same length")

    share = float(treatment.mean())
    started = time.perf_counter()
    propensity = cross_fitted_propensity(features, treatment, folds=folds, seed=seed, kind=kind)
    fit_seconds = time.perf_counter() - started

    observed_auc = float(roc_auc_score(treatment, propensity))
    observed_log_loss = float(log_loss(treatment, propensity))
    constant = np.full(len(treatment), share)
    constant_log_loss = float(log_loss(treatment, constant))
    constant_brier = float(brier_score_loss(treatment, constant))
    observed_brier = float(brier_score_loss(treatment, propensity))

    rng = np.random.default_rng(seed)
    null_aucs: list[float] = []
    permutation_started = time.perf_counter()
    for index in range(permutations):
        shuffled = rng.permutation(treatment)
        null_scores = cross_fitted_propensity(
            features, shuffled, folds=folds, seed=seed + 1000 + index, kind=kind
        )
        null_aucs.append(float(roc_auc_score(shuffled, null_scores)))
    permutation_seconds = time.perf_counter() - permutation_started

    null_array = np.asarray(null_aucs, dtype=float)
    exceedances = int((null_array >= observed_auc).sum()) if permutations else 0
    # Add-one p-value: valid for a finite permutation set and never reports zero.
    p_value = (exceedances + 1) / (permutations + 1) if permutations else float("nan")

    return {
        "n_rows": len(treatment),
        "n_features": int(features.shape[1]),
        "treatment_share": share,
        "model_kind": kind,
        "folds": folds,
        "seed": seed,
        "treatment_predictability": {
            "oof_roc_auc": observed_auc,
            "oof_log_loss": observed_log_loss,
            "constant_propensity_log_loss": constant_log_loss,
            "log_loss_improvement": constant_log_loss - observed_log_loss,
            "oof_brier": observed_brier,
            "constant_propensity_brier": constant_brier,
            "brier_skill_vs_constant": (
                1.0 - observed_brier / constant_brier if constant_brier else float("nan")
            ),
        },
        "permutation_test": {
            "permutations": permutations,
            "null_auc_mean": float(null_array.mean()) if permutations else float("nan"),
            "null_auc_sd": float(null_array.std(ddof=1)) if permutations > 1 else float("nan"),
            "null_auc_q95": float(np.quantile(null_array, 0.95)) if permutations else float("nan"),
            "n_null_at_or_above_observed": exceedances,
            "p_value_add_one": p_value,
            "null_hypothesis": (
                "treatment labels are exchangeable across rows given the pooled frame"
            ),
        },
        "estimated_propensity": {
            "min": float(propensity.min()),
            "q01": float(np.quantile(propensity, 0.01)),
            "q05": float(np.quantile(propensity, 0.05)),
            "median": float(np.median(propensity)),
            "q95": float(np.quantile(propensity, 0.95)),
            "q99": float(np.quantile(propensity, 0.99)),
            "max": float(propensity.max()),
            "support": _support_report(treatment, propensity),
            "effective_sample_size_estimated_e": _effective_sample_size(treatment, propensity),
            "effective_sample_size_constant_e": _effective_sample_size(treatment, constant),
        },
        "runtime": {
            "cross_fit_seconds": round(fit_seconds, 2),
            "permutation_seconds": round(permutation_seconds, 2),
            "seconds_per_permutation": (
                round(permutation_seconds / permutations, 3) if permutations else None
            ),
        },
        "interpretation_limits": [
            "Diagnostic on a pooled frame. Campaign and customer identifiers are absent, "
            "so campaign-level variation in treatment rates, post-randomization "
            "preselection, a non-pre-treatment covariate and non-uniform assignment are "
            "not distinguishable here.",
            "The permutation null assumes exchangeable rows. Repeated customers would "
            "break it, and the file does not let that be checked.",
            "An estimated propensity strictly inside (0, 1) does not demonstrate "
            "positivity or ignorability; it is a fitted value, not a design probability.",
            "Rejecting the pooled-IID null does not certify any particular alternative, "
            "and does not show the dataset paper's per-campaign randomization was wrong.",
        ],
    }


#: Below this ratio of effective to nominal sample size, reweighting by the
#: estimated propensity destroys more precision than it could repair.
_ESS_COLLAPSE_RATIO = 0.10


def _ess_verdict(report: dict[str, Any]) -> dict[str, Any]:
    """Whether estimating ``e(X)`` is even a usable repair on this data."""

    propensity = report["estimated_propensity"]
    estimated = propensity["effective_sample_size_estimated_e"]
    constant = propensity["effective_sample_size_constant_e"]
    ratio = estimated / constant if constant else float("nan")
    collapsed = bool(ratio < _ESS_COLLAPSE_RATIO)
    return {
        "ess_ratio_estimated_over_constant": ratio,
        "ess_collapsed": collapsed,
        "reweighting_is_a_usable_repair": not collapsed,
        "note": (
            f"Reweighting by the estimated propensity leaves an effective sample size of "
            f"{estimated:,.0f} out of {constant:,.0f}. A handful of extreme weights would "
            "carry the whole estimate, so estimating e(X) is not a repair for the "
            "identification problem here; it relocates it into the variance."
            if collapsed
            else "Reweighting by the estimated propensity retains a usable effective "
            "sample size, but positivity and ignorability remain assumptions."
        ),
    }


def _verdict(report: dict[str, Any], *, alpha: float = 0.05) -> dict[str, Any]:
    p_value = report["permutation_test"]["p_value_add_one"]
    auc = report["treatment_predictability"]["oof_roc_auc"]
    rejected = bool(p_value <= alpha)
    return {
        "alpha": alpha,
        "pooled_iid_exchangeability_rejected": rejected,
        "constant_propensity_justified_by_design": not rejected,
        "reweighting": _ess_verdict(report),
        "evidence_state": "EXPLORATORY",
        "decision": (
            "Keep the dataset as a conditional benchmark. Do not promote a causal claim "
            "from a constant propensity; report IPW and DR results as sensitivity "
            "analyses under stated identification assumptions."
            if rejected
            else "No pooled dependence detected at this sample size; a constant "
            "propensity remains an assumption, not a verified design probability."
        ),
        "headline": (f"out-of-fold treatment ROC-AUC {auc:.4f}, permutation p = {p_value:.4g}"),
    }


def _render_markdown(report: dict[str, Any], verdict: dict[str, Any]) -> str:
    predictability = report["treatment_predictability"]
    permutation = report["permutation_test"]
    propensity = report["estimated_propensity"]
    lines = [
        "# Orange assignment-integrity audit",
        "",
        "Resolves, within the sources that can be checked from the repository, the "
        "question left open by finding F01 of the V3 review: is the pooled treatment "
        "indicator predictable from the supplied pre-treatment covariates?",
        "",
        f"- rows: {report['n_rows']:,}, features: {report['n_features']}, "
        f"treatment share: {report['treatment_share']:.4%}",
        f"- cross-fitted out-of-fold ROC-AUC: **{predictability['oof_roc_auc']:.4f}**",
        f"- out-of-fold log loss {predictability['oof_log_loss']:.4f} versus "
        f"{predictability['constant_propensity_log_loss']:.4f} for a constant propensity "
        f"(improvement {predictability['log_loss_improvement']:.4f})",
        f"- Brier skill against the constant propensity: "
        f"{predictability['brier_skill_vs_constant']:.4f}",
        f"- permutation null ({permutation['permutations']} refits): mean AUC "
        f"{permutation['null_auc_mean']:.4f}, 95th percentile "
        f"{permutation['null_auc_q95']:.4f}",
        f"- permutations at or above the observed AUC: "
        f"{permutation['n_null_at_or_above_observed']}; add-one p-value "
        f"**{permutation['p_value_add_one']:.4g}**",
        "",
        "## Positivity and support",
        "",
        f"Estimated `e(X)` spans [{propensity['min']:.4f}, {propensity['max']:.4f}] "
        f"with median {propensity['median']:.4f}.",
        "",
        "| Minimum action propensity | Units outside support | Share |",
        "|---|---:|---:|",
    ]
    for row in propensity["support"]:
        lines.append(
            f"| {row['min_action_propensity']:.3f} | {row['n_outside_support']:,} "
            f"| {row['share_outside_support']:.2%} |"
        )
    lines.extend(
        [
            "",
            f"Inverse-probability effective sample size: "
            f"{propensity['effective_sample_size_estimated_e']:,.0f} with the estimated "
            f"propensity against {propensity['effective_sample_size_constant_e']:,.0f} with "
            "the constant one. Effective sample size is not a substitute for the number of "
            "churn events or the number of independent clusters.",
            "",
            f"**{verdict['reweighting']['note']}**",
            "",
            "## Verdict",
            "",
            f"- {verdict['headline']}",
            f"- pooled-IID exchangeability rejected at alpha {verdict['alpha']}: "
            f"**{verdict['pooled_iid_exchangeability_rejected']}**",
            f"- evidence state: {verdict['evidence_state']}",
            f"- decision: {verdict['decision']}",
            "",
            "## What this cannot settle",
            "",
        ]
    )
    lines.extend(f"- {limit}" for limit in report["interpretation_limits"])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument(
        "--permutations",
        type=int,
        default=100,
        help="each permutation refits the full cross-fitted pipeline",
    )
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--model", default="logistic", choices=("logistic", "hgb"))
    parser.add_argument("--output-dir", default="reports/v4")
    parser.add_argument(
        "--dataset",
        default="orange",
        choices=("orange", "hillstrom"),
        help="which campaign log to audit; the audit itself is the same either way",
    )
    args = parser.parse_args(argv)

    if args.dataset == "orange":
        from .orange_data import FEATURE_COLUMNS, TREATMENT_COLUMN, load_orange

        frame = load_orange()
        features = frame.loc[:, list(FEATURE_COLUMNS)]
        treatment = frame[TREATMENT_COLUMN].to_numpy(dtype=int)
        label = "OpenML 45580 / Orange Belgium"
        stem = "ORANGE_ASSIGNMENT_AUDIT.md"
    else:
        from .hillstrom_data import (
            CONTROL_ARM,
            feature_frame,
            load_hillstrom,
        )
        from .hillstrom_data import (
            TREATMENT_COLUMN as ARM_COLUMN,
        )

        # Audit the declared primary contrast only: a three-arm log would make
        # "treatment predictability" mean something different.
        frame = load_hillstrom()
        primary = frame.loc[frame[ARM_COLUMN].isin(["Mens E-Mail", CONTROL_ARM])]
        primary = primary.reset_index(drop=True)
        features = feature_frame(primary)
        treatment = (primary[ARM_COLUMN] == "Mens E-Mail").to_numpy(dtype=int)
        label = "Hillstrom MineThatData, Mens E-Mail versus No E-Mail"
        stem = "HILLSTROM_ASSIGNMENT_AUDIT.md"

    report = audit_assignment(
        features,
        treatment,
        folds=args.folds,
        permutations=args.permutations,
        seed=args.seed,
        kind=args.model,
    )
    report["dataset"] = label
    verdict = _verdict(report)
    report["verdict"] = verdict

    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.dataset == "orange" else f"_{args.dataset}"
    (destination / f"assignment_audit{suffix}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (destination / stem).write_text(_render_markdown(report, verdict), encoding="utf-8")

    print(verdict["headline"])
    print(f"pooled-IID exchangeability rejected: {verdict['pooled_iid_exchangeability_rejected']}")
    print(verdict["reweighting"]["note"])
    print(verdict["decision"])
    print(f"Reports written to {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
