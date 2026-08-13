import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import auc


def transformed_outcome(y_true, treatment, propensity: float | None = None) -> np.ndarray:
    """Revert-label / transformed outcome có kỳ vọng điều kiện bằng CATE trên RCT.

    ``R = Y * (T-p) / (p*(1-p))`` và ``E[R|X] = tau(X)`` khi propensity ``p`` là
    xác suất gán treatment. Dùng làm metric phụ cho model selection; variance của R cao nên
    không thay Qini/AUUC làm báo cáo chính.
    """
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    if y_true.shape != treatment.shape:
        raise ValueError("y_true và treatment phải có cùng shape")
    if y_true.size == 0 or not np.isfinite(y_true).all():
        raise ValueError("y_true phải không rỗng và hữu hạn")
    if not np.isfinite(treatment).all() or not set(np.unique(treatment)).issubset(
        {0.0, 1.0}
    ):
        raise ValueError("treatment phải hữu hạn và chỉ gồm 0/1")
    p = float(np.mean(treatment) if propensity is None else propensity)
    if not 0 < p < 1:
        raise ValueError(f"propensity phải nằm trong (0, 1), nhận được {p}")
    return y_true * (treatment - p) / (p * (1.0 - p))


def transformed_outcome_mse(y_true, treatment, uplift_score, propensity: float | None = None) -> float:
    """MSE giữa CATE score và transformed outcome; nhỏ hơn là tốt hơn.

    Đây là validation loss không cần ground-truth CATE cá nhân. Nó unbiased về thứ tự
    kỳ vọng giữa candidate trong cùng validation set nhưng có variance cao, vì vậy pipeline
    dùng nó như metric phụ cùng Qini/AUUC chứ không chọn model chỉ bằng một con số này.
    """
    score = np.asarray(uplift_score, dtype="float64")
    pseudo = transformed_outcome(y_true, treatment, propensity=propensity)
    return float(np.mean((pseudo - score) ** 2))


def uplift_calibration_error(
    y_true,
    treatment,
    uplift_score,
    n_bins: int = 10,
) -> float:
    """Expected uplift calibration error (EUCE) theo equal-frequency bins.

    Trong mỗi bin xếp theo predicted CATE, so mean predicted CATE với chênh lệch conversion
    treatment-control quan sát được. Metric chỉ có ý nghĩa cho score có scale CATE; không dùng
    cho Response baseline hoặc rank ensemble.
    """
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    score = np.asarray(uplift_score, dtype="float64")
    if not (len(y_true) == len(treatment) == len(score)):
        raise ValueError("y_true, treatment và uplift_score phải có cùng độ dài")
    if n_bins < 2 or n_bins > len(score):
        raise ValueError("n_bins phải nằm trong [2, n_samples]")

    order = np.argsort(score, kind="mergesort")
    errors = []
    weights = []
    for idx in np.array_split(order, n_bins):
        t_bin = treatment[idx]
        y_bin = y_true[idx]
        n_t = np.sum(t_bin == 1)
        n_c = np.sum(t_bin == 0)
        if n_t == 0 or n_c == 0:
            continue
        observed = y_bin[t_bin == 1].mean() - y_bin[t_bin == 0].mean()
        errors.append(abs(float(observed - score[idx].mean())))
        weights.append(len(idx))
    if not errors:
        return float("nan")
    return float(np.average(errors, weights=weights))


def _qini_curve_raw(y_true: np.ndarray, uplift: np.ndarray, treatment: np.ndarray):
    """Qini(t) = Y1(t) - Y0(t) * N1(t)/N0(t), sorted by uplift score descending.

    Nguồn khái niệm: Radcliffe & Surry (2011), TR-2011-1, mục 4.2, định nghĩa Qini
    measure bằng diện tích giữa incremental-gains curve và random-targeting reference.
    Paper không đưa công thức per-threshold mà dẫn Radcliffe (2007); repository chưa có
    bản mở của nguồn đó để đối chiếu. Hành vi per-threshold ở đây theo
    `sklift.metrics.qini_curve` và được kiểm tra số học trong tests/test_evaluation.py.
    Gộp các điểm có uplift score trùng nhau (tie) thành 1 threshold để khớp hành vi
    `sklift` khi có trùng giá trị.
    """
    order = np.argsort(uplift, kind="mergesort")[::-1]
    y_true = y_true[order]
    treatment = treatment[order]
    uplift = uplift[order]

    y_ctrl = np.where(treatment == 0, y_true, 0.0)
    y_trmnt = np.where(treatment == 1, y_true, 0.0)

    distinct_idx = np.where(np.diff(uplift))[0]
    threshold_idx = np.r_[distinct_idx, uplift.size - 1]

    n1 = np.cumsum(treatment)[threshold_idx]
    y1 = np.cumsum(y_trmnt)[threshold_idx]
    n_all = threshold_idx + 1
    n0 = n_all - n1
    y0 = np.cumsum(y_ctrl)[threshold_idx]

    ratio = np.divide(n1, n0, out=np.zeros_like(n1), where=n0 != 0)
    qini_values = y1 - y0 * ratio

    if n_all.size == 0 or qini_values[0] != 0 or n_all[0] != 0:
        n_all = np.r_[0, n_all]
        qini_values = np.r_[0, qini_values]

    return n_all, qini_values


