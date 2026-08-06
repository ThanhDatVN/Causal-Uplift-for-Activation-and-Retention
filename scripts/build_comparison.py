"""Ghep tat ca CATE da luu (output/legacy/first_run_scores/cate_*.npy) thanh bang so sanh cuoi cung + Qini curve
+ phan khuc — KHONG train lai model. Danh gia moi model tren CUNG holdout Y,T da luu.

Chay sau khi da co du CATE cua ca baseline (train_baselines.py) va Causal Forest
(train_causal_forest.py tren Colab, tai cate_causal_forest.npy ve output/holdout/):

    .venv/Scripts/python.exe scripts/build_comparison.py --n-boot 500

Xuat: output/legacy/qini_comparison.csv, output/legacy/qini_curve.png, output/segments.csv.
So sánh cặp dùng percentile CI của chênh lệch Qini; `segments.csv` chỉ là
score-sign diagnostic, không phải principal-stratum labels.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation import (
    auuc_score,
    bootstrap_ci,
    paired_bootstrap_difference_ci,
    qini_curve,
    qini_score,
)
from src.paths import OUTPUT_DIR

# thu tu hien thi + mau, tu don gian/thien lech -> tinh vi/robust
MODEL_ORDER = ["Response", "S-Learner", "T-Learner", "X-Learner", "DR-Learner", "Causal Forest"]
PALETTE = {"Response": "#7c879c", "S-Learner": "#c9a227", "T-Learner": "#b9691f",
           "X-Learner": "#0e7c7b", "DR-Learner": "#5b8def", "Causal Forest": "#b4483a"}
BASELINE_MODEL = "T-Learner"
SEG_EPS = 1e-4  # ngưỡng diagnostic cho dấu score; không phải principal strata


def slug(name):
    return name.lower().replace("-", "_").replace(" ", "_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cate_dir = OUTPUT_DIR / "legacy" / "first_run_scores"
    yt = np.load(OUTPUT_DIR / "holdout" / "final_test_yt.npz")
    Y_te, T_te = yt["Y"], yt["T"]
    frac, n_test = float(yt["frac"]), int(yt["n_test"])
    print(f"[load] holdout frac={frac} n_test={n_test:,}", flush=True)

    cates = {}
    for name in MODEL_ORDER:
        f = cate_dir / f"cate_{slug(name)}.npy"
        if f.exists():
            cates[name] = np.load(f)
            print(f"[load] {name:16s} <- {f.name}", flush=True)
        else:
            print(f"[skip] {name:16s} (chua co {f.name})", flush=True)

    if BASELINE_MODEL not in cates:
        raise SystemExit(
            f"Thieu {BASELINE_MODEL} — khong the tinh paired difference. "
            "Chay train_baselines.py truoc."
        )

    rows = []
    for name, cate in cates.items():
        q = qini_score(Y_te, T_te, cate)
        a = auuc_score(Y_te, T_te, cate)
        lb, ub = bootstrap_ci(Y_te, T_te, cate, n_boot=args.n_boot, seed=args.seed)
        if name == BASELINE_MODEL:
            comparison = None
        else:
            comparison = paired_bootstrap_difference_ci(
                cate,
                cates[BASELINE_MODEL],
                Y_te,
                T_te,
                n_boot=args.n_boot,
                seed=args.seed,
            )
        rows.append({
            "model": name, "qini_score": q, "qini_ci_low": lb, "qini_ci_high": ub,
            "auuc_score": a,
            "qini_delta_vs_t_learner": (
                np.nan if comparison is None else comparison["observed_difference"]
            ),
            "qini_delta_ci_low": (
                np.nan if comparison is None else comparison["ci_low"]
            ),
            "qini_delta_ci_high": (
                np.nan if comparison is None else comparison["ci_high"]
            ),
            "qini_ci_excludes_zero": bool((lb > 0) or (ub < 0)),
            "sample_frac": frac, "n_test": n_test,
        })
        delta_text = (
            "baseline"
            if comparison is None
            else (
                f"delta={comparison['observed_difference']:.4f} "
                f"CI=[{comparison['ci_low']:.4f},{comparison['ci_high']:.4f}]"
            )
        )
        print(
            f"[eval] {name:16s} qini={q:.4f} CI=[{lb:.4f},{ub:.4f}] "
            f"auuc={a:.4f} {delta_text}",
            flush=True,
        )

    result = pd.DataFrame(rows).sort_values(
        "model", key=lambda s: s.map({m: i for i, m in enumerate(MODEL_ORDER)})
    ).reset_index(drop=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUTPUT_DIR / "qini_comparison.csv"
    result.to_csv(out_csv, index=False)
    print(f"\n[write] {out_csv}", flush=True)
    print(result.to_string(index=False), flush=True)

    # Qini curve chong len nhau
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 6))
    for name in MODEL_ORDER:
        if name not in cates:
            continue
        curve = qini_curve(Y_te, T_te, cates[name])
        plt.plot(curve["n_targeted"], curve["qini"], label=name, color=PALETTE[name], linewidth=2)
    q_end = qini_curve(Y_te, T_te, cates[BASELINE_MODEL])["qini"].iloc[-1]
    plt.plot([0, n_test], [0, q_end], "--", color="#999", linewidth=1, label="Random targeting")
    plt.xlabel("So khach hang duoc nham toi (xep theo uplift giam dan)")
    plt.ylabel("Qini (so conversion tang them tich luy)")
    plt.title(f"Qini curve — {len(cates)} model (holdout {n_test:,}, sample {frac:.0%})")
    plt.legend()
    plt.tight_layout()
    out_png = OUTPUT_DIR / "qini_curve.png"
    plt.savefig(out_png, dpi=120)
    print(f"[write] {out_png}", flush=True)

    # Bảng diagnostic lịch sử; không dùng test để promote model hoặc gán principal strata.
    cate_result = result.loc[result["model"] != "Response"]
    if cate_result.empty:
        raise SystemExit("Không có CATE model để tạo score-sign diagnostic")
    best = cate_result.sort_values("qini_score", ascending=False).iloc[0]["model"]
    cate_best = cates[best]
    seg = pd.Series(
        np.where(
            cate_best > SEG_EPS,
            "Predicted positive effect",
            np.where(
                cate_best < -SEG_EPS,
                "Predicted negative effect",
                "Near-zero score",
            ),
        )
    )
    seg_tbl = pd.DataFrame({"segment": seg}).assign(cate=cate_best).groupby("segment").agg(
        pct_population=("segment", lambda s: round(100 * len(s) / len(seg), 2)),
        mean_cate=("cate", lambda s: round(float(s.mean()), 6)),
    ).reset_index()
    seg_tbl.insert(0, "best_model", best)
    out_seg = OUTPUT_DIR / "segments.csv"
    seg_tbl.to_csv(out_seg, index=False)
    print(f"[write] {out_seg}  (best model = {best})", flush=True)
    print(seg_tbl.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
