"""Train 5 model local (Response, S/T/X-Learner, DR-Learner) tren holdout dung chung cua Criteo,
danh gia bang Qini/AUUC + paired bootstrap CI, xuat ma tran so sanh + Qini curve + luu CATE.

Causal Forest chay rieng tren Colab (train_causal_forest.py) roi ghep bang build_comparison.py,
dung cung holdout/seed de so cong bang.

Chay:
    .venv/Scripts/python.exe scripts/train_baselines.py --frac 0.50 --n-boot 500
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.baselines import (
    fit_dr_learner,
    fit_response_baseline,
    fit_s_learner,
    fit_t_learner,
    fit_x_learner,
)
from src.data import FEATURES, load_criteo_full, stratified_sample, train_test_holdout, xty
from src.evaluation import (
    auuc_score,
    bootstrap_ci,
    paired_bootstrap_difference_ci,
    qini_curve,
    qini_score,
)
from src.paths import OUTPUT_DIR

BASELINE_MODEL = "T-Learner"  # moc so sanh cho paired bootstrap


def evaluate(name, cate, Y_test, T_test, n_boot, seed):
    q = qini_score(Y_test, T_test, cate)
    a = auuc_score(Y_test, T_test, cate)
    lb, ub = bootstrap_ci(Y_test, T_test, cate, n_boot=n_boot, seed=seed)
    print(f"[eval] {name:16s} qini={q:.4f} CI=[{lb:.4f},{ub:.4f}] auuc={a:.4f}", flush=True)
    return {"model": name, "qini_score": q, "qini_ci_low": lb, "qini_ci_high": ub, "auuc_score": a}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frac", type=float, default=0.50, help="ti le sample tu full dataset")
    ap.add_argument("--test-size", type=float, default=0.30)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    t0 = time.time()
    print(f"[load] doc full dataset...", flush=True)
    df = load_criteo_full(dtype_f32=True)
    df = stratified_sample(df, frac=args.frac, seed=args.seed)
    train_df, test_df = train_test_holdout(df, test_size=args.test_size, seed=args.seed)
    print(f"[split] frac={args.frac} train={len(train_df):,} test={len(test_df):,} "
          f"(test conv={test_df['conversion'].mean():.5f}) time={time.time()-t0:.1f}s", flush=True)

    X_tr, T_tr, Y_tr = xty(train_df)
    X_te, T_te, Y_te = xty(test_df)

    cates = {}

    t = time.time()
    resp = fit_response_baseline(X_tr, Y_tr, seed=args.seed)
    cates["Response"] = resp.effect(X_te)
    print(f"[fit] Response       {time.time()-t:.1f}s", flush=True)

    t = time.time()
    slrn = fit_s_learner(X_tr, T_tr, Y_tr, seed=args.seed)
    cates["S-Learner"] = slrn.effect(X_te).ravel()
    print(f"[fit] S-Learner      {time.time()-t:.1f}s", flush=True)

    t = time.time()
    tlrn = fit_t_learner(X_tr, T_tr, Y_tr, seed=args.seed)
    cates["T-Learner"] = tlrn.effect(X_te)
    print(f"[fit] T-Learner      {time.time()-t:.1f}s", flush=True)

    t = time.time()
    xlrn = fit_x_learner(X_tr, T_tr, Y_tr, seed=args.seed)
    cates["X-Learner"] = xlrn.effect(X_te)
    print(f"[fit] X-Learner      {time.time()-t:.1f}s", flush=True)

    t = time.time()
    drlrn = fit_dr_learner(X_tr, T_tr, Y_tr, cv=3, seed=args.seed)
    cates["DR-Learner"] = drlrn.effect(X_te).ravel()
    print(f"[fit] DR-Learner     {time.time()-t:.1f}s", flush=True)

    # Luu CATE tren tap test + holdout (Y,T) de sau nay ghep Causal Forest (chay Colab)
    # vao cung bang so sanh MA KHONG can train lai baseline. build_comparison.py doc cac file nay.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cate_dir = OUTPUT_DIR / "legacy" / "first_run_scores"
    cate_dir.mkdir(exist_ok=True)
    np.savez(OUTPUT_DIR / "holdout" / "final_test_yt.npz", Y=Y_te, T=T_te,
             frac=args.frac, seed=args.seed, n_test=len(test_df))
    for name, cate in cates.items():
        slug = name.lower().replace("-", "_")
        np.save(cate_dir / f"cate_{slug}.npy", np.asarray(cate, dtype="float64"))
    print(f"[write] {cate_dir}/ (CATE {len(cates)} model + holdout Y,T)", flush=True)

    rows = []
    for name, cate in cates.items():
        rows.append(evaluate(name, cate, Y_te, T_te, args.n_boot, args.seed))

    baseline_cate = cates[BASELINE_MODEL]
    for r in rows:
        if r["model"] == BASELINE_MODEL:
            r["qini_delta_vs_t_learner"] = np.nan
            r["qini_delta_ci_low"] = np.nan
            r["qini_delta_ci_high"] = np.nan
        else:
            comparison = paired_bootstrap_difference_ci(
                cates[r["model"]],
                baseline_cate,
                Y_te,
                T_te,
                n_boot=args.n_boot,
                seed=args.seed,
            )
            r["qini_delta_vs_t_learner"] = comparison["observed_difference"]
            r["qini_delta_ci_low"] = comparison["ci_low"]
            r["qini_delta_ci_high"] = comparison["ci_high"]
        r["qini_ci_excludes_zero"] = bool(
            (r["qini_ci_low"] > 0) or (r["qini_ci_high"] < 0)
        )
        r["sample_frac"] = args.frac
        r["n_test"] = len(test_df)

    result = pd.DataFrame(rows)[
        ["model", "qini_score", "qini_ci_low", "qini_ci_high", "auuc_score",
         "qini_delta_vs_t_learner", "qini_delta_ci_low", "qini_delta_ci_high",
         "qini_ci_excludes_zero", "sample_frac", "n_test"]
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUTPUT_DIR / "qini_comparison.csv"
    result.to_csv(out_csv, index=False)
    print(f"\n[write] {out_csv}", flush=True)
    print(result.to_string(index=False), flush=True)

    # Qini curve chong len nhau
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    palette = {"Response": "#7c879c", "S-Learner": "#c9a227", "T-Learner": "#b9691f",
               "X-Learner": "#0e7c7b", "DR-Learner": "#5b8def"}
    plt.figure(figsize=(8, 6))
    for name, cate in cates.items():
        curve = qini_curve(Y_te, T_te, cate)
        plt.plot(curve["n_targeted"], curve["qini"], label=name, color=palette.get(name), linewidth=2)
    n_max = len(test_df)
    q_end = qini_curve(Y_te, T_te, cates[BASELINE_MODEL])["qini"].iloc[-1]
    plt.plot([0, n_max], [0, q_end], "--", color="#999", linewidth=1, label="Random targeting")
    plt.xlabel("So khach hang duoc nham toi (xep theo uplift giam dan)")
    plt.ylabel("Qini (so conversion tang them tich luy)")
    plt.title(f"Qini curve — baseline models (holdout {n_max:,} khach hang, sample {args.frac:.0%})")
    plt.legend()
    plt.tight_layout()
    out_png = OUTPUT_DIR / "qini_curve.png"
    plt.savefig(out_png, dpi=120)
    print(f"[write] {out_png}", flush=True)

    # Diagnostic buckets theo dấu score; không phải principal strata quan sát được.
    seg_rows = []
    for name, cate in cates.items():
        if name == "Response":
            continue  # Response khong phai CATE thuc, khong phan khuc
        seg = pd.Series(
            np.where(
                cate > 1e-4,
                "Predicted positive effect",
                np.where(cate < -1e-4, "Predicted negative effect", "Near-zero score"),
            )
        )
        counts = seg.value_counts(normalize=True).mul(100).round(2)
        for k, v in counts.items():
            seg_rows.append({"model": name, "segment": k, "pct_population": v})
    seg_df = pd.DataFrame(seg_rows)
    out_seg = OUTPUT_DIR / "segments_baseline.csv"
    seg_df.to_csv(out_seg, index=False)
    print(f"[write] {out_seg}", flush=True)
    print(seg_df.to_string(index=False), flush=True)

    print(f"\n[done] tong thoi gian {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
