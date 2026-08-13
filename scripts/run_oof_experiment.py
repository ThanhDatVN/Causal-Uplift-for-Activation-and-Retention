"""Chạy cross-fitting OOF cho toàn bộ candidate của protocol Sprint 3.

Trình tự cố định:

1. tái dựng development pool (Sprint 2 ``fit + validation``) và kiểm tra split hash;
2. tùy chọn subsample phân tầng cho stage smoke/screen;
3. cross-fit nuisance ``mu0``/``mu1`` **một lần** trên đúng bộ fold;
4. dựng DR signal và adjusted transformed outcome dùng chung cho mọi candidate;
5. cross-fit từng candidate, chấm out-of-fold, ghi registry;
6. paired bootstrap trên cùng OOF rows;
7. ghi manifest và OOF score.

Điểm quan trọng về tính hợp lệ: mọi candidate được chấm bằng **cùng một** effect
signal, nên chênh lệch giữa hai model không lẫn với chênh lệch giữa hai tín hiệu
đánh giá. Nuisance dùng chung bộ fold với candidate; đây là cross-fitting chuẩn,
mỗi dòng vẫn chỉ được chấm bởi model không fit trên dòng đó.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from lightgbm import LGBMClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Console Windows mặc định là cp1252 và không encode được tiếng Việt trong log.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from src.candidates import FitContext, candidate_from_dict, lgbm_params
from src.evaluation import auuc_score, qini_score, uplift_calibration_error
from src.experiment import (
    FullDataRunLock,
    IMPROVEMENT_DIR,
    ResourceGateBreached,
    SplitArrays,
    append_registry,
    base_registry_fields,
    build_sprint3_splits,
    config_hash,
    git_state,
    ResourceMonitor,
    make_folds,
)
from src.paths import REPO_ROOT
from src.policy import doubly_robust_effect_signal
from src.policy_evaluation import (
    doubly_robust_risk,
    dr_policy_value_curve,
    expected_random_policy_value,
    paired_policy_difference_band,
    paired_policy_area_bootstrap,
    policy_area,
    policy_area_difference_summary,
    random_topk_sensitivity,
    top_tail_event_support,
)
from src.ranking_metrics import (
    adjusted_transformed_outcome,
    paired_difference_summary,
    paired_rate_bootstrap,
    rate_score,
)


PROTOCOL_PATH = REPO_ROOT / "configs" / "sprint3_improvement_protocol.json"


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _split_outcome_name(split: SplitArrays) -> str:
    return "conversion" if "visit" in split.auxiliary_outcomes else "visit"


def cross_fit_nuisance(
    split: SplitArrays,
    folds: list[tuple[np.ndarray, np.ndarray]],
    seed: int,
    params: dict | None = None,
) -> dict[str, np.ndarray]:
    """OOF ``mu0``/``mu1`` bằng một classifier cho mỗi arm trên mỗi fold."""
    n = len(split)
    mu0 = np.zeros(n, dtype="float64")
    mu1 = np.zeros(n, dtype="float64")
    for fold_index, (train_idx, test_idx) in enumerate(folds):
        for arm, target in ((0, mu0), (1, mu1)):
            arm_rows = train_idx[split.treatment[train_idx] == arm]
            model = LGBMClassifier(**lgbm_params(seed + fold_index, params))
            model.fit(split.X[arm_rows], split.outcome[arm_rows])
            target[test_idx] = model.predict_proba(split.X[test_idx])[:, 1]
            del model
        print(f"  [nuisance] fold {fold_index + 1}/{len(folds)} done", flush=True)
    return {"mu0": mu0, "mu1": mu1}


def cross_fit_candidate(
    spec,
    split: SplitArrays,
    folds: list[tuple[np.ndarray, np.ndarray]],
    propensity: float,
    seed: int,
    monitor=None,
) -> dict:
    """Fit candidate trên từng fold train và chấm fold test tương ứng.

    ``monitor`` được kiểm tra giữa hai fold — điểm dừng an toàn duy nhất bên
    trong vòng lặp này.
    """
    oof_score = np.full(len(split), np.nan, dtype="float64")
    fit_seconds = 0.0
    predict_seconds = 0.0
    fold_diagnostics: list[dict[str, object]] = []
    for fold_index, (train_idx, test_idx) in enumerate(folds):
        if monitor is not None:
            monitor.raise_if_breached(f"{spec.name} fold {fold_index + 1}")
        context = FitContext(
            X=split.X[train_idx],
            treatment=split.treatment[train_idx],
            outcome=split.outcome[train_idx],
            propensity=propensity,
            seed=seed + fold_index,
            params=spec.params,
            outcome_name=_split_outcome_name(split),
            auxiliary_outcomes={
                name: values[train_idx]
                for name, values in split.auxiliary_outcomes.items()
            },
        )
        started = time.perf_counter()
        predict = spec.build(context)
        fit_seconds += time.perf_counter() - started
        started = time.perf_counter()
        oof_score[test_idx] = np.asarray(
            predict(split.X[test_idx]),
            dtype="float64",
        ).ravel()
        predict_seconds += time.perf_counter() - started
        stacker = getattr(predict, "stacker", None)
        if stacker is not None:
            fold_diagnostics.append(
                {
                    "fold_index": fold_index,
                    "coefficients": np.asarray(
                        stacker.coefficients_, dtype="float64"
                    ).tolist(),
                    "training_diagnostics": dict(
                        getattr(stacker, "training_diagnostics_", {})
                    ),
                }
            )
        del context, predict
        # LightGBM and large augmented NumPy matrices can otherwise retain their
        # high-water mark until a later fold.  A collection checkpoint keeps the
        # process-isolated full-data path below the registered RAM guard.
        gc.collect()
        print(
            f"  [{spec.name}] fold {fold_index + 1}/{len(folds)} "
            f"fit={fit_seconds:.1f}s predict={predict_seconds:.1f}s",
            flush=True,
        )
    return {
        "score": oof_score,
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        "fold_diagnostics": fold_diagnostics,
    }


def score_metrics(
    score: np.ndarray,
    split: SplitArrays,
    dr_signal: np.ndarray,
    adjusted_signal: np.ndarray,
    budgets: np.ndarray,
    is_cate_scale: bool,
) -> dict:
    outcome = split.outcome.astype("float64")
    treatment = split.treatment.astype("float64")
    curve = dr_policy_value_curve(dr_signal, score, budgets=budgets)
    adjusted_curve = dr_policy_value_curve(adjusted_signal, score, budgets=budgets)
    return {
        "policy_area_dr": policy_area(budgets, curve["gross_value_per_customer"]),
        "policy_area_dr_adjusted": policy_area(
            budgets,
            adjusted_curve["gross_value_per_customer"],
        ),
        "autoc_dr": rate_score(dr_signal, score, weighting="autoc"),
        "autoc_dr_adjusted": rate_score(adjusted_signal, score, weighting="autoc"),
        "rate_qini_dr": rate_score(dr_signal, score, weighting="qini"),
        "qini_score": qini_score(outcome, treatment, score),
        "auuc_score": auuc_score(outcome, treatment, score),
        "uplift_calibration_error": (
            uplift_calibration_error(outcome, treatment, score, n_bins=10)
            if is_cate_scale
            else np.nan
        ),
        "doubly_robust_risk": (
            doubly_robust_risk(dr_signal, score) if is_cate_scale else np.nan
        ),
        "score_mean": float(np.mean(score)),
        "score_std": float(np.std(score)),
        "negative_score_fraction": float(np.mean(score < 0)),
        "unique_score_count": int(np.unique(score).size),
    }


def early_stop_reason(
    score: np.ndarray,
    protocol: dict,
    *,
    candidate_curve: np.ndarray | None = None,
    reference_curve: np.ndarray | None = None,
    budgets: np.ndarray | None = None,
) -> str | None:
    rules = protocol["early_stop"]
    if not np.isfinite(score).all():
        return "non_finite_score"
    if np.unique(score).size < int(rules["constant_score_unique_threshold"]):
        return "constant_score"
    if (
        rules.get("dominated_at_every_budget_5_to_20", False)
        and candidate_curve is not None
        and reference_curve is not None
        and budgets is not None
    ):
        mask = (budgets >= 0.05) & (budgets <= 0.20)
        if mask.any() and np.all(candidate_curve[mask] < reference_curve[mask]):
            return "dominated_at_every_budget_5_to_20"
    return None


def validate_execution_contract(
    protocol: dict,
    *,
    stage: str,
    pool_fraction: float,
    fold_seed: int,
    n_folds: int,
    n_boot: int,
    outcome: str | None = None,
) -> None:
    """Reject CLI settings that silently diverge from a registered protocol."""
    if not 0 < pool_fraction <= 1:
        raise ValueError("pool_fraction phải nằm trong (0, 1]")
    if n_boot < 2:
        raise ValueError("n_boot phải >= 2")

    registered_outcome = protocol.get("estimand", {}).get("outcome")
    if outcome is not None and registered_outcome is not None:
        if outcome != str(registered_outcome):
            raise ValueError(
                f"outcome={outcome!r} khác protocol={registered_outcome!r}; "
                "estimand diagnostic cần protocol và output namespace riêng"
            )

    cross_fitting = protocol.get("cross_fitting", {})
    registered_n_folds = cross_fitting.get("n_folds")
    if registered_n_folds is not None and n_folds != int(registered_n_folds):
        raise ValueError(
            f"n_folds={n_folds} khác protocol={registered_n_folds}"
        )
    registered_seeds = {
        int(value)
        for key in ("primary_fold_seed", "secondary_fold_seed")
        if (value := cross_fitting.get(key)) is not None
    }
    if registered_seeds and fold_seed not in registered_seeds:
        raise ValueError(
            f"fold_seed={fold_seed} không thuộc protocol={sorted(registered_seeds)}"
        )

    execution = protocol.get("execution")
    if not execution:
        return
    expected_pool = {
        "smoke": execution.get("smoke_pool_fraction"),
        "screen": execution.get("screen_pool_fraction"),
        "finalist": 1.0,
    }.get(stage)
    if expected_pool is not None and not np.isclose(
        pool_fraction,
        float(expected_pool),
        rtol=0.0,
        atol=1e-12,
    ):
        raise ValueError(
            f"pool_fraction={pool_fraction} khác protocol {stage}={expected_pool}"
        )

    primary_seed = cross_fitting.get("primary_fold_seed")
    if stage == "smoke":
        expected_boot = execution.get("smoke_bootstrap_replicates")
    elif primary_seed is not None and fold_seed == int(primary_seed):
        expected_boot = execution.get("primary_seed_bootstrap_replicates")
    else:
        expected_boot = execution.get("secondary_seed_bootstrap_replicates")
    allowed_boot = {
        int(value)
        for value in (
            expected_boot,
            execution.get("process_isolated_component_bootstrap_replicates"),
        )
        if value is not None
    }
    if allowed_boot and n_boot not in allowed_boot:
        raise ValueError(
            f"n_boot={n_boot} không thuộc protocol={sorted(allowed_boot)} "
            f"cho stage={stage}, fold_seed={fold_seed}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool-frac", type=float, default=1.0)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROTOCOL_PATH,
        help="Protocol JSON; mặc định giữ nguyên Sprint 3 v1.",
    )
    parser.add_argument("--pool-seed", type=int, default=77)
    parser.add_argument("--fold-seed", type=int, default=None)
    parser.add_argument("--n-folds", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--outcome",
        default="conversion",
        choices=["conversion", "visit"],
        help=(
            "Doi outcome la doi ESTIMAND. visit chi dung lam power diagnostic cho "
            "giao thuc, khong phai ket qua san pham."
        ),
    )
    parser.add_argument(
        "--stage",
        default="screen",
        choices=["smoke", "screen", "finalist"],
    )
    parser.add_argument(
        "--candidates",
        default="",
        help="Danh sách tên candidate, phân tách bằng dấu phẩy; rỗng là toàn bộ protocol.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    protocol_bytes = args.protocol.read_bytes()
    protocol = json.loads(protocol_bytes.decode("utf-8"))
    protocol_sha256 = hashlib.sha256(protocol_bytes).hexdigest()
    n_folds = args.n_folds or int(protocol["cross_fitting"]["n_folds"])
    fold_seed = (
        args.fold_seed
        if args.fold_seed is not None
        else int(protocol["cross_fitting"]["primary_fold_seed"])
    )
    budgets = np.asarray(protocol["metrics"]["primary_budget_grid"], dtype="float64")
    output_dir = args.output_dir or (IMPROVEMENT_DIR / args.stage)
    validate_execution_contract(
        protocol,
        stage=args.stage,
        pool_fraction=args.pool_frac,
        fold_seed=fold_seed,
        n_folds=n_folds,
        n_boot=args.n_boot,
        outcome=args.outcome,
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Output directory không rỗng ở {output_dir}; dùng namespace mới để "
            "không ghi đè artifact hoàn chỉnh hoặc partial-run provenance."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    gate = protocol["resource_gate"]
    available_gb = psutil.virtual_memory().available / 2**30
    if available_gb < float(gate["min_available_ram_gb"]):
        raise MemoryError(
            f"Resource gate: cần >= {gate['min_available_ram_gb']} GB RAM khả dụng, "
            f"hiện có {available_gb:.2f} GB."
        )

    started = time.time()
    print("[data] building Sprint 3 splits", flush=True)
    splits = build_sprint3_splits(outcome=args.outcome)
    development = splits["development"]
    if args.pool_frac < 1.0:
        development = development.subsample(args.pool_frac, seed=args.pool_seed)
    # OOF không đọc confirmation. Giải phóng cache/full split sau khi subsample
    # để tránh giữ hàng trăm MB không dùng trong toàn bộ vòng fit.
    del splits
    counts = development.arm_counts()
    print(
        f"[data] development rows={counts['n_rows']:,} "
        f"treated={counts['n_treated']:,} control={counts['n_control']:,} "
        f"conv_t={counts['n_conversion_treated']:,} "
        f"conv_c={counts['n_conversion_control']:,}",
        flush=True,
    )
    if counts["n_conversion_control"] < 200 and args.stage != "smoke":
        raise ValueError(
            "control conversions < 200: stage screen/finalist không đủ event theo "
            "selection contract"
        )
    if counts["n_conversion_control"] < 200:
        print(
            "[warn] control conversions < 200: this stage only exercises the code "
            "path and must not be used to select a model.",
            flush=True,
        )

    propensity = float(protocol["estimand"]["propensity_value"])
    folds = make_folds(
        development.treatment,
        development.outcome,
        n_folds=n_folds,
        seed=fold_seed,
    )

    selected_names = [
        name.strip() for name in args.candidates.split(",") if name.strip()
    ]
    specs = [candidate_from_dict(item) for item in protocol["candidates"]]
    if selected_names:
        known = {spec.name for spec in specs}
        unknown = sorted(set(selected_names) - known)
        if unknown:
            raise ValueError(f"Candidate không có trong protocol: {unknown}")
        specs = [spec for spec in specs if spec.name in selected_names]

    # Ngưỡng RAM khả dụng được lấy từ chính protocol đã đăng ký, không phải hằng
    # số rời rạc trong script. Monitor bật cờ khi vi phạm; runner dừng ở điểm an
    # toàn giữa hai fold hoặc hai candidate.
    with ResourceMonitor(
        min_available_gb=float(gate["min_available_ram_gb"]),
        max_system_memory_percent=float(gate["max_system_memory_percent"]),
    ) as monitor:
        print(
            f"[gate] theo doi RAM kha dung, nguong "
            f"{gate['min_available_ram_gb']} GB",
            flush=True,
        )
        print("[nuisance] cross-fitting mu0/mu1", flush=True)
        nuisance_started = time.perf_counter()
        nuisance = cross_fit_nuisance(development, folds, seed=args.seed)
        monitor.raise_if_breached("sau nuisance cross-fitting")
        nuisance_seconds = time.perf_counter() - nuisance_started
        dr_signal = doubly_robust_effect_signal(
            development.outcome,
            development.treatment,
            nuisance["mu0"],
            nuisance["mu1"],
            propensity=propensity,
        )
        pooled_outcome = (
            propensity * nuisance["mu1"] + (1.0 - propensity) * nuisance["mu0"]
        )
        adjusted_signal = adjusted_transformed_outcome(
            development.outcome,
            development.treatment,
            pooled_outcome,
            propensity=propensity,
        )
        print(
            f"[nuisance] done in {nuisance_seconds:.1f}s "
            f"ate_dr={np.mean(dr_signal):.8f} "
            f"ate_adjusted={np.mean(adjusted_signal):.8f}",
            flush=True,
        )

        registry_rows: list[dict] = []
        oof_scores: dict[str, np.ndarray] = {}
        candidate_diagnostics: dict[str, list[dict[str, object]]] = {}
        resource_abort: ResourceGateBreached | None = None
        for spec in specs:
            print(f"[candidate] {spec.name}", flush=True)
            outcome_tag = "" if args.outcome == "conversion" else f"-{args.outcome}"
            base = base_registry_fields(
                run_id=(
                    f"{protocol['protocol_id']}-{args.stage}"
                    f"{outcome_tag}-{spec.name}"
                ),
                status=args.stage,
                development=development,
            )
            base.update(
                {
                    "outcome": args.outcome,
                    "candidate": spec.name,
                    "candidate_family": spec.family,
                    "config_hash": config_hash(spec.as_config()),
                    "config_json": json.dumps(
                        spec.as_config(),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "fold_seed": fold_seed,
                    "n_folds": n_folds,
                    "pool_fraction": args.pool_frac,
                }
            )
            try:
                monitor.raise_if_breached(f"trước candidate {spec.name}")
                result = cross_fit_candidate(
                    spec,
                    development,
                    folds,
                    propensity=propensity,
                    seed=args.seed,
                    monitor=monitor,
                )
            except Exception as error:  # noqa: BLE001 - registry phải ghi mọi thất bại
                base.update(
                    {
                        "status": "failed",
                        "failure_reason": f"{type(error).__name__}: {error}",
                        "peak_process_rss_gb": monitor.peak_process_rss_gb,
                        "min_system_available_ram_gb": (
                            monitor.min_system_available_ram_gb
                        ),
                        "max_system_memory_percent": (
                            monitor.max_system_memory_percent
                        ),
                    }
                )
                registry_rows.append(base)
                print(f"  [failed] {type(error).__name__}: {error}", flush=True)
                if isinstance(error, ResourceGateBreached):
                    resource_abort = error
                    break
                continue

            score = result["score"]
            candidate_curve = dr_policy_value_curve(
                dr_signal,
                score,
                budgets=budgets,
            )["gross_value_per_customer"]
            reference_curve = None
            if spec.name != "Response" and "Response" in oof_scores:
                reference_curve = dr_policy_value_curve(
                    dr_signal,
                    oof_scores["Response"],
                    budgets=budgets,
                )["gross_value_per_customer"]
            stop_reason = early_stop_reason(
                score,
                protocol,
                candidate_curve=candidate_curve,
                reference_curve=reference_curve,
                budgets=budgets,
            )
            base.update(
                {
                    "fit_seconds": result["fit_seconds"],
                    "predict_seconds": result["predict_seconds"],
                    "peak_process_rss_gb": monitor.peak_process_rss_gb,
                    "min_system_available_ram_gb": (
                        monitor.min_system_available_ram_gb
                    ),
                    "max_system_memory_percent": (
                        monitor.max_system_memory_percent
                    ),
                }
            )
            if stop_reason is not None:
                base.update({"status": "failed", "failure_reason": stop_reason})
                registry_rows.append(base)
                print(f"  [early stop] {stop_reason}", flush=True)
                continue

            base.update(
                score_metrics(
                    score,
                    development,
                    dr_signal,
                    adjusted_signal,
                    budgets,
                    spec.is_cate_scale,
                )
            )
            registry_rows.append(base)
            oof_scores[spec.name] = score.astype("float32")
            if result["fold_diagnostics"]:
                candidate_diagnostics[spec.name] = result["fold_diagnostics"]
            print(
                f"  policy_area_dr={base['policy_area_dr']:.8f} "
                f"autoc={base['autoc_dr']:.8f} qini={base['qini_score']:.6f}",
                flush=True,
            )

    append_registry(registry_rows)
    pd.DataFrame(registry_rows).to_csv(
        output_dir / "oof_metrics.csv",
        index=False,
    )

    if resource_abort is not None:
        raise resource_abort

    if not oof_scores:
        raise RuntimeError("Không candidate nào chạy xong; xem registry để biết lý do.")

    np.savez_compressed(
        output_dir / "oof_scores.npz",
        source_index=development.source_index,
        treatment=development.treatment,
        outcome=development.outcome,
        dr_signal=dr_signal.astype("float32"),
        adjusted_signal=adjusted_signal.astype("float32"),
        mu0=nuisance["mu0"].astype("float32"),
        mu1=nuisance["mu1"].astype("float32"),
        **oof_scores,
    )

    print(f"[bootstrap] paired comparisons n_boot={args.n_boot}", flush=True)
    area_bootstrap = paired_policy_area_bootstrap(
        oof_scores,
        dr_signal,
        budgets=budgets,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    rate_bootstrap = paired_rate_bootstrap(
        oof_scores,
        dr_signal,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    reference_names = [
        name for name in ("Response", "X-Renormalized") if name in oof_scores
    ]
    comparison_rows = []
    for reference in reference_names:
        for name in oof_scores:
            if name == reference:
                continue
            area = policy_area_difference_summary(area_bootstrap, name, reference)
            rate = paired_difference_summary(rate_bootstrap, name, reference)
            comparison_rows.append(
                {
                    "stage": args.stage,
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
    pd.DataFrame(comparison_rows).to_csv(
        output_dir / "paired_comparisons.csv",
        index=False,
    )

    band_rows = []
    for reference in reference_names:
        candidates = [name for name in oof_scores if name != reference]
        if not candidates:
            continue
        band = paired_policy_difference_band(
            area_bootstrap,
            reference=reference,
            candidates=candidates,
        )
        for candidate_index, name in enumerate(band["candidate_names"]):
            for budget_index, budget in enumerate(band["budget_fraction"]):
                band_rows.append(
                    {
                        "stage": args.stage,
                        "fold_seed": fold_seed,
                        "model_a": name,
                        "model_b": reference,
                        "budget_fraction": float(budget),
                        "observed_difference": float(
                            band["observed_difference"][candidate_index, budget_index]
                        ),
                        "pointwise_ci_low": float(
                            band["pointwise_ci_low"][candidate_index, budget_index]
                        ),
                        "pointwise_ci_high": float(
                            band["pointwise_ci_high"][candidate_index, budget_index]
                        ),
                        "simultaneous_ci_low": float(
                            band["simultaneous_ci_low"][candidate_index, budget_index]
                        ),
                        "simultaneous_ci_high": float(
                            band["simultaneous_ci_high"][candidate_index, budget_index]
                        ),
                        "standard_error": float(
                            band["standard_error"][candidate_index, budget_index]
                        ),
                        "family_size": band["family_size"],
                        "critical_value": band["critical_value"],
                        "inference_scope": band["scope"],
                        "n_boot": band["n_boot"],
                    }
                )
    pd.DataFrame(band_rows).to_csv(
        output_dir / "paired_policy_difference_bands.csv",
        index=False,
    )

    curve_rows = []
    for model_index, name in enumerate(area_bootstrap["model_names"]):
        for budget_index, budget in enumerate(budgets):
            curve_rows.append(
                {
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
                }
            )
    expected_random = expected_random_policy_value(dr_signal, budgets=budgets)
    for budget_index, budget in enumerate(budgets):
        curve_rows.append(
            {
                "model": "Expected random (stochastic policy)",
                "budget_fraction": float(budget),
                "gross_value_per_customer": float(
                    expected_random["gross_value_per_customer"][budget_index]
                ),
                "ci_low": None,
                "ci_high": None,
            }
        )
    pd.DataFrame(curve_rows).to_csv(
        output_dir / "budget_value_curve.csv",
        index=False,
    )

    support_rows = []
    for name, score in oof_scores.items():
        for row in top_tail_event_support(
            development.outcome,
            development.treatment,
            score,
            budgets=budgets,
        ):
            support_rows.append(
                {
                    "stage": args.stage,
                    "fold_seed": fold_seed,
                    "model": name,
                    **row,
                }
            )
    pd.DataFrame(support_rows).to_csv(
        output_dir / "tail_event_support.csv",
        index=False,
    )

    random_sensitivity = random_topk_sensitivity(
        dr_signal,
        budgets=budgets,
        n_seeds=20,
        seed=args.seed,
    )
    pd.DataFrame(
        {
            "budget_fraction": budgets,
            "random_value_mean": random_sensitivity["value_mean"],
            "random_value_min": random_sensitivity["value_min"],
            "random_value_max": random_sensitivity["value_max"],
            "expected_random_value": expected_random["gross_value_per_customer"],
        }
    ).to_csv(output_dir / "random_policy_sensitivity.csv", index=False)

    manifest = {
        "manifest_schema_version": 2,
        "protocol_id": protocol["protocol_id"],
        "protocol_path": args.protocol.resolve().relative_to(REPO_ROOT).as_posix(),
        "protocol_sha256": protocol_sha256,
        "stage": args.stage,
        "outcome": args.outcome,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "development_index_sha256": development.index_sha256,
        "pool_fraction": args.pool_frac,
        "pool_seed": args.pool_seed,
        "model_seed": args.seed,
        "fold_seed": fold_seed,
        "n_folds": n_folds,
        "propensity": propensity,
        "candidate_config_hashes": {
            spec.name: config_hash(spec.as_config()) for spec in specs
        },
        "candidate_fold_diagnostics": candidate_diagnostics,
        "code_state": git_state(),
        "arm_counts": counts,
        "budget_grid": budgets.tolist(),
        "n_boot": args.n_boot,
        "paired_policy_band_family_size": (
            int(len(oof_scores) - 1) * int(len(budgets))
            if reference_names
            else 0
        ),
        "paired_policy_band_scope": "conditional_on_fixed_oof_scores",
        "nuisance_seconds": nuisance_seconds,
        "peak_process_rss_gb": monitor.peak_process_rss_gb,
        "min_system_available_ram_gb": monitor.min_system_available_ram_gb,
        "max_system_memory_percent": monitor.max_system_memory_percent,
        "resource_gate_passed": not monitor.breached,
        "elapsed_seconds": time.time() - started,
        "candidates_completed": sorted(oof_scores),
        "random_policy_area_mean": random_sensitivity["policy_area_mean"],
        "random_policy_area_std": random_sensitivity["policy_area_std"],
        "expected_random_mean_effect": expected_random["mean_effect_signal"],
        "scope_note": (
            "Development pool OOF only. Confirmation Sprint 2 khong duoc doc o "
            "buoc nay."
        ),
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[write] {output_dir}", flush=True)
    print(f"[done] elapsed={time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    with FullDataRunLock():
        main()
