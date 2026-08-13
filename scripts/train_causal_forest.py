"""Train CausalForestDML trên holdout dùng chung với các model khác.

Đây là bước sau khi Sprint 1 local đã freeze. EconML/scikit-learn trong script
chạy bằng CPU và system RAM; chọn Kaggle GPU không tự làm nhanh hơn.

Hai chế độ split, chọn bằng ``--split``:

``sprint1`` (mặc định)
    ``stratified_sample(frac, seed)`` rồi ``train_test_holdout``. Với
    ``--frac 0.50 --test-size 0.30 --seed 42`` holdout trùng khít final test
    Sprint 1, tức so được với bảng release năm model.

``sprint3``
    Tái dựng đúng split Sprint 2/3: lấy **phần bù** của sample Sprint 1 rồi chia
    fit/validation/confirmation. Fit trên development (fit + validation), predict
    trên confirmation. Hai tập này rời hẳn holdout Sprint 1, nên điểm số chỉ so
    với bảng confirmation Sprint 3 — và so được **chính xác**, vì cùng dòng và
    cùng DR signal đã đóng băng trong ``output/sprint3/confirmation_predictions.npz``.

Ba profile:

``kaggle-safe``
    Cấu hình đã chạy ba mốc 20/30/50%. ``min_samples_leaf=500`` là thoả hiệp tài
    nguyên, **không** phải cấu hình phù hợp cho outcome hiếm — xem ``rare-outcome``.

``research``
    Cấu hình nặng để benchmark tài nguyên. ``min_samples_leaf=200`` đi **sai
    hướng** cho outcome 0,29%; giữ lại để tái lập benchmark Sprint 1 mục 8, không
    dùng cho nghiên cứu chất lượng.

``rare-outcome``
    Đăng ký trong ``configs/causal_forest_rare_outcome_protocol_v1.json``. Ràng
    buộc bó nhất ở bài toán này là **số sự kiện control mỗi lá**: với treatment
    85/15 và conversion control 0,1938%, ``min_samples_leaf=500`` chỉ cho 0,145 sự
    kiện control mỗi lá, tức đại đa số lá có nhánh control rỗng.
    ``min_samples_leaf=10000`` nâng con số đó lên khoảng 2,9.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.dummy import DummyClassifier

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import (
    load_criteo_full,
    stratified_complement,
    stratified_sample,
    train_test_holdout,
    xty,
)
from src.experiment import (
    SPRINT1_SAMPLING_SEED,
    SPRINT1_SELECTED_FRACTION,
    SPRINT2_CONFIRMATION_SEED,
    SPRINT2_SPLIT_HASHES,
    SPRINT2_SPLIT_SEED,
    sha256_indices,
)
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
    "rare-outcome": {
        "n_estimators": 500,
        "min_samples_leaf": 10000,
        "cv": 3,
        "max_samples": 0.45,
        "inference": False,
    },
}

# Tên file điểm số theo profile. Hai tên đầu là tên lịch sử, không được đổi vì
# artifact đã phát hành và `evaluate_causal_forest.py` mặc định đọc chúng.
SCORE_NAMES = {
    "kaggle-safe": "cate_causal_forest_kaggle_safe.npy",
    "research": "cate_causal_forest.npy",
    "rare-outcome": "cate_causal_forest_rare_outcome.npy",
}


def build_sprint1_split(full, frac: float, test_size: float, seed: int):
    """Split lịch sử của Sprint 1: sample rồi chia train/test."""
    df = stratified_sample(full, frac=frac, seed=seed)
    train_df, test_df = train_test_holdout(df, test_size=test_size, seed=seed)
    return train_df, test_df, None


def build_sprint3_split(full):
    """Tái dựng development + confirmation của Sprint 2/3.

    Dùng lại đúng các hằng số trong ``src.experiment`` để chỉ có một nguồn sự
    thật, và đối chiếu hash source-index với manifest Sprint 2 trước khi trả về.
    Lệch hash thì dừng, vì khi đó điểm số sẽ nằm trên tập khác với bảng
    confirmation đang có.
    """
    pool = stratified_complement(
        full,
        selected_frac=SPRINT1_SELECTED_FRACTION,
        seed=SPRINT1_SAMPLING_SEED,
        preserve_index=True,
    )
    fit_df, remainder = train_test_holdout(
        pool,
        test_size=0.40,
        seed=SPRINT2_SPLIT_SEED,
        preserve_index=True,
    )
    validation_df, confirmation_df = train_test_holdout(
        remainder,
        test_size=0.50,
        seed=SPRINT2_CONFIRMATION_SEED,
        preserve_index=True,
    )
    del remainder, pool

    observed = {
        "fit": sha256_indices(fit_df.index.to_numpy(dtype="int64")),
        "validation": sha256_indices(validation_df.index.to_numpy(dtype="int64")),
        "confirmation": sha256_indices(
            confirmation_df.index.to_numpy(dtype="int64")
        ),
    }
    mismatched = {
        name: (value, SPRINT2_SPLIT_HASHES[name])
        for name, value in observed.items()
        if value != SPRINT2_SPLIT_HASHES[name]
    }
    if mismatched:
        raise ValueError(
            "Split hash không khớp manifest Sprint 2; dừng vì điểm số sẽ không "
            f"đặt chung bảng confirmation được: {mismatched}"
        )

    development_df = pd.concat([fit_df, validation_df])
    del fit_df, validation_df
    source_index = confirmation_df.index.to_numpy(dtype="int64")
    return development_df, confirmation_df, source_index


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
    parser.add_argument(
        "--split",
        choices=["sprint1", "sprint3"],
        default="sprint1",
        help=(
            "sprint1: sample + holdout lịch sử; "
            "sprint3: development/confirmation của Sprint 2/3 (bỏ qua --frac/--test-size)"
        ),
    )
    parser.add_argument("--profile", choices=PROFILES, default="kaggle-safe")
    parser.add_argument(
        "--train-subsample",
        type=float,
        default=None,
        help=(
            "CHỈ dùng cho smoke test code path: lấy mẫu phân tầng phần train, giữ "
            "nguyên tập predict. Giá trị này được ghi vào artifact nên một lần "
            "smoke không thể bị nhầm thành run thật."
        ),
    )
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
    full = load_criteo_full(dtype_f32=True, path=args.data_path)
    if args.split == "sprint1":
        train_df, test_df, source_index = build_sprint1_split(
            full,
            frac=args.frac,
            test_size=args.test_size,
            seed=args.seed,
        )
    else:
        train_df, test_df, source_index = build_sprint3_split(full)
    del full
    if args.train_subsample is not None:
        if not 0 < args.train_subsample <= 1:
            raise ValueError("--train-subsample phải nằm trong (0, 1]")
        before = len(train_df)
        train_df = stratified_sample(
            train_df,
            frac=args.train_subsample,
            seed=args.seed,
            preserve_index=True,
        )
        print(
            f"[smoke] --train-subsample={args.train_subsample:g}: train "
            f"{before:,} -> {len(train_df):,}. KHONG phai run that.",
            flush=True,
        )
    print(
        f"[split] mode={args.split} frac={args.frac} train={len(train_df):,} "
        f"test={len(test_df):,} time={time.time() - started:.1f}s",
        flush=True,
    )
    X_train, T_train, Y_train = xty(train_df, dtype="float32")
    X_test, T_test, Y_test = xty(test_df, dtype="float32")
    del train_df, test_df

    # Số sự kiện control kỳ vọng trong một lá là ràng buộc bó nhất khi outcome
    # hiếm; in ra để đọc log biết cấu hình có hợp lý không mà không phải tự tính.
    control_rate = float(Y_train[T_train == 0].mean())
    control_share = float(np.mean(T_train == 0))
    events_per_leaf = min_samples_leaf * control_share * control_rate
    print(
        f"[leaf] min_samples_leaf={min_samples_leaf} -> ky vong "
        f"{events_per_leaf:.3f} su kien control moi la "
        f"(control_share={control_share:.4f} control_rate={control_rate:.6f})",
        flush=True,
    )

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
    output_name = SCORE_NAMES[args.profile]
    np.save(cate_dir / output_name, np.asarray(cate, dtype="float64"))
    # Hash của Y/T cho phép kiểm chứng sau khi tải artifact về rằng holdout này
    # đúng là tập đã dự kiến. Với split sprint1 chỉ trùng final test Sprint 1 khi
    # frac=0.50, test_size=0.30, seed=42; ở fraction khác holdout là tập khác.
    # Với split sprint3, `source_index` mới là khoá đối chiếu: nó phải trùng khít
    # `source_index` trong output/sprint3/confirmation_predictions.npz.
    import hashlib

    y_hash = hashlib.sha256(Y_test.astype("int8").tobytes()).hexdigest()
    t_hash = hashlib.sha256(T_test.astype("int8").tobytes()).hexdigest()
    payload = {
        "Y": Y_test,
        "T": T_test,
        "frac": args.frac,
        "seed": args.seed,
        "n_test": len(Y_test),
        "test_size": args.test_size,
        "y_sha256": y_hash,
        "t_sha256": t_hash,
        "split": args.split,
        "profile": args.profile,
        "n_train": len(Y_train),
        "train_subsample": (
            -1.0 if args.train_subsample is None else float(args.train_subsample)
        ),
        # Cấu hình **thực tế** đã chạy, không phải cấu hình trong profile: cờ dòng
        # lệnh có thể ghi đè. Ghi lại để đối chiếu được với protocol đã đăng ký.
        "effective_n_estimators": int(n_estimators),
        "effective_min_samples_leaf": int(min_samples_leaf),
        "effective_cv": int(cv),
        "effective_max_samples": float(profile["max_samples"]),
        "effective_inference": bool(profile["inference"]),
        "control_events_per_leaf": float(events_per_leaf),
    }
    if source_index is not None:
        payload["source_index"] = source_index
    np.savez(cate_dir / "holdout_test_yt.npz", **payload)
    print(f"[holdout] y_sha256={y_hash[:24]} t_sha256={t_hash[:24]}", flush=True)
    print(
        f"[write] {cate_dir / output_name} n={len(cate):,} "
        f"mean={cate.mean():.6f} total_time={time.time() - started:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
