"""Đóng băng toàn bộ chẩn đoán dữ liệu vào ``output/eda/``.

Chạy:

    .venv/Scripts/python.exe scripts/run_eda_profile.py

Script này là phần **tính toán** của bước phân tích dữ liệu;
``notebooks/01_eda_criteo.ipynb`` là phần trình bày và đọc lại chính các artifact
ở đây. Tách như vậy vì hai lý do: notebook không phải chạy lại 14 triệu dòng mỗi
lần mở, và mọi con số trong notebook truy được về một run có `run_manifest.json`
ghi seed, phiên bản thư viện và SHA-256 của file nguồn.

Các bước nặng (cardinality, sentinel mask, trùng lặp, hiệu ứng theo tầng) chạy
trên **toàn bộ** dữ liệu. Chỉ balance diagnostics chạy trên mẫu stratified, vì
KS-test và propensity model không cần toàn bộ dòng để cho kết luận và chi phí
tăng tuyến tính.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover - stdout không hỗ trợ
    pass

from src.data import (
    FEATURES,
    load_criteo_full,
    propensity_auc,
    stratified_sample,
    validate_criteo_schema,
)
from src.eda import (
    arm_outcome_table,
    balance_table,
    binned_effect_table,
    cochran_q,
    difference_in_means,
    duplicate_profile,
    feature_cardinality_profile,
    file_sha256,
    minimum_detectable_effect,
    post_treatment_leakage_report,
    prognostic_dominance_summary,
    propensity_overlap,
    quantile_bins,
    required_sample_size,
    sample_representativity,
    sentinel_mask_agreement,
    sentinel_mask_matrix,
    sentinel_mask_profile,
)
from src.paths import CRITEO_PATH, OUTPUT_DIR, REPO_ROOT

OUTCOMES = ["conversion", "visit", "exposure"]
POST_TREATMENT_COLUMNS = ["visit", "exposure"]


def log(message: str) -> None:
    print(message, flush=True)


def nonlinear_propensity_auc(df: pd.DataFrame, seed: int) -> float:
    """AUC của một propensity model dạng cây, làm đối trọng với model tuyến tính.

    Cần thiết vì phần lớn cấu trúc của Criteo nằm ở *pattern sentinel* chứ không
    ở giá trị liên tục, và logistic regression gần như không đọc được cấu trúc
    đó. Một model tuyến tính cho AUC quanh 0,5 vì thế là bằng chứng yếu hơn nhiều
    so với việc một model cây cũng chỉ đạt quanh 0,5.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    train_df, test_df = train_test_split(
        df, test_size=0.3, random_state=seed, shuffle=True, stratify=df["treatment"]
    )
    model = HistGradientBoostingClassifier(
        max_iter=120, learning_rate=0.1, max_leaf_nodes=31, random_state=seed
    )
    model.fit(train_df[FEATURES].to_numpy("float32"), train_df["treatment"].to_numpy())
    probability = model.predict_proba(test_df[FEATURES].to_numpy("float32"))[:, 1]
    return float(roc_auc_score(test_df["treatment"].to_numpy(), probability))


