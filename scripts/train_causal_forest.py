"""Train CausalForestDML trên cùng holdout với 5 model local.

Đây là bước sau khi Sprint 1 local đã freeze. EconML/scikit-learn trong script
chạy bằng CPU và system RAM; chọn Kaggle GPU không tự làm nhanh hơn.

Runbook đề xuất:
    python scripts/train_causal_forest.py --profile kaggle-safe --frac 0.20
    python scripts/train_causal_forest.py --profile kaggle-safe --frac 0.30
    python scripts/train_causal_forest.py --profile kaggle-safe --frac 0.50

Chỉ chạy 50% nếu hai preflight hoàn tất, peak RAM < 75% RAM runtime và còn đủ
thời gian session. `research` giữ cấu hình nặng 500 cây/inference để benchmark,
không phải mặc định trên Kaggle Free.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from lightgbm import LGBMRegressor
from sklearn.dummy import DummyClassifier

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import load_criteo_full, stratified_sample, train_test_holdout, xty
from src.paths import OUTPUT_DIR


PROFILES = {
    "kaggle-safe": {
        "n_estimators": 200,
        "min_samples_leaf": 500,
        "cv": 2,
        "max_samples": 0.25,
        "inference": False,
    },
    "research": {
        "n_estimators": 500,
        "min_samples_leaf": 200,
        "cv": 3,
        "max_samples": 0.45,
        "inference": True,
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="CSV Criteo; bỏ trống để dùng src.paths.CRITEO_PATH",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR / "causal_forest",
        help="thư mục riêng cho Causal Forest; không ghi đè holdout release",
    )
    parser.add_argument("--frac", type=float, default=0.50, help="phải khớp 5 model local")
    parser.add_argument("--test-size", type=float, default=0.30)
    parser.add_argument("--profile", choices=PROFILES, default="kaggle-safe")
    parser.add_argument("--n-estimators", type=int, default=None)
    parser.add_argument("--min-samples-leaf", type=int, default=None)
    parser.add_argument("--cv", type=int, default=None)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    n_estimators = args.n_estimators or profile["n_estimators"]
    min_samples_leaf = args.min_samples_leaf or profile["min_samples_leaf"]
    cv = args.cv or profile["cv"]
    if n_estimators % 4 != 0:
        raise ValueError("n_estimators phải chia hết cho subforest_size mặc định 4")

    started = time.time()
    df = stratified_sample(
        load_criteo_full(dtype_f32=True, path=args.data_path),
        frac=args.frac,
        seed=args.seed,
    )
    train_df, test_df = train_test_holdout(
        df,
        test_size=args.test_size,
        seed=args.seed,
    )
    print(
        f"[split] frac={args.frac} train={len(train_df):,} test={len(test_df):,} "
        f"time={time.time() - started:.1f}s",
        flush=True,
    )
    X_train, T_train, Y_train = xty(train_df, dtype="float32")
    X_test, T_test, Y_test = xty(test_df, dtype="float32")

    from econml.dml import CausalForestDML

    print(
        f"[fit] profile={args.profile} n_estimators={n_estimators} "
        f"min_samples_leaf={min_samples_leaf} cv={cv} "
        f"max_samples={profile['max_samples']} inference={profile['inference']}",
        flush=True,
    )
    model = CausalForestDML(
        model_y=LGBMRegressor(
            n_estimators=200,
            max_depth=5,
            random_state=args.seed,
            verbose=-1,
        ),
        # RCT: treatment assignment không cần flexible propensity model.
        model_t=DummyClassifier(strategy="prior"),
        discrete_treatment=True,
        n_estimators=n_estimators,
        min_samples_leaf=min_samples_leaf,
        max_samples=profile["max_samples"],
        honest=True,
        inference=profile["inference"],
        cv=cv,
        n_jobs=args.n_jobs,
        random_state=args.seed,
    )
    fit_started = time.time()
    model.fit(Y=Y_train, T=T_train, X=X_train)
    print(f"[fit] done fit_time={time.time() - fit_started:.1f}s", flush=True)
    cate = model.effect(X_test).ravel()

    cate_dir = args.output_dir
    cate_dir.mkdir(parents=True, exist_ok=True)
    output_name = (
        "cate_causal_forest.npy"
        if args.profile == "research"
        else "cate_causal_forest_kaggle_safe.npy"
    )
    np.save(cate_dir / output_name, np.asarray(cate, dtype="float64"))
    np.savez(
        cate_dir / "holdout_test_yt.npz",
        Y=Y_test,
        T=T_test,
        frac=args.frac,
        seed=args.seed,
        n_test=len(test_df),
    )
    print(
        f"[write] {cate_dir / output_name} n={len(cate):,} "
        f"mean={cate.mean():.6f} total_time={time.time() - started:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
