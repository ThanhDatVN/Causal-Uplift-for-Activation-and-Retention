"""So sánh candidate OOF, dựng ensemble và chốt shortlist cho retrospective confirmation.

Script chỉ đọc prediction out-of-fold đã lưu; nó không fit lại model gốc. Ensemble
weights được học trên chính OOF đó, và điểm ensemble dùng để so sánh là điểm
cross-fitted thêm một lớp nữa nên không lạc quan so với single model.

Confirmation Sprint 2 không được đọc ở bước này.
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

from src.ensemble import (
    causal_q_aggregation,
    cross_fitted_ensemble_score,
    doubly_robust_losses,
    rank_average_score,
)
from src.evaluation import auuc_score, qini_score
from src.paths import REPO_ROOT
from src.policy_evaluation import (
    dr_policy_value_curve,
    paired_policy_area_bootstrap,
    policy_area,
    policy_area_difference_summary,
)
from src.ranking_metrics import (
    paired_difference_summary,
    paired_rate_bootstrap,
    rate_score,
)

PROTOCOL_PATH = REPO_ROOT / "configs" / "sprint3_improvement_protocol.json"
RESERVED_KEYS = {
    "source_index",
    "treatment",
    "outcome",
    "dr_signal",
    "adjusted_signal",
    "mu0",
    "mu1",
}


def load_oof(run_dir: Path) -> dict:
    payload = np.load(run_dir / "oof_scores.npz")
    scores = {
        key: payload[key].astype("float64")
        for key in payload.files
        if key not in RESERVED_KEYS
    }
    return {
        "scores": scores,
        "dr_signal": payload["dr_signal"].astype("float64"),
        "adjusted_signal": payload["adjusted_signal"].astype("float64"),
        "treatment": payload["treatment"].astype("float64"),
        "outcome": payload["outcome"].astype("float64"),
        "source_index": payload["source_index"],
    }


def metric_row(
    name: str,
    score: np.ndarray,
    data: dict,
    budgets: np.ndarray,
    is_cate_scale: bool,
) -> dict:
    curve = dr_policy_value_curve(data["dr_signal"], score, budgets=budgets)
    adjusted = dr_policy_value_curve(
        data["adjusted_signal"],
        score,
        budgets=budgets,
    )
    return {
        "model": name,
        "policy_area_dr": policy_area(budgets, curve["gross_value_per_customer"]),
        "policy_area_dr_adjusted": policy_area(
            budgets,
            adjusted["gross_value_per_customer"],
        ),
        "autoc_dr": rate_score(data["dr_signal"], score, weighting="autoc"),
        "autoc_dr_adjusted": rate_score(
            data["adjusted_signal"],
            score,
            weighting="autoc",
        ),
        "rate_qini_dr": rate_score(data["dr_signal"], score, weighting="qini"),
        "qini_score": qini_score(data["outcome"], data["treatment"], score),
        "auuc_score": auuc_score(data["outcome"], data["treatment"], score),
        "is_cate_scale": is_cate_scale,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-dir",
        type=Path,
        action="append",
        required=True,
        help="Thư mục kết quả OOF; lặp lại tham số để so sánh nhiều fold seed.",
    )
    parser.add_argument("--n-boot", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shortlist-size", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    budgets = np.asarray(protocol["metrics"]["primary_budget_grid"], dtype="float64")
    cate_scale = {
        item["name"]: bool(item.get("is_cate_scale", True))
        for item in protocol["candidates"]
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    ensemble_report: dict[str, dict] = {}
    primary_dir = args.run_dir[0]

    for run_dir in args.run_dir:
        data = load_oof(run_dir)
        manifest = json.loads((run_dir / "run_manifest.json").read_text("utf-8"))
        tag = f"seed{manifest['fold_seed']}"
        print(f"[load] {run_dir} rows={len(data['dr_signal']):,} {tag}", flush=True)

        scores = dict(data["scores"])
        cate_models = {
            name: values
            for name, values in scores.items()
            if cate_scale.get(name, True)
        }
        if len(cate_models) >= 2:
            for method in ("causal_q_aggregation", "best_single_dr_risk"):
                result = cross_fitted_ensemble_score(
                    cate_models,
                    data["dr_signal"],
                    method=method,
                    n_splits=2,
                    seed=args.seed,
                )
                label = {
                    "causal_q_aggregation": "Ensemble-QAgg",
                    "best_single_dr_risk": "Ensemble-BestSingle",
                }[method]
                scores[label] = result["score"]
                cate_scale[label] = True
                ensemble_report[f"{label}@{tag}"] = {
                    "method": method,
                    "full_sample_weights": result["full_sample_weights"],
                    "fold_weights": result["fold_weights"],
                    "candidate_dr_losses": doubly_robust_losses(
                        cate_models,
                        data["dr_signal"],
                    ),
                }
        if len(scores) >= 2:
            rank_pool = {
                name: values
                for name, values in data["scores"].items()
                if name in cate_models or not cate_scale.get(name, True)
            }
            scores["Ensemble-RankAverage"] = rank_average_score(rank_pool)
            cate_scale["Ensemble-RankAverage"] = False
            ensemble_report[f"Ensemble-RankAverage@{tag}"] = {
                "method": "rank_average",
                "members": sorted(rank_pool),
                "note": (
                    "Heuristic thu hang; khong co bao dam ly thuyet cua "
                    "Q-aggregation. Gop duoc ca ranking score."
                ),
            }

        for name, score in scores.items():
            row = metric_row(
                name,
                score,
                data,
                budgets,
                cate_scale.get(name, True),
            )
            row["fold_seed"] = manifest["fold_seed"]
            row["pool_fraction"] = manifest["pool_fraction"]
            row["n_rows"] = len(score)
            all_rows.append(row)

        if run_dir == primary_dir:
            area_bootstrap = paired_policy_area_bootstrap(
                scores,
                data["dr_signal"],
                budgets=budgets,
                n_boot=args.n_boot,
                seed=args.seed,
            )
            rate_bootstrap = paired_rate_bootstrap(
                scores,
                data["dr_signal"],
                n_boot=args.n_boot,
                seed=args.seed,
            )
            comparison_rows = []
            for reference in ("Response", "X-Renormalized"):
                if reference not in scores:
                    continue
                for name in scores:
                    if name == reference:
                        continue
                    area = policy_area_difference_summary(
                        area_bootstrap,
                        name,
                        reference,
                    )
                    rate = paired_difference_summary(rate_bootstrap, name, reference)
                    comparison_rows.append(
                        {
                            "model_a": name,
                            "model_b": reference,
                            "fold_seed": manifest["fold_seed"],
                            "policy_area_difference": area["observed_difference"],
                            "policy_area_ci_low": area["ci_low"],
                            "policy_area_ci_high": area["ci_high"],
                            "policy_area_probability_positive": area[
                                "probability_difference_positive"
                            ],
                            "autoc_difference": rate["observed_difference"],
                            "autoc_ci_low": rate["ci_low"],
                            "autoc_ci_high": rate["ci_high"],
                            "n_boot": args.n_boot,
                        }
                    )
            pd.DataFrame(comparison_rows).to_csv(
                args.output_dir / "paired_comparisons.csv",
                index=False,
            )

    ranking = pd.DataFrame(all_rows)
    ranking.to_csv(args.output_dir / "candidate_ranking.csv", index=False)

    # Shortlist lấy trung bình policy_area_dr qua các fold seed đã chạy; model
    # chỉ có kết quả ở một seed vẫn được xét nhưng ghi rõ số seed.
    aggregate = (
        ranking.groupby("model")
        .agg(
            policy_area_dr_mean=("policy_area_dr", "mean"),
            policy_area_dr_min=("policy_area_dr", "min"),
            autoc_dr_mean=("autoc_dr", "mean"),
            qini_mean=("qini_score", "mean"),
            n_seeds=("fold_seed", "nunique"),
        )
        .sort_values("policy_area_dr_mean", ascending=False)
    )
    aggregate.to_csv(args.output_dir / "candidate_aggregate.csv")
    print(aggregate.to_string(), flush=True)

    reference_models = [
        name for name in ("Response", "X-Renormalized") if name in aggregate.index
    ]
    challengers = [
        name for name in aggregate.index if name not in reference_models
    ][: args.shortlist_size]
    shortlist = reference_models + challengers

    payload = {
        "protocol_id": protocol["protocol_id"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_dirs": [str(path) for path in args.run_dir],
        "budget_grid": budgets.tolist(),
        "n_boot": args.n_boot,
        "shortlist": shortlist,
        "reference_models": reference_models,
        "ranking_by_policy_area_dr": aggregate.index.tolist(),
        "ensembles": ensemble_report,
        "note": (
            "Shortlist duoc chot trước khi doc confirmation. Khong duoc them "
            "candidate sau khi xem ket qua confirmation."
        ),
    }
    (args.output_dir / "shortlist.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=float),
        encoding="utf-8",
    )
    print(f"[write] {args.output_dir}", flush=True)
    print(f"[shortlist] {shortlist}", flush=True)


if __name__ == "__main__":
    main()
