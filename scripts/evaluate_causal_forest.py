"""Chấm điểm artifact Causal Forest tải về từ Kaggle.

Đây là bước còn thiếu giữa `kaggle_causal_forest_gate.py` (chỉ kiểm tra tài nguyên
và tính toàn vẹn artifact) và báo cáo. Gate **không** đánh giá chất lượng model;
script này mới làm việc đó.

Hai chế độ, tự phát hiện:

1. **Comparable.** Khi holdout đi kèm là final test Sprint 1 (chỉ xảy ra với
   ``--frac 0.50 --test-size 0.30 --seed 42``), script đối chiếu Y/T với holdout đã
   phát hành rồi so Causal Forest với cả năm model release bằng paired bootstrap
   trên đúng cùng những dòng đó.
2. **Standalone.** Với fraction 20%/30%, holdout là tập khác. Script vẫn tính metric
   cho riêng Causal Forest để dựng learning curve, nhưng **từ chối** so sánh với số
   release, vì hai con số nằm trên hai tập test khác nhau.

Chế độ 2 chính là chỗ dễ sai nhất khi đọc kết quả Kaggle: Qini 20% và Qini release
50% không so trực tiếp được.
"""

from __future__ import annotations

import argparse
import hashlib
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

from src.data import load_criteo_full, stratified_sample, train_test_holdout, xty
from src.evaluation import auuc_score, paired_qini_bootstrap_matrix, qini_score
from src.paths import OUTPUT_DIR
from src.policy import doubly_robust_effect_signal, ipw_effect_signal
from src.policy_evaluation import (
    DEFAULT_BUDGET_GRID,
    dr_policy_value_curve,
    paired_policy_area_bootstrap,
    policy_area,
    policy_area_difference_summary,
)
from src.ranking_metrics import rate_score

RELEASE_MODELS = ["Response", "S-Learner", "T-Learner", "X-Learner", "DR-Learner"]
RELEASE_HOLDOUT = OUTPUT_DIR / "cate" / "holdout_test_yt.npz"
RELEASE_CATE_DIR = OUTPUT_DIR / "optimization" / "cate"


def _slug(name: str) -> str:
    return name.lower().replace("-", "_")


def _sha256_array(values: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(values, dtype="int8").tobytes()).hexdigest()


def load_release_scores() -> dict[str, np.ndarray] | None:
    """Score của năm model release; ``None`` nếu chưa có artifact."""
    scores = {}
    for model in RELEASE_MODELS:
        path = RELEASE_CATE_DIR / f"cate_{_slug(model)}_sprint1_release.npy"
        if not path.exists():
            return None
        scores[model] = np.load(path).astype("float64").ravel()
    return scores


def build_dr_signal(
    Y: np.ndarray,
    T: np.ndarray,
    frac: float,
    test_size: float,
    seed: int,
    data_path: str | None,
) -> tuple[np.ndarray, str]:
    """DR signal cho holdout, với nuisance fit trên đúng phần train tương ứng.

    Train và test rời nhau nên không cần cross-fitting: một model cho mỗi arm fit
    trên train rồi predict test là đủ và không rò rỉ.
    """
    df = stratified_sample(
        load_criteo_full(dtype_f32=True, path=data_path),
        frac=frac,
        seed=seed,
    )
    train_df, test_df = train_test_holdout(df, test_size=test_size, seed=seed)
    _, T_check, Y_check = xty(test_df)
    if not (
        np.array_equal(Y_check.astype("int8"), Y.astype("int8"))
        and np.array_equal(T_check.astype("int8"), T.astype("int8"))
    ):
        raise ValueError(
            "Holdout tái dựng không khớp holdout trong artifact. Kiểm tra lại "
            "--frac/--test-size/--seed đúng bằng giá trị đã dùng khi train."
        )
    X_train, T_train, Y_train = xty(train_df, dtype="float32")
    X_test, _, _ = xty(test_df, dtype="float32")
    propensity = float(T_train.mean())
    mu = {}
    for arm in (0, 1):
        rows = np.flatnonzero(T_train == arm)
        model = LGBMClassifier(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=1000,
            reg_alpha=1.0,
            reg_lambda=5.0,
            colsample_bytree=0.9,
            random_state=seed + arm,
            verbose=-1,
        )
        model.fit(X_train[rows], Y_train[rows])
        mu[arm] = model.predict_proba(X_test)[:, 1]
        del model
    signal = doubly_robust_effect_signal(
        Y,
        T,
        mu[0],
        mu[1],
        propensity=propensity,
    )
    return signal, f"doubly_robust (nuisance fit tren train frac={frac:g})"


