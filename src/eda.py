"""Chẩn đoán dữ liệu cho một randomized incrementality test.

Module này chứa phần **tính toán** của bước phân tích dữ liệu; phần trình bày nằm
ở ``notebooks/01_eda_criteo.ipynb`` và artifact đóng băng ở ``output/eda/``. Tách
như vậy để mọi con số trong notebook truy được về một hàm có test, giống cách
Sprint 3 tách ``scripts/run_oof_experiment.py`` khỏi ``notebooks/02``.

Bốn nhóm câu hỏi, theo đúng thứ tự một phân tích nhân quả phải trả lời:

1. **Dữ liệu có đúng như hợp đồng không** — schema, cardinality, sentinel value,
   trùng lặp. :func:`feature_cardinality_profile`, :func:`sentinel_mask_profile`,
   :func:`duplicate_profile`.
2. **Thiết kế có cho phép suy luận nhân quả không** — cân bằng covariate, overlap,
   biến hậu can thiệp. :func:`balance_table`, :func:`post_treatment_leakage_report`.
3. **Hiệu ứng trung bình là bao nhiêu và đo được tới đâu** —
   :func:`difference_in_means`, :func:`minimum_detectable_effect`,
   :func:`required_sample_size`.
4. **Có heterogeneity để mô hình hoá không, và nó có dạng gì** —
   :func:`binned_effect_table`, :func:`cochran_q`, :func:`prognostic_dominance_summary`.

Quy ước chung: hàm nhận mảng/DataFrame và trả về ``DataFrame``/``dict`` thuần,
không vẽ hình, không ghi file, không phụ thuộc đường dẫn repo.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm, pearsonr, spearmanr

__all__ = [
    "file_sha256",
    "feature_cardinality_profile",
    "sentinel_mask_matrix",
    "sentinel_mask_agreement",
    "sentinel_mask_profile",
    "duplicate_profile",
    "balance_table",
    "propensity_overlap",
    "arm_outcome_table",
    "difference_in_means",
    "minimum_detectable_effect",
    "required_sample_size",
    "post_treatment_leakage_report",
    "quantile_bins",
    "binned_effect_table",
    "cochran_q",
    "prognostic_dominance_summary",
    "sample_representativity",
]


# ---------------------------------------------------------------------------
# 1. Toàn vẹn và cấu trúc dữ liệu
# ---------------------------------------------------------------------------


def file_sha256(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 của một file, đọc theo chunk để không nạp cả file vào RAM."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def feature_cardinality_profile(
    df: pd.DataFrame,
    feature_cols: list[str],
    n_quantile_bins: int = 10,
) -> pd.DataFrame:
    """Cardinality, khối lượng tập trung ở mode, và độ phân giải phân vị.

    Ba cột quan trọng nhất và lý do có mặt:

    - ``mode_share`` — tỉ lệ dòng nằm đúng ở giá trị mode. Một feature có
      ``mode_share`` gần 1 hầu như không mang thông tin phân biệt; mô tả nó bằng
      mean/std sẽ tạo ấn tượng sai về một biến liên tục.
    - ``n_effective_quantile_bins`` — số bin thực sự tạo được khi cắt
      ``n_quantile_bins`` phân vị. Bằng 1 nghĩa là **không** phân tầng được theo
      phân vị, nên mọi phân tích "theo decile" trên feature đó là vô nghĩa.
    - ``skew``/``kurtosis`` — cảnh báo rằng quy tắc outlier theo ``±k·sigma`` (giả
      định phân phối gần chuẩn) không áp dụng được.

    Hàm không kết luận feature nào "xấu"; nó chỉ đo để bước sau chọn công cụ đúng.
    """
    if not feature_cols:
        raise ValueError("feature_cols không được rỗng")
    missing = sorted(set(feature_cols) - set(df.columns))
    if missing:
        raise KeyError(f"Thiếu cột: {missing}")
    if n_quantile_bins < 2:
        raise ValueError("n_quantile_bins phải >= 2")

    n = len(df)
    if n == 0:
        raise ValueError("df không được rỗng")

    rows = []
    for feature in feature_cols:
        values = df[feature]
        counts = values.value_counts()
        quantile_bins = quantile_bins_count(values.to_numpy(), n_quantile_bins)
        rows.append(
            {
                "feature": feature,
                "dtype": str(values.dtype),
                "n_missing": int(values.isna().sum()),
                "n_unique": int(values.nunique()),
                "mode_value": float(counts.index[0]),
                "mode_share": float(counts.iloc[0] / n),
                "top3_share": float(counts.iloc[:3].sum() / n),
                "mean": float(values.mean()),
                "std": float(values.std()),
                "min": float(values.min()),
                "p25": float(values.quantile(0.25)),
                "p50": float(values.quantile(0.50)),
                "p75": float(values.quantile(0.75)),
                "max": float(values.max()),
                "skew": float(values.skew()),
                "kurtosis": float(values.kurt()),
                "n_effective_quantile_bins": int(quantile_bins),
            }
        )
    return pd.DataFrame(rows)


def quantile_bins_count(values: np.ndarray, n_bins: int) -> int:
    """Số bin thực tế thu được khi cắt ``n_bins`` phân vị, sau khi gộp biên trùng."""
    binned = quantile_bins(values, n_bins)
    return int(pd.Series(binned).nunique(dropna=True))


def quantile_bins(values, n_bins: int = 10) -> np.ndarray:
    """Chỉ số bin phân vị, gộp các biên trùng nhau thay vì báo lỗi.

    Với feature có point mass lớn, nhiều biên phân vị rơi vào cùng một giá trị.
    ``duplicates="drop"`` gộp chúng lại, nên số bin trả về có thể nhỏ hơn
    ``n_bins`` — đó là thông tin cần giữ, không phải lỗi cần che.
    """
    array = np.asarray(values, dtype="float64").ravel()
    if array.size == 0:
        raise ValueError("values không được rỗng")
    if n_bins < 2:
        raise ValueError("n_bins phải >= 2")
    return pd.qcut(array, n_bins, labels=False, duplicates="drop")


def sentinel_mask_matrix(
    df: pd.DataFrame,
    feature_cols: list[str],
    sentinel_values: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Ma trận boolean "dòng này có nằm ở sentinel value của feature không".

    Sentinel mặc định là mode. Giả thuyết đi kèm — và là lý do hàm này tồn tại —
    là point mass ở một giá trị duy nhất thường không phải một mức thật của biến
    mà là mã của *không quan sát được*. Nếu đúng, "0 ô thiếu" chỉ đúng về mặt cú
    pháp, còn missingness thật vẫn có và nằm ẩn trong mask này.

    Hàm chỉ dựng mask; :func:`sentinel_mask_agreement` mới là phép kiểm giả thuyết.
    """
    if not feature_cols:
        raise ValueError("feature_cols không được rỗng")
    resolved = dict(sentinel_values or {})
    mask = {}
    for feature in feature_cols:
        if feature not in resolved:
            resolved[feature] = float(df[feature].mode().iloc[0])
        mask[feature] = df[feature].to_numpy() == resolved[feature]
    return pd.DataFrame(mask, index=df.index), resolved