def _perfect_qini_curve_raw(y_true: np.ndarray, treatment: np.ndarray):
    perfect_score = y_true * treatment - y_true * (1 - treatment)
    return _qini_curve_raw(y_true, perfect_score, treatment)


def qini_curve(y_true, treatment, uplift_score) -> pd.DataFrame:
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    uplift_score = np.asarray(uplift_score, dtype="float64")

    n_all, qini_values = _qini_curve_raw(y_true, uplift_score, treatment)
    return pd.DataFrame({"n_targeted": n_all, "qini": qini_values})


def _uplift_curve_raw(y_true: np.ndarray, uplift: np.ndarray, treatment: np.ndarray):
    """UpliftCurve(t) = (Y1(t)/N1(t) - Y0(t)/N0(t)) * N(t) — khác Qini ở chỗ dùng CHÊNH LỆCH
    TỈ LỆ (mean uplift) nhân với tổng cỡ mẫu N(t), thay vì Y1(t) - Y0(t)·N1(t)/N0(t).

    NGUỒN GỐC — đọc trực tiếp mã nguồn `sklift.metrics.uplift_curve` (thư viện tham chiếu
    công khai, `.venv/Lib/site-packages/sklift/metrics/metrics.py`) trước khi viết, đúng
    nguyên tắc mục 6.1: không suy đoán công thức AUUC. Docstring của `sklift` tự ghi nguồn
    tham khảo cho định nghĩa "uplift curve" là Devriendt, Guns & Verbeke (2020), *Learning
    to rank for uplift modeling*, arXiv:2002.05897 — **paper này CHƯA được đọc trực tiếp
    trong dự án**, chỉ ghi lại đúng những gì `sklift` tự trích dẫn, không tự nhận đã verify
    nội dung paper đó.
    """
    order = np.argsort(uplift, kind="mergesort")[::-1]
    y_true = y_true[order]
    treatment = treatment[order]
    uplift = uplift[order]

    y_ctrl = np.where(treatment == 0, y_true, 0.0)
    y_trmnt = np.where(treatment == 1, y_true, 0.0)

    distinct_idx = np.where(np.diff(uplift))[0]
    threshold_idx = np.r_[distinct_idx, uplift.size - 1]

    n1 = np.cumsum(treatment)[threshold_idx]
    y1 = np.cumsum(y_trmnt)[threshold_idx]
    n_all = threshold_idx + 1
    n0 = n_all - n1
    y0 = np.cumsum(y_ctrl)[threshold_idx]

    rate1 = np.divide(y1, n1, out=np.zeros_like(y1), where=n1 != 0)
    rate0 = np.divide(y0, n0, out=np.zeros_like(y0), where=n0 != 0)
    curve_values = (rate1 - rate0) * n_all

    if n_all.size == 0 or curve_values[0] != 0 or n_all[0] != 0:
        n_all = np.r_[0, n_all]
        curve_values = np.r_[0, curve_values]

    return n_all, curve_values


def _perfect_uplift_curve_raw(y_true: np.ndarray, treatment: np.ndarray):
    cr_num = np.sum((y_true == 1) & (treatment == 0))
    tn_num = np.sum((y_true == 0) & (treatment == 1))
    summand = y_true if cr_num > tn_num else treatment
    perfect_uplift = 2 * (y_true == treatment).astype("float64") + summand
    return _uplift_curve_raw(y_true, perfect_uplift, treatment)