def metrics_for(
    name: str,
    score: np.ndarray,
    Y: np.ndarray,
    T: np.ndarray,
    signal: np.ndarray,
    budgets: np.ndarray,
) -> dict:
    curve = dr_policy_value_curve(signal, score, budgets=budgets)
    return {
        "model": name,
        "n": int(len(score)),
        "policy_area_dr": policy_area(budgets, curve["gross_value_per_customer"]),
        "autoc_dr": rate_score(signal, score, weighting="autoc"),
        "qini_score": qini_score(Y, T, score),
        "auuc_score": auuc_score(Y, T, score),
        "score_mean": float(np.mean(score)),
        "score_std": float(np.std(score)),
        "negative_score_fraction": float(np.mean(score < 0)),
        "unique_score_count": int(np.unique(score).size),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage-dir",
        type=Path,
        required=True,
        help="Thư mục preflight_* tải về từ Kaggle.",
    )
    parser.add_argument(
        "--score-name",
        default="cate_causal_forest_kaggle_safe.npy",
    )
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--signal",
        choices=["dr", "ipw"],
        default="dr",
        help=(
            "dr fit nuisance tren phan train tuong ung (variance thap hon); "
            "ipw khong can fit gi them."
        ),
    )
    parser.add_argument("--data-path", default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR / "causal_forest_release",
    )
    args = parser.parse_args()

    started = time.time()
    score_path = args.stage_dir / args.score_name
    holdout_path = args.stage_dir / "holdout_test_yt.npz"
    for path in (score_path, holdout_path):
        if not path.exists():
            raise FileNotFoundError(f"Thiếu artifact: {path}")

    score = np.load(score_path).astype("float64").ravel()
    holdout = np.load(holdout_path, allow_pickle=False)
    Y = holdout["Y"].astype("float64").ravel()
    T = holdout["T"].astype("float64").ravel()
    frac = float(holdout["frac"])
    seed = int(holdout["seed"])
    test_size = float(holdout["test_size"]) if "test_size" in holdout else 0.30

    if not (len(score) == len(Y) == len(T)):
        raise ValueError(
            f"Độ dài không khớp: score={len(score)}, Y={len(Y)}, T={len(T)}"
        )
    if not np.isfinite(score).all():
        raise ValueError("Score Causal Forest có giá trị không hữu hạn")
    print(
        f"[artifact] rows={len(score):,} frac={frac:g} test_size={test_size:g} "
        f"seed={seed}",
        flush=True,
    )

    # Xác định xem holdout này có đúng là final test Sprint 1 không.
    comparable = False
    release_scores = None
    if RELEASE_HOLDOUT.exists():
        release = np.load(RELEASE_HOLDOUT)
        same_rows = len(release["Y"]) == len(Y)
        if same_rows:
            comparable = bool(
                _sha256_array(release["Y"]) == _sha256_array(Y)
                and _sha256_array(release["T"]) == _sha256_array(T)
            )
    if comparable:
        release_scores = load_release_scores()
        if release_scores is None:
            comparable = False
            print(
                "[warn] holdout khớp nhưng thiếu file score release; "
                "chuyển sang chế độ standalone.",
                flush=True,
            )

    mode = "comparable_with_sprint1_release" if comparable else "standalone"
    print(f"[mode] {mode}", flush=True)
    if not comparable:
        print(
            "[note] Holdout nay KHONG phai final test Sprint 1. Metric duoi day "
            "chi dung de dung learning curve cua Causal Forest; khong so truc tiep "
            "voi bang release.",
            flush=True,
        )

    budgets = np.asarray(DEFAULT_BUDGET_GRID, dtype="float64")
    if args.signal == "dr":
        signal, signal_label = build_dr_signal(
            Y,
            T,
            frac=frac,
            test_size=test_size,
            seed=seed,
            data_path=args.data_path,
        )
    else:
        signal = ipw_effect_signal(Y, T, propensity=float(np.mean(T)))
        signal_label = "ipw (propensity = ty le treatment quan sat tren holdout)"
    print(f"[signal] {signal_label} ate={np.mean(signal):.8f}", flush=True)

    all_scores = {"Causal Forest": score}
    if comparable:
        all_scores.update(release_scores)

    rows = [
        metrics_for(name, values, Y, T, signal, budgets)
        for name, values in all_scores.items()
    ]
    metrics = pd.DataFrame(rows).sort_values("policy_area_dr", ascending=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output_dir / f"cf_metrics_frac_{frac:g}.csv", index=False)
    print(
        metrics[["model", "policy_area_dr", "autoc_dr", "qini_score"]].to_string(
            index=False
        ),
        flush=True,
    )

    comparisons = pd.DataFrame()
    if comparable and len(all_scores) > 1:
        print(f"[bootstrap] paired n_boot={args.n_boot}", flush=True)
        area_bootstrap = paired_policy_area_bootstrap(
            all_scores,
            signal,
            budgets=budgets,
            n_boot=args.n_boot,
            seed=args.seed,
        )
        qini_bootstrap = paired_qini_bootstrap_matrix(
            all_scores,
            Y,
            T,
            n_boot=args.n_boot,
            seed=args.seed,
        )
        names = qini_bootstrap["model_names"]
        cf_index = names.index("Causal Forest")
        comparison_rows = []
        for model in RELEASE_MODELS:
            area = policy_area_difference_summary(
                area_bootstrap,
                "Causal Forest",
                model,
            )
            other = names.index(model)
            qini_difference = (
                qini_bootstrap["draws"][:, cf_index]
                - qini_bootstrap["draws"][:, other]
            )
            comparison_rows.append(
                {
                    "model_a": "Causal Forest",
                    "model_b": model,
                    "policy_area_difference": area["observed_difference"],
                    "policy_area_ci_low": area["ci_low"],
                    "policy_area_ci_high": area["ci_high"],
                    "policy_area_probability_positive": area[
                        "probability_difference_positive"
                    ],
                    "qini_difference": float(
                        qini_bootstrap["observed"][cf_index]
                        - qini_bootstrap["observed"][other]
                    ),
                    "qini_ci_low": float(np.quantile(qini_difference, 0.025)),
                    "qini_ci_high": float(np.quantile(qini_difference, 0.975)),
                    "n_boot": args.n_boot,
                }
            )
        comparisons = pd.DataFrame(comparison_rows)
        comparisons.to_csv(
            args.output_dir / f"cf_paired_comparisons_frac_{frac:g}.csv",
            index=False,
        )
        print(comparisons.to_string(index=False), flush=True)

    gate_manifest_path = args.stage_dir / "gate_manifest.json"
    gate = (
        json.loads(gate_manifest_path.read_text(encoding="utf-8"))
        if gate_manifest_path.exists()
        else None
    )
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage_dir": str(args.stage_dir),
        "mode": mode,
        "fraction": frac,
        "test_size": test_size,
        "seed": seed,
        "holdout_rows": int(len(Y)),
        "holdout_is_sprint1_final_test": comparable,
        "effect_signal": signal_label,
        "budget_grid": budgets.tolist(),
        "n_boot": args.n_boot if comparable else None,
        "metrics": metrics.to_dict(orient="records"),
        "paired_comparisons": (
            comparisons.to_dict(orient="records") if len(comparisons) else []
        ),
        "resource_gate": (gate or {}).get("runtime"),
        "gate_status": (gate or {}).get("status"),
        "elapsed_seconds": time.time() - started,
        "scope_note": (
            "Causal Forest duoc chay tren Kaggle voi profile kaggle-safe "
            "(inference=False). Khong goi effect_interval(); moi khoang tin cay o "
            "day den tu holdout bootstrap."
        ),
        "comparability_note": (
            "So sanh voi bang release chi hop le khi holdout dung bang final test "
            "Sprint 1, tuc frac=0.50 test_size=0.30 seed=42."
        ),
    }
    (args.output_dir / f"cf_summary_frac_{frac:g}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=float),
        encoding="utf-8",
    )
    print(f"[write] {args.output_dir}", flush=True)
    print(f"[done] elapsed={time.time() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