def sentinel_mask_agreement(mask: pd.DataFrame) -> pd.DataFrame:
    """Tỉ lệ dòng mà hai feature cùng ở (hoặc cùng không ở) sentinel.

    Giá trị đúng bằng ``1.0`` cho một cặp là bằng chứng mạnh: hai feature dùng
    **chung một nguồn missingness**. Khi đó chúng không phải hai biến độc lập về
    mặt quan sát được, dù giá trị của chúng khác nhau.
    """
    columns = list(mask.columns)
    values = mask.to_numpy()
    n = values.shape[0]
    agreement = np.empty((len(columns), len(columns)), dtype="float64")
    for i in range(len(columns)):
        agreement[i, i] = 1.0
        for j in range(i + 1, len(columns)):
            share = float(np.count_nonzero(values[:, i] == values[:, j]) / n)
            agreement[i, j] = agreement[j, i] = share
    return pd.DataFrame(agreement, index=columns, columns=columns)


def sentinel_mask_profile(
    mask: pd.DataFrame,
    top_k: int = 10,
) -> dict:
    """Phân bố các *pattern* sentinel và số feature thật sự quan sát được mỗi dòng.

    ``n_observed_per_row`` là số feature **không** nằm ở sentinel. Phân bố của nó
    là thước đo trực tiếp của chiều thông tin thực tế: nếu phần lớn dòng chỉ quan
    sát được vài feature trên tổng số, không gian covariate hẹp hơn nhiều so với
    con số danh nghĩa, và mọi estimator CATE đều bị chặn bởi giới hạn đó.
    """
    if mask.empty:
        raise ValueError("mask không được rỗng")
    values = mask.to_numpy()
    n_rows, n_features = values.shape
    weights = (1 << np.arange(n_features, dtype="int64"))
    key = values.astype("int64") @ weights
    counts = pd.Series(key).value_counts()

    def render(pattern_key: int) -> str:
        bits = format(int(pattern_key), f"0{n_features}b")[::-1]
        return "".join("." if bit == "1" else "O" for bit in bits)

    patterns = pd.DataFrame(
        {
            "pattern": [render(k) for k in counts.index[:top_k]],
            "pattern_key": [int(k) for k in counts.index[:top_k]],
            "n_rows": counts.iloc[:top_k].to_numpy(),
            "share": (counts.iloc[:top_k] / n_rows).to_numpy(),
        }
    )
    n_observed = n_features - values.sum(axis=1)
    observed_distribution = (
        pd.Series(n_observed).value_counts().sort_index().rename("n_rows").to_frame()
    )
    observed_distribution["share"] = observed_distribution["n_rows"] / n_rows
    observed_distribution.index.name = "n_observed_features"
    return {
        "n_distinct_patterns": int(counts.size),
        "n_possible_patterns": int(2**n_features),
        "top_patterns": patterns,
        "observed_per_row": observed_distribution,
        "median_observed_features": float(np.median(n_observed)),
        "pattern_key": key,
        "legend": "O = quan sát được (khác sentinel), . = ở sentinel value",
    }