def uplift_curve(y_true, treatment, uplift_score) -> pd.DataFrame:
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    uplift_score = np.asarray(uplift_score, dtype="float64")

    n_all, curve_values = _uplift_curve_raw(y_true, uplift_score, treatment)
    return pd.DataFrame({"n_targeted": n_all, "uplift": curve_values})


def auuc_score(y_true, treatment, uplift_score) -> float:
    """AUUC (normalized Area Under the Uplift Curve) — cùng công thức chuẩn hoá AUC(actual)
    trừ AUC(random), chia AUC(perfect) trừ AUC(random) như `qini_score`, nhưng dùng
    `_uplift_curve_raw`/`_perfect_uplift_curve_raw` thay vì đường Qini. Đối chiếu bắt buộc
    với `sklift.metrics.uplift_auc_score` (xem tests/test_evaluation.py).
    """
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    uplift_score = np.asarray(uplift_score, dtype="float64")

    x_actual, y_actual = _uplift_curve_raw(y_true, uplift_score, treatment)
    x_perfect, y_perfect = _perfect_uplift_curve_raw(y_true, treatment)
    x_baseline, y_baseline = np.array([0, x_perfect[-1]]), np.array([0, y_perfect[-1]])

    auc_baseline = auc(x_baseline, y_baseline)
    auc_perfect = auc(x_perfect, y_perfect) - auc_baseline
    auc_actual = auc(x_actual, y_actual) - auc_baseline

    if auc_perfect == 0:
        warnings.warn(
            "auuc_score: perfect curve has zero area — AUUC không xác định được ở sample "
            "này, trả về NaN thay vì chia cho 0.",
            RuntimeWarning,
            stacklevel=2,
        )
        return float("nan")

    return auc_actual / auc_perfect


def qini_score(y_true, treatment, uplift_score) -> float:
    """Qini coefficient: AUC(actual) - AUC(random), normalized bởi AUC(perfect) - AUC(random).

    Cùng định nghĩa với `sklift.metrics.qini_auc_score(negative_effect=True)` — đối chiếu
    bắt buộc theo mục 6.2 CAUSAL_UPLIFT_PLAN.md, lệch < 1e-6. Lưu ý: đây là 1 trong nhiều
    biến thể "qini coefficient" xuất hiện trong tài liệu (Radcliffe & Surry 2011 mục 4.2
    liệt kê riêng: Q = diện tích thô chia N², q0 = tỉ lệ so với "zero-downlift optimum"
    khi giả định không có negative effect). Biến thể ở đây — chuẩn hoá theo đường "perfect"
    có tính cả negative effect (`negative_effect=True`) — là lựa chọn của `sklift`, không
    phải Q hay q0 nguyên bản trong paper 2011; chọn biến thể này vì đây là hàm cross-check
    bắt buộc theo mục 6.2, không phải vì nó "đúng hơn" các biến thể khác.
    """
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    uplift_score = np.asarray(uplift_score, dtype="float64")

    x_actual, y_actual = _qini_curve_raw(y_true, uplift_score, treatment)
    x_perfect, y_perfect = _perfect_qini_curve_raw(y_true, treatment)
    x_baseline, y_baseline = np.array([0, x_perfect[-1]]), np.array([0, y_perfect[-1]])

    auc_baseline = auc(x_baseline, y_baseline)
    auc_perfect = auc(x_perfect, y_perfect) - auc_baseline
    auc_actual = auc(x_actual, y_actual) - auc_baseline

    if auc_perfect == 0:
        warnings.warn(
            "qini_score: perfect curve has zero area (vd. không có conversion nào, hoặc "
            "control-responder count == treated-non-responder count trong sample này) — "
            "Qini không xác định được ở sample này, trả về NaN thay vì chia cho 0.",
            RuntimeWarning,
            stacklevel=2,
        )
        return float("nan")

    return auc_actual / auc_perfect


