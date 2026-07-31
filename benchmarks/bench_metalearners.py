"""
Fit T-Learner / X-Learner / DR-Learner that tren mau stratify cua Criteo Uplift,
de so sanh tai nguyen voi CausalForestDML (bench_causal_forest.py).

Chay doc lap:
    .venv/Scripts/python.exe benchmarks/bench_metalearners.py --frac 0.05 --model xlearner
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
    ap.add_argument("--frac", type=float, required=True)
    ap.add_argument("--model", choices=["tlearner", "xlearner", "drlearner"], required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = load_stratified_sample(args.frac, args.seed)
    X = df[FEATURES].to_numpy(dtype="float64")
    T = df["treatment"].to_numpy(dtype="float64")
    Y = df["conversion"].to_numpy(dtype="float64")

    from lightgbm import LGBMClassifier, LGBMRegressor

    t0 = time.time()
    if args.model == "tlearner":
        from econml.metalearners import TLearner
        model = TLearner(models=LGBMRegressor(n_estimators=200, max_depth=5, verbose=-1))
        model.fit(Y=Y, T=T, X=X)
    elif args.model == "xlearner":
        from econml.metalearners import XLearner
        model = XLearner(
            models=LGBMRegressor(n_estimators=200, max_depth=5, verbose=-1),
            propensity_model=LGBMClassifier(n_estimators=200, max_depth=5, verbose=-1),
        )
        model.fit(Y=Y, T=T, X=X)
    else:  # drlearner
        from econml.dr import DRLearner
        model = DRLearner(
            model_regression=LGBMRegressor(n_estimators=200, max_depth=5, verbose=-1),
            model_propensity=LGBMClassifier(n_estimators=200, max_depth=5, verbose=-1),
            cv=3,
            random_state=args.seed,
        )
        model.fit(Y=Y, T=T, X=X)

    fit_time = time.time() - t0
    print(f"[fit] model={args.model} rows={len(df):,} fit_time={fit_time:.1f}s", flush=True)

    cate = model.effect(X[:2000])
    print(f"[effect] n={len(cate)} cate_mean={np.mean(cate):.5f} cate_std={np.std(cate):.5f}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
