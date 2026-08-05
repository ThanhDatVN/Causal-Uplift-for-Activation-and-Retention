"""Retrospective confirmation và quyết định champion cho Sprint 3.

Chạy đúng một lần sau khi shortlist và code đã khóa. Trình tự:

1. đọc shortlist đã chốt trên development OOF;
2. fit nuisance ``mu0``/``mu1`` trên **toàn bộ** development rồi predict
   confirmation — hai tập rời nhau nên không cần cross-fitting ở bước này;
3. refit từng finalist trên toàn bộ development, predict confirmation;
4. dựng ensemble bằng weights đã học trên development OOF, không học lại;
5. paired bootstrap cho ``policy_area_dr``, AUTOC và Qini so với Response;
6. áp promotion rule đã đăng ký và ghi quyết định kể cả khi không đổi champion.

Confirmation Sprint 2 đã được xem ở Sprint 2 nên mọi kết quả ở đây phải được gọi
là **retrospective confirmation**, không phải prospective test.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from lightgbm import LGBMClassifier

from src.candidates import FitContext, candidate_from_dict, lgbm_params
from src.evaluation import auuc_score, qini_score, uplift_calibration_error
from src.experiment import (
    ResourceMonitor,
    append_registry,
    base_registry_fields,
    build_sprint3_splits,
    config_hash,
)
from src.paths import OUTPUT_DIR, REPO_ROOT
from src.policy import (
    bootstrap_policy_values,
    doubly_robust_effect_signal,
    ipw_effect_signal,
    policy_value_from_signal,
    top_budget_policy,
)
from src.policy_evaluation import (
    doubly_robust_risk,
    dr_policy_value_curve,
    expected_random_policy_value,
    paired_policy_area_bootstrap,
    policy_area,
    policy_area_difference_summary,
    random_topk_sensitivity,
)
from src.ranking_metrics import (
    adjusted_transformed_outcome,
    paired_difference_summary,
    paired_rate_bootstrap,
    rate_score,
)

PROTOCOL_PATH = REPO_ROOT / "configs" / "sprint3_improvement_protocol.json"
RUN_ID = "sprint3-retrospective-confirmation-v1"
CHAMPION_REFERENCE = "Response"


def fit_full_development_nuisance(development, seed: int) -> dict:
    """Một model cho mỗi arm trên toàn bộ development; predict trên confirmation."""
    models = {}
    for arm in (0, 1):
        rows = np.flatnonzero(development.treatment == arm)
        model = LGBMClassifier(**lgbm_params(seed + arm))
        model.fit(development.X[rows], development.outcome[rows])
        models[arm] = model
    return models


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument(
        "--oof-run-dir",
        type=Path,
        required=True,
        help="Thư mục OOF cung cấp ensemble weights đã học trên development.",
    )
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--main-budget", type=float, default=0.10)
    parser.add_argument("--main-cost", type=float, default=0.0005)
    parser.add_argument("--value-per-conversion", type=float, default=1.0)
    parser.add_argument("--costs", default="0,0.00025,0.0005,0.001")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "sprint3")
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    shortlist_payload = json.loads(args.shortlist.read_text(encoding="utf-8"))
    budgets = np.asarray(protocol["metrics"]["primary_budget_grid"], dtype="float64")
    costs = [float(value) for value in args.costs.split(",") if value.strip()]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()

    specs_by_name = {
        item["name"]: candidate_from_dict(item) for item in protocol["candidates"]
    }
    shortlist = list(shortlist_payload["shortlist"])
    base_models = [name for name in shortlist if name in specs_by_name]
    ensemble_names = [name for name in shortlist if name.startswith("Ensemble-")]

    # Một ensemble trong shortlist có thể có member không tự lọt vào shortlist.
    # Member đó vẫn phải được refit, nếu không weights sẽ bị chuẩn hóa lại và
    # ensemble trên confirmation không còn là ensemble đã học trên development.
    for name in ensemble_names:
        for key, entry in shortlist_payload["ensembles"].items():
            if not key.startswith(f"{name}@"):
                continue
            members = (
                entry.get("members")
                if entry["method"] == "rank_average"
                else [
                    member
                    for member, weight in entry.get(
                        "full_sample_weights", {}
                    ).items()
                    if weight > 0
                ]
            )
            for member in members or []:
                if member in specs_by_name and member not in base_models:
                    base_models.append(member)
                    print(
                        f"[shortlist] thêm {member} vì là member của {name}",
                        flush=True,
                    )

    print("[data] building Sprint 3 splits", flush=True)
    splits = build_sprint3_splits()
    development = splits["development"]
    confirmation = splits["confirmation"]
    propensity = float(development.treatment.mean())
    print(
        f"[data] development={len(development):,} confirmation={len(confirmation):,} "
        f"propensity={propensity:.6f}",
        flush=True,
    )

    with ResourceMonitor() as monitor:
        print("[nuisance] fitting mu0/mu1 on full development", flush=True)
        nuisance_models = fit_full_development_nuisance(development, seed=args.seed)
        mu0 = nuisance_models[0].predict_proba(confirmation.X)[:, 1]
        mu1 = nuisance_models[1].predict_proba(confirmation.X)[:, 1]
        del nuisance_models
        dr_signal = doubly_robust_effect_signal(
            confirmation.outcome,
            confirmation.treatment,
            mu0,
            mu1,
            propensity=propensity,
        )
        ipw_signal = ipw_effect_signal(
            confirmation.outcome,
            confirmation.treatment,
            propensity=propensity,
        )
        adjusted_signal = adjusted_transformed_outcome(
            confirmation.outcome,
            confirmation.treatment,
            propensity * mu1 + (1.0 - propensity) * mu0,
            propensity=propensity,
        )
        print(
            f"[nuisance] ate_dr={np.mean(dr_signal):.8f} "
            f"ate_ipw={np.mean(ipw_signal):.8f}",
            flush=True,
        )

        registry_rows: list[dict] = []
        confirmation_scores: dict[str, np.ndarray] = {}
        development_full = FitContext(
            X=development.X,
            treatment=development.treatment,
            outcome=development.outcome,
            propensity=propensity,
            seed=args.seed,
            params={},
        )
        for name in base_models:
            spec = specs_by_name[name]
            print(f"[refit] {name} on full development", flush=True)
            context = FitContext(
                X=development_full.X,
                treatment=development_full.treatment,
                outcome=development_full.outcome,
                propensity=propensity,
                seed=args.seed,
                params=spec.params,
            )
            fit_started = time.perf_counter()
            predict = spec.build(context)
            fit_seconds = time.perf_counter() - fit_started
            predict_started = time.perf_counter()
            score = np.asarray(predict(confirmation.X), dtype="float64").ravel()
            predict_seconds = time.perf_counter() - predict_started
            confirmation_scores[name] = score
            del context, predict

            row = base_registry_fields(
                run_id=f"{RUN_ID}-{name}",
                status="retrospective_confirmation",
                development=development,
                evaluation=confirmation,
            )
            row.update(
                {
                    "candidate": name,
                    "candidate_family": spec.family,
                    "config_hash": config_hash(spec.as_config()),
                    "config_json": json.dumps(
                        spec.as_config(),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "fold_seed": None,
                    "n_folds": None,
                    "pool_fraction": 1.0,
                    "fit_seconds": fit_seconds,
                    "predict_seconds": predict_seconds,
                    "peak_process_rss_gb": monitor.peak_process_rss_gb,
                    "min_system_available_ram_gb": (
                        monitor.min_system_available_ram_gb
                    ),
                }
            )
            registry_rows.append(row)
            print(f"  fit={fit_seconds:.1f}s predict={predict_seconds:.1f}s", flush=True)

        ensemble_weights_used: dict[str, dict] = {}
        for name in ensemble_names:
            entries = {
                key: value
                for key, value in shortlist_payload["ensembles"].items()
                if key.startswith(f"{name}@")
            }
            if not entries:
                print(f"[skip] không tìm thấy weights cho {name}", flush=True)
                continue
            entry = next(iter(entries.values()))
            if entry["method"] == "rank_average":
                members = [
                    member
                    for member in entry["members"]
                    if member in confirmation_scores
                ]
                if len(members) < 2:
                    print(f"[skip] {name} thiếu member đã refit", flush=True)
                    continue
                from src.ensemble import rank_average_score

                confirmation_scores[name] = rank_average_score(
                    {member: confirmation_scores[member] for member in members}
                )
                ensemble_weights_used[name] = {
                    "method": entry["method"],
                    "members": members,
                }
                continue
            weights = entry["full_sample_weights"]
            members = [
                member
                for member, weight in weights.items()
                if member in confirmation_scores and weight > 0
            ]
            if not members:
                print(f"[skip] {name} không có member nào đã refit", flush=True)
                continue
            total = sum(weights[member] for member in members)
            combined = np.zeros(len(confirmation), dtype="float64")
            applied = {}
            for member in members:
                share = weights[member] / total
                applied[member] = share
                combined += share * confirmation_scores[member]
            confirmation_scores[name] = combined
            ensemble_weights_used[name] = {
                "method": entry["method"],
                "weights_learned_on": "development OOF",
                "weights_applied": applied,
                "renormalized_because_of_missing_members": total < 0.999,
            }
            print(f"[ensemble] {name} weights={applied}", flush=True)

    cate_scale = {
        item["name"]: bool(item.get("is_cate_scale", True))
        for item in protocol["candidates"]
    }
    metric_rows = []
    for name, score in confirmation_scores.items():
        is_cate = cate_scale.get(name, not name.startswith("Ensemble-RankAverage"))
        curve = dr_policy_value_curve(dr_signal, score, budgets=budgets)
        adjusted_curve = dr_policy_value_curve(
            adjusted_signal,
            score,
            budgets=budgets,
        )
        metric_rows.append(
            {
                "run_id": RUN_ID,
                "split": "retrospective_confirmation",
                "model": name,
                "n": len(score),
                "policy_area_dr": policy_area(
                    budgets,
                    curve["gross_value_per_customer"],
                ),
                "policy_area_dr_adjusted": policy_area(
                    budgets,
                    adjusted_curve["gross_value_per_customer"],
                ),
                "autoc_dr": rate_score(dr_signal, score, weighting="autoc"),
                "autoc_dr_adjusted": rate_score(
                    adjusted_signal,
                    score,
                    weighting="autoc",
                ),
                "rate_qini_dr": rate_score(dr_signal, score, weighting="qini"),
                "qini_score": qini_score(
                    confirmation.outcome,
                    confirmation.treatment,
                    score,
                ),
                "auuc_score": auuc_score(
                    confirmation.outcome,
                    confirmation.treatment,
                    score,
                ),
                "uplift_calibration_error": (
                    uplift_calibration_error(
                        confirmation.outcome,
                        confirmation.treatment,
                        score,
                        n_bins=10,
                    )
                    if is_cate
                    else np.nan
                ),
                "doubly_robust_risk": (
                    doubly_robust_risk(dr_signal, score) if is_cate else np.nan
                ),
                "score_mean": float(np.mean(score)),
                "score_std": float(np.std(score)),
                "negative_score_fraction": float(np.mean(score < 0)),
                "unique_score_count": int(np.unique(score).size),
                "is_cate_scale": is_cate,
            }
        )
    metrics = pd.DataFrame(metric_rows).sort_values(
        "policy_area_dr",
        ascending=False,
    )
    metrics.to_csv(output_dir / "confirmation_metrics.csv", index=False)
    print(
        metrics[
            ["model", "policy_area_dr", "autoc_dr", "qini_score"]
        ].to_string(index=False),
        flush=True,
    )

    print(f"[bootstrap] paired comparisons n_boot={args.n_boot}", flush=True)
    area_bootstrap = paired_policy_area_bootstrap(
        confirmation_scores,
        dr_signal,
        budgets=budgets,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    rate_bootstrap = paired_rate_bootstrap(
        confirmation_scores,
        dr_signal,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    comparison_rows = []
    for reference in (CHAMPION_REFERENCE, "X-Renormalized"):
        if reference not in confirmation_scores:
            continue
        for name in confirmation_scores:
            if name == reference:
                continue
            area = policy_area_difference_summary(area_bootstrap, name, reference)
            rate = paired_difference_summary(rate_bootstrap, name, reference)
            comparison_rows.append(
                {
                    "run_id": RUN_ID,
                    "model_a": name,
                    "model_b": reference,
                    "policy_area_difference": area["observed_difference"],
                    "policy_area_ci_low": area["ci_low"],
                    "policy_area_ci_high": area["ci_high"],
                    "policy_area_probability_positive": area[
                        "probability_difference_positive"
                    ],
                    "autoc_difference": rate["observed_difference"],
                    "autoc_ci_low": rate["ci_low"],
                    "autoc_ci_high": rate["ci_high"],
                    "autoc_probability_positive": rate[
                        "probability_difference_positive"
                    ],
                    "n_boot": args.n_boot,
                }
            )
    comparisons = pd.DataFrame(comparison_rows)
    comparisons.to_csv(output_dir / "paired_comparisons.csv", index=False)

    curve_rows = []
    for model_index, name in enumerate(area_bootstrap["model_names"]):
        for budget_index, budget in enumerate(budgets):
            curve_rows.append(
                {
                    "run_id": RUN_ID,
                    "model": name,
                    "budget_fraction": float(budget),
                    "gross_value_per_customer": float(
                        area_bootstrap["observed_curve"][model_index, budget_index]
                    ),
                    "ci_low": float(
                        area_bootstrap["curve_ci_low"][model_index, budget_index]
                    ),
                    "ci_high": float(
                        area_bootstrap["curve_ci_high"][model_index, budget_index]
                    ),
                    "break_even_contact_cost": (
                        float(
                            area_bootstrap["observed_curve"][
                                model_index, budget_index
                            ]
                            / budget
                        )
                        if budget > 0
                        else None
                    ),
                }
            )
    expected_random = expected_random_policy_value(dr_signal, budgets=budgets)
    random_sensitivity = random_topk_sensitivity(
        dr_signal,
        budgets=budgets,
        n_seeds=20,
        seed=args.seed,
    )
    for budget_index, budget in enumerate(budgets):
        curve_rows.append(
            {
                "run_id": RUN_ID,
                "model": "Expected random (stochastic policy)",
                "budget_fraction": float(budget),
                "gross_value_per_customer": float(
                    expected_random["gross_value_per_customer"][budget_index]
                ),
                "ci_low": float(random_sensitivity["value_min"][budget_index]),
                "ci_high": float(random_sensitivity["value_max"][budget_index]),
                "break_even_contact_cost": None,
            }
        )
    pd.DataFrame(curve_rows).to_csv(
        output_dir / "policy_budget_curve.csv",
        index=False,
    )

    # Kịch bản chính có cost/value giả định, dùng cho dashboard.
    main_policies = {
        "Treat none": np.zeros(len(confirmation), dtype="int8"),
        "Random top-k": top_budget_policy(
            np.random.default_rng(args.seed).random(len(confirmation)),
            args.main_budget,
        ),
        **{
            f"{name} top-k": top_budget_policy(score, args.main_budget)
            for name, score in confirmation_scores.items()
        },
    }
    contributions = np.column_stack(
        [
            policy * (args.value_per_conversion * dr_signal - args.main_cost)
            for policy in main_policies.values()
        ]
    )
    policy_bootstrap = bootstrap_policy_values(
        contributions,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    names = list(main_policies)
    random_index = names.index("Random top-k")
    policy_rows = []
    for index, (policy_name, policy) in enumerate(main_policies.items()):
        difference = (
            policy_bootstrap["draws"][:, index]
            - policy_bootstrap["draws"][:, random_index]
        )
        policy_rows.append(
            {
                "run_id": RUN_ID,
                "policy": policy_name,
                "budget_fraction": args.main_budget,
                "contact_cost_assumption": args.main_cost,
                "value_per_conversion_assumption": args.value_per_conversion,
                "target_fraction": float(np.mean(policy)),
                "ipw_net_scenario_value_per_customer": policy_value_from_signal(
                    policy,
                    ipw_signal,
                    args.value_per_conversion,
                    args.main_cost,
                ),
                "dr_net_scenario_value_per_customer": policy_bootstrap["mean"][index],
                "dr_ci_low": policy_bootstrap["ci_low"][index],
                "dr_ci_high": policy_bootstrap["ci_high"][index],
                "dr_delta_vs_random": (
                    policy_bootstrap["mean"][index]
                    - policy_bootstrap["mean"][random_index]
                ),
                "dr_delta_vs_random_ci_low": float(np.quantile(difference, 0.025)),
                "dr_delta_vs_random_ci_high": float(np.quantile(difference, 0.975)),
                "n_boot": args.n_boot,
                "is_monetary_observation": False,
            }
        )
    pd.DataFrame(policy_rows).to_csv(
        output_dir / "policy_value_comparison.csv",
        index=False,
    )

    sensitivity_rows = []
    for budget in budgets:
        policies = {
            "Treat none": np.zeros(len(confirmation), dtype="int8"),
            **{
                f"{name} top-k": top_budget_policy(score, budget)
                for name, score in confirmation_scores.items()
            },
        }
        for cost in costs:
            for policy_name, policy in policies.items():
                target_fraction = float(np.mean(policy))
                gross_dr = policy_value_from_signal(policy, dr_signal)
                gross_ipw = policy_value_from_signal(policy, ipw_signal)
                sensitivity_rows.append(
                    {
                        "run_id": RUN_ID,
                        "policy": policy_name,
                        "budget_fraction": float(budget),
                        "contact_cost_assumption": cost,
                        "value_per_conversion_assumption": args.value_per_conversion,
                        "target_fraction": target_fraction,
                        "gross_incremental_conversions_per_customer_dr": gross_dr,
                        "gross_incremental_conversions_per_customer_ipw": gross_ipw,
                        "net_scenario_value_per_customer_dr": (
                            gross_dr * args.value_per_conversion
                            - target_fraction * cost
                        ),
                        "is_monetary_observation": False,
                        "interpretation": "conversion-equivalent assumption scenario",
                    }
                )
    pd.DataFrame(sensitivity_rows).to_csv(
        output_dir / "policy_sensitivity.csv",
        index=False,
    )

    # Promotion rule. Điều kiện 1 được kiểm tra theo **từng seed**: với mỗi fold
    # seed đã chạy, challenger phải thắng Response ở chính seed đó. So sánh hai
    # giá trị đã gộp qua seed sẽ bỏ sót trường hợp challenger thắng đậm ở một seed
    # và thua ở seed còn lại.
    oof_ranking = pd.read_csv(args.oof_run_dir / "candidate_ranking.csv")
    champion_by_seed = (
        oof_ranking.loc[oof_ranking["model"] == CHAMPION_REFERENCE]
        .set_index("fold_seed")["policy_area_dr"]
        .to_dict()
    )
    decision_rows = []
    champion_area = float(
        metrics.loc[metrics["model"] == CHAMPION_REFERENCE, "policy_area_dr"].iloc[0]
    )
    for name in confirmation_scores:
        if name == CHAMPION_REFERENCE:
            continue
        comparison = comparisons.loc[
            (comparisons["model_a"] == name)
            & (comparisons["model_b"] == CHAMPION_REFERENCE)
        ]
        if comparison.empty:
            continue
        comparison = comparison.iloc[0]
        challenger_by_seed = (
            oof_ranking.loc[oof_ranking["model"] == name]
            .set_index("fold_seed")["policy_area_dr"]
            .to_dict()
        )
        shared_seeds = sorted(set(challenger_by_seed) & set(champion_by_seed))
        n_seeds = len(shared_seeds)
        seeds_won = [
            seed
            for seed in shared_seeds
            if challenger_by_seed[seed] > champion_by_seed[seed]
        ]
        condition_1 = bool(n_seeds >= 2 and len(seeds_won) == n_seeds)
        condition_2 = bool(comparison["policy_area_difference"] > 0)
        condition_3 = bool(comparison["policy_area_ci_low"] > 0)
        decision_rows.append(
            {
                "run_id": RUN_ID,
                "challenger": name,
                "champion": CHAMPION_REFERENCE,
                "oof_seeds_evaluated": n_seeds,
                "oof_seeds_won": len(seeds_won),
                "condition_1_oof_wins_all_seeds": condition_1,
                "condition_2_confirmation_same_sign": condition_2,
                "condition_3_paired_ci_lower_bound_positive": condition_3,
                "confirmation_policy_area_difference": comparison[
                    "policy_area_difference"
                ],
                "confirmation_ci_low": comparison["policy_area_ci_low"],
                "confirmation_ci_high": comparison["policy_area_ci_high"],
                "promoted": bool(condition_1 and condition_2 and condition_3),
            }
        )
    decisions = pd.DataFrame(decision_rows)
    decisions.to_csv(output_dir / "promotion_decision.csv", index=False)
    promoted = (
        decisions.loc[decisions["promoted"], "challenger"].tolist()
        if not decisions.empty
        else []
    )
    final_champion = promoted[0] if promoted else CHAMPION_REFERENCE

    append_registry(registry_rows)
    np.savez_compressed(
        output_dir / "confirmation_predictions.npz",
        source_index=confirmation.source_index,
        treatment=confirmation.treatment,
        conversion=confirmation.outcome,
        dr_signal=dr_signal.astype("float32"),
        ipw_signal=ipw_signal.astype("float32"),
        mu0=mu0.astype("float32"),
        mu1=mu1.astype("float32"),
        **{name: score.astype("float32") for name, score in confirmation_scores.items()},
    )

    manifest = {
        "run_id": RUN_ID,
        "protocol_id": protocol["protocol_id"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "retrospective_confirmation_complete",
        "evidence_class": "retrospective_confirmation",
        "evidence_note": (
            "Confirmation Sprint 2 da duoc quan sat va bao cao o Sprint 2. Ket qua "
            "o day khong phai prospective unseen test."
        ),
        "shortlist_source": str(args.shortlist),
        "oof_run_dir": str(args.oof_run_dir),
        "development_rows": len(development),
        "confirmation_rows": len(confirmation),
        "development_index_sha256": development.index_sha256,
        "confirmation_index_sha256": confirmation.index_sha256,
        "propensity": propensity,
        "budget_grid": budgets.tolist(),
        "n_boot": args.n_boot,
        "main_scenario": {
            "budget_fraction": args.main_budget,
            "contact_cost": args.main_cost,
            "value_per_conversion": args.value_per_conversion,
            "monetary_outcome_available": False,
        },
        "models_evaluated": sorted(confirmation_scores),
        "ensemble_weights": ensemble_weights_used,
        "champion_reference": CHAMPION_REFERENCE,
        "champion_policy_area_dr": champion_area,
        "promoted_challengers": promoted,
        "final_champion": final_champion,
        "promotion_rule": protocol["promotion_rule"],
        "peak_process_rss_gb": monitor.peak_process_rss_gb,
        "min_system_available_ram_gb": monitor.min_system_available_ram_gb,
        "elapsed_seconds": time.time() - started,
        "random_policy_area_mean": random_sensitivity["policy_area_mean"],
        "random_policy_area_std": random_sensitivity["policy_area_std"],
    }
    (output_dir / "protocol_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=float),
        encoding="utf-8",
    )
    print(f"[write] {output_dir}", flush=True)
    print(f"[decision] final champion = {final_champion}", flush=True)
    if promoted:
        print(f"[decision] promoted: {promoted}", flush=True)
    else:
        print(
            "[decision] no challenger met the promotion rule; champion unchanged",
            flush=True,
        )
    print(f"[done] elapsed={time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()


