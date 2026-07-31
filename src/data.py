import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from src.paths import CRITEO_PATH

FEATURES = [f"f{i}" for i in range(12)]
REQUIRED_COLUMNS = FEATURES + ["treatment", "conversion", "visit", "exposure"]


def load_criteo_full(
    dtype_f32: bool = True,
    path: str | None = None,
) -> pd.DataFrame:
    if dtype_f32:
        dtype = {f: "float32" for f in FEATURES}
        dtype.update({"treatment": "int8", "conversion": "int8", "visit": "int8", "exposure": "int8"})
    else:
        dtype = None
    return pd.read_csv(path or CRITEO_PATH, dtype=dtype)


def validate_criteo_schema(df: pd.DataFrame) -> dict:
    """Kiểm tra data contract tối thiểu trước EDA/modeling.

    Hàm không khẳng định dữ liệu đã được randomized; nó chỉ kiểm tra schema,
    kiểu binary và giá trị hữu hạn của 12 feature được phép dùng.
    """
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    extra_columns = sorted(set(df.columns) - set(REQUIRED_COLUMNS))
    binary_values = {}
    for column in ["treatment", "conversion", "visit", "exposure"]:
        if column not in df:
            continue
        values = [
            value.item() if isinstance(value, np.generic) else value
            for value in pd.Series(df[column].dropna().unique()).tolist()
        ]
        binary_values[column] = sorted(values, key=lambda value: str(value))
    invalid_binary = {
        column: values
        for column, values in binary_values.items()
        if not set(values).issubset({0, 1})
    }
    all_features_finite = False
    if not (set(FEATURES) - set(df.columns)):
        try:
            feature_values = df[FEATURES].to_numpy(dtype="float64", copy=False)
            all_features_finite = bool(np.isfinite(feature_values).all())
        except (TypeError, ValueError):
            all_features_finite = False
    missing_cells = (
        int(df[REQUIRED_COLUMNS].isna().sum().sum())
        if not missing_columns
        else None
    )
    return {
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "missing_columns": missing_columns,
        "extra_columns": extra_columns,
        "binary_values": binary_values,
        "invalid_binary_columns": invalid_binary,
        "missing_cells": missing_cells,
        "all_features_finite": all_features_finite,
        "valid": bool(
            not missing_columns
            and not extra_columns
            and not invalid_binary
            and missing_cells == 0
            and all_features_finite
        ),
    }


def _stratified_sample_indices(
    df: pd.DataFrame,
    frac: float,
    seed: int = 42,
) -> np.ndarray:
    """Trả về đúng các index được ``stratified_sample`` chọn.

    Tách helper này ra để Sprint 2 có thể lấy phần bù của sample Sprint 1 một
    cách tái lập, thay vì tạo một sample ngẫu nhiên mới có thể chồng lấn test cũ.
    """
    if not 0 < frac <= 1:
        raise ValueError("frac phải nằm trong (0, 1]")
    if not df.index.is_unique:
        raise ValueError("DataFrame index phải unique để tạo sample và phần bù")
    if frac == 1.0:
        return df.index.to_numpy(copy=True)

    rng = np.random.default_rng(seed)
    parts: list[np.ndarray] = []
    for _, g in df.groupby(["treatment", "conversion"], sort=False):
        n = max(1, int(round(len(g) * frac)))
        idx = rng.choice(g.index.values, size=min(n, len(g)), replace=False)
        parts.append(idx)
    return np.concatenate(parts)


def stratified_sample(
    df: pd.DataFrame,
    frac: float,
    seed: int = 42,
    preserve_index: bool = False,
) -> pd.DataFrame:
    selected_idx = _stratified_sample_indices(df, frac=frac, seed=seed)
    selected = df.loc[selected_idx]
    return selected if preserve_index else selected.reset_index(drop=True)


def stratified_complement(
    df: pd.DataFrame,
    selected_frac: float,
    seed: int = 42,
    preserve_index: bool = False,
) -> pd.DataFrame:
    """Lấy phần dữ liệu không được chọn bởi một ``stratified_sample`` lịch sử.

    Với ``selected_frac=0.5, seed=42``, hàm này trả về phần bù chính xác của
    sample 50% đã dùng cho Sprint 1. Đây là pool mới cho Sprint 2; final test
    Sprint 1 vẫn đóng.
    """
    selected_idx = _stratified_sample_indices(df, frac=selected_frac, seed=seed)
    selected_mask = df.index.isin(selected_idx)
    complement = df.loc[~selected_mask]
    return complement if preserve_index else complement.reset_index(drop=True)


def train_test_holdout(
    df: pd.DataFrame,
    test_size: float = 0.3,
    seed: int = 42,
    preserve_index: bool = False,
):
    """Chia 1 holdout train/test cố định, dùng chung cho MỌI model để so sánh công bằng.

    Stratify theo (treatment, conversion) để cả 2 phía giữ nguyên tỉ lệ treatment/control
    và conversion hiếm (0.29%) — tránh trường hợp tập test tình cờ không có conversion nào,
    khiến qini_score trả NaN. Seed cố định (42) để tái lập.
    """
    strata = df["treatment"].astype(str) + "_" + df["conversion"].astype(str)
    train_df, test_df = train_test_split(
        df, test_size=test_size, random_state=seed, shuffle=True, stratify=strata
    )
    if preserve_index:
        return train_df, test_df
    return train_df.reset_index(drop=True), test_df.reset_index(drop=True)


