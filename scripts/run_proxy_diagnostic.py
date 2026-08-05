"""Chạy chẩn đoán proxy-ordering trên OOF prediction đã có.

Trả lời câu hỏi mà ba sprint đặt ra nhưng chưa có công cụ: **khi nào Response
ngừng xếp hạng đúng?** Xem `src/proxy_diagnostic.py` cho ranh giới nguồn của
từng phần.

Script chỉ đọc artifact có sẵn; không fit lại model nào.
"""

from __future__ import annotations

import argparse
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

from src.paths import OUTPUT_DIR
from src.proxy_diagnostic import (
    ordering_condition_by_budget,
    proxy_rank_agreement,
    unbiased_ordering_condition,
)

RESERVED = {
    "source_index",
    "treatment",
    "outcome",
    "dr_signal",
    "adjusted_signal",
    "mu0",
    "mu1",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oof-file",
        type=Path,
        default=OUTPUT_DIR / "improvement" / "finalist" / "oof_scores.npz",
    )
    parser.add_argument("--proxy", default="Response")
    parser.add_argument(
        "--max-cate-bound",
        type=float,
        default=None,
        help=(
            "Chan tren cua CATE lon nhat. Bo trong de lay max cua plug-in tau "
            "(mu1 - mu0) quan sat duoc, lam mot lua chon bao thu co the tai lap."
        ),
    )
    parser.add_argument("--sample-size", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR / "improvement" / "proxy_diagnostic",
    )
    args = parser.parse_args()

    if not args.oof_file.exists():
        raise FileNotFoundError(f"Thiếu OOF artifact: {args.oof_file}")
    payload = np.load(args.oof_file)
    if args.proxy not in payload.files:
        raise KeyError(
            f"Không có proxy {args.proxy!r} trong artifact; có "
            f"{sorted(set(payload.files) - RESERVED)}"
        )

    mu0 = payload["mu0"].astype("float64")
    mu1 = payload["mu1"].astype("float64")
    proxy = payload[args.proxy].astype("float64")
    plugin_tau = mu1 - mu0
    beta_max = (
        float(args.max_cate_bound)
        if args.max_cate_bound is not None
        else float(np.max(plugin_tau))
    )
    beta_source = (
        "nguoi dung nhap"
        if args.max_cate_bound is not None
        else "max cua plug-in tau = mu1 - mu0 tren development OOF"
    )
    print(f"[input] n={len(mu0):,} proxy={args.proxy}", flush=True)
    print(
        f"[input] beta_max={beta_max:.6f} ({beta_source})",
        flush=True,
    )

    global_condition = unbiased_ordering_condition(mu0, beta_max)
    print(
        f"[global] theta_max={global_condition.theta_max:.6f} "
        f"threshold={global_condition.threshold:.6f} "
        f"holds={global_condition.holds}",
        flush=True,
    )

    budget_rows = ordering_condition_by_budget(mu0, proxy, beta_max)
    budget_frame = pd.DataFrame(budget_rows)
    print(
        budget_frame[
            ["budget_fraction", "n_targeted", "theta_max", "threshold", "holds"]
        ].to_string(index=False),
        flush=True,
    )

    cate_models = {
        name: payload[name].astype("float64")
        for name in payload.files
        if name not in RESERVED and name != args.proxy
    }
    cate_models["plugin_tau (mu1 - mu0)"] = plugin_tau
    agreement = pd.DataFrame(
        proxy_rank_agreement(
            proxy,
            cate_models,
            sample_size=args.sample_size,
            seed=args.seed,
        )
    ).sort_values("spearman_rho", ascending=False)
    print(agreement.to_string(index=False), flush=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    budget_frame.to_csv(
        args.output_dir / "ordering_condition_by_budget.csv",
        index=False,
    )
    agreement.to_csv(args.output_dir / "proxy_rank_agreement.csv", index=False)

    baseline_quantiles = {
        f"q{q}": float(np.quantile(mu0, q))
        for q in (0.5, 0.9, 0.99, 0.999, 0.9999, 1.0)
    }
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "oof_file": str(args.oof_file),
        "proxy": args.proxy,
        "n": int(len(mu0)),
        "beta_max": beta_max,
        "beta_max_source": beta_source,
        "global_condition": global_condition.as_dict(),
        "baseline_probability_quantiles": baseline_quantiles,
        "by_budget": budget_rows,
        "rank_agreement": agreement.to_dict(orient="records"),
        "source_note": (
            "Bat dang thuc theta_max < (1 - beta_max)/2 lay tu Fernandez-Loria & "
            "Loria, arXiv 2206.12532 v7. Day la dieu kien DU, khong phai dieu "
            "kien CAN: dieu kien hong khong ket luan proxy xep hang sai."
        ),
        "extension_note": (
            "Bang theo budget la cach van dung cua repo, ap dung bat dang thuc "
            "goc cho tung sub-population top-b. Paper phat bieu cho toan "
            "population; mo rong nay chua duoc nguon chung minh."
        ),
        "not_implemented": (
            "Dieu kien subset cua paper co bien tau_k khong duoc dinh nghia du ro "
            "trong ban trich xuat nen khong hien thuc."
        ),
    }
    (args.output_dir / "proxy_diagnostic_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=float),
        encoding="utf-8",
    )
    print(f"[write] {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