def effect_by_feature_bins(
    df: pd.DataFrame,
    outcome: str,
    n_bins: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hiệu ứng theo phân vị của từng feature, cộng bảng kiểm đồng nhất đi kèm.

    Feature nào chỉ tạo được một bin thì không phân tầng được — nó vẫn xuất hiện
    trong bảng heterogeneity với ``n_bins = 1`` và ``q_statistic`` rỗng, vì "không
    đo được" là một kết quả cần thấy chứ không phải một dòng cần giấu.
    """
    y = df[outcome].to_numpy("float64")
    t = df["treatment"].to_numpy("float64")
    strata, tests = [], []
    for feature in FEATURES:
        bins = quantile_bins(df[feature].to_numpy(), n_bins)
        n_effective = int(pd.Series(bins).nunique(dropna=True))
        if n_effective < 2:
            tests.append(
                {
                    "feature": feature,
                    "n_bins": n_effective,
                    "stratifiable": False,
                    "q_statistic": np.nan,
                    "df": np.nan,
                    "p_value": np.nan,
                    "i_squared": np.nan,
                    "min_effect": np.nan,
                    "max_effect": np.nan,
                    "effect_ratio_max_over_min": np.nan,
                }
            )
            continue
        table = binned_effect_table(y, t, bins, bin_label="bin")
        table.insert(0, "feature", feature)
        strata.append(table)
        test = cochran_q(table["effect"], table["standard_error"])
        minimum, maximum = float(table["effect"].min()), float(table["effect"].max())
        tests.append(
            {
                "feature": feature,
                "n_bins": int(len(table)),
                "stratifiable": True,
                "q_statistic": test["q_statistic"],
                "df": test["df"],
                "p_value": test["p_value"],
                "i_squared": test["i_squared"],
                "min_effect": minimum,
                "max_effect": maximum,
                "effect_ratio_max_over_min": maximum / minimum if minimum > 0 else np.inf,
            }
        )
    if not strata:
        raise ValueError("Không feature nào phân tầng được — kiểm tra lại dữ liệu")
    return pd.concat(strata, ignore_index=True), pd.DataFrame(tests)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--balance-frac", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-bins", type=int, default=10)
    parser.add_argument(
        "--min-pattern-rows",
        type=int,
        default=20_000,
        help="Pattern sentinel nhỏ hơn ngưỡng này bị loại khỏi bảng hiệu ứng.",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "eda")
    parser.add_argument(
        "--skip-nonlinear-propensity",
        action="store_true",
        help="Bỏ qua propensity model dạng cây (bước tốn thời gian nhất).",
    )
    args = parser.parse_args()

    started = time.time()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # -- 1. Toàn vẹn và hợp đồng dữ liệu -----------------------------------
    log("[1/8] Kiểm tra toàn vẹn file nguồn")
    checksum = file_sha256(CRITEO_PATH)
    df = load_criteo_full(dtype_f32=True)
    contract = validate_criteo_schema(df)
    if not contract["valid"]:
        raise ValueError(f"Data contract failed: {contract}")
    n_rows = len(df)
    log(f"       {n_rows:,} dòng · sha256 {checksum[:12]}… · contract valid")

    # -- 2. Cấu trúc biến ---------------------------------------------------
    log("[2/8] Cardinality và point mass")
    cardinality = feature_cardinality_profile(df, FEATURES, n_quantile_bins=args.n_bins)
    cardinality.to_csv(output_dir / "feature_profile.csv", index=False)

    log("[3/8] Sentinel mask và pattern cấu trúc")
    mask, sentinels = sentinel_mask_matrix(df, FEATURES)
    agreement = sentinel_mask_agreement(mask)
    agreement.to_csv(output_dir / "sentinel_mask_agreement.csv")
    pattern_profile = sentinel_mask_profile(mask, top_k=15)
    pattern_profile["top_patterns"].to_csv(
        output_dir / "sentinel_patterns.csv", index=False
    )
    pattern_profile["observed_per_row"].to_csv(
        output_dir / "sentinel_observed_per_row.csv"
    )
    pattern_key = pattern_profile.pop("pattern_key")
    shared_sentinel_masks = [
        {"feature_a": a, "feature_b": b}
        for i, a in enumerate(FEATURES)
        for b in FEATURES[i + 1 :]
        if agreement.loc[a, b] == 1.0
    ]
    del mask

    log("[4/8] Trùng lặp vector đặc trưng")
    duplicates = duplicate_profile(df, FEATURES)

    # -- 3. Thiết kế --------------------------------------------------------
    log(f"[5/8] Balance diagnostics trên mẫu {args.balance_frac:.0%}")
    balance_sample = stratified_sample(df, frac=args.balance_frac, seed=args.seed)
    balance = balance_table(balance_sample, FEATURES)
    balance.to_csv(output_dir / "balance_smd.csv", index=False)
    representativity = sample_representativity(
        df, balance_sample, FEATURES + ["treatment"] + OUTCOMES
    )
    representativity.to_csv(output_dir / "sample_representativity.csv", index=False)
    linear_auc = float(propensity_auc(balance_sample, FEATURES, seed=args.seed))
    tree_auc = (
        None
        if args.skip_nonlinear_propensity
        else nonlinear_propensity_auc(balance_sample, seed=args.seed)
    )
    design_propensity = float(df["treatment"].mean())
    overlap = propensity_overlap(
        np.full(n_rows, design_propensity), df["treatment"].to_numpy(), n_bins=20
    )
    overlap_bins = overlap.pop("bins")
    overlap_bins.to_csv(output_dir / "propensity_overlap_bins.csv", index=False)
    del balance_sample

    leakage = post_treatment_leakage_report(df, POST_TREATMENT_COLUMNS)
    leakage.to_csv(output_dir / "post_treatment_leakage.csv", index=False)

    # -- 4. Hiệu ứng trung bình và công suất --------------------------------
    log("[6/8] ATE, risk ratio và công suất thống kê")
    arms = arm_outcome_table(df, OUTCOMES)
    arms.to_csv(output_dir / "arm_outcome_summary.csv", index=False)
    # `exposure` không có sự kiện nào ở nhánh control, nên risk ratio của nó là
    # NaN. Dòng vẫn được giữ trong bảng: NaN ở đây chính là dấu hiệu của một biến
    # hậu can thiệp, không phải một ô bị lỗi.
    ate_rows = []
    for outcome in OUTCOMES:
        row = difference_in_means(df[outcome].to_numpy(), df["treatment"].to_numpy())
        row["outcome"] = outcome
        ate_rows.append(row)
    ate = pd.DataFrame(ate_rows).set_index("outcome").reset_index()
    ate.to_csv(output_dir / "average_treatment_effect.csv", index=False)

    conversion_rate_control = float(ate.loc[ate["outcome"] == "conversion", "rate_control"].iloc[0])
    observed_ate = float(
        ate.loc[ate["outcome"] == "conversion", "difference_in_means"].iloc[0]
    )
    mde = minimum_detectable_effect(conversion_rate_control, n_rows, design_propensity)
    power_rows = []
    for label, effect in [
        ("ATE quan sát được", observed_ate),
        ("1/2 ATE", observed_ate / 2),
        ("1/10 ATE", observed_ate / 10),
        ("1/100 ATE", observed_ate / 100),
    ]:
        needed = required_sample_size(effect, conversion_rate_control, design_propensity)
        power_rows.append(
            {
                "target_effect_label": label,
                "target_effect": effect,
                "required_n": needed,
                "required_n_over_criteo": needed / n_rows,
                "detectable_at_current_n": bool(effect >= mde),
            }
        )
    power = pd.DataFrame(power_rows)
    power.to_csv(output_dir / "power_analysis.csv", index=False)

    # -- 5. Heterogeneity ---------------------------------------------------
    log("[7/8] Hiệu ứng theo tầng và chẩn đoán prognostic dominance")
    decile_effects, heterogeneity = effect_by_feature_bins(df, "conversion", args.n_bins)
    decile_effects.to_csv(output_dir / "effect_by_feature_bin.csv", index=False)
    heterogeneity.to_csv(output_dir / "heterogeneity_by_feature.csv", index=False)

    pattern_effects = binned_effect_table(
        df["conversion"].to_numpy(),
        df["treatment"].to_numpy(),
        pattern_key,
        bin_label="pattern_key",
    )
    pattern_effects = pattern_effects[
        pattern_effects["n"] >= args.min_pattern_rows
    ].reset_index(drop=True)
    pattern_effects.to_csv(output_dir / "effect_by_sentinel_pattern.csv", index=False)

    feature_dominance = {}
    for feature, group in decile_effects.groupby("feature", sort=True):
        group = group.reset_index(drop=True)
        if len(group) < 3:
            feature_dominance[feature] = {
                "n_strata": int(len(group)),
                "inference_note": (
                    "Fewer than three effective quantile strata; use the "
                    "feature-level Cochran Q in heterogeneity_by_feature.csv only."
                ),
            }
            continue
        feature_dominance[feature] = prognostic_dominance_summary(group)
    dominance = {
        # Cùng customer được dùng lại qua nhiều feature: chỉ mô tả khi gộp.
        # Suy luận hợp lệ được báo riêng trên các strata rời nhau của từng feature.
        "feature_bins": prognostic_dominance_summary(
            decile_effects,
            independent_strata=False,
        ),
        "feature_bins_by_feature": feature_dominance,
        "sentinel_patterns": prognostic_dominance_summary(pattern_effects),
    }
    (output_dir / "prognostic_dominance.json").write_text(
        json.dumps(dominance, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # -- 6. Summary và manifest --------------------------------------------
    log("[8/8] Ghi summary và manifest")
    stratifiable = heterogeneity[heterogeneity["stratifiable"]]
    summary = pd.DataFrame(
        [
            {"metric": "n_rows", "value": n_rows},
            {"metric": "n_columns", "value": int(df.shape[1])},
            {"metric": "n_missing_cells", "value": int(contract["missing_cells"])},
            {"metric": "treatment_rate", "value": design_propensity},
            {"metric": "conversion_rate", "value": float(df["conversion"].mean())},
            {"metric": "conversion_events_control", "value": int(ate.loc[0, "events_control"])},
            {"metric": "ate_conversion", "value": observed_ate},
            {"metric": "ate_conversion_ci_low", "value": float(ate.loc[0, "ci_low"])},
            {"metric": "ate_conversion_ci_high", "value": float(ate.loc[0, "ci_high"])},
            {"metric": "risk_ratio_conversion", "value": float(ate.loc[0, "risk_ratio"])},
            {"metric": "mde_conversion", "value": mde},
            {"metric": "ate_over_mde", "value": observed_ate / mde},
            {"metric": "max_mode_share", "value": float(cardinality["mode_share"].max())},
            {"metric": "n_features_mode_share_above_0p9", "value": int((cardinality["mode_share"] > 0.9).sum())},
            {"metric": "n_features_stratifiable_by_decile", "value": int(len(stratifiable))},
            {"metric": "median_observed_features_per_row", "value": pattern_profile["median_observed_features"]},
            {"metric": "n_sentinel_patterns", "value": pattern_profile["n_distinct_patterns"]},
            {"metric": "n_shared_sentinel_mask_pairs", "value": len(shared_sentinel_masks)},
            {"metric": "duplicate_row_share", "value": duplicates["duplicate_row_share"]},
            {"metric": "propensity_auc_linear", "value": linear_auc},
            {"metric": "propensity_auc_tree", "value": tree_auc},
            {"metric": "max_abs_smd", "value": float(balance["abs_smd"].max())},
            {"metric": "prognostic_pearson_r", "value": dominance["feature_bins"]["pearson_r"]},
            {"metric": "prognostic_spearman_rho", "value": dominance["feature_bins"]["spearman_rho"]},
            {"metric": "q_ratio_additive_over_multiplicative", "value": dominance["feature_bins"]["q_ratio_additive_over_multiplicative"]},
            {"metric": "pooled_risk_ratio_across_strata", "value": dominance["feature_bins"]["pooled_risk_ratio"]},
        ]
    )
    summary.to_csv(output_dir / "eda_summary.csv", index=False)

    manifest = {
        "run": {
            "script": "scripts/run_eda_profile.py",
            "seed": args.seed,
            "balance_frac": args.balance_frac,
            "n_bins": args.n_bins,
            "min_pattern_rows": args.min_pattern_rows,
            "elapsed_seconds": round(time.time() - started, 1),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "source": {
            "path": CRITEO_PATH.relative_to(REPO_ROOT).as_posix(),
            "file_size_bytes": int(CRITEO_PATH.stat().st_size),
            "sha256": checksum,
            "schema_contract": contract,
        },
        "feature_policy": {
            "allowed_pre_treatment_features": FEATURES,
            "primary_outcome": "conversion",
            "excluded_post_treatment": POST_TREATMENT_COLUMNS,
        },
        "structure": {
            "sentinel_values": sentinels,
            "shared_sentinel_mask_pairs": shared_sentinel_masks,
            "n_distinct_sentinel_patterns": pattern_profile["n_distinct_patterns"],
            "n_possible_sentinel_patterns": pattern_profile["n_possible_patterns"],
            "median_observed_features_per_row": pattern_profile["median_observed_features"],
            "duplicates": duplicates,
        },
        "design": {
            "design_propensity": design_propensity,
            "propensity_auc_linear": linear_auc,
            "propensity_auc_tree": tree_auc,
            "max_abs_smd": float(balance["abs_smd"].max()),
            "median_abs_smd": float(balance["abs_smd"].median()),
            "n_features_abs_smd_above_0p1": int((balance["abs_smd"] > 0.1).sum()),
            "overlap": overlap,
            "interpretation": (
                "Balance diagnostics mô tả cân bằng quan sát được. Căn cứ cho random "
                "assignment đến từ provenance của thí nghiệm, không từ AUC/SMD."
            ),
        },
        "power": {
            "minimum_detectable_effect": mde,
            "observed_ate": observed_ate,
            "ate_over_mde": observed_ate / mde,
            "alpha": 0.05,
            "power": 0.80,
        },
        "prognostic_dominance": dominance,
        "artifacts": sorted(p.name for p in output_dir.glob("*.csv"))
        + sorted(p.name for p in output_dir.glob("*.json")),
    }
    manifest_path = output_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=float),
        encoding="utf-8",
    )

    log("")
    log(f"[write] {output_dir.relative_to(REPO_ROOT).as_posix()}/ — {len(manifest['artifacts'])} file")
    log(f"        ATE conversion = {observed_ate:.6g}, MDE = {mde:.3g}, tỉ số = {observed_ate / mde:.1f}")
    log(f"        {int((cardinality['mode_share'] > 0.9).sum())}/12 feature có mode_share > 0,9")
    log(f"        {len(stratifiable)}/12 feature phân tầng được theo decile")
    log(
        "        prognostic dominance (pooled descriptive only): r = "
        f"{dominance['feature_bins']['pearson_r']:.4f}; "
        "Q/I² reported per independent feature partition"
    )
    log(f"        tổng thời gian {manifest['run']['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    main()