def train_validation_split(df: pd.DataFrame, validation_size: float = 0.2, seed: int = 43):
    """Tách validation chỉ từ phần train, không chạm final holdout.

    Dùng seed khác seed=42 của final holdout để tránh hai phép chia vô tình trùng cấu trúc,
    nhưng vẫn stratify theo treatment × outcome hiếm.
    """
    return train_test_holdout(df, test_size=validation_size, seed=seed)


def rare_outcome_undersample(
    df: pd.DataFrame,
    factor: float,
    outcome: str = "conversion",
    seed: int = 42,
) -> pd.DataFrame:
    """Undersample negative theo treatment arm, theo Nyberg et al. (2021).

    Với mỗi arm ``t``, giữ toàn bộ positive và giữ negative theo:

        keep_rate_t = (1 / factor - mean(Y | T=t)) / (1 - mean(Y | T=t))

    Cách này làm conversion rate trong *mỗi* arm tăng đúng hệ số ``factor`` ở dữ liệu
    sampled. Không được thay bằng việc giữ cùng một tỉ lệ negative ở hai arm vì cách
    ngây thơ đó có thể đổi uplift. Với rare outcome, Nyberg et al. dùng xấp xỉ
    ``tau_sampled ≈ factor * tau_original``; chia score cho ``factor`` chỉ là rescaling
    xấp xỉ, không phải probability calibration chính xác. Qini/AUUC chỉ phụ thuộc
    ranking nên không đổi khi nhân/chia một hằng số dương.
    """
    if factor < 1:
        raise ValueError("factor phải >= 1")
    if factor == 1:
        return df.copy().reset_index(drop=True)

    rng = np.random.default_rng(seed)
    parts = []
    for treatment_value, arm in df.groupby("treatment", sort=False):
        positive = arm[arm[outcome] == 1]
        negative = arm[arm[outcome] == 0]
        positive_rate = float(arm[outcome].mean())
        if positive_rate <= 0:
            raise ValueError(f"Arm treatment={treatment_value} không có positive outcome")
        max_factor = 1.0 / positive_rate
        if factor >= max_factor:
            raise ValueError(
                f"factor={factor} quá lớn cho arm treatment={treatment_value}; "
                f"cần factor < {max_factor:.3f}"
            )
        keep_rate = (1.0 / factor - positive_rate) / (1.0 - positive_rate)
        n_keep = int(round(len(negative) * keep_rate))
        keep_idx = rng.choice(negative.index.to_numpy(), size=n_keep, replace=False)
        parts.extend([positive, negative.loc[keep_idx]])

    sampled = pd.concat(parts, ignore_index=True)
    return sampled.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def xty(
    df: pd.DataFrame,
    outcome: str = "conversion",
    dtype: str = "float64",
):
    """Tách (X, T, Y) chuẩn cho các hàm fit_*: X = f0..f11, T = treatment, Y = outcome."""
    X = df[FEATURES].to_numpy(dtype=dtype)
    T = df["treatment"].to_numpy(dtype=dtype)
    Y = df[outcome].to_numpy(dtype=dtype)
    return X, T, Y


def propensity_auc(
    df: pd.DataFrame,
    feature_cols: list,
    seed: int = 42,
    test_size: float = 0.3,
) -> float:
    """Holdout AUC khi dự đoán treatment từ feature tiền treatment.

    AUC gần 0.5 là một balance diagnostic, không tự chứng minh randomization.
    Dùng holdout thay vì chấm in-sample để tránh optimistic bias.
    """
    train_df, test_df = train_test_split(
        df,
        test_size=test_size,
        random_state=seed,
        shuffle=True,
        stratify=df["treatment"],
    )
    X = train_df[feature_cols].to_numpy(dtype="float64")
    y = train_df["treatment"].to_numpy()
    model = LogisticRegression(max_iter=1000, random_state=seed)
    model.fit(X, y)
    proba = model.predict_proba(test_df[feature_cols].to_numpy(dtype="float64"))[:, 1]
    return roc_auc_score(test_df["treatment"].to_numpy(), proba)


def standardized_mean_difference_by_treatment(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    """Standardized mean difference (SMD) giữa treatment và control.

    ``SMD = (mean_t - mean_c) / sqrt((var_t + var_c)/2)``.
    Báo cả SMD có dấu và trị tuyệt đối; không dùng p-value làm tiêu chí chính
    vì với hàng triệu quan sát, sai khác rất nhỏ cũng có thể có p-value nhỏ.
    """
    treated = df.loc[df["treatment"] == 1, feature_cols]
    control = df.loc[df["treatment"] == 0, feature_cols]
    mean_t = treated.mean()
    mean_c = control.mean()
    pooled_sd = np.sqrt((treated.var(ddof=1) + control.var(ddof=1)) / 2.0)
    mean_difference = mean_t - mean_c
    smd = mean_difference / pooled_sd.replace(0, np.nan)
    smd = smd.mask((pooled_sd == 0) & (mean_difference != 0), np.inf)
    smd = smd.mask((pooled_sd == 0) & (mean_difference == 0), 0.0)
    return pd.DataFrame(
        {
            "feature": feature_cols,
            "mean_treatment": mean_t.to_numpy(),
            "mean_control": mean_c.to_numpy(),
            "smd": smd.to_numpy(),
            "abs_smd": smd.abs().to_numpy(),
        }
    )


def ks_test_by_treatment(df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    treat = df.loc[df["treatment"] == 1]
    control = df.loc[df["treatment"] == 0]
    rows = []
    for f in feature_cols:
        stat, p_value = ks_2samp(treat[f], control[f])
        rows.append({"feature": f, "ks_stat": stat, "p_value": p_value})
    return pd.DataFrame(rows)
