"""Learning curve ba stage Causal Forest, bổ sung cho `evaluate_causal_forest.py`.

Phân công giữa hai script, cố ý không chồng nhau:

| Việc | Script |
|---|---|
| Chấm điểm **một** stage, so với 5 model release, paired bootstrap | `evaluate_causal_forest.py` |
| Learning curve **ba** stage, phân bố điểm, tài nguyên | script này |

Script kia là nguồn sự thật duy nhất cho bảng so sánh release; script này **không** tính
lại các số đó, chỉ đọc lại từ artifact nó ghi ra. Hai nguồn cho cùng một con số là cách
chắc chắn nhất để chúng lệch nhau về sau.

Không cần nạp Criteo: `holdout_test_yt.npz` đã mang sẵn ``Y`` và ``T``, còn IPW signal
chỉ cần thêm tỷ lệ treatment ước lượng từ chính holdout — hợp lệ vì Criteo là randomized
design.

**Giới hạn.** Chỉ stage 50% có holdout trùng final test Sprint 1. Qini của stage 20% và
30% đọc theo chiều học, không đặt cạnh bảng release được. Script tự kiểm bằng cách so
``Y``/``T`` với holdout release và ghi kết quả vào cột ``comparable_to_release``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.evaluation import auuc_score, qini_score
from src.policy_evaluation import DEFAULT_BUDGET_GRID, dr_policy_value_curve, policy_area_from_scores
from src.ranking_metrics import autoc_score

REPO = Path(__file__).resolve().parent.parent
CF_DIR = REPO / "output" / "causal_forest"
RELEASE_CATE = REPO / "output" / "optimization" / "cate"
RELEASE_HOLDOUT = REPO / "output" / "holdout" / "final_test_yt.npz"
SCORE_NAME = "cate_causal_forest_kaggle_safe.npy"
STAGES = ("0p2", "0p3", "0p5")

# Tên hiển thị cố định, để màu trong biểu đồ bám theo model chứ không theo thứ hạng.
DISPLAY = {
    "response": "Response",
    "s_learner": "S-Learner",
    "x_learner": "X-Learner",
    "dr_learner": "DR-Learner",
    "t_learner": "T-Learner",
}


def load_stage(slug: str):
    stage = CF_DIR / f"preflight_{slug}"
    holdout = np.load(stage / "holdout_test_yt.npz")
    score = np.load(stage / SCORE_NAME).ravel()
    manifest = json.loads((stage / "gate_manifest.json").read_text(encoding="utf-8"))
    y = holdout["Y"].astype(np.int8)
    t = holdout["T"].astype(np.int8)
    if score.size != y.size:
        raise ValueError(f"{slug}: score {score.size:,} khác holdout {y.size:,}")
    return y, t, score, manifest


def is_release_holdout(y: np.ndarray, t: np.ndarray) -> bool:
    if not RELEASE_HOLDOUT.exists():
        return False
    ref = np.load(RELEASE_HOLDOUT)
    ry, rt = ref["Y"].astype(np.int8), ref["T"].astype(np.int8)
    return y.shape == ry.shape and np.array_equal(y, ry) and np.array_equal(t, rt)


def ipw_signal(y: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Transformed outcome với propensity hằng số ước lượng từ chính holdout."""
    p = float(t.mean())
    return y * (t - p) / (p * (1.0 - p))


def _log_lines(slug: str) -> list[str]:
    return (CF_DIR / f"preflight_{slug}" / "train.log").read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()


def fit_seconds(slug: str) -> float:
    for line in _log_lines(slug):
        if "[fit] done fit_time=" in line:
            return float(line.split("fit_time=")[1].rstrip("s").strip())
    return float("nan")


def n_train(slug: str) -> int:
    """Số dòng train, đọc thẳng từ log thay vì suy ra từ fraction."""
    for line in _log_lines(slug):
        if line.startswith("[split]") and "train=" in line:
            return int(line.split("train=")[1].split()[0].replace(",", ""))
    return -1


def stage_row(slug: str) -> dict:
    y, t, score, manifest = load_stage(slug)
    signal = ipw_signal(y, t)
    runtime = manifest["runtime"]
    return {
        "stage": slug,
        "fraction": manifest["fraction"],
        "n_train": n_train(slug),
        "n_holdout": int(y.size),
        "comparable_to_release": is_release_holdout(y, t),
        "qini": qini_score(y, t, score),
        "auuc": auuc_score(y, t, score),
        "autoc_ipw": autoc_score(signal, score),
        "policy_area_ipw": policy_area_from_scores(signal, score, DEFAULT_BUDGET_GRID),
        "observed_ate": float(y[t == 1].mean() - y[t == 0].mean()),
        "score_mean": float(score.mean()),
        "score_std": float(score.std()),
        "score_p01": float(np.percentile(score, 1)),
        "score_p50": float(np.percentile(score, 50)),
        "score_p99": float(np.percentile(score, 99)),
        "score_unique": int(np.unique(score).size),
        "score_negative_fraction": float((score < 0).mean()),
        "peak_rss_gb": runtime["peak_process_tree_rss_gb"],
        "peak_ram_fraction": runtime["peak_process_tree_ram_fraction"],
        "wall_seconds": runtime["wall_seconds"],
        "fit_seconds": fit_seconds(slug),
    }