def duplicate_profile(df: pd.DataFrame, feature_cols: list[str]) -> dict:
    """Mức trùng lặp của vector đặc trưng.

    Trùng lặp có hai hệ quả trái ngược nhau và cả hai đều phải nói ra:

    - Nó cho phép so sánh *trong cùng một tầng X chính xác*, tức một phép kiểm
      phi tham số không cần model nào.
    - Nó làm các dòng không còn độc lập hoàn toàn, nên bootstrap ở mức dòng coi
      các bản sao là quan sát riêng biệt. Với tỉ lệ trùng nhỏ, ảnh hưởng nhỏ;
      con số ở đây để người đọc tự đánh giá thay vì phải giả định.
    """
    n = len(df)
    if n == 0:
        raise ValueError("df không được rỗng")
    group_sizes = df.groupby(feature_cols, sort=False, observed=True).size()
    repeated = group_sizes[group_sizes > 1]
    return {
        "n_rows": int(n),
        "n_distinct_feature_vectors": int(group_sizes.size),
        "n_duplicate_rows": int(n - group_sizes.size),
        "duplicate_row_share": float((n - group_sizes.size) / n),
        "n_rows_in_repeated_groups": int(repeated.sum()),
        "share_rows_in_repeated_groups": float(repeated.sum() / n),
        "max_group_size": int(group_sizes.max()),
        "mean_group_size": float(group_sizes.mean()),
    }


# ---------------------------------------------------------------------------
# 2. Tính hợp lệ của thiết kế
# ---------------------------------------------------------------------------


def balance_table(
    df: pd.DataFrame,
    feature_cols: list[str],
    treatment_col: str = "treatment",
) -> pd.DataFrame:
    """SMD kèm KS statistic cho từng feature, xếp theo ``abs_smd`` giảm dần.

    SMD là tiêu chí chính vì nó là *effect size*, không phụ thuộc cỡ mẫu. Với 14
    triệu dòng, p-value của bất kỳ kiểm định nào cũng sẽ nhỏ khi có chênh lệch
    thực tế bằng 0,001 độ lệch chuẩn — nên p-value không dùng làm tiêu chí
    chính, chỉ đi kèm để đọc cùng statistic.

    Ngưỡng quy ước trong tài liệu matching: ``|SMD| < 0,1`` là cân bằng chấp nhận
    được. Ngưỡng này là quy ước, không phải kiểm định.
    """
    from scipy.stats import ks_2samp

    treated = df.loc[df[treatment_col] == 1, feature_cols]
    control = df.loc[df[treatment_col] == 0, feature_cols]
    if treated.empty or control.empty:
        raise ValueError("Cần cả hai arm để tính balance")

    mean_t, mean_c = treated.mean(), control.mean()
    pooled_sd = np.sqrt((treated.var(ddof=1) + control.var(ddof=1)) / 2.0)
    difference = mean_t - mean_c
    smd = difference / pooled_sd.replace(0, np.nan)
    smd = smd.mask((pooled_sd == 0) & (difference != 0), np.inf)
    smd = smd.mask((pooled_sd == 0) & (difference == 0), 0.0)

    ks_stat, ks_p = [], []
    for feature in feature_cols:
        statistic, p_value = ks_2samp(treated[feature], control[feature])
        ks_stat.append(float(statistic))
        ks_p.append(float(p_value))

    table = pd.DataFrame(
        {
            "feature": feature_cols,
            "mean_treatment": mean_t.to_numpy(),
            "mean_control": mean_c.to_numpy(),
            "mean_difference": difference.to_numpy(),
            "pooled_sd": pooled_sd.to_numpy(),
            "smd": smd.to_numpy(),
            "abs_smd": smd.abs().to_numpy(),
            "ks_stat": ks_stat,
            "ks_p_value": ks_p,
        }
    )
    return table.sort_values("abs_smd", ascending=False, ignore_index=True)


