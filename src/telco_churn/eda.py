"""Reproducible exploratory data analysis for the IBM Telco sample.

The module deliberately stops before train/test splitting or model fitting. Its outputs are
descriptive evidence and modeling hypotheses, not causal retention recommendations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.stats import chi2_contingency

EXPECTED_COLUMNS = [
    "customerID",
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "tenure",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
    "MonthlyCharges",
    "TotalCharges",
    "Churn",
]

KEY_CATEGORICAL = [
    "gender",
    "SeniorCitizen",
    "Partner",
    "Dependents",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
]

TENURE_LABELS = ["0-6", "7-12", "13-24", "25-48", "49-72"]
SOURCE_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_and_clean(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_csv(path, dtype={"TotalCharges": "string"})
    missing_columns = sorted(set(EXPECTED_COLUMNS) - set(raw.columns))
    unexpected_columns = sorted(set(raw.columns) - set(EXPECTED_COLUMNS))
    if missing_columns or unexpected_columns:
        raise ValueError(
            f"Schema mismatch; missing={missing_columns}, unexpected={unexpected_columns}"
        )

    data = raw.copy()
    blank_total_charges = data["TotalCharges"].fillna("").str.strip().eq("")
    data["TotalCharges"] = pd.to_numeric(data["TotalCharges"], errors="coerce")
    invalid_numeric_total_charges = int(data["TotalCharges"].isna().sum())
    data["churn_flag"] = data["Churn"].map({"No": 0, "Yes": 1})
    if data["churn_flag"].isna().any():
        raise ValueError("Churn contains values outside {'No', 'Yes'}")

    quality = {
        "rows": len(data),
        "columns_raw": len(raw.columns),
        "sha256": sha256_file(path),
        "source_url": SOURCE_URL,
        "duplicate_rows": int(raw.duplicated().sum()),
        "duplicate_customer_ids": int(raw["customerID"].duplicated().sum()),
        "blank_total_charges": int(blank_total_charges.sum()),
        "numeric_missing_total_charges_after_parse": invalid_numeric_total_charges,
        "blank_total_charges_with_tenure_zero": int(
            (blank_total_charges & data["tenure"].eq(0)).sum()
        ),
        "invalid_churn_labels": int(data["churn_flag"].isna().sum()),
        "tenure_min": int(data["tenure"].min()),
        "tenure_max": int(data["tenure"].max()),
        "monthly_charges_min": float(data["MonthlyCharges"].min()),
        "monthly_charges_max": float(data["MonthlyCharges"].max()),
        "negative_total_charges": int(data["TotalCharges"].lt(0).sum()),
        "phone_service_structural_inconsistencies": int(
            (data["PhoneService"].eq("No") & ~data["MultipleLines"].eq("No phone service")).sum()
        ),
    }

    internet_addons = [
        "OnlineSecurity",
        "OnlineBackup",
        "DeviceProtection",
        "TechSupport",
        "StreamingTV",
        "StreamingMovies",
    ]
    no_internet = data["InternetService"].eq("No")
    internet_inconsistency = pd.Series(False, index=data.index)
    for column in internet_addons:
        internet_inconsistency |= no_internet & ~data[column].eq("No internet service")
    quality["internet_service_structural_inconsistencies"] = int(internet_inconsistency.sum())

    return data, quality


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (math.nan, math.nan)
    p = successes / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    half_width = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator
    return center - half_width, center + half_width


def categorical_summary(data: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for feature in KEY_CATEGORICAL:
        grouped = (
            data.groupby(feature, dropna=False, observed=True)["churn_flag"]
            .agg(["size", "sum", "mean"])
            .reset_index()
            .rename(
                columns={
                    feature: "level",
                    "size": "n",
                    "sum": "churners",
                    "mean": "churn_rate",
                }
            )
        )
        intervals = [wilson_interval(int(row.churners), int(row.n)) for row in grouped.itertuples()]
        grouped["ci95_low"] = [item[0] for item in intervals]
        grouped["ci95_high"] = [item[1] for item in intervals]
        contingency = pd.crosstab(data[feature], data["churn_flag"])
        chi2, p_value, _, _ = chi2_contingency(contingency)
        n = contingency.to_numpy().sum()
        minimum_dimension = min(contingency.shape) - 1
        cramers_v = math.sqrt(chi2 / (n * minimum_dimension)) if minimum_dimension else 0.0
        grouped.insert(0, "feature", feature)
        grouped["chi2_p_value"] = p_value
        grouped["cramers_v"] = cramers_v
        frames.append(grouped)
    result = pd.concat(frames, ignore_index=True)
    feature_tests = result[["feature", "chi2_p_value"]].drop_duplicates().copy()
    feature_tests = feature_tests.sort_values("chi2_p_value")
    test_count = len(feature_tests)
    raw_adjusted = (
        feature_tests["chi2_p_value"].to_numpy() * test_count / np.arange(1, test_count + 1)
    )
    feature_tests["chi2_q_value_bh"] = np.minimum.accumulate(raw_adjusted[::-1])[::-1].clip(max=1.0)
    return result.merge(feature_tests[["feature", "chi2_q_value_bh"]], on="feature")


def schema_profile(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in EXPECTED_COLUMNS:
        series = data[column]
        non_null = series.dropna()
        rows.append(
            {
                "column": column,
                "dtype_after_load": str(series.dtype),
                "non_null": int(series.notna().sum()),
                "missing": int(series.isna().sum()),
                "unique_non_null": int(series.nunique(dropna=True)),
                "min": non_null.min() if pd.api.types.is_numeric_dtype(series) else "",
                "max": non_null.max() if pd.api.types.is_numeric_dtype(series) else "",
                "sample_values": " | ".join(map(str, non_null.drop_duplicates().head(5))),
            }
        )
    return pd.DataFrame(rows)


def numeric_summary(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature in ["tenure", "MonthlyCharges", "TotalCharges"]:
        no = data.loc[data["churn_flag"].eq(0), feature].dropna()
        yes = data.loc[data["churn_flag"].eq(1), feature].dropna()
        pooled_sd = math.sqrt((no.var(ddof=1) + yes.var(ddof=1)) / 2)
        standardized_difference = (yes.mean() - no.mean()) / pooled_sd if pooled_sd else math.nan
        rows.append(
            {
                "feature": feature,
                "non_churn_n": int(no.size),
                "non_churn_mean": float(no.mean()),
                "non_churn_median": float(no.median()),
                "churn_n": int(yes.size),
                "churn_mean": float(yes.mean()),
                "churn_median": float(yes.median()),
                "standardized_mean_difference_churn_minus_non_churn": float(
                    standardized_difference
                ),
            }
        )
    return pd.DataFrame(rows)


def cohort_summary(data: pd.DataFrame) -> pd.DataFrame:
    working = data.copy()
    working["tenure_cohort"] = pd.cut(
        working["tenure"],
        bins=[-0.001, 6, 12, 24, 48, 72],
        labels=TENURE_LABELS,
        include_lowest=True,
    )
    return (
        working.groupby(["tenure_cohort", "Contract"], observed=True)["churn_flag"]
        .agg(n="size", churners="sum", churn_rate="mean")
        .reset_index()
    )


def write_plots(
    data: pd.DataFrame, categorical: pd.DataFrame, cohorts: pd.DataFrame, output_dir: Path
) -> None:
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    counts = data["Churn"].value_counts().reindex(["No", "Yes"])
    figure, axis = plt.subplots(figsize=(6.4, 4.2))
    bars = axis.bar(counts.index, counts.values, color=["#6b7280", "#b45309"])
    axis.set(title="Churn prevalence", xlabel="Observed label", ylabel="Customers")
    axis.bar_label(bars, labels=[f"{value:,}" for value in counts.values], padding=3)
    figure.tight_layout()
    figure.savefig(figure_dir / "target_prevalence.png", dpi=160)
    plt.close(figure)

    selected = categorical[
        categorical["feature"].isin(["Contract", "InternetService", "PaymentMethod"])
    ]
    labels = selected["feature"] + " · " + selected["level"].astype(str)
    order = np.argsort(selected["churn_rate"].to_numpy())
    figure, axis = plt.subplots(figsize=(9, 6.5))
    axis.barh(
        labels.iloc[order],
        selected["churn_rate"].iloc[order],
        color="#2563eb",
        alpha=0.82,
    )
    axis.set(title="Observed churn rate in key segments", xlabel="Churn rate", ylabel="")
    axis.xaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    figure.tight_layout()
    figure.savefig(figure_dir / "key_segment_churn_rates.png", dpi=160)
    plt.close(figure)

    pivot = cohorts.pivot(index="tenure_cohort", columns="Contract", values="churn_rate")
    pivot = pivot.reindex(index=TENURE_LABELS)
    counts = cohorts.pivot(index="tenure_cohort", columns="Contract", values="n")
    counts = counts.reindex(index=TENURE_LABELS, columns=pivot.columns)
    figure, axis = plt.subplots(figsize=(8.2, 4.8))
    image = axis.imshow(pivot.to_numpy(), aspect="auto", cmap="Blues", vmin=0, vmax=0.65)
    axis.set_xticks(range(len(pivot.columns)), labels=pivot.columns, rotation=15, ha="right")
    axis.set_yticks(range(len(pivot.index)), labels=pivot.index)
    axis.set(title="Churn rate by tenure cohort and contract", xlabel="Contract", ylabel="Tenure")
    for row in range(pivot.shape[0]):
        for column in range(pivot.shape[1]):
            value = pivot.iloc[row, column]
            if pd.notna(value):
                axis.text(
                    column,
                    row,
                    f"{value:.1%}\n(n={int(counts.iloc[row, column]):,})",
                    ha="center",
                    va="center",
                    fontsize=9,
                )
    figure.colorbar(image, ax=axis, label="Churn rate")
    figure.tight_layout()
    figure.savefig(figure_dir / "tenure_contract_heatmap.png", dpi=160)
    plt.close(figure)


def build_markdown_report(
    quality: dict[str, Any],
    categorical: pd.DataFrame,
    numeric: pd.DataFrame,
    cohorts: pd.DataFrame,
) -> str:
    overall_churners = int(quality["churners"])
    overall_rows = int(quality["rows"])
    top_levels = categorical.sort_values("churn_rate", ascending=False).head(5)
    strongest_features = (
        categorical[["feature", "cramers_v"]]
        .drop_duplicates()
        .sort_values("cramers_v", ascending=False)
        .head(5)
    )

    def pct(value: float) -> str:
        return f"{value:.1%}"

    lines = [
        "# EDA Report — IBM Telco Customer Churn",
        "",
        "> Trạng thái: hoàn tất EDA mô tả; chưa train, tune hay chọn mô hình. Các liên hệ dưới đây "
        "không phải quan hệ nhân quả.",
        "",
        "## Executive summary",
        "",
        f"- Dataset có **{overall_rows:,} khách hàng**, **{overall_churners:,} churners** "
        f"({pct(overall_churners / overall_rows)}). Vì vậy accuracy của luật luôn đoán `No` đã là "
        f"{pct(1 - overall_churners / overall_rows)}; accuracy không được dùng làm metric chính.",
        f"- Có **{quality['blank_total_charges']}** chuỗi trống trong `TotalCharges`; tất cả đều có "
        f"`tenure = 0`. Đây là missing có cấu trúc. Giữ các dòng này, kiểm tra điều kiện rồi gán 0 "
        "trong pipeline là hợp lý hơn xóa khách hàng mới.",
        f"- Có **{quality['duplicate_customer_ids']}** `customerID` trùng và "
        f"**{quality['duplicate_rows']}** dòng trùng hoàn toàn.",
        "- Dataset không có timestamp/snapshot date/campaign treatment. Vì vậy không thể kiểm chứng "
        "temporal split, 30-day prediction horizon hay tác động thực của ưu đãi; business impact chỉ là "
        "scenario analysis.",
        "",
        "## Những segment có churn rate quan sát cao",
        "",
        "| Feature | Level | n | Churn rate | 95% Wilson CI |",
        "|---|---|---:|---:|---:|",
    ]
    for row in top_levels.itertuples():
        lines.append(
            f"| {row.feature} | {row.level} | {row.n:,} | {pct(row.churn_rate)} | "
            f"{pct(row.ci95_low)}–{pct(row.ci95_high)} |"
        )

    lines.extend(
        [
            "",
            "Cramér's V chỉ dùng để sàng lọc sức liên hệ đơn biến. File CSV có cả p-value và "
            "Benjamini–Hochberg q-value qua 16 kiểm định; significance vẫn không chứng minh feature "
            "gây churn và không thay thế đánh giá out-of-sample.",
            "",
            "| Feature | Cramér's V |",
            "|---|---:|",
        ]
    )
    for row in strongest_features.itertuples():
        lines.append(f"| {row.feature} | {row.cramers_v:.3f} |")

    lines.extend(
        [
            "",
            "## Numeric profile",
            "",
            "| Feature | Non-churn mean | Churn mean | Standardized difference |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in numeric.itertuples():
        lines.append(
            f"| {row.feature} | {row.non_churn_mean:.2f} | {row.churn_mean:.2f} | "
            f"{row.standardized_mean_difference_churn_minus_non_churn:.3f} |"
        )

    month_to_month_early = cohorts[
        cohorts["tenure_cohort"].eq("0-6") & cohorts["Contract"].eq("Month-to-month")
    ]
    if not month_to_month_early.empty:
        cohort = month_to_month_early.iloc[0]
        cohort_text = (
            f"Trong cohort tenure 0–6 tháng + month-to-month, churn rate quan sát là "
            f"{pct(cohort['churn_rate'])} (n={int(cohort['n']):,})."
        )
    else:
        cohort_text = "Không tìm thấy cohort tenure 0–6 tháng + month-to-month."

    lines.extend(
        [
            "",
            "## Diễn giải có giới hạn",
            "",
            f"- {cohort_text}",
            "- `Contract`, `tenure`, `InternetService` và `PaymentMethod` là các giả thuyết ưu tiên cho "
            "mô hình/segment analysis; chưa được biến thành khuyến nghị can thiệp.",
            "- `gender` và `SeniorCitizen` phải được dùng để audit slice. Trước production cần thử ablation "
            "không dùng thuộc tính nhạy cảm và không xuất chúng thành reason code.",
            "- Tương quan giữa phí, tenure và churn không cho phép kết luận giảm giá sẽ giữ chân. Cần "
            "randomized treatment/control data để ước lượng uplift.",
            "",
            "## Quyết định cho phase mô hình",
            "",
            "1. Loại `customerID` khỏi features nhưng giữ làm join key/audit key.",
            "2. Parse `TotalCharges`; với đúng điều kiện `tenure == 0` và missing, gán 0 trong transformer. "
            "Mọi missing khác phải fail validation.",
            "3. Không resample trước split/CV. Mọi encoder/imputer/calibrator phải fit chỉ trên training fold.",
            "4. Dùng stratified split vì sample không có thời gian, đồng thời ghi rõ đây là proxy kém hơn "
            "out-of-time validation.",
            "5. Primary metric là Average Precision; báo thêm ROC-AUC, Brier/log loss, calibration curve và "
            "Recall/Precision/Lift@budget.",
            "",
            "## Artifacts",
            "",
            "- `summary.json`: machine-readable quality/prevalence summary.",
            "- `schema_profile.csv`: dtype, missing, cardinality, range và sample values từng cột.",
            "- `categorical_churn_rates.csv`: counts, rates, Wilson intervals, chi-square và Cramér's V.",
            "- `numeric_by_churn.csv`: numeric profiles và standardized mean difference.",
            "- `tenure_contract_cohorts.csv`: cohort table phục vụ heatmap.",
            "- `figures/`: ba biểu đồ PNG tái lập được.",
            "",
        ]
    )
    return "\n".join(lines)


def run_eda(input_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data, quality = load_and_clean(input_path)
    quality.update(
        {
            "churners": int(data["churn_flag"].sum()),
            "non_churners": int(data["churn_flag"].eq(0).sum()),
            "churn_rate": float(data["churn_flag"].mean()),
            "unique_customer_ids": int(data["customerID"].nunique()),
            "analysis_environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "matplotlib": matplotlib.__version__,
            },
        }
    )
    categorical = categorical_summary(data)
    numeric = numeric_summary(data)
    cohorts = cohort_summary(data)
    profile = schema_profile(data)

    categorical.to_csv(output_dir / "categorical_churn_rates.csv", index=False)
    numeric.to_csv(output_dir / "numeric_by_churn.csv", index=False)
    cohorts.to_csv(output_dir / "tenure_contract_cohorts.csv", index=False)
    profile.to_csv(output_dir / "schema_profile.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_plots(data, categorical, cohorts, output_dir)
    (output_dir / "EDA_REPORT.md").write_text(
        build_markdown_report(quality, categorical, numeric, cohorts), encoding="utf-8"
    )
    return quality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/Telco-Customer-Churn.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("reports/eda"))
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    summary = run_eda(arguments.input, arguments.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