def budget_curves() -> pd.DataFrame:
    """Đường gross policy value theo ngân sách.

    Gồm ba stage Causal Forest, cộng năm model release đánh giá trên **cùng** holdout
    stage 50% — để biểu đồ so được Causal Forest với champion trên một trục duy nhất.
    """
    rows = []
    for slug in STAGES:
        y, t, score, _ = load_stage(slug)
        curve = dr_policy_value_curve(ipw_signal(y, t), score, DEFAULT_BUDGET_GRID)
        for budget, value in zip(curve["budget_fraction"], curve["gross_value_per_customer"]):
            rows.append(
                {
                    "series": "Causal Forest",
                    "stage": slug,
                    "budget": float(budget),
                    "policy_value": float(value),
                }
            )

    y, t, _, _ = load_stage("0p5")
    if is_release_holdout(y, t):
        signal = ipw_signal(y, t)
        for path in sorted(RELEASE_CATE.glob("*_sprint1_release.npy")):
            name = DISPLAY[path.stem.replace("cate_", "").replace("_sprint1_release", "")]
            curve = dr_policy_value_curve(signal, np.load(path).ravel(), DEFAULT_BUDGET_GRID)
            for budget, value in zip(curve["budget_fraction"], curve["gross_value_per_customer"]):
                rows.append(
                    {
                        "series": name,
                        "stage": "0p5",
                        "budget": float(budget),
                        "policy_value": float(value),
                    }
                )
    return pd.DataFrame(rows)


def score_histogram(bins: int) -> pd.DataFrame:
    """Histogram điểm CATE dùng chung mép bin, để ba stage chồng lên nhau so được."""
    scores = {slug: load_stage(slug)[2] for slug in STAGES}
    lo = min(float(np.percentile(s, 0.5)) for s in scores.values())
    hi = max(float(np.percentile(s, 99.5)) for s in scores.values())
    edges = np.linspace(lo, hi, bins + 1)
    rows = []
    for slug, score in scores.items():
        density, _ = np.histogram(score, bins=edges, density=True)
        for left, right, value in zip(edges[:-1], edges[1:], density):
            rows.append(
                {
                    "stage": slug,
                    "bin_left": float(left),
                    "bin_right": float(right),
                    "bin_mid": float((left + right) / 2),
                    "density": float(value),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bins", type=int, default=60)
    parser.add_argument("--output-dir", type=Path, default=CF_DIR / "analysis")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    curve = pd.DataFrame([stage_row(s) for s in STAGES])
    print("=== Learning curve ba stage ===", flush=True)
    print(
        curve[
            [
                "stage", "fraction", "n_holdout", "comparable_to_release",
                "qini", "policy_area_ipw", "autoc_ipw", "score_unique",
            ]
        ].to_string(index=False),
        flush=True,
    )
    print(flush=True)
    print("=== Tài nguyên ===", flush=True)
    print(
        curve[["stage", "peak_rss_gb", "peak_ram_fraction", "fit_seconds", "wall_seconds"]]
        .to_string(index=False),
        flush=True,
    )

    curve.to_csv(args.output_dir / "learning_curve.csv", index=False)
    budget_curves().to_csv(args.output_dir / "budget_value_curve.csv", index=False)
    score_histogram(args.bins).to_csv(args.output_dir / "score_histogram.csv", index=False)

    summary = {
        "generated_from": "output/causal_forest/preflight_{0p2,0p3,0p5}",
        "signal": "ipw_constant_propensity",
        "release_comparison_source": "output/causal_forest/release/ (evaluate_causal_forest.py)",
        "stages_comparable_to_release": curve.loc[
            curve["comparable_to_release"], "stage"
        ].tolist(),
        "score_degenerate": bool(curve["score_unique"].min() <= 10),
        "min_unique_scores": int(curve["score_unique"].min()),
        "limitations": [
            "Chỉ stage 50% so được với bảng release; 20% và 30% dùng holdout khác.",
            "Signal là IPW với propensity hằng số, không phải DR.",
            "Profile kaggle-safe đặt inference=False nên không có khoảng tin cậy cá nhân.",
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(flush=True)
    print(f"[write] {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
