"""Biểu đồ cho kết quả Causal Forest.

Đọc artifact do `evaluate_causal_forest.py` và `analyze_causal_forest_release.py` ghi ra;
không tính lại metric nào. Mọi con số trên hình đều truy được về một file CSV.

Quy ước màu, cố định theo **thực thể** chứ không theo thứ hạng, để một biểu đồ lọc bớt
model không làm đổi màu những model còn lại:

- Causal Forest — xanh, chủ thể của báo cáo này
- Response — cam, champion đang giữ ngôi
- còn lại — xám, ngữ cảnh

Bảng màu lấy từ bảng đã kiểm chứng; cặp xanh/cam đạt toàn bộ kiểm tra all-pairs ở cả
light lẫn dark (CVD ΔE 24,7 protan, normal-vision ΔE 33,6, contrast ≥ 3:1).

Không dùng trục kép ở bất kỳ hình nào: hai đại lượng khác thang thì tách thành hai panel
dùng chung trục x.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
RELEASE_DIR = REPO / "output" / "causal_forest" / "release"
ANALYSIS_DIR = REPO / "output" / "causal_forest" / "analysis"

CF = "Causal Forest"
CHAMPION = "Response"

INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"
BLUE = "#2a78d6"     # Causal Forest
ORANGE = "#eb6834"   # Response
NEUTRAL = "#b9b7ae"  # các model còn lại


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "semibold",
        "axes.titlecolor": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": AXIS,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "legend.frameon": False,
        "figure.dpi": 130,
    })


def recessive(ax, axis: str = "y") -> None:
    """Lưới mờ, chỉ theo một trục; bỏ khung trên và phải."""
    ax.grid(True, axis=axis, linewidth=0.8, color=GRID, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)


def bar_colour(model: str) -> str:
    if model == CF:
        return BLUE
    if model == CHAMPION:
        return ORANGE
    return NEUTRAL


# --------------------------------------------------------------------------- #


def plot_paired_differences(out: Path) -> None:
    """Forest plot: Causal Forest trừ từng model, hai metric hai panel.

    Đây là hình mang bằng chứng chính. Điểm nào có CI không chứa 0 mới là khác biệt có ý
    nghĩa; phần còn lại là hoà. Chấm được tô đậm khi CI loại trừ 0, để mờ khi chứa 0 —
    trạng thái đọc được cả khi in đen trắng, không chỉ dựa vào màu.
    """
    d = pd.read_csv(RELEASE_DIR / "cf_paired_comparisons_frac_0.5.csv")
    specs = [
        ("policy_area_difference", "policy_area_ci_low", "policy_area_ci_high",
         "policy_area_dr  —  metric chính từ Sprint 3"),
        ("qini_difference", "qini_ci_low", "qini_ci_high",
         "Qini  —  metric lịch sử"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))

    for ax, (col, lo_col, hi_col, title) in zip(axes, specs):
        frame = d.sort_values(col).reset_index(drop=True)
        y = np.arange(len(frame))
        excludes_zero = ~((frame[lo_col] <= 0) & (frame[hi_col] >= 0))

        ax.axvline(0, color=INK_2, linewidth=1.2, zorder=2)
        for i, row in frame.iterrows():
            solid = bool(excludes_zero[i])
            ax.plot(
                [row[lo_col], row[hi_col]], [i, i],
                color=BLUE if solid else NEUTRAL,
                linewidth=2, solid_capstyle="butt", zorder=3,
                alpha=1.0 if solid else 0.85,
            )
            ax.plot(
                row[col], i, "o", markersize=9,
                color=BLUE if solid else SURFACE,
                markeredgecolor=BLUE if solid else NEUTRAL,
                markeredgewidth=2, zorder=4,
            )

        ax.set_yticks(y)
        ax.set_yticklabels([f"vs {m}" for m in frame["model_b"]])
        ax.set_title(title, loc="left", pad=10)
        ax.set_xlabel("chênh lệch  (Causal Forest − model)")
        ax.set_ylim(-0.6, len(frame) - 0.4)
        recessive(ax, axis="x")
        ax.ticklabel_format(axis="x", style="sci", scilimits=(-3, 3))

    fig.text(
        0.5, -0.02,
        "Chấm đặc = khoảng tin cậy 95% không chứa 0 (khác biệt có ý nghĩa).  "
        "Chấm rỗng = CI chứa 0 (hoà).  Paired percentile bootstrap, 500 lần, "
        "trên 2.096.940 dòng final test Sprint 1.",
        ha="center", fontsize=8.5, color=MUTED,
    )
    fig.suptitle(
        "Causal Forest hoà với Response trên cả hai metric; vượt rõ ba model "
        "theo policy_area_dr, một theo Qini",
        x=0.012, ha="left", fontsize=13, fontweight="semibold", color=INK,
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out.name}")


def plot_metric_disagreement(out: Path) -> None:
    """Hai metric xếp hạng khác nhau — hai panel, mỗi panel một thang riêng.

    Cố ý **không** dùng trục kép. Hai đại lượng khác đơn vị đặt chung một trục là cách
    nhanh nhất để tạo ra một hình vô nghĩa.
    """
    d = pd.read_csv(RELEASE_DIR / "cf_metrics_frac_0.5.csv")
    specs = [
        ("policy_area_dr", "policy_area_dr  —  metric chính", "{:.6f}"),
        ("qini_score", "Qini  —  metric lịch sử", "{:.4f}"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))

    for ax, (col, title, fmt) in zip(axes, specs):
        frame = d.sort_values(col).reset_index(drop=True)
        y = np.arange(len(frame))
        colours = [bar_colour(m) for m in frame["model"]]
        ax.barh(y, frame[col], color=colours, height=0.62, zorder=3)

        span = float(frame[col].max())
        for i, (value, model) in enumerate(zip(frame[col], frame["model"])):
            weight = "semibold" if model in (CF, CHAMPION) else "normal"
            ax.text(
                value + span * 0.015, i, fmt.format(value),
                va="center", ha="left", fontsize=9,
                color=INK if model in (CF, CHAMPION) else INK_2,
                fontweight=weight,
            )

        ax.set_yticks(y)
        ax.set_yticklabels(frame["model"])
        for tick, model in zip(ax.get_yticklabels(), frame["model"]):
            if model in (CF, CHAMPION):
                tick.set_color(INK)
                tick.set_fontweight("semibold")
        ax.set_xlim(0, span * 1.18)
        ax.set_title(title, loc="left", pad=10)
        recessive(ax, axis="x")

    fig.suptitle(
        "Cùng một holdout, hai metric cho hai thứ hạng khác nhau",
        x=0.012, ha="left", fontsize=13.5, fontweight="semibold", color=INK,
    )
    fig.text(
        0.012, 0.90,
        "Causal Forest đứng đầu theo policy_area_dr nhưng thứ ba theo Qini. "
        "Cả hai chênh lệch so với Response đều có CI chứa 0.",
        ha="left", fontsize=9.5, color=INK_2,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out.name}")


def plot_learning_curve(out: Path) -> None:
    """Metric và tài nguyên theo lượng dữ liệu — bốn panel, chung trục x."""
    d = pd.read_csv(ANALYSIS_DIR / "learning_curve.csv")
    x = d["fraction"] * 100

    fig, axes = plt.subplots(1, 4, figsize=(13.5, 3.6))
    panels = [
        ("qini", "Qini", "{:.4f}", BLUE),
        ("policy_area_ipw", "policy_area (IPW)", "{:.6f}", BLUE),
        ("peak_rss_gb", "Peak RSS (GB)", "{:.2f}", INK_2),
        ("fit_seconds", "Thời gian fit (phút)", "{:.0f}", INK_2),
    ]

    for ax, (col, title, fmt, colour) in zip(axes, panels):
        values = d[col] / 60 if col == "fit_seconds" else d[col]
        ax.plot(x, values, "-o", color=colour, linewidth=2, markersize=8, zorder=3)
        # Đặt nhãn về phía **không** có đường: so giá trị của điểm với trung bình các
        # điểm kề. Neighbour cao hơn nghĩa là đường đi lên phía trên điểm, nên nhãn phải
        # xuống dưới. Quy tắc cứng "luôn đặt trên" làm đường cắt ngang chữ ở mọi panel
        # đơn điệu.
        v = list(map(float, values))
        dx = [15, 0, -15]   # điểm đầu lệch phải, cuối lệch trái, để không tràn khung
        for i, (xi, vi, comparable) in enumerate(zip(x, values, d["comparable_to_release"])):
            neighbours = [v[j] for j in (i - 1, i + 1) if 0 <= j < len(v)]
            below = sum(neighbours) / len(neighbours) > v[i]
            ax.annotate(
                fmt.format(vi), (xi, vi), textcoords="offset points",
                xytext=(dx[i], -17 if below else 10),
                ha="center", fontsize=8.5, color=INK_2,
            )
            if col in ("qini", "policy_area_ipw") and not comparable:
                ax.plot(xi, vi, "o", markersize=8, color=SURFACE,
                        markeredgecolor=colour, markeredgewidth=2, zorder=4)
        ax.set_title(title, loc="left", pad=8, fontsize=11)
        ax.set_xlabel("phần dữ liệu dùng (%)")
        ax.set_xticks([20, 30, 50])
        ax.set_xlim(14, 56)
        margin = (float(values.max()) - float(values.min())) or 1.0
        ax.set_ylim(float(values.min()) - margin * 0.35, float(values.max()) + margin * 0.55)
        recessive(ax, axis="y")

    fig.suptitle(
        "Tài nguyên tăng tuyến tính theo lượng dữ liệu; metric gần như đứng yên",
        x=0.008, ha="left", fontsize=13.5, fontweight="semibold", color=INK,
    )
    fig.text(
        0.008, 0.87,
        "Chấm rỗng = holdout khác final test Sprint 1. Ba mốc metric nằm trên ba tập test "
        "khác nhau nên không đọc được như một đường học; chúng chỉ cho thấy không có "
        "bước nhảy nào khi tăng dữ liệu.",
        ha="left", fontsize=9, color=MUTED,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.83))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out.name}")


def plot_score_distribution(out: Path) -> None:
    """Phân bố điểm CATE: Causal Forest so với Response.

    Hình này trả lời câu hỏi "model có suy biến không" bằng hình dạng, không bằng lời.
    """
    hist = pd.read_csv(ANALYSIS_DIR / "score_histogram.csv")
    metrics = pd.read_csv(RELEASE_DIR / "cf_metrics_frac_0.5.csv").set_index("model")
    # Percentile lấy từ chính mảng điểm, không suy ra từ mép bin của histogram.
    stages = pd.read_csv(ANALYSIS_DIR / "learning_curve.csv").set_index("stage")
    cf_hist = hist[hist["stage"] == "0p5"]

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0))

    # Phân bố cực nhọn: 99% khối lượng nằm trong một dải rất hẹp còn đuôi phải kéo tới
    # 0,035. Vẽ nguyên dải thì panel gần như trống. Cắt ở p0,5–p99 và ghi rõ đã cắt.
    ax = axes[0]
    lo = float(np.percentile(cf_hist["bin_mid"], 0))
    hi = float(np.percentile(cf_hist["bin_mid"], 100))
    window = cf_hist[(cf_hist["bin_mid"] >= lo) & (cf_hist["bin_mid"] <= 0.012)]
    ax.fill_between(window["bin_mid"], window["density"], color=BLUE, alpha=0.18, zorder=2)
    ax.plot(window["bin_mid"], window["density"], color=BLUE, linewidth=2, zorder=3)
    ax.axvline(0, color=INK_2, linewidth=1.2, zorder=4)
    ax.set_title("Phân bố điểm CATE của Causal Forest, mốc 50%", loc="left", pad=10)
    ax.set_xlabel("điểm CATE   (cắt ở 0,012; đuôi phải kéo tới 0,071)")
    ax.set_ylabel("mật độ")
    ax.annotate(
        f"{metrics.loc[CF, 'unique_score_count']:,.0f} giá trị phân biệt\n"
        f"{metrics.loc[CF, 'negative_score_fraction']:.1%} điểm âm\n"
        f"trung vị {stages.loc['0p5', 'score_p50']:.6f}\n"
        f"trung bình {stages.loc['0p5', 'score_mean']:.6f}",
        xy=(0.97, 0.92), xycoords="axes fraction", ha="right", va="top",
        fontsize=9.5, color=INK_2,
    )
    recessive(ax, axis="y")

    # Thang log: dùng chấm + đường dẫn mảnh, KHÔNG dùng cột. Độ dài cột chỉ mang nghĩa
    # khi tính từ 0, mà thang log không có 0.
    ax = axes[1]
    models = [CF, CHAMPION, "S-Learner", "X-Learner", "DR-Learner", "T-Learner"]
    frame = metrics.loc[models, "unique_score_count"].sort_values()
    y = np.arange(len(frame))
    floor = 5.0
    for i, (model, value) in enumerate(frame.items()):
        colour = bar_colour(model)
        ax.plot([floor, value], [i, i], color=colour, linewidth=1.4, alpha=0.5, zorder=2)
        ax.plot(value, i, "o", markersize=10, color=colour,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
        ax.text(value * 1.35, i, f"{value:,.0f}", va="center", fontsize=9,
                color=INK if model in (CF, CHAMPION) else INK_2,
                fontweight="semibold" if model in (CF, CHAMPION) else "normal")
    ax.axvline(10, color=MUTED, linewidth=1.4, linestyle="--", zorder=3)
    ax.annotate(
        "ngưỡng suy biến đã đăng ký: 10",
        xy=(10, -0.75), xytext=(11, -0.75), fontsize=8.5, color=MUTED, va="center",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(frame.index)
    for tick, model in zip(ax.get_yticklabels(), frame.index):
        if model in (CF, CHAMPION):
            tick.set_color(INK)
            tick.set_fontweight("semibold")
    ax.set_xscale("log")
    ax.set_xlim(floor, float(frame.max()) * 6)
    ax.set_ylim(-1.2, len(frame) - 0.4)
    ax.set_title("Số giá trị điểm phân biệt  (thang log)", loc="left", pad=10)
    recessive(ax, axis="x")

    fig.suptitle(
        "Causal Forest không suy biến — phân tán rộng hơn mọi model release",
        x=0.012, ha="left", fontsize=13.5, fontweight="semibold", color=INK,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out.name}")


def plot_budget_curve(out: Path) -> None:
    """Gross policy value theo ngân sách, trên cùng holdout stage 50%.

    Chỉ hai đường được nhấn — Causal Forest và champion. Bốn model còn lại vẽ xám làm
    ngữ cảnh, không dán nhãn, để mắt không phải phân giải sáu đường cùng lúc.
    """
    d = pd.read_csv(ANALYSIS_DIR / "budget_value_curve.csv")
    d = d[d["stage"] == "0p5"]
    context = [s for s in d["series"].unique() if s not in (CF, CHAMPION)]

    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    for name in context:
        frame = d[d["series"] == name]
        ax.plot(frame["budget"] * 100, frame["policy_value"],
                color=NEUTRAL, linewidth=1.6, zorder=2)

    for name, colour in ((CHAMPION, ORANGE), (CF, BLUE)):
        frame = d[d["series"] == name]
        ax.plot(frame["budget"] * 100, frame["policy_value"], "-o",
                color=colour, linewidth=2.2, markersize=8, label=name, zorder=4)
        ax.annotate(
            name,
            xy=(float(frame["budget"].iloc[-1]) * 100, float(frame["policy_value"].iloc[-1])),
            # Ở mốc 30% Causal Forest nằm dưới Response, nên nhãn phải lệch theo đúng
            # chiều đó; đặt ngược lại là hai nhãn đè lên nhau.
            xytext=(9, -11 if name == CF else 7), textcoords="offset points",
            color=colour, fontsize=10, fontweight="semibold", va="center",
        )

    ax.set_title("Gross policy value trên mỗi khách hàng theo ngân sách",
                 loc="left", pad=10)
    ax.set_xlabel("ngân sách — phần khách hàng được nhắm (%)")
    ax.set_ylabel("giá trị / khách hàng")
    ax.set_xlim(0, 38)
    ax.legend(loc="lower right", fontsize=9.5)
    recessive(ax, axis="y")
    fig.text(0.012, -0.02,
             "Đường xám: S-Learner, X-Learner, DR-Learner, T-Learner. Signal IPW với "
             "propensity hằng số. policy_area_dr là trung bình trapezoid của đường này "
             "trên dải 1–30%.",
             ha="left", fontsize=8.5, color=MUTED)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {out.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ANALYSIS_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    style()

    plot_paired_differences(args.output_dir / "cf_paired_differences.png")
    plot_metric_disagreement(args.output_dir / "cf_metric_disagreement.png")
    plot_learning_curve(args.output_dir / "cf_learning_curve.png")
    plot_score_distribution(args.output_dir / "cf_score_distribution.png")
    plot_budget_curve(args.output_dir / "cf_budget_curve.png")
    print(f"[write] {args.output_dir}")


if __name__ == "__main__":
    main()
