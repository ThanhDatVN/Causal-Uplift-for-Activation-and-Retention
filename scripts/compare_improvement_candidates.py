"""So sánh candidate OOF, dựng ensemble và chốt shortlist cho retrospective confirmation.

Script chỉ đọc prediction out-of-fold đã lưu; nó không fit lại model gốc. Ensemble
weights có weight-stage holdout riêng, nhưng base model không được refit theo outer
fold. Vì vậy đây là OOS cho bước học weights, không phải fully nested stacking.

Confirmation Sprint 2 không được đọc ở bước này.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.ensemble import (
    causal_q_aggregation,
    cross_fitted_weight_ensemble_score,
    doubly_robust_losses,
    rank_average_score,
)
from src.evaluation import auuc_score, qini_score
from src.paths import REPO_ROOT
from src.policy_evaluation import (
    dr_policy_value_curve,
    paired_policy_area_bootstrap,
    policy_area,
    policy_area_difference_summary,
)
from src.ranking_metrics import (
    paired_difference_summary,
    paired_rate_bootstrap,
    rate_score,
)

PROTOCOL_PATH = REPO_ROOT / "configs" / "sprint3_improvement_protocol.json"
RESERVED_KEYS = {
    "source_index",
    "treatment",
    "outcome",
    "dr_signal",
    "adjusted_signal",
    "mu0",
    "mu1",
}
COMPARABILITY_FIELDS = (
    "manifest_schema_version",
    "protocol_id",
    "protocol_sha256",
    "stage",
    "outcome",
    "development_index_sha256",
    "pool_fraction",
    "pool_seed",
    "model_seed",
    "n_folds",
    "propensity",
    "budget_grid",
)
STRICT_MANIFEST_SCHEMA_VERSION = 2


def _score_names(data: dict) -> set[str]:
    scores = data.get("scores")
    if isinstance(scores, dict):
        return set(scores)
    return set(data) - RESERVED_KEYS


def validate_run_manifest(
    manifest: dict,
    data: dict,
    *,
    allow_legacy_manifests: bool = False,
) -> str:
    """Validate one manifest and return ``strict`` or ``legacy`` evidence mode."""
    version = manifest.get("manifest_schema_version")
    if version is None:
        if not allow_legacy_manifests:
            raise ValueError(
                "Legacy run manifest bi tu choi; chi dung "
                "--allow-legacy-manifests cho diagnostic khong advancement"
            )
        return "legacy"
    if version != STRICT_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "Run-dir khong dung manifest schema bat buoc: "
            f"expected={STRICT_MANIFEST_SCHEMA_VERSION}, actual={version!r}"
        )

    required = (*COMPARABILITY_FIELDS, "candidate_config_hashes")
    missing = [field for field in required if manifest.get(field) is None]
    if missing:
        raise ValueError(f"Run-dir thieu comparability provenance: {missing}")

    config_hashes = manifest["candidate_config_hashes"]
    if not isinstance(config_hashes, dict):
        raise ValueError("candidate_config_hashes trong manifest phai la object")
    invalid_hashes = [
        name
        for name in sorted(_score_names(data))
        if not isinstance(config_hashes.get(name), str) or not config_hashes[name]
    ]
    if invalid_hashes:
        raise ValueError(
            "Run-dir thieu candidate config hash cho OOF scores: "
            f"{invalid_hashes}"
        )
    return "strict"


def assert_manifest_matches_protocol(
    manifest: dict,
    protocol: dict,
    protocol_sha256: str,
) -> None:
    """Bind a strict run manifest to the exact CLI protocol snapshot."""
    expected = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha256,
        "n_folds": int(protocol["cross_fitting"]["n_folds"]),
        "propensity": float(protocol["estimand"]["propensity_value"]),
        "budget_grid": [
            float(value) for value in protocol["metrics"]["primary_budget_grid"]
        ],
    }
    mismatches = {
        field: (manifest.get(field), expected_value)
        for field, expected_value in expected.items()
        if manifest.get(field) != expected_value
    }
    if mismatches:
        raise ValueError(
            "Run-dir khong khop CLI protocol snapshot: "
            f"{mismatches}"
        )


def load_oof(run_dir: Path) -> dict:
    payload = np.load(run_dir / "oof_scores.npz")
    scores = {
        key: payload[key].astype("float64")
        for key in payload.files
        if key not in RESERVED_KEYS
    }
    return {
        "scores": scores,
        "dr_signal": payload["dr_signal"].astype("float64"),
        "adjusted_signal": payload["adjusted_signal"].astype("float64"),
        "treatment": payload["treatment"].astype("float64"),
        "outcome": payload["outcome"].astype("float64"),
        "source_index": payload["source_index"],
    }


def metric_row(
    name: str,
    score: np.ndarray,
    data: dict,
    budgets: np.ndarray,
    is_cate_scale: bool,
) -> dict:
    curve = dr_policy_value_curve(data["dr_signal"], score, budgets=budgets)
    adjusted = dr_policy_value_curve(
        data["adjusted_signal"],
        score,
        budgets=budgets,
    )
    return {
        "model": name,
        "policy_area_dr": policy_area(budgets, curve["gross_value_per_customer"]),
        "policy_area_dr_adjusted": policy_area(
            budgets,
            adjusted["gross_value_per_customer"],
        ),
        "autoc_dr": rate_score(data["dr_signal"], score, weighting="autoc"),
        "autoc_dr_adjusted": rate_score(
            data["adjusted_signal"],
            score,
            weighting="autoc",
        ),
        "rate_qini_dr": rate_score(data["dr_signal"], score, weighting="qini"),
        "qini_score": qini_score(data["outcome"], data["treatment"], score),
        "auuc_score": auuc_score(data["outcome"], data["treatment"], score),
        "is_cate_scale": is_cate_scale,
    }


def assert_comparable_runs(
    reference_manifest: dict,
    current_manifest: dict,
    reference_data: dict,
    current_data: dict,
    *,
    allow_legacy_manifests: bool = False,
) -> None:
    """Reject cross-seed aggregation if the underlying OOF population changed."""
    modes = (
        validate_run_manifest(
            reference_manifest,
            reference_data,
            allow_legacy_manifests=allow_legacy_manifests,
        ),
        validate_run_manifest(
            current_manifest,
            current_data,
            allow_legacy_manifests=allow_legacy_manifests,
        ),
    )
    if modes[0] != modes[1]:
        raise ValueError(
            "Run-dir khong cung manifest schema mode: "
            f"reference={modes[0]!r}, current={modes[1]!r}"
        )

    mismatches = {
        field: (reference_manifest.get(field), current_manifest.get(field))
        for field in COMPARABILITY_FIELDS
        if reference_manifest.get(field) != current_manifest.get(field)
    }
    if mismatches:
        raise ValueError(f"Run-dir khong cung comparison contract: {mismatches}")

    if modes[0] == "strict":
        reference_hashes = reference_manifest["candidate_config_hashes"]
        current_hashes = current_manifest["candidate_config_hashes"]
        common_candidates = _score_names(reference_data) & _score_names(current_data)
        config_mismatches = {
            candidate: (reference_hashes[candidate], current_hashes[candidate])
            for candidate in sorted(common_candidates)
            if reference_hashes[candidate] != current_hashes[candidate]
        }
        if config_mismatches:
            raise ValueError(
                "Run-dir dung cung ten candidate nhung khac config hash: "
                f"{config_mismatches}"
            )

    for field in ("source_index", "treatment", "outcome"):
        if not np.array_equal(reference_data[field], current_data[field]):
            raise ValueError(
                f"Run-dir khong co cung {field} OOF theo dung thu tu"
            )


def assert_unique_model_fold_seed(ranking: pd.DataFrame) -> None:
    """Reject duplicate evidence cells instead of choosing or averaging one."""
    duplicates = ranking.duplicated(["model", "fold_seed"], keep=False)
    if duplicates.any():
        duplicate_keys = (
            ranking.loc[duplicates, ["model", "fold_seed"]]
            .drop_duplicates()
            .to_dict("records")
        )
        raise ValueError(
            "Ranking co duplicate model/fold_seed; tu choi chon dong tuy y: "
            f"{duplicate_keys}"
        )


def advancement_table(
    ranking: pd.DataFrame,
    *,
    reference: str,
    require_all_fold_seeds: bool,
    required_fold_seeds: tuple[int, ...] | list[int] | None = None,
) -> pd.DataFrame:
    """Apply the preregistered point-estimate gate without reading confirmation.

    A mean across seeds can hide a regression on one fold assignment.  The data
    optimization protocol therefore requires the challenger and reference to have
    exactly the registered fold seeds, with a win on every seed.  This helper keeps
    that rule explicit and independently testable instead of treating whichever
    seeds happened to be supplied as the complete experiment.
    """
    assert_unique_model_fold_seed(ranking)

    required_seed_set: set[int] | None = None
    if require_all_fold_seeds:
        if required_fold_seeds is None:
            raise ValueError(
                "required_fold_seeds bat buoc khi require_all_fold_seeds=True"
            )
        normalized = tuple(int(seed) for seed in required_fold_seeds)
        required_seed_set = set(normalized)
        if not required_seed_set:
            raise ValueError("required_fold_seeds khong duoc rong")
        if len(required_seed_set) != len(normalized):
            raise ValueError("required_fold_seeds khong duoc trung lap")

    reference_rows = (
        ranking.loc[ranking["model"] == reference, ["fold_seed", "policy_area_dr"]]
        .set_index("fold_seed")["policy_area_dr"]
    )
    if reference_rows.empty:
        raise ValueError(f"Khong tim thay reference {reference!r} trong ranking")

    rows: list[dict[str, object]] = []
    for model, model_rows in ranking.groupby("model", sort=False):
        if model == reference:
            continue
        observed = (
            model_rows[["fold_seed", "policy_area_dr"]]
            .set_index("fold_seed")["policy_area_dr"]
        )
        common = sorted(set(reference_rows.index) & set(observed.index))
        deltas = [float(observed.loc[seed] - reference_rows.loc[seed]) for seed in common]
        if require_all_fold_seeds:
            assert required_seed_set is not None
            complete = (
                set(reference_rows.index) == required_seed_set
                and set(observed.index) == required_seed_set
            )
            advance = complete and bool(deltas) and all(delta > 0 for delta in deltas)
        else:
            complete = set(common) == set(reference_rows.index)
            advance = bool(deltas) and float(np.mean(deltas)) > 0
        reason = (
            "beats_reference_on_every_fold_seed"
            if advance
            else "missing_fold_seed"
            if not complete
            else "does_not_beat_reference_on_every_fold_seed"
        )
        rows.append(
            {
                "model": model,
                "reference": reference,
                "fold_seeds": ";".join(str(seed) for seed in common),
                "n_fold_seeds": len(common),
                "min_policy_area_delta": min(deltas) if deltas else np.nan,
                "mean_policy_area_delta": float(np.mean(deltas)) if deltas else np.nan,
                "advance": advance,
                "reason": reason,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["advance", "mean_policy_area_delta"],
        ascending=[False, False],
    )


def registered_fold_seeds(protocol: dict) -> tuple[int, ...]:
    """Resolve the exact advancement seeds declared by a protocol.

    New protocols may declare ``selection_rule.required_fold_seeds`` directly.
    Existing protocols derive the same contract from their primary and secondary
    cross-fitting seeds.
    """
    selection_rule = protocol.get("selection_rule", {})
    configured = selection_rule.get("required_fold_seeds")
    if configured is None:
        cross_fitting = protocol.get("cross_fitting", {})
        configured = [
            cross_fitting.get("primary_fold_seed"),
            cross_fitting.get("secondary_fold_seed"),
        ]
    if not isinstance(configured, (list, tuple)):
        raise ValueError("required_fold_seeds trong protocol phai la danh sach")
    seeds = tuple(int(seed) for seed in configured if seed is not None)
    if not seeds:
        raise ValueError("Protocol khong khai bao fold seed bat buoc")
    if len(set(seeds)) != len(seeds):
        raise ValueError("Protocol khai bao fold seed bat buoc bi trung lap")
    return seeds


def restrict_advancement_to_registered(
    decisions: pd.DataFrame,
    registered_candidates: set[str],
) -> pd.DataFrame:
    """Keep diagnostic ensembles in the report but out of the advancement gate."""
    restricted = decisions.copy()
    diagnostic = ~restricted["model"].isin(registered_candidates)
    restricted.loc[diagnostic, "advance"] = False
    restricted.loc[diagnostic, "reason"] = "diagnostic_ensemble_not_eligible"
    return restricted


def block_legacy_advancement(decisions: pd.DataFrame) -> pd.DataFrame:
    """Keep legacy diagnostics visible while making them advancement-ineligible."""
    blocked = decisions.copy()
    blocked["advance"] = False
    blocked["reason"] = "legacy_manifest_not_eligible"
    return blocked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-dir",
        type=Path,
        action="append",
        required=True,
        help="Thư mục kết quả OOF; lặp lại tham số để so sánh nhiều fold seed.",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROTOCOL_PATH,
        help="Protocol đã dùng để sinh các OOF run-dir.",
    )
    parser.add_argument("--n-boot", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shortlist-size", type=int, default=5)
    parser.add_argument(
        "--no-ensembles",
        action="store_true",
        help="Skip diagnostic ensembles, e.g. for a two-model finalist comparison.",
    )
    parser.add_argument(
        "--allow-legacy-manifests",
        action="store_true",
        help=(
            "Allow legacy manifests for diagnostic ranking only. Legacy evidence "
            "can never advance a challenger."
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    protocol_bytes = args.protocol.read_bytes()
    protocol = json.loads(protocol_bytes.decode("utf-8"))
    protocol_sha256 = hashlib.sha256(protocol_bytes).hexdigest()
    budgets = np.asarray(protocol["metrics"]["primary_budget_grid"], dtype="float64")
    cate_scale = {
        item["name"]: bool(item.get("is_cate_scale", True))
        for item in protocol["candidates"]
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    ensemble_report: dict[str, dict] = {}
    primary_dir = args.run_dir[0]
    reference_manifest: dict | None = None
    reference_data: dict | None = None
    legacy_manifest_mode = False

    for run_dir in args.run_dir:
        data = load_oof(run_dir)
        manifest = json.loads((run_dir / "run_manifest.json").read_text("utf-8"))
        manifest_mode = validate_run_manifest(
            manifest,
            data,
            allow_legacy_manifests=args.allow_legacy_manifests,
        )
        if manifest_mode == "strict":
            assert_manifest_matches_protocol(
                manifest,
                protocol,
                protocol_sha256,
            )
        else:
            legacy_manifest_mode = True
        if reference_manifest is None:
            reference_manifest = manifest
            reference_data = data
        else:
            assert reference_data is not None
            assert_comparable_runs(
                reference_manifest,
                manifest,
                reference_data,
                data,
                allow_legacy_manifests=args.allow_legacy_manifests,
            )
        tag = f"seed{manifest['fold_seed']}"
        print(f"[load] {run_dir} rows={len(data['dr_signal']):,} {tag}", flush=True)

        scores = dict(data["scores"])
        cate_models = {
            name: values
            for name, values in scores.items()
            if cate_scale.get(name, True)
        }
        if not args.no_ensembles and len(cate_models) >= 2:
            for method in ("causal_q_aggregation", "best_single_dr_risk"):
                result = cross_fitted_weight_ensemble_score(
                    cate_models,
                    data["dr_signal"],
                    method=method,
                    n_splits=2,
                    seed=args.seed,
                )
                label = {
                    "causal_q_aggregation": "Ensemble-QAgg",
                    "best_single_dr_risk": "Ensemble-BestSingle",
                }[method]
                scores[label] = result["score"]
                cate_scale[label] = True
                ensemble_report[f"{label}@{tag}"] = {
                    "method": method,
                    "full_sample_weights": result["full_sample_weights"],
                    "fold_weights": result["fold_weights"],
                    "candidate_dr_losses": doubly_robust_losses(
                        cate_models,
                        data["dr_signal"],
                    ),
                    "validation_scope": result["validation_scope"],
                    "nested_base_models": result["nested_base_models"],
                }
        if not args.no_ensembles and len(scores) >= 2:
            rank_pool = {
                name: values
                for name, values in data["scores"].items()
                if name in cate_models or not cate_scale.get(name, True)
            }
            scores["Ensemble-RankAverage"] = rank_average_score(rank_pool)
            cate_scale["Ensemble-RankAverage"] = False
            ensemble_report[f"Ensemble-RankAverage@{tag}"] = {
                "method": "rank_average",
                "members": sorted(rank_pool),
                "note": (
                    "Heuristic thu hang; khong co bao dam ly thuyet cua "
                    "Q-aggregation. Gop duoc ca ranking score."
                ),
            }

        for name, score in scores.items():
            row = metric_row(
                name,
                score,
                data,
                budgets,
                cate_scale.get(name, True),
            )
            row["fold_seed"] = manifest["fold_seed"]
            row["pool_fraction"] = manifest["pool_fraction"]
            row["n_rows"] = len(score)
            all_rows.append(row)

        if run_dir == primary_dir:
            area_bootstrap = paired_policy_area_bootstrap(
                scores,
                data["dr_signal"],
                budgets=budgets,
                n_boot=args.n_boot,
                seed=args.seed,
            )
            rate_bootstrap = paired_rate_bootstrap(
                scores,
                data["dr_signal"],
                n_boot=args.n_boot,
                seed=args.seed,
            )
            comparison_rows = []
            for reference in ("Response", "X-Renormalized"):
                if reference not in scores:
                    continue
                for name in scores:
                    if name == reference:
                        continue
                    area = policy_area_difference_summary(
                        area_bootstrap,
                        name,
                        reference,
                    )
                    rate = paired_difference_summary(rate_bootstrap, name, reference)
                    comparison_rows.append(
                        {
                            "model_a": name,
                            "model_b": reference,
                            "fold_seed": manifest["fold_seed"],
                            "policy_area_difference": area["observed_difference"],
                            "policy_area_ci_low": area["ci_low"],
                            "policy_area_ci_high": area["ci_high"],
                            "policy_area_probability_positive": area[
                                "probability_difference_positive"
                            ],
                            "autoc_difference": rate["observed_difference"],
                            "autoc_ci_low": rate["ci_low"],
                            "autoc_ci_high": rate["ci_high"],
                            "n_boot": args.n_boot,
                        }
                    )
            pd.DataFrame(comparison_rows).to_csv(
                args.output_dir / "paired_comparisons.csv",
                index=False,
            )

    ranking = pd.DataFrame(all_rows)
    assert_unique_model_fold_seed(ranking)
    ranking.to_csv(args.output_dir / "candidate_ranking.csv", index=False)

    # Shortlist lấy trung bình policy_area_dr qua các fold seed đã chạy; model
    # chỉ có kết quả ở một seed vẫn được xét nhưng ghi rõ số seed.
    aggregate = (
        ranking.groupby("model")
        .agg(
            policy_area_dr_mean=("policy_area_dr", "mean"),
            policy_area_dr_min=("policy_area_dr", "min"),
            autoc_dr_mean=("autoc_dr", "mean"),
            qini_mean=("qini_score", "mean"),
            n_seeds=("fold_seed", "nunique"),
        )
        .sort_values("policy_area_dr_mean", ascending=False)
    )
    aggregate.to_csv(args.output_dir / "candidate_aggregate.csv")
    print(aggregate.to_string(), flush=True)

    reference_models = [
        name for name in ("Response", "X-Renormalized") if name in aggregate.index
    ]
    selection_rule = protocol.get("selection_rule", {})
    advance_reference = selection_rule.get("advance_reference")
    require_all_fold_seeds = bool(
        selection_rule.get("advance_all_fold_seeds", False)
    )
    required_fold_seeds = (
        registered_fold_seeds(protocol) if require_all_fold_seeds else None
    )
    if advance_reference:
        decisions = advancement_table(
            ranking,
            reference=str(advance_reference),
            require_all_fold_seeds=require_all_fold_seeds,
            required_fold_seeds=required_fold_seeds,
        )
        if selection_rule.get("advance_registered_candidates_only", False):
            registered = {item["name"] for item in protocol["candidates"]}
            decisions = restrict_advancement_to_registered(decisions, registered)
        if legacy_manifest_mode:
            decisions = block_legacy_advancement(decisions)
        decisions.to_csv(args.output_dir / "advancement_decision.csv", index=False)
        eligible = set(decisions.loc[decisions["advance"], "model"])
        challengers = [
            name
            for name in aggregate.index
            if name not in reference_models and name in eligible
        ][: args.shortlist_size]
    else:
        decisions = None
        challengers = (
            []
            if legacy_manifest_mode
            else [
                name for name in aggregate.index if name not in reference_models
            ][: args.shortlist_size]
        )
    shortlist = reference_models + challengers

    payload = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha256,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_dirs": [str(path) for path in args.run_dir],
        "budget_grid": budgets.tolist(),
        "n_boot": args.n_boot,
        "shortlist": shortlist,
        "reference_models": reference_models,
        "advance_reference": advance_reference,
        "advance_all_fold_seeds": selection_rule.get(
            "advance_all_fold_seeds",
            False,
        ),
        "required_fold_seeds": list(required_fold_seeds or ()),
        "ranking_by_policy_area_dr": aggregate.index.tolist(),
        "ensembles": ensemble_report,
        "ensembles_enabled": not args.no_ensembles,
        "legacy_manifest_mode": legacy_manifest_mode,
        "advancement_eligible": not legacy_manifest_mode,
        "note": (
            "Shortlist duoc chot trước khi doc confirmation. Khong duoc them "
            "candidate sau khi xem ket qua confirmation."
        ),
    }
    (args.output_dir / "shortlist.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=float),
        encoding="utf-8",
    )
    print(f"[write] {args.output_dir}", flush=True)
    print(f"[shortlist] {shortlist}", flush=True)


if __name__ == "__main__":
    main()
