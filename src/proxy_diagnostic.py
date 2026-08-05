"""Chẩn đoán khi nào một proxy dự báo xếp hạng đúng theo treatment effect.

Bối cảnh: ba sprint liên tiếp cho thấy Response — một model dự báo
``P(conversion)``, không phải CATE estimator — xếp hạng tốt hơn mọi CATE learner
đã thử. Module này trả lời câu hỏi tiếp theo: **khi nào điều đó ngừng đúng?**

Nguồn: Fernández-Loría & Loría, *Causal Ordering Without Effect Estimation: A
Framework for Using Proxies in Treatment Prioritization*, arXiv 2206.12532
(bản v7, HTML). Khung này định nghĩa *amenability* ``A`` là xu hướng tiềm ẩn bị
can thiệp tác động, và nêu điều kiện để một tín hiệu dự báo ``S`` xếp hạng đúng
theo CATE:

- **Amenability Mediation:** ``E[S | A, X] = E[S | A]``;
- **Amenability Monotonicity:** ``E[S | A]`` đơn điệu nghiêm ngặt theo ``A``.

Hai điều kiện đó kéo theo unbiased ordering (Proposition 2). Chúng không kiểm tra
trực tiếp được từ dữ liệu vì ``A`` là biến tiềm ẩn, nên paper đưa ra một công cụ
phân tích dùng hai đại lượng quan sát/ước lượng được.

## Ranh giới nguồn — đọc trước khi dùng

Ba mức khác nhau trong module này, được đánh dấu rõ:

1. :func:`unbiased_ordering_condition` — **lấy nguyên văn từ nguồn.** Bất đẳng
   thức ``theta_max < (1 − beta_max) / 2``.
2. :func:`ordering_condition_by_budget` — **cách vận dụng của repo này**, không
   phải của paper. Nó áp đúng bất đẳng thức trên cho từng sub-population top-b
   thay vì cho toàn bộ population.
3. :func:`proxy_rank_agreement` — thống kê mô tả thông thường (Spearman), không
   cần nguồn.

**Không hiện thực:** paper còn nêu một điều kiện cho *subset* dạng
``tau_k < [1 + ((1+beta_max)/(1−beta_max))² · (theta_max/(1−theta_max))]⁻¹``.
Biến ``tau_k`` trong bản trích xuất không được định nghĩa đủ rõ để hiện thực mà
không suy đoán, nên nó bị bỏ qua theo quy tắc không tự chế công thức của dự án.
Muốn dùng, phải đọc đầy đủ mục 4.6 của bản gốc trước.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import spearmanr


@dataclass(frozen=True)
class OrderingCondition:
    """Kết quả kiểm tra điều kiện unbiased ordering."""

    theta_max: float
    beta_max: float
    threshold: float
    holds: bool
    n: int

    def as_dict(self) -> dict:
        return {
            "theta_max": self.theta_max,
            "beta_max": self.beta_max,
            "threshold": self.threshold,
            "holds": self.holds,
            "n": self.n,
        }


def unbiased_ordering_condition(
    baseline_probability,
    max_cate_bound: float,
) -> OrderingCondition:
    """Điều kiện đủ để proxy xếp hạng đúng theo CATE, lấy nguyên văn từ nguồn.

    ``theta_max`` là xác suất baseline lớn nhất trong population, tức
    ``max_x P(Y = 1 | X = x, không treatment)``. ``beta_max`` là chặn trên của
    CATE lớn nhất; paper ghi rõ đại lượng này do chuyên gia đặt vì không ước
    lượng trực tiếp được.

    Điều kiện::

        theta_max < (1 − beta_max) / 2

    Đúng thì unbiased ordering giữ được trên toàn population. **Không đúng thì
    kết luận không đảo ngược lại**: đây là điều kiện đủ, không phải điều kiện
    cần. Proxy vẫn có thể xếp hạng tốt khi điều kiện hỏng; chỉ là khung này
    không còn bảo đảm.
    """
    theta = np.asarray(baseline_probability, dtype="float64").ravel()
    if theta.size == 0:
        raise ValueError("baseline_probability không được rỗng")
    if not np.isfinite(theta).all():
        raise ValueError("baseline_probability phải hữu hạn")
    if np.any((theta < 0) | (theta > 1)):
        raise ValueError("baseline_probability phải nằm trong [0, 1]")
    beta = float(max_cate_bound)
    if not 0 <= beta < 1:
        raise ValueError("max_cate_bound phải nằm trong [0, 1)")

    theta_max = float(theta.max())
    threshold = (1.0 - beta) / 2.0
    return OrderingCondition(
        theta_max=theta_max,
        beta_max=beta,
        threshold=threshold,
        holds=bool(theta_max < threshold),
        n=int(theta.size),
    )


def ordering_condition_by_budget(
    baseline_probability,
    proxy_score,
    max_cate_bound: float,
    budgets=(0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 1.00),
) -> list[dict]:
    """Áp cùng bất đẳng thức cho từng nhóm top-b theo proxy score.

    **Đây là cách vận dụng của repo, không phải phát biểu của paper.** Lý do
    vận dụng: policy sản phẩm chỉ target top-b, nên điều kiện trên toàn
    population có thể hỏng chỉ vì một đuôi rất nhỏ mà policy không bao giờ chạm
    tới. Áp cho đúng nhóm được target cho câu trả lời sát quyết định hơn.

    Giới hạn phải nêu kèm khi báo cáo: điều kiện gốc được phát biểu cho toàn
    population; áp cho sub-population là mở rộng chưa được nguồn chứng minh.
    """
    theta = np.asarray(baseline_probability, dtype="float64").ravel()
    score = np.asarray(proxy_score, dtype="float64").ravel()
    if theta.shape != score.shape:
        raise ValueError("baseline_probability và proxy_score phải cùng độ dài")
    grid = np.asarray(budgets, dtype="float64").ravel()
    if np.any((grid <= 0) | (grid > 1)):
        raise ValueError("budgets phải nằm trong (0, 1]")

    order = np.argsort(score, kind="mergesort")[::-1]
    sorted_theta = theta[order]
    rows = []
    for budget in grid:
        n_target = max(1, int(np.floor(len(score) * float(budget))))
        subset = sorted_theta[:n_target]
        condition = unbiased_ordering_condition(subset, max_cate_bound)
        rows.append(
            {
                "budget_fraction": float(budget),
                "n_targeted": int(n_target),
                **condition.as_dict(),
            }
        )
    return rows


def proxy_rank_agreement(
    proxy_score,
    cate_estimates: dict[str, np.ndarray],
    sample_size: int | None = 200_000,
    seed: int = 42,
) -> list[dict]:
    """Spearman giữa proxy và từng ước lượng CATE; thống kê mô tả thuần tuý.

    Đây **không** phải kiểm định điều kiện của paper. Nó chỉ đo thứ hạng của
    proxy trùng bao nhiêu với thứ hạng của các CATE estimator đã chạy. Tương
    quan cao nghĩa là hai bên xếp hạng giống nhau, không nghĩa là bên nào đúng —
    không bên nào quan sát được ``tau`` thật.

    Với dữ liệu hàng triệu dòng, Spearman được tính trên một mẫu ngẫu nhiên để
    giữ chi phí hữu hạn; ``sample_size=None`` dùng toàn bộ.
    """
    score = np.asarray(proxy_score, dtype="float64").ravel()
    rows = []
    rng = np.random.default_rng(seed)
    if sample_size is not None and sample_size < len(score):
        index = rng.choice(len(score), size=sample_size, replace=False)
    else:
        index = np.arange(len(score))
    for name, values in cate_estimates.items():
        estimate = np.asarray(values, dtype="float64").ravel()
        if len(estimate) != len(score):
            raise ValueError(f"{name} có độ dài khác proxy_score")
        correlation, p_value = spearmanr(score[index], estimate[index])
        rows.append(
            {
                "cate_model": name,
                "spearman_rho": float(correlation),
                "p_value": float(p_value),
                "n_used": int(len(index)),
            }
        )
    return rows