def propensity_overlap(propensity_score, treatment, n_bins: int = 20) -> dict:
    """Kiểm tra positivity: mọi vùng của score có mặt ở cả hai arm không.

    Ước lượng IPW/DR chỉ xác định được khi ``0 < e(x) < 1`` với mọi ``x`` có mật
    độ dương. Trong một RCT điều này đúng theo thiết kế, nhưng vẫn phải kiểm
    trên dữ liệu đã nhận được: một bug ở khâu chia tập hoặc lọc dòng sẽ hiện ra
    ngay ở đây dưới dạng bin chỉ có một arm.
    """
    score = np.asarray(propensity_score, dtype="float64").ravel()
    arm = np.asarray(treatment, dtype="float64").ravel()
    if score.shape != arm.shape:
        raise ValueError("propensity_score và treatment phải cùng độ dài")
    if n_bins < 2:
        raise ValueError("n_bins phải >= 2")

    edges = np.linspace(score.min(), score.max(), n_bins + 1)
    index = np.clip(np.digitize(score, edges[1:-1]), 0, n_bins - 1)
    frame = pd.DataFrame({"bin": index, "t": arm})
    counts = (
        frame.groupby("bin")["t"]
        .agg(n="size", n_treated="sum")
        .reindex(range(n_bins), fill_value=0)
    )
    counts["n_control"] = counts["n"] - counts["n_treated"]
    counts["bin_low"] = edges[:-1]
    counts["bin_high"] = edges[1:]
    occupied = counts[counts["n"] > 0]
    single_arm = occupied[(occupied["n_treated"] == 0) | (occupied["n_control"] == 0)]
    return {
        "bins": counts.reset_index(),
        "min_propensity": float(score.min()),
        "max_propensity": float(score.max()),
        "n_occupied_bins": int(len(occupied)),
        "n_single_arm_bins": int(len(single_arm)),
        "share_rows_in_single_arm_bins": float(single_arm["n"].sum() / len(score)),
        "positivity_holds_in_sample": bool(len(single_arm) == 0),
    }


def arm_outcome_table(
    df: pd.DataFrame,
    outcome_cols: list[str],
    treatment_col: str = "treatment",
) -> pd.DataFrame:
    """Bảng đếm theo arm cho từng outcome: n, số sự kiện, tỉ lệ.

    Số **sự kiện tuyệt đối ở nhánh control** là đại lượng quyết định của toàn bộ
    dự án: nó là mẫu số của mọi ước lượng phản thực và do đó là trần thông tin
    cho mọi model. Vì vậy nó được báo cáo dưới dạng đếm, không chỉ dưới dạng tỉ lệ.
    """
    rows = []
    for arm_value, arm in df.groupby(treatment_col, sort=True):
        for outcome in outcome_cols:
            rows.append(
                {
                    "treatment": int(arm_value),
                    "outcome": outcome,
                    "n_rows": int(len(arm)),
                    "n_events": int(arm[outcome].sum()),
                    "rate": float(arm[outcome].mean()),
                }
            )
    return pd.DataFrame(rows)


