"""Chẩn đoán khi nào một proxy xếp hạng đúng theo treatment effect.

Nguồn: arXiv 2206.12532. Chẩn đoán này trả lời câu hỏi trung tâm của dự án — vì sao xếp
theo `p₀` lại gần đúng xếp theo `τ`.

Điều dễ hiện thực sai nhất, và được kiểm riêng: điều kiện bị chi phối bởi **giá trị lớn
nhất** của chặn CATE, không phải bởi trung bình. Dùng trung bình sẽ cho kết luận lạc quan
sai ở đúng những trường hợp cần cẩn thận nhất.
"""

import numpy as np
import pytest

from src.proxy_diagnostic import (
    ordering_condition_by_budget,
    proxy_rank_agreement,
    unbiased_ordering_condition,
)


def test_condition_matches_the_stated_inequality():
    """Kiểm tra đúng bất đẳng thức ``theta_max < (1 − beta_max)/2`` của nguồn."""
    # beta_max = 0.2  ->  threshold = 0.4
    result = unbiased_ordering_condition([0.1, 0.399, 0.05], max_cate_bound=0.2)
    assert result.threshold == pytest.approx(0.4)
    assert result.theta_max == pytest.approx(0.399)
    assert result.holds is True

    result = unbiased_ordering_condition([0.1, 0.401, 0.05], max_cate_bound=0.2)
    assert result.holds is False


def test_threshold_shrinks_as_the_cate_bound_grows():
    """CATE bound lớn hơn làm điều kiện khó thỏa hơn, đúng theo công thức."""
    thresholds = [
        unbiased_ordering_condition([0.1], max_cate_bound=beta).threshold
        for beta in (0.0, 0.1, 0.3, 0.6)
    ]
    assert thresholds == sorted(thresholds, reverse=True)
    assert thresholds[0] == pytest.approx(0.5)


def test_condition_is_driven_by_the_maximum_not_the_mean():
    """Một đuôi rất nhỏ cũng đủ làm hỏng điều kiện toàn population."""
    mostly_small = np.full(100_000, 0.001)
    mostly_small[0] = 0.9
    result = unbiased_ordering_condition(mostly_small, max_cate_bound=0.1)
    assert result.theta_max == pytest.approx(0.9)
    assert result.holds is False
    # Bỏ đúng một dòng đuôi là điều kiện thỏa lại.
    assert unbiased_ordering_condition(mostly_small[1:], max_cate_bound=0.1).holds


def test_budget_view_is_monotone_in_theta_max():
    """theta_max của nhóm top-b không giảm khi b tăng, vì tập lồng nhau."""
    rng = np.random.default_rng(0)
    n = 20_000
    score = rng.random(n)
    baseline = rng.random(n) * 0.5
    rows = ordering_condition_by_budget(
        baseline,
        score,
        max_cate_bound=0.05,
        budgets=(0.01, 0.05, 0.1, 0.5, 1.0),
    )
    theta_max = [row["theta_max"] for row in rows]
    assert theta_max == sorted(theta_max)
    assert rows[-1]["n_targeted"] == n


def test_budget_view_flags_where_the_condition_breaks():
    """Đưa baseline cao vào đúng nhóm score cao thì điều kiện hỏng ngay ở budget nhỏ."""
    n = 10_000
    score = np.linspace(1.0, 0.0, n)
    baseline = np.full(n, 0.01)
    baseline[:50] = 0.95  # 0.5% đầu bảng có baseline rất cao
    rows = ordering_condition_by_budget(
        baseline,
        score,
        max_cate_bound=0.1,
        budgets=(0.01, 0.10),
    )
    assert rows[0]["holds"] is False
    assert rows[1]["holds"] is False
    # Nếu đuôi cao nằm ở cuối bảng score thì budget nhỏ lại thỏa.
    reversed_rows = ordering_condition_by_budget(
        baseline[::-1],
        score,
        max_cate_bound=0.1,
        budgets=(0.01, 1.0),
    )
    assert reversed_rows[0]["holds"] is True
    assert reversed_rows[-1]["holds"] is False


def test_rank_agreement_detects_identical_and_reversed_orderings():
    rng = np.random.default_rng(1)
    score = rng.random(5_000)
    rows = proxy_rank_agreement(
        score,
        {
            "same": score * 3.0 + 1.0,
            "reversed": -score,
            "noise": rng.random(5_000),
        },
        sample_size=None,
    )
    by_name = {row["cate_model"]: row for row in rows}
    assert by_name["same"]["spearman_rho"] == pytest.approx(1.0)
    assert by_name["reversed"]["spearman_rho"] == pytest.approx(-1.0)
    assert abs(by_name["noise"]["spearman_rho"]) < 0.1


def test_rank_agreement_subsamples_large_inputs_reproducibly():
    rng = np.random.default_rng(2)
    score = rng.random(50_000)
    estimates = {"a": rng.random(50_000)}
    first = proxy_rank_agreement(score, estimates, sample_size=1_000, seed=7)
    second = proxy_rank_agreement(score, estimates, sample_size=1_000, seed=7)
    assert first[0]["n_used"] == 1_000
    assert first[0]["spearman_rho"] == pytest.approx(second[0]["spearman_rho"])


def test_input_validation():
    with pytest.raises(ValueError):
        unbiased_ordering_condition([], max_cate_bound=0.1)
    with pytest.raises(ValueError):
        unbiased_ordering_condition([0.5, 1.5], max_cate_bound=0.1)
    with pytest.raises(ValueError):
        unbiased_ordering_condition([0.5], max_cate_bound=1.0)
    with pytest.raises(ValueError):
        unbiased_ordering_condition([0.5, np.nan], max_cate_bound=0.1)
    with pytest.raises(ValueError):
        ordering_condition_by_budget([0.1], [0.1, 0.2], max_cate_bound=0.1)
    with pytest.raises(ValueError):
        ordering_condition_by_budget([0.1], [0.1], max_cate_bound=0.1, budgets=(1.5,))
    with pytest.raises(ValueError):
        proxy_rank_agreement(np.zeros(5), {"bad": np.zeros(4)})
