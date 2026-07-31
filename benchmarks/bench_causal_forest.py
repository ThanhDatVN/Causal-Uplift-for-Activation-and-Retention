"""
Fit CausalForestDML that (khong mo phong) tren mau stratify cua Criteo Uplift.
Dung boi scripts/bench_harness.py de do wall time + peak RAM theo tung muc sample.

Chay doc lap:
    .venv/Scripts/python.exe benchmarks/bench_causal_forest.py --frac 0.05 --n-estimators 500
"""
import argparse
import time

import numpy as np
import pandas as pd

DATA_PATH = "data/criteo-research-uplift-v2.1.csv.gz"
FEATURES = [f"f{i}" for i in range(12)]


def load_stratified_sample(frac: float, seed: int = 42) -> pd.DataFrame:
    t0 = time.time()
    dtype = {f: "float32" for f in FEATURES}
    dtype.update({"treatment": "int8", "conversion": "int8", "visit": "int8", "exposure": "int8"})
    df = pd.read_csv(DATA_PATH, dtype=dtype)
    print(f"[load] full rows={len(df):,} time={time.time()-t0:.1f}s", flush=True)

    if frac < 1.0:
        rng = np.random.default_rng(seed)
        parts = []
        for (_, _), g in df.groupby(["treatment", "conversion"], sort=False):
            n = max(1, int(round(len(g) * frac)))
            idx = rng.choice(g.index.values, size=min(n, len(g)), replace=False)
            parts.append(df.loc[idx])
        df = pd.concat(parts, ignore_index=True)
    print(f"[sample] frac={frac} rows={len(df):,}", flush=True)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frac", type=float, required=True, help="ty le sample tren tong 13.9M dong")
    ap.add_argument("--n-estimators", type=int, default=500)
    ap.add_argument("--min-samples-leaf", type=int, default=200)
    ap.add_argument("--cv", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = load_stratified_sample(args.frac, args.seed)

    from lightgbm import LGBMClassifier, LGBMRegressor
    from econml.dml import CausalForestDML

    model = CausalForestDML(
        model_y=LGBMRegressor(n_estimators=200, max_depth=5, verbose=-1),
        model_t=LGBMClassifier(n_estimators=200, max_depth=5, verbose=-1),
        discrete_treatment=True,  # BAT BUOC: T (treatment) la nhi phan 0/1, khong phai lien tuc.
                                   # Thieu dong nay se loi "Cannot use a classifier as a first
                                   # stage model when the target is continuous!" vi mac dinh cua
                                   # econml la discrete_treatment=False.
        n_estimators=args.n_estimators,
        min_samples_leaf=args.min_samples_leaf,
        honest=True,
        inference=True,
        cv=args.cv,
        random_state=args.seed,
    )

    t0 = time.time()
    model.fit(
        Y=df["conversion"].to_numpy(dtype="float64"),
        T=df["treatment"].to_numpy(dtype="float64"),
        X=df[FEATURES].to_numpy(dtype="float64"),
    )
    fit_time = time.time() - t0
    print(
        f"[fit] rows={len(df):,} n_estimators={args.n_estimators} "
        f"min_samples_leaf={args.min_samples_leaf} cv={args.cv} fit_time={fit_time:.1f}s",
        flush=True,
    )

    sample_x = df[FEATURES].to_numpy(dtype="float64")[:2000]
    cate = model.effect(sample_x)
    print(f"[effect] n={len(cate)} cate_mean={np.mean(cate):.5f} cate_std={np.std(cate):.5f}", flush=True)

    print("DONE", flush=True)


if __name__ == "__main__":
    main()