def _weighted_qini_curve_from_order(
    y_true: np.ndarray,
    treatment: np.ndarray,
    uplift_score: np.ndarray,
    sample_weight: np.ndarray,
    order: np.ndarray,
):
    """Qini curve cho bootstrap multiplicity weights trên một order đã sort.

    Một nonparametric bootstrap sample tương đương gán cho mỗi quan sát số lần
    nó được rút (multinomial count). Vì score không đổi giữa các resample, ta
    sort một lần và chỉ cập nhật cumulative weighted counts.
    """
    y = y_true[order]
    t = treatment[order]
    score = uplift_score[order]
    weight = sample_weight[order]

    distinct_idx = np.where(np.diff(score))[0]
    threshold_idx = np.r_[distinct_idx, score.size - 1]
    weighted_t = weight * t
    weighted_c = weight * (1.0 - t)
    n1 = np.cumsum(weighted_t)[threshold_idx]
    n0 = np.cumsum(weighted_c)[threshold_idx]
    n_all = n1 + n0
    y1 = np.cumsum(weighted_t * y)[threshold_idx]
    y0 = np.cumsum(weighted_c * y)[threshold_idx]

    # Score groups absent from this resample do not exist in the expanded
    # bootstrap sample; remove zero-width curve points.
    keep = np.diff(np.r_[0.0, n_all]) > 0
    n1, n0, n_all, y1, y0 = (
        values[keep] for values in (n1, n0, n_all, y1, y0)
    )
    ratio = np.divide(n1, n0, out=np.zeros_like(n1), where=n0 != 0)
    qini_values = y1 - y0 * ratio
    return np.r_[0.0, n_all], np.r_[0.0, qini_values]


def _weighted_qini_score(
    y_true: np.ndarray,
    treatment: np.ndarray,
    uplift_score: np.ndarray,
    sample_weight: np.ndarray,
    order: np.ndarray,
    perfect_order: np.ndarray,
) -> float:
    x_actual, y_actual = _weighted_qini_curve_from_order(
        y_true,
        treatment,
        uplift_score,
        sample_weight,
        order,
    )
    perfect_score = y_true * treatment - y_true * (1.0 - treatment)
    x_perfect, y_perfect = _weighted_qini_curve_from_order(
        y_true,
        treatment,
        perfect_score,
        sample_weight,
        perfect_order,
    )
    x_baseline = np.array([0.0, x_perfect[-1]])
    y_baseline = np.array([0.0, y_perfect[-1]])
    auc_baseline = auc(x_baseline, y_baseline)
    auc_perfect = auc(x_perfect, y_perfect) - auc_baseline
    if auc_perfect == 0:
        return float("nan")
    return float((auc(x_actual, y_actual) - auc_baseline) / auc_perfect)


def bootstrap_ci(y_true, treatment, uplift_score, n_boot: int = 500, seed: int = 42, alpha: float = 0.05):
    """Nonparametric bootstrap percentile CI cho qini_score (Efron & Tibshirani, 1993,
    *An Introduction to the Bootstrap* — phương pháp percentile bootstrap chuẩn, không
    gắn với 1 paper uplift cụ thể nào).

    arXiv 2210.02152 không phải nguồn của procedure này: phụ lục A.3 của paper dùng
    normal-approximation interval và outcome adjustment. Implementation bên dưới dùng
    percentile bootstrap theo Efron & Tibshirani; negative-control test kiểm tra coverage
    của 0 trên fixture có expected ranking effect bằng 0.
    """
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    uplift_score = np.asarray(uplift_score, dtype="float64")
    n = len(y_true)

    rng = np.random.default_rng(seed)
    order = np.argsort(uplift_score, kind="mergesort")[::-1]
    perfect_score = y_true * treatment - y_true * (1.0 - treatment)
    perfect_order = np.argsort(perfect_score, kind="mergesort")[::-1]
    scores = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # qini_score đã tự warn 1 lần; ở đây chỉ cần đếm NaN
        for _ in range(n_boot):
            idx = rng.integers(0, n, size=n)
            weight = np.bincount(idx, minlength=n).astype("float64", copy=False)
            scores.append(
                _weighted_qini_score(
                    y_true,
                    treatment,
                    uplift_score,
                    weight,
                    order,
                    perfect_order,
                )
            )
    scores = np.asarray(scores, dtype="float64")
    n_undefined = int(np.sum(~np.isfinite(scores)))
    scores = scores[np.isfinite(scores)]

    if len(scores) == 0:
        raise ValueError(
            f"bootstrap_ci: toàn bộ {n_boot} resample đều cho qini_score = NaN (không có "
            "conversion nào trong dữ liệu đầu vào, hoặc mẫu quá nhỏ để có treatment-effect "
            "asymmetry) — không tính được CI. Kiểm tra lại dữ liệu đầu vào trước khi gọi hàm này."
        )
    if n_undefined > 0:
        warnings.warn(
            f"bootstrap_ci: {n_undefined}/{n_boot} resample cho qini_score = NaN, đã bỏ qua khi "
            "tính percentile — CI dựa trên ít resample hơn n_boot yêu cầu.",
            RuntimeWarning,
            stacklevel=2,
        )

    lb = np.percentile(scores, 100 * alpha / 2)
    ub = np.percentile(scores, 100 * (1 - alpha / 2))
    return lb, ub