def post_treatment_leakage_report(
    df: pd.DataFrame,
    candidate_cols: list[str],
    outcome: str = "conversion",
    treatment_col: str = "treatment",
) -> pd.DataFrame:
    """Bằng chứng số cho việc một biến là hậu can thiệp và không được làm feature.

    Ba dấu hiệu, mỗi cái là một cột:

    - ``rate_control == 0`` khi biến chỉ tồn tại dưới treatment. Đây là dấu hiệu
      dứt khoát nhất: biến không được định nghĩa ở nhánh control.
    - ``outcome_rate_when_zero == 0`` khi biến là *điều kiện cần* của outcome.
      Đưa một biến như vậy vào feature cho model gần như toàn bộ đáp án.
    - ``smd_by_treatment`` khác 0 rõ rệt: phân phối của biến bị treatment tác động.

    Hàm chỉ báo cáo. Quyết định loại biến nằm ở feature contract
    (``src/candidates.py``) và ở protocol đã đăng ký.
    """
    treated_mask = df[treatment_col] == 1
    y = df[outcome].to_numpy(dtype="float64")
    rows = []
    for column in candidate_cols:
        values = df[column].to_numpy(dtype="float64")
        positive = values > 0
        rate_t = float(values[treated_mask.to_numpy()].mean())
        rate_c = float(values[~treated_mask.to_numpy()].mean())
        var_t = float(values[treated_mask.to_numpy()].var(ddof=1))
        var_c = float(values[~treated_mask.to_numpy()].var(ddof=1))
        pooled = float(np.sqrt((var_t + var_c) / 2.0))
        rows.append(
            {
                "column": column,
                "rate_treatment": rate_t,
                "rate_control": rate_c,
                "smd_by_treatment": float((rate_t - rate_c) / pooled) if pooled > 0 else np.inf,
                "outcome_rate_when_positive": float(y[positive].mean()) if positive.any() else np.nan,
                "outcome_rate_when_zero": float(y[~positive].mean()) if (~positive).any() else np.nan,
                "only_defined_under_treatment": bool(rate_c == 0.0),
                "necessary_for_outcome": bool((~positive).any() and y[~positive].sum() == 0),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Hiệu ứng trung bình và công suất thống kê
# ---------------------------------------------------------------------------


def difference_in_means(
    outcome,
    treatment,
    alpha: float = 0.05,
) -> dict:
    """ATE của một outcome nhị phân, kèm CI cho cả thang cộng và thang nhân.

    Thang cộng (``difference_in_means``) là đại lượng quyết định trực tiếp: nó
    cho biết một lần liên hệ tạo thêm bao nhiêu conversion. Thang nhân
    (``risk_ratio``) là đại lượng cần để hiểu *cấu trúc* của hiệu ứng — CI của nó
    dùng phép xấp xỉ Katz trên ``log(RR)``, hợp lệ khi số sự kiện ở cả hai arm đủ lớn.

    Trên RCT, hiệu hai trung bình là ước lượng không thiên lệch của ATE; sai số
    chuẩn dùng công thức hai tỉ lệ độc lập.
    """
    y = np.asarray(outcome, dtype="float64").ravel()
    t = np.asarray(treatment, dtype="float64").ravel()
    if y.shape != t.shape:
        raise ValueError("outcome và treatment phải cùng độ dài")
    if not 0 < alpha < 1:
        raise ValueError("alpha phải nằm trong (0, 1)")
    treated, control = y[t == 1], y[t == 0]
    if treated.size == 0 or control.size == 0:
        raise ValueError("Cần cả hai arm để tính difference in means")

    n_t, n_c = treated.size, control.size
    p_t, p_c = float(treated.mean()), float(control.mean())
    events_t, events_c = float(treated.sum()), float(control.sum())
    z = float(norm.ppf(1 - alpha / 2))

    estimate = p_t - p_c
    standard_error = float(np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c))

    result = {
        "n_treated": int(n_t),
        "n_control": int(n_c),
        "events_treated": int(events_t),
        "events_control": int(events_c),
        "rate_treated": p_t,
        "rate_control": p_c,
        "difference_in_means": estimate,
        "standard_error": standard_error,
        "ci_low": estimate - z * standard_error,
        "ci_high": estimate + z * standard_error,
        "z_statistic": estimate / standard_error if standard_error > 0 else np.nan,
        "alpha": alpha,
    }
    if events_t > 0 and events_c > 0:
        log_rr = float(np.log(p_t / p_c))
        se_log_rr = float(np.sqrt(1 / events_t - 1 / n_t + 1 / events_c - 1 / n_c))
        result.update(
            {
                "risk_ratio": float(np.exp(log_rr)),
                "log_risk_ratio": log_rr,
                "se_log_risk_ratio": se_log_rr,
                "risk_ratio_ci_low": float(np.exp(log_rr - z * se_log_rr)),
                "risk_ratio_ci_high": float(np.exp(log_rr + z * se_log_rr)),
            }
        )
    else:
        result.update(
            {
                "risk_ratio": np.nan,
                "log_risk_ratio": np.nan,
                "se_log_risk_ratio": np.nan,
                "risk_ratio_ci_low": np.nan,
                "risk_ratio_ci_high": np.nan,
            }
        )
    return result


def minimum_detectable_effect(
    baseline_rate: float,
    n_total: int,
    treatment_share: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """MDE cho hiệu hai tỉ lệ, hai phía.

    ``MDE = (z_{1-alpha/2} + z_{power}) · se``, với ``se`` tính dưới giả định cả hai
    arm có tỉ lệ bằng ``baseline_rate``. Đây là xấp xỉ chuẩn: nó bỏ qua việc
    phương sai ở nhánh treatment tăng nhẹ khi hiệu ứng dương, nên hơi lạc quan —
    chênh lệch không đáng kể ở tỉ lệ nhỏ như 0,3%.
    """
    if not 0 < baseline_rate < 1:
        raise ValueError("baseline_rate phải nằm trong (0, 1)")
    if n_total <= 0:
        raise ValueError("n_total phải > 0")
    if not 0 < treatment_share < 1:
        raise ValueError("treatment_share phải nằm trong (0, 1)")
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("alpha và power phải nằm trong (0, 1)")

    n_treated = n_total * treatment_share
    n_control = n_total * (1 - treatment_share)
    variance = baseline_rate * (1 - baseline_rate)
    standard_error = float(np.sqrt(variance / n_treated + variance / n_control))
    return float((norm.ppf(1 - alpha / 2) + norm.ppf(power)) * standard_error)


def required_sample_size(
    effect: float,
    baseline_rate: float,
    treatment_share: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """Tổng cỡ mẫu cần để một hiệu ứng cho trước đạt ``power``.

    Nghịch đảo của :func:`minimum_detectable_effect`. Dùng để trả lời "cần bao
    nhiêu dữ liệu nữa" bằng số học thay vì bằng thêm thí nghiệm.
    """
    if effect == 0:
        raise ValueError("effect phải khác 0")
    if not 0 < baseline_rate < 1:
        raise ValueError("baseline_rate phải nằm trong (0, 1)")
    if not 0 < treatment_share < 1:
        raise ValueError("treatment_share phải nằm trong (0, 1)")

    variance = baseline_rate * (1 - baseline_rate)
    unit_variance = variance / treatment_share + variance / (1 - treatment_share)
    z_sum = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return float(unit_variance * (z_sum / abs(effect)) ** 2)


# ---------------------------------------------------------------------------
# 4. Heterogeneity
# ---------------------------------------------------------------------------


def binned_effect_table(
    outcome,
    treatment,
    bins,
    bin_label: str = "bin",
    min_events_per_arm: int = 1,
) -> pd.DataFrame:
    """Hiệu ứng quan sát được trong từng tầng, trên cả thang cộng và thang nhân.

    Đây là phép ước lượng heterogeneity **không dùng model nào**: trong một RCT,
    hiệu hai tỉ lệ bên trong một tầng xác định bởi biến tiền treatment vẫn là ước
    lượng không thiên lệch của CATE trung bình trong tầng đó. Nhờ vậy nó là mốc
    tham chiếu để đọc mọi kết quả CATE learner về sau.

    Bin nào không đủ ``min_events_per_arm`` sự kiện ở cả hai arm sẽ bị loại, vì
    ``log(RR)`` không xác định và sai số chuẩn của tỉ lệ không đáng tin ở đó.
    """
    y = np.asarray(outcome, dtype="float64").ravel()
    t = np.asarray(treatment, dtype="float64").ravel()
    b = np.asarray(bins).ravel()
    if not (y.shape == t.shape == b.shape):
        raise ValueError("outcome, treatment và bins phải cùng độ dài")

    frame = pd.DataFrame({"bin": b, "t": t, "y": y}).dropna(subset=["bin"])
    grouped = frame.groupby(["bin", "t"])["y"].agg(["size", "sum"]).unstack("t")
    if 0 not in grouped["size"].columns or 1 not in grouped["size"].columns:
        raise ValueError("Cần cả hai arm xuất hiện trong bins")

    n_t = grouped["size"][1]
    n_c = grouped["size"][0]
    events_t = grouped["sum"][1]
    events_c = grouped["sum"][0]
    table = pd.DataFrame(
        {
            bin_label: grouped.index,
            "n": (n_t.fillna(0) + n_c.fillna(0)).to_numpy(),
            "n_treated": n_t.to_numpy(),
            "n_control": n_c.to_numpy(),
            "events_treated": events_t.to_numpy(),
            "events_control": events_c.to_numpy(),
        }
    ).dropna()
    table = table[
        (table["events_treated"] >= min_events_per_arm)
        & (table["events_control"] >= min_events_per_arm)
    ].reset_index(drop=True)
    if table.empty:
        raise ValueError(
            "Không bin nào đủ sự kiện ở cả hai arm — giảm số bin hoặc "
            "giảm min_events_per_arm"
        )

    rate_t = table["events_treated"] / table["n_treated"]
    rate_c = table["events_control"] / table["n_control"]
    table["baseline_rate"] = rate_c
    table["treated_rate"] = rate_t
    table["effect"] = rate_t - rate_c
    table["standard_error"] = np.sqrt(
        rate_t * (1 - rate_t) / table["n_treated"]
        + rate_c * (1 - rate_c) / table["n_control"]
    )
    table["log_risk_ratio"] = np.log(rate_t / rate_c)
    table["se_log_risk_ratio"] = np.sqrt(
        1 / table["events_treated"]
        - 1 / table["n_treated"]
        + 1 / table["events_control"]
        - 1 / table["n_control"]
    )
    table["risk_ratio"] = np.exp(table["log_risk_ratio"])
    z = float(norm.ppf(0.975))
    table["effect_ci_low"] = table["effect"] - z * table["standard_error"]
    table["effect_ci_high"] = table["effect"] + z * table["standard_error"]
    return table


def cochran_q(estimates, standard_errors) -> dict:
    """Kiểm định đồng nhất Cochran ``Q`` cho một nhóm ước lượng có sai số chuẩn.

    ``Q = sum w_i (theta_i − theta_bar)²`` với ``w_i = 1/se_i²``; dưới giả thuyết
    "mọi tầng có cùng hiệu ứng", ``Q ~ chi²(k−1)``. ``I²`` là phần phương sai
    vượt quá mức do sai số lấy mẫu gây ra.

    Hàm được dùng cho *hai thang đo* trên cùng một bảng tầng. So sánh ``Q`` giữa
    hai thang là cách trả lời câu hỏi "hiệu ứng đồng nhất theo thang nào" —
    thang có ``Q`` nhỏ hơn nhiều là thang mà hiệu ứng gần như bất biến, và đó là
    thông tin trực tiếp cho việc chọn cách xếp hạng khách hàng.
    """
    theta = np.asarray(estimates, dtype="float64").ravel()
    se = np.asarray(standard_errors, dtype="float64").ravel()
    if theta.shape != se.shape:
        raise ValueError("estimates và standard_errors phải cùng độ dài")
    finite = np.isfinite(theta) & np.isfinite(se) & (se > 0)
    theta, se = theta[finite], se[finite]
    k = theta.size
    if k < 2:
        raise ValueError("Cần ít nhất 2 ước lượng hữu hạn có se > 0")

    weight = 1.0 / se**2
    pooled = float((weight * theta).sum() / weight.sum())
    q = float((weight * (theta - pooled) ** 2).sum())
    df = k - 1
    return {
        "k": int(k),
        "pooled_estimate": pooled,
        "pooled_standard_error": float(np.sqrt(1.0 / weight.sum())),
        "q_statistic": q,
        "df": int(df),
        "p_value": float(chi2.sf(q, df)),
        "i_squared": float(max(0.0, (q - df) / q)) if q > 0 else 0.0,
    }


def prognostic_dominance_summary(
    table: pd.DataFrame,
    *,
    independent_strata: bool = True,
) -> dict:
    """Hiệu ứng có tỉ lệ thuận với rủi ro nền không, và mạnh tới mức nào.

    Câu hỏi này quyết định một điều rất thực tế: **có cần ước lượng CATE để xếp
    hạng khách hàng không.** Nếu ``effect(x) ≈ (RR − 1) · baseline(x)`` với ``RR``
    gần như không đổi, thì thứ tự theo hiệu ứng trùng thứ tự theo rủi ro nền, và
    một model dự báo outcome thông thường đã xếp hạng đúng — không phải vì nó ước
    lượng được hiệu ứng, mà vì nó ước lượng đúng thứ hạng.

    Hàm trả về ba bằng chứng cho mệnh đề đó: tương quan giữa
    ``baseline_rate`` và ``effect``, tương quan hạng của cùng cặp, và tỉ số
    ``Q_additive / Q_multiplicative``. Tỉ số lớn hơn 1 nghĩa là hiệu ứng đồng
    nhất hơn hẳn trên thang nhân so với thang cộng.

    ``independent_strata=False`` phải dùng khi bảng gộp các phân hoạch chồng lấn
    (ví dụ decile của nhiều feature). Khi đó hàm chỉ trả thống kê mô tả và đặt
    p-value/Q/I² thành ``None``. Cochran Q và pooling inverse-variance đòi hỏi
    các ước lượng độc lập; áp dụng chúng cho những hàng tái sử dụng cùng quan
    sát sẽ làm bằng chứng quá tự tin.

    Đây là **thống kê mô tả trên các tầng đã có**, không phải kiểm định điều kiện
    lý thuyết nào; điều kiện đủ để proxy xếp hạng đúng nằm ở
    :mod:`src.proxy_diagnostic`.
    """
    required = {"baseline_rate", "effect", "standard_error", "log_risk_ratio", "se_log_risk_ratio"}
    missing = sorted(required - set(table.columns))
    if missing:
        raise KeyError(f"table thiếu cột: {missing}")
    if len(table) < 3:
        raise ValueError("Cần ít nhất 3 tầng để tóm tắt prognostic dominance")

    pearson_r, pearson_p = pearsonr(table["baseline_rate"], table["effect"])
    spearman_r, spearman_p = spearmanr(table["baseline_rate"], table["effect"])
    ratio = table["effect"] / table["baseline_rate"]
    summary = {
        "n_strata": int(len(table)),
        "independent_strata": bool(independent_strata),
        "pearson_r": float(pearson_r),
        "pearson_p_value": float(pearson_p) if independent_strata else None,
        "spearman_rho": float(spearman_r),
        "spearman_p_value": float(spearman_p) if independent_strata else None,
        "effect_over_baseline_median": float(ratio.median()),
        "effect_over_baseline_iqr": float(ratio.quantile(0.75) - ratio.quantile(0.25)),
    }
    if not independent_strata:
        summary.update(
            {
                "pooled_risk_ratio": None,
                "q_additive": None,
                "q_multiplicative": None,
                "q_ratio_additive_over_multiplicative": None,
                "i_squared_additive": None,
                "i_squared_multiplicative": None,
                "p_value_additive": None,
                "p_value_multiplicative": None,
                "inference_note": (
                    "Descriptive only: rows reuse observations across overlapping "
                    "feature partitions. Inferential summaries are reported per feature."
                ),
            }
        )
        return summary

    additive = cochran_q(table["effect"], table["standard_error"])
    multiplicative = cochran_q(
        table["log_risk_ratio"], table["se_log_risk_ratio"]
    )
    summary.update(
        {
            "pooled_risk_ratio": float(np.exp(multiplicative["pooled_estimate"])),
            "q_additive": additive["q_statistic"],
            "q_multiplicative": multiplicative["q_statistic"],
            "q_ratio_additive_over_multiplicative": (
                float(additive["q_statistic"] / multiplicative["q_statistic"])
                if multiplicative["q_statistic"] > 0
                else np.inf
            ),
            "i_squared_additive": additive["i_squared"],
            "i_squared_multiplicative": multiplicative["i_squared"],
            "p_value_additive": additive["p_value"],
            "p_value_multiplicative": multiplicative["p_value"],
        }
    )
    return summary


def sample_representativity(
    full: pd.DataFrame,
    sample: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """So trung bình từng cột giữa toàn bộ dữ liệu và một mẫu, kèm SMD.

    Dùng để chứng minh rằng biểu đồ vẽ trên mẫu đại diện được cho tổng thể, thay
    vì để người đọc phải tin. SMD ở đây đo *sai lệch do lấy mẫu*, không phải sai
    lệch giữa hai arm.
    """
    rows = []
    for column in columns:
        full_values = full[column]
        sample_values = sample[column]
        pooled = float(np.sqrt((full_values.var(ddof=1) + sample_values.var(ddof=1)) / 2.0))
        difference = float(sample_values.mean() - full_values.mean())
        rows.append(
            {
                "column": column,
                "full_mean": float(full_values.mean()),
                "sample_mean": float(sample_values.mean()),
                "difference": difference,
                "smd": difference / pooled if pooled > 0 else 0.0,
            }
        )
    return pd.DataFrame(rows)
