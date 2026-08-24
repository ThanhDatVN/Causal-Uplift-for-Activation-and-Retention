"""Khóa các bất biến accessibility của web app.

Ba thứ ở đây đều đã từng thiếu trong repo, và cả ba đều thuộc loại không ai phát hiện ra
khi dùng chuột trên màn hình sáng:

1. **Tương phản dưới ngưỡng.** Theme sáng từng có `--text-muted` ở `3,41:1` và `--accent`
   ở `4,19:1`, trong khi WCAG AA đòi `4,5:1` cho chữ thường. Hai token đó được dùng cho
   nhãn của stat tile và cho tab đang chọn.
2. **Không có focus style.** Người dùng bàn phím không thấy mình đang ở đâu.
3. **Tab không khai báo trạng thái.** `role="tab"` mà thiếu `aria-selected` thì trình đọc
   màn hình không biết tab nào đang mở.

Test đọc thẳng CSS và HTML thay vì chạy trình duyệt, nên nó rẻ và chạy được trên CI không
có Chrome.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "webapp" / "static"

# Ngưỡng WCAG 2.1 AA cho chữ thường. Chữ lớn được phép 3:1 nhưng các token dưới đây đều
# dùng cho chữ nhỏ — nhãn stat tile là 0,62rem — nên áp mức chặt hơn.
AA_NORMAL_TEXT = 4.5

TEXT_TOKENS = (
    "text-primary",
    "text-secondary",
    "text-muted",
    "accent",
    "success-text",
    "critical",
)


def relative_luminance(value: str) -> float:
    raw = value.lstrip("#")
    channels = [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    high, low = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (high + 0.05) / (low + 0.05)


def css_text() -> str:
    return (STATIC / "app.css").read_text(encoding="utf-8")


def palette_blocks() -> dict[str, dict[str, str]]:
    """Mọi khối khai báo token màu, khóa theo selector."""
    blocks: dict[str, dict[str, str]] = {}
    for selector, body in re.findall(r"(:root[^{]*)\{([^}]*)\}", css_text()):
        tokens = dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", body))
        if "page" in tokens:
            blocks[selector.strip()] = tokens
    return blocks


def test_palette_blocks_are_discovered():
    """Nếu regex hỏng thì các test dưới đây pass rỗng, nên chốt số khối trước."""
    blocks = palette_blocks()
    assert len(blocks) >= 2, f"Chi tim thay {len(blocks)} bang mau, nghi ngo regex hong"


@pytest.mark.parametrize("token", TEXT_TOKENS)
def test_text_contrast_meets_aa_in_every_theme(token):
    """Mọi token chữ phải đạt AA trên nền `--page` của chính theme đó."""
    failures = []
    for selector, tokens in palette_blocks().items():
        if token not in tokens:
            continue
        ratio = contrast_ratio(tokens[token], tokens["page"])
        if ratio < AA_NORMAL_TEXT:
            failures.append(
                f"{selector}: --{token} {tokens[token]} tren {tokens['page']} "
                f"= {ratio:.2f}:1 < {AA_NORMAL_TEXT}"
            )
    assert not failures, "Tuong phan duoi nguong AA:\n" + "\n".join(f"  {f}" for f in failures)


def test_focus_visible_style_exists():
    """Phải có vòng focus, và phải dùng :focus-visible để chuột không kích hoạt nó."""
    css = css_text()
    assert ":focus-visible" in css, "Khong co style :focus-visible"
    assert re.search(r":focus-visible[^{]*\{[^}]*outline:", css), (
        "«:focus-visible» co ton tai nhung khong dat outline"
    )


def test_reduced_motion_is_respected():
    assert "prefers-reduced-motion" in css_text(), (
        "Khong co khoi @media prefers-reduced-motion"
    )


def test_every_tab_declares_state_and_target():
    """Mỗi tab phải có `aria-selected`, `aria-controls` và đúng một tab được chọn."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    tabs = re.findall(r"<button[^>]*role=\"tab\"[^>]*>", html)
    assert tabs, "Khong tim thay tab nao"
    for tab in tabs:
        assert "aria-selected=" in tab, f"Tab thieu aria-selected: {tab[:80]}"
        assert "aria-controls=" in tab, f"Tab thieu aria-controls: {tab[:80]}"
        assert "tabindex=" in tab, f"Tab thieu tabindex cho roving focus: {tab[:80]}"
    selected = [tab for tab in tabs if 'aria-selected="true"' in tab]
    assert len(selected) == 1, f"Phai co dung mot tab duoc chon, dang co {len(selected)}"


def test_every_tabpanel_is_labelled_by_its_tab():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    panels = re.findall(r"<section[^>]*role=\"tabpanel\"[^>]*>", html)
    assert panels, "Khong tim thay tabpanel nao"
    for panel in panels:
        assert "aria-labelledby=" in panel, f"Panel thieu aria-labelledby: {panel[:80]}"


def test_keyboard_navigation_is_wired():
    """Mẫu tabs của WAI-ARIA đòi phím mũi tên, Home và End."""
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in script, f"Chua xu ly phim {key}"