def paired_bootstrap_difference_ci(
    scores_a,
    scores_b,
    y_true,
    treatment,
    n_boot: int = 500,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict:
    """Percentile bootstrap CI cho ``Qini(A) - Qini(B)`` trên cùng holdout.

    Mỗi bootstrap iteration dùng cùng một bộ index cho cả hai model để giữ
    pairing. Đây là output so sánh chính; CI chứa 0 nghĩa là dữ liệu hiện tại
    chưa tách được hai model theo metric/biến thể Qini này.
    """
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    scores_a = np.asarray(scores_a, dtype="float64")
    scores_b = np.asarray(scores_b, dtype="float64")
    if not (len(y_true) == len(treatment) == len(scores_a) == len(scores_b)):
        raise ValueError("scores_a, scores_b, y_true và treatment phải có cùng độ dài")
    if n_boot < 2:
        raise ValueError("n_boot phải >= 2")
    if not 0 < alpha < 1:
        raise ValueError("alpha phải nằm trong (0, 1)")

    observed = qini_score(y_true, treatment, scores_a) - qini_score(
        y_true, treatment, scores_b
    )
    rng = np.random.default_rng(seed)
    n = len(y_true)
    order_a = np.argsort(scores_a, kind="mergesort")[::-1]
    order_b = np.argsort(scores_b, kind="mergesort")[::-1]
    perfect_score = y_true * treatment - y_true * (1.0 - treatment)
    perfect_order = np.argsort(perfect_score, kind="mergesort")[::-1]
    diffs = []
    values_a = []
    values_b = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for _ in range(n_boot):
            idx = rng.integers(0, n, size=n)
            weight = np.bincount(idx, minlength=n).astype("float64", copy=False)
            value_a = _weighted_qini_score(
                y_true,
                treatment,
                scores_a,
                weight,
                order_a,
                perfect_order,
            )
            value_b = _weighted_qini_score(
                y_true,
                treatment,
                scores_b,
                weight,
                order_b,
                perfect_order,
            )
            if np.isfinite(value_a) and np.isfinite(value_b):
                values_a.append(value_a)
                values_b.append(value_b)
                diffs.append(value_a - value_b)
    if not diffs:
        raise ValueError("Không có bootstrap difference hữu hạn để tính CI")
    diffs = np.asarray(diffs, dtype="float64")
    values_a = np.asarray(values_a, dtype="float64")
    values_b = np.asarray(values_b, dtype="float64")
    return {
        "observed_difference": float(observed),
        "ci_low": float(np.percentile(diffs, 100 * alpha / 2)),
        "ci_high": float(np.percentile(diffs, 100 * (1 - alpha / 2))),
        "score_a_ci_low": float(np.percentile(values_a, 100 * alpha / 2)),
        "score_a_ci_high": float(np.percentile(values_a, 100 * (1 - alpha / 2))),
        "score_b_ci_low": float(np.percentile(values_b, 100 * alpha / 2)),
        "score_b_ci_high": float(np.percentile(values_b, 100 * (1 - alpha / 2))),
        "probability_difference_positive": float(np.mean(diffs > 0)),
        "n_valid_bootstrap": int(len(diffs)),
    }


def paired_qini_bootstrap_matrix(
    scores_by_model: dict[str, np.ndarray],
    y_true,
    treatment,
    n_boot: int = 500,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap nhiều Qini score trên cùng resample, chỉ tính perfect curve một lần.

    Hàm này phục vụ so sánh nhiều model trên một confirmation set. Tất cả model
    dùng cùng bootstrap weights nên mọi difference giữ đúng pairing.
    """
    names = list(scores_by_model)
    if not names:
        raise ValueError("scores_by_model không được rỗng")
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    scores = {
        name: np.asarray(value, dtype="float64")
        for name, value in scores_by_model.items()
    }
    n = len(y_true)
    if any(len(value) != n for value in scores.values()) or len(treatment) != n:
        raise ValueError("Mọi score, y_true và treatment phải có cùng độ dài")
    if n_boot < 2:
        raise ValueError("n_boot phải >= 2")
    if not 0 < alpha < 1:
        raise ValueError("alpha phải nằm trong (0, 1)")

    orders = {
        name: np.argsort(value, kind="mergesort")[::-1]
        for name, value in scores.items()
    }
    perfect_score = y_true * treatment - y_true * (1.0 - treatment)
    perfect_order = np.argsort(perfect_score, kind="mergesort")[::-1]
    observed = np.array(
        [qini_score(y_true, treatment, scores[name]) for name in names],
        dtype="float64",
    )
    draws = np.full((n_boot, len(names)), np.nan, dtype="float64")
    rng = np.random.default_rng(seed)
    for bootstrap_index in range(n_boot):
        idx = rng.integers(0, n, size=n)
        weight = np.bincount(idx, minlength=n).astype("float64", copy=False)
        x_perfect, y_perfect = _weighted_qini_curve_from_order(
            y_true,
            treatment,
            perfect_score,
            weight,
            perfect_order,
        )
        auc_baseline = auc(
            np.array([0.0, x_perfect[-1]]),
            np.array([0.0, y_perfect[-1]]),
        )
        denominator = auc(x_perfect, y_perfect) - auc_baseline
        if denominator == 0:
            continue
        for model_index, name in enumerate(names):
            x_actual, y_actual = _weighted_qini_curve_from_order(
                y_true,
                treatment,
                scores[name],
                weight,
                orders[name],
            )
            draws[bootstrap_index, model_index] = (
                auc(x_actual, y_actual) - auc_baseline
            ) / denominator

    valid = np.isfinite(draws).all(axis=1)
    if not np.any(valid):
        raise ValueError("Không có bootstrap draw hữu hạn cho toàn bộ model")
    valid_draws = draws[valid]
    return {
        "model_names": names,
        "observed": observed,
        "draws": valid_draws,
        "ci_low": np.quantile(valid_draws, alpha / 2, axis=0),
        "ci_high": np.quantile(valid_draws, 1 - alpha / 2, axis=0),
        "n_valid_bootstrap": int(valid.sum()),
    }


def paired_bootstrap_compare(scores_a, scores_b, y_true, treatment, n_boot: int = 500, seed: int = 42) -> float:
    """Legacy paired-bootstrap tail heuristic.

    Hàm được giữ để tương thích code cũ, nhưng output không được dùng làm p-value headline
    vì chưa có inversion/null-centering protocol chuẩn. Báo cáo release phải dùng
    :func:`paired_bootstrap_difference_ci`, tức percentile CI của chênh lệch Qini trên
    cùng bootstrap samples.
    """
    y_true = np.asarray(y_true, dtype="float64")
    treatment = np.asarray(treatment, dtype="float64")
    scores_a = np.asarray(scores_a, dtype="float64")
    scores_b = np.asarray(scores_b, dtype="float64")
    n = len(y_true)

    rng = np.random.default_rng(seed)
    diffs = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # qini_score đã tự warn; ở đây chỉ đếm NaN
        for _ in range(n_boot):
            idx = rng.integers(0, n, size=n)
            qa = qini_score(y_true[idx], treatment[idx], scores_a[idx])
            qb = qini_score(y_true[idx], treatment[idx], scores_b[idx])
            diffs.append(qa - qb)
    diffs = np.asarray(diffs, dtype="float64")
    n_undefined = int(np.sum(~np.isfinite(diffs)))
    diffs = diffs[np.isfinite(diffs)]

    if len(diffs) == 0:
        raise ValueError(
            f"paired_bootstrap_compare: toàn bộ {n_boot} resample đều cho qini_score = NaN ở "
            "ít nhất 1 trong 2 model (không có conversion nào, hoặc mẫu quá nhỏ) — không so "
            "sánh được. Kiểm tra lại dữ liệu đầu vào."
        )
    if n_undefined > 0:
        warnings.warn(
            f"paired_bootstrap_compare: {n_undefined}/{n_boot} resample bị bỏ qua vì qini_score "
            "= NaN ở ít nhất 1 model — p-value dựa trên ít resample hơn n_boot yêu cầu.",
            RuntimeWarning,
            stacklevel=2,
        )

    p_le = np.mean(diffs <= 0)
    p_ge = np.mean(diffs >= 0)
    return float(min(1.0, 2 * min(p_le, p_ge)))
