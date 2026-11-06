"""Locked-holdout benchmark for treatment-aware telecom retention decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split

from telco_churn.orange_data import (
    EXPECTED_CATEGORICAL,
    EXPECTED_MD5,
    EXPECTED_NUMERIC,
    FEATURE_COLUMNS,
    OPENML_ID,
    TARGET_COLUMN,
    TREATMENT_COLUMN,
    file_md5,
    load_orange,
)
from telco_churn.uplift import (
    ate_with_wald_interval,
    bootstrap_selected_effect,
    budget_table,
    cross_fit_potential_outcomes,
    curve_metrics,
    doubly_robust_scores,
    fit_policy_model,
    ipw_scores,
    required_sample_size,
    top_fraction_mask,
)

SEED = 20260914
CANDIDATES = (
    "risk_logistic",
    "risk_rf",
    "t_logistic",
    "t_rf",
    "s_hgb",
    "dr_hgb",
    "x_hgb",
)
BUDGETS = (0.10, 0.20, 0.30)


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value)}")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a small Markdown table without adding a runtime dependency."""
    columns = [str(column) for column in frame.columns]

    def clean(value: Any) -> str:
        if isinstance(value, float):
            rendered = f"{value:.6f}"
        else:
            rendered = str(value)
        return rendered.replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend(
        "| " + " | ".join(clean(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def make_locked_split(frame: pd.DataFrame, *, seed: int = SEED) -> pd.DataFrame:
    positions = np.arange(len(frame))
    joint = (
        frame[TREATMENT_COLUMN].astype(str) + "_" + frame[TARGET_COLUMN].astype(str)
    ).to_numpy()
    development, test = train_test_split(
        positions, test_size=0.20, random_state=seed, stratify=joint
    )
    split = np.full(len(frame), "development", dtype=object)
    split[test] = "test"
    manifest = pd.DataFrame(
        {
            "row_id": frame.index,
            "source_position": positions,
            "treatment": frame[TREATMENT_COLUMN].to_numpy(),
            "outcome": frame[TARGET_COLUMN].to_numpy(),
            "split": split,
            "seed": seed,
        }
    )
    assert len(development) + len(test) == len(frame)
    return manifest


def _manifest_sha256(manifest: pd.DataFrame) -> str:
    payload = manifest.to_csv(index=False, lineterminator="\n").encode()
    return hashlib.sha256(payload).hexdigest()


def balance_diagnostics(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    treated = frame[TREATMENT_COLUMN].eq(1)
    numeric_rows = []
    for column in EXPECTED_NUMERIC:
        x0 = frame.loc[~treated, column].astype(float)
        x1 = frame.loc[treated, column].astype(float)
        pooled = math.sqrt((x0.var(ddof=1) + x1.var(ddof=1)) / 2)
        smd = (x1.mean() - x0.mean()) / pooled if pooled else 0.0
        numeric_rows.append(
            {
                "feature": column,
                "control_mean": x0.mean(),
                "treated_mean": x1.mean(),
                "standardized_mean_difference": smd,
                "absolute_smd": abs(smd),
            }
        )
    categorical_rows = []
    for column in EXPECTED_CATEGORICAL:
        levels = sorted(frame[column].astype(str).unique())
        for level in levels:
            p0 = frame.loc[~treated, column].astype(str).eq(level).mean()
            p1 = frame.loc[treated, column].astype(str).eq(level).mean()
            categorical_rows.append(
                {
                    "feature": column,
                    "level": level,
                    "control_share": p0,
                    "treated_share": p1,
                    "absolute_share_difference": abs(p1 - p0),
                }
            )
    return pd.DataFrame(numeric_rows), pd.DataFrame(categorical_rows)


def _oof_scores(
    name: str,
    features: pd.DataFrame,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    propensity: float,
    folds: int,
    seed: int,
) -> np.ndarray:
    scores = np.zeros(len(features), dtype=float)
    joint = treatment * 2 + outcome
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for fold, (train, valid) in enumerate(splitter.split(features, joint)):
        fitted = fit_policy_model(
            name,
            features.iloc[train],
            treatment[train],
            outcome[train],
            propensity=propensity,
            seed=seed + 100 * fold,
        )
        scores[valid] = fitted.predict(features.iloc[valid])[0]
    return scores


def _random_scores(ids: np.ndarray, seed: int) -> np.ndarray:
    # Stable under row reordering: score is a hash of the immutable source row id.
    return np.array(
        [
            int.from_bytes(hashlib.sha256(f"{seed}:{row_id}".encode()).digest()[:8], "big") / 2**64
            for row_id in ids
        ]
    )


def _curve_points(score: np.ndarray, effect: np.ndarray, model: str) -> pd.DataFrame:
    order = np.argsort(-score, kind="stable")
    n = len(score)
    return pd.DataFrame(
        {
            "model": model,
            "targeted_fraction": np.arange(1, n + 1) / n,
            "cumulative_prevented_churn_per_customer": np.cumsum(effect[order]) / n,
        }
    )


def _plot_curves(curves: pd.DataFrame, path: Path, *, title: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for name, part in curves.groupby("model", sort=False):
        sampled = part.iloc[:: max(1, len(part) // 400)]
        ax.plot(
            sampled["targeted_fraction"],
            sampled["cumulative_prevented_churn_per_customer"],
            label=name,
            linewidth=1.6,
        )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(title=title, xlabel="Fraction contacted", ylabel="Estimated prevented churn / cohort")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _power_summary(frame: pd.DataFrame) -> dict[str, float | int | None]:
    ate = ate_with_wald_interval(
        frame[TARGET_COLUMN].to_numpy(), frame[TREATMENT_COLUMN].to_numpy()
    )
    q = float(frame[TREATMENT_COLUMN].mean())
    p0 = float(ate["control_churn_rate"])
    p1 = float(ate["treated_churn_rate"])
    variance_factor = p0 * (1 - p0) / (1 - q) + p1 * (1 - p1) / q
    mde = (1.959963984540054 + 0.8416212335729143) * math.sqrt(variance_factor / len(frame))
    observed = float(ate["ate_prevented_churn"])
    required_observed = required_sample_size(p0, p1, q, observed) if observed > 0 else None
    return {
        **ate,
        "treatment_fraction": q,
        "mde_80pct_power_two_sided_alpha_0_05": mde,
        "required_n_for_observed_effect_80pct_power": required_observed,
        "required_n_for_one_percentage_point_80pct_power": required_sample_size(p0, p1, q, 0.01),
    }


def _make_report(
    *,
    profile: dict[str, Any],
    oof_comparison: pd.DataFrame,
    oof_budget: pd.DataFrame,
    test_comparison: pd.DataFrame,
    locked: dict[str, Any],
    test_power: dict[str, Any],
) -> str:
    selected_test = test_comparison[
        (test_comparison["model"] == locked["model"])
        & (test_comparison["budget_fraction"] == locked["budget_fraction"])
    ].iloc[0]
    launch = locked["test_decision"] == "launch"
    required = profile["power"]["required_n_for_observed_effect_80pct_power"]
    required_text = f"{required:,}" if required is not None else "không xác định"
    return "\n".join(
        [
            "# Orange Belgium causal-retention benchmark",
            "",
            "## Kết luận quyết định",
            "",
            (
                "**LAUNCH**: policy vượt các cổng bằng chứng đã khóa trước."
                if launch
                else "**NO LAUNCH**: dữ liệu hiện tại chưa đủ bằng chứng để biện minh cho chiến dịch."
            ),
            "",
            f"Policy chọn hoàn toàn trên development OOF là `{locked['model']}` tại "
            f"{locked['budget_fraction']:.0%} capacity. Trên holdout: DR uplift "
            f"{selected_test['dr_uplift']:.3%} (bootstrap 95% CI "
            f"[{locked['test_ci95_low']:.3%}, {locked['test_ci95_high']:.3%}]); "
            f"IPW uplift {selected_test['ipw_uplift']:.3%} (95% CI "
            f"[{locked['test_ipw_ci95_low']:.3%}, {locked['test_ipw_ci95_high']:.3%}]); "
            f"số churn ngăn được ước lượng {selected_test['dr_incremental_churns_prevented']:.2f}. "
            "Đây là intention-to-treat estimate, không phải bằng chứng rằng mọi khách được gọi đều nhận ưu đãi.",
            "",
            "Cổng launch yêu cầu đồng thời: cả DR và IPW CI dưới > 0, Qini holdout > 0, mỗi arm trong "
            "nhóm chọn có ít nhất 20 churn event. Không được đổi model/budget sau khi xem holdout.",
            "",
            "## Tại sao classifier IBM không giải quyết bài toán này",
            "",
            "Risk model ước lượng `P(churn|X)`; retention policy cần `E[Y(0)-Y(1)|X]`. "
            "Người có rủi ro cao có thể vẫn rời mạng dù được gọi, còn người rủi ro vừa mới là người "
            "thay đổi hành vi vì treatment. Bảng dưới so sánh trực tiếp risk ranking và causal ranking "
            "trên cùng một randomized campaign.",
            "",
            "## Dữ liệu và signal-to-noise",
            "",
            f"OpenML {OPENML_ID}: {profile['rows']:,} mẫu, 178 feature ẩn danh, "
            f"treatment {profile['power']['treatment_fraction']:.2%}. Churn control "
            f"{profile['power']['control_churn_rate']:.3%}, treatment "
            f"{profile['power']['treated_churn_rate']:.3%}; ATE ngăn churn "
            f"{profile['power']['ate_prevented_churn']:.3%} (95% CI "
            f"[{profile['power']['ci95_low']:.3%}, {profile['power']['ci95_high']:.3%}]).",
            "",
            f"MDE ở 80% power là {profile['power']['mde_80pct_power_two_sided_alpha_0_05']:.3%}; "
            f"để phát hiện effect thô đang quan sát cần xấp xỉ {required_text} mẫu nếu tỷ lệ và "
            "phân bổ arm không đổi. Đây là lý do phải báo uncertainty thay vì chỉ báo AUUC.",
            "",
            "## OOF model selection (development only)",
            "",
            _markdown_table(oof_comparison),
            "",
            "## Development policy search",
            "",
            _markdown_table(oof_budget),
            "",
            "## Holdout — các model khác chỉ là exploratory",
            "",
            _markdown_table(test_comparison),
            "",
            "## Diễn giải kinh tế không bịa CLV",
            "",
            "Dataset không có margin, offer cost hay contact cost. Vì vậy repo không tạo ra một con số "
            "'profit' giả. Cột `break_even_contact_cost_per_value_unit` chính là uplift: nếu một churn "
            "được ngăn có giá trị V, contact cost tối đa để hòa vốn là `uplift × V`. Khi CI chứa 0, "
            "không tồn tại contact cost dương được bảo đảm bởi dữ liệu.",
            "",
            "## Giới hạn bắt buộc",
            "",
            "- Campaign chỉ randomize trong tập khách đã được churn model cũ chọn là high-risk; kết quả "
            "không ngoại suy cho toàn bộ customer base.",
            "- Public file gộp ba campaign Sep–Dec 2020 nhưng không có timestamp/campaign/customer ID; "
            "không thể temporal backtest, kiểm tra khách lặp lại hay interference.",
            "- Feature PCA/factor đều ẩn danh: dùng được để benchmark quyết định, không được gọi feature "
            "importance là nguyên nhân churn hay viết playbook nghiệp vụ từ chúng.",
            "- Outcome hiếm và treatment effect nhỏ; Qini/AUUC có phương sai lớn. Holdout duy nhất được "
            "giữ để đánh giá policy đã chọn, không dùng lại để tuning.",
            "",
            "## Artifact kiểm toán",
            "",
            "`split_manifest.csv`, OOF/test predictions, IPW và cross-fitted DR scores, bootstrap CI, "
            "balance tables và checksum đều được lưu trong thư mục này.",
            "",
            "## Holdout power snapshot",
            "",
            f"Holdout ATE: {test_power['ate_prevented_churn']:.3%}, 95% CI "
            f"[{test_power['ci95_low']:.3%}, {test_power['ci95_high']:.3%}].",
            "",
        ]
    )


def run_benchmark(
    data_path: Path,
    output_dir: Path,
    model_dir: Path,
    *,
    seed: int = SEED,
    quick: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures").mkdir(exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    frame = load_orange(data_path)
    manifest = make_locked_split(frame, seed=seed)
    manifest.to_csv(output_dir / "split_manifest.csv", index=False)
    split = manifest.set_index("row_id")["split"].reindex(frame.index)
    development = split.eq("development").to_numpy()
    test = split.eq("test").to_numpy()

    x = frame.loc[:, FEATURE_COLUMNS]
    t = frame[TREATMENT_COLUMN].to_numpy(dtype=int)
    y = frame[TARGET_COLUMN].to_numpy(dtype=int)
    ids = frame.index.to_numpy(dtype=str)
    propensity = float(t[development].mean())
    folds = 3 if quick else 5
    bootstrap_repeats = 500 if quick else 2_000

    numeric_balance, categorical_balance = balance_diagnostics(frame)
    numeric_balance.sort_values("absolute_smd", ascending=False).to_csv(
        output_dir / "balance_numeric.csv", index=False
    )
    categorical_balance.sort_values("absolute_share_difference", ascending=False).to_csv(
        output_dir / "balance_categorical.csv", index=False
    )

    x_dev = x.loc[development].reset_index(drop=True)
    t_dev = t[development]
    y_dev = y[development]
    ids_dev = ids[development]
    p0_oof, p1_oof = cross_fit_potential_outcomes(
        x_dev, t_dev, y_dev, folds=folds, seed=seed, kind="logistic"
    )
    dev_ipw = ipw_scores(y_dev, t_dev, propensity)
    dev_dr = doubly_robust_scores(y_dev, t_dev, p0_oof, p1_oof, propensity)

    candidate_scores: dict[str, np.ndarray] = {"random": _random_scores(ids_dev, seed)}
    for name in CANDIDATES:
        candidate_scores[name] = _oof_scores(
            name,
            x_dev,
            t_dev,
            y_dev,
            propensity=propensity,
            folds=folds,
            seed=seed,
        )

    comparison_rows = []
    budget_parts = []
    curve_parts = []
    for name, score in candidate_scores.items():
        ipw_curve = curve_metrics(score, dev_ipw)
        dr_curve = curve_metrics(score, dev_dr)
        comparison_rows.append(
            {
                "model": name,
                "qini_ipw": ipw_curve["qini"],
                "auuc_ipw": ipw_curve["auuc"],
                "qini_dr": dr_curve["qini"],
                "auuc_dr": dr_curve["auuc"],
            }
        )
        table = budget_table(score, ids_dev, y_dev, t_dev, dev_ipw, dev_dr, budgets=BUDGETS)
        table.insert(0, "model", name)
        for index, row in table.iterrows():
            mask = top_fraction_mask(score, ids_dev, float(row["budget_fraction"]))
            interval = bootstrap_selected_effect(
                mask, dev_dr, repeats=bootstrap_repeats, seed=seed + index
            )
            table.loc[index, "dr_ci95_low"] = interval["ci95_low"]
            table.loc[index, "dr_ci95_high"] = interval["ci95_high"]
        budget_parts.append(table)
        curve_parts.append(_curve_points(score, dev_dr, name))
    oof_comparison = pd.DataFrame(comparison_rows).sort_values("qini_dr", ascending=False)
    oof_budget = pd.concat(budget_parts, ignore_index=True)
    oof_comparison.to_csv(output_dir / "oof_model_comparison.csv", index=False)
    oof_budget.to_csv(output_dir / "oof_budget_metrics.csv", index=False)
    pd.DataFrame(
        {
            "row_id": ids_dev,
            "treatment": t_dev,
            "outcome": y_dev,
            "p0_nuisance_oof": p0_oof,
            "p1_nuisance_oof": p1_oof,
            "ipw_effect": dev_ipw,
            "dr_effect": dev_dr,
            **{f"score_{name}": score for name, score in candidate_scores.items()},
        }
    ).to_csv(output_dir / "oof_predictions.csv", index=False)
    development_curves = pd.concat(curve_parts, ignore_index=True)
    _plot_curves(
        development_curves,
        output_dir / "figures" / "development_uplift_curves.png",
        title="Development OOF doubly-robust uplift curves",
    )

    # Model and capacity are chosen without holdout access. Maximizing total estimated
    # prevented churn permits a smaller policy if marginal uplift turns negative.
    eligible = oof_budget[oof_budget["model"] != "random"].copy()
    selected_row = eligible.sort_values(
        ["dr_incremental_churns_prevented", "dr_ci95_low"], ascending=False
    ).iloc[0]
    selected_name = str(selected_row["model"])
    selected_budget = float(selected_row["budget_fraction"])

    x_test = x.loc[test].reset_index(drop=True)
    t_test = t[test]
    y_test = y[test]
    ids_test = ids[test]
    # Both nuisance models are trained on development data only. They are used to
    # build a lower-variance DR evaluation score, never to fit against test outcomes.
    common_t = fit_policy_model(
        "t_logistic", x_dev, t_dev, y_dev, propensity=propensity, seed=seed + 9_100
    )
    common_0 = common_t.model_0
    common_1 = common_t.model_1
    if common_0 is None or common_1 is None:
        raise RuntimeError("Failed to fit common holdout nuisance models")
    p0_test = common_0.predict_proba(x_test)[:, 1]
    p1_test = common_1.predict_proba(x_test)[:, 1]
    test_ipw = ipw_scores(y_test, t_test, propensity)
    test_dr = doubly_robust_scores(y_test, t_test, p0_test, p1_test, propensity)

    fitted_models = {}
    test_scores: dict[str, np.ndarray] = {"random": _random_scores(ids_test, seed)}
    test_p0: dict[str, np.ndarray] = {"random": np.full(len(x_test), y_dev[t_dev == 0].mean())}
    test_p1: dict[str, np.ndarray] = {"random": np.full(len(x_test), y_dev[t_dev == 1].mean())}
    for name in CANDIDATES:
        fitted = fit_policy_model(name, x_dev, t_dev, y_dev, propensity=propensity, seed=seed)
        fitted_models[name] = fitted
        score, p0, p1 = fitted.predict(x_test)
        test_scores[name] = score
        test_p0[name] = p0
        test_p1[name] = p1

    test_rows = []
    test_curves = []
    for name, score in test_scores.items():
        curve = curve_metrics(score, test_dr)
        factual_probability = np.where(
            t_test == 1,
            np.where(np.isnan(test_p1[name]), test_p0[name], test_p1[name]),
            test_p0[name],
        )
        probability_metrics = {
            "factual_average_precision": average_precision_score(y_test, factual_probability),
            "factual_roc_auc": roc_auc_score(y_test, factual_probability),
            "factual_brier": brier_score_loss(y_test, factual_probability),
        }
        table = budget_table(score, ids_test, y_test, t_test, test_ipw, test_dr, budgets=BUDGETS)
        for _, row in table.iterrows():
            test_rows.append(
                {
                    "model": name,
                    **curve,
                    **probability_metrics,
                    **row.to_dict(),
                }
            )
        test_curves.append(_curve_points(score, test_dr, name))
    test_comparison = pd.DataFrame(test_rows)
    test_comparison.to_csv(output_dir / "holdout_exploratory_metrics.csv", index=False)
    _plot_curves(
        pd.concat(test_curves, ignore_index=True),
        output_dir / "figures" / "holdout_uplift_curves.png",
        title="Holdout doubly-robust uplift curves (exploratory except locked policy)",
    )

    locked_score = test_scores[selected_name]
    locked_mask = top_fraction_mask(locked_score, ids_test, selected_budget)
    locked_interval = bootstrap_selected_effect(
        locked_mask, test_dr, repeats=bootstrap_repeats, seed=seed + 20_000
    )
    locked_ipw_interval = bootstrap_selected_effect(
        locked_mask, test_ipw, repeats=bootstrap_repeats, seed=seed + 21_000
    )
    locked_curve = curve_metrics(locked_score, test_dr)
    control_events = int(np.sum(y_test[locked_mask & (t_test == 0)]))
    treated_events = int(np.sum(y_test[locked_mask & (t_test == 1)]))
    gates = {
        "positive_dr_ci_lower": locked_interval["ci95_low"] > 0,
        "positive_ipw_ci_lower": locked_ipw_interval["ci95_low"] > 0,
        "positive_qini": locked_curve["qini"] > 0,
        "at_least_20_control_churn_events": control_events >= 20,
        "at_least_20_treated_churn_events": treated_events >= 20,
    }
    locked = {
        "model": selected_name,
        "budget_fraction": selected_budget,
        "selected_on": "development OOF only",
        "development_dr_incremental_churns_prevented": float(
            selected_row["dr_incremental_churns_prevented"]
        ),
        "test_dr_uplift": locked_interval["estimate"],
        "test_ci95_low": locked_interval["ci95_low"],
        "test_ci95_high": locked_interval["ci95_high"],
        "test_ipw_uplift": locked_ipw_interval["estimate"],
        "test_ipw_ci95_low": locked_ipw_interval["ci95_low"],
        "test_ipw_ci95_high": locked_ipw_interval["ci95_high"],
        "test_qini_dr": locked_curve["qini"],
        "selected_control_churn_events": control_events,
        "selected_treated_churn_events": treated_events,
        "gates": gates,
        "test_decision": "launch" if all(gates.values()) else "no_launch",
    }
    _write_json(output_dir / "locked_policy_decision.json", locked)

    pd.DataFrame(
        {
            "row_id": ids_test,
            "treatment": t_test,
            "outcome": y_test,
            "p0_nuisance": p0_test,
            "p1_nuisance": p1_test,
            "ipw_effect": test_ipw,
            "dr_effect": test_dr,
            "locked_selected": locked_mask.astype(int),
            **{f"score_{name}": score for name, score in test_scores.items()},
        }
    ).to_csv(output_dir / "holdout_predictions.csv", index=False)

    profile = {
        "openml_id": OPENML_ID,
        "raw_md5": file_md5(data_path),
        "expected_md5": EXPECTED_MD5,
        "rows": len(frame),
        "numeric_features": len(EXPECTED_NUMERIC),
        "categorical_features": len(EXPECTED_CATEGORICAL),
        "duplicate_rows": int(frame.duplicated().sum()),
        "missing_cells": int(frame.isna().sum().sum()),
        "manifest_sha256": _manifest_sha256(manifest),
        "seed": seed,
        "development_rows": int(development.sum()),
        "test_rows": int(test.sum()),
        "max_absolute_numeric_smd": float(numeric_balance["absolute_smd"].max()),
        "max_absolute_categorical_share_difference": float(
            categorical_balance["absolute_share_difference"].max()
        ),
        "power": _power_summary(frame),
    }
    test_power = _power_summary(frame.loc[test])
    _write_json(output_dir / "data_profile.json", profile)

    bundle = {
        "model": fitted_models[selected_name],
        "model_name": selected_name,
        "budget_fraction": selected_budget,
        "feature_columns": list(FEATURE_COLUMNS),
        "score_semantics": "estimated E[churn_without_offer - churn_with_offer | X]",
        "training_propensity": propensity,
        "decision": locked["test_decision"],
        "raw_md5": EXPECTED_MD5,
    }
    joblib.dump(bundle, model_dir / "orange_retention_policy.joblib")
    report = _make_report(
        profile=profile,
        oof_comparison=oof_comparison,
        oof_budget=oof_budget,
        test_comparison=test_comparison,
        locked=locked,
        test_power=test_power,
    )
    (output_dir / "CAUSAL_BENCHMARK_REPORT.md").write_text(report, encoding="utf-8")
    return {"profile": profile, "locked": locked}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/raw/churn-uplift-mlg.arff"))
    parser.add_argument("--output", type=Path, default=Path("reports/uplift"))
    parser.add_argument("--model-dir", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.data, args.output, args.model_dir, seed=args.seed, quick=args.quick)
    print(json.dumps(result["locked"], indent=2, default=_json_default))


if __name__ == "__main__":
    main()
