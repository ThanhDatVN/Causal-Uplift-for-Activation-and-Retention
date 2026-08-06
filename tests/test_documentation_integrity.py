"""Kiểm tra tính toàn vẹn của tài liệu.

Ba loại lỗi mà test này bắt, cả ba đều đã xảy ra thật trong repo:

1. **Link markdown hỏng** — xảy ra mỗi lần di chuyển file vào `archive/`.
2. **Đường dẫn trong backtick trỏ sai chỗ** — `report/SPRINT_1_FINAL_REPORT.md` từng ghi
   `output/optimization/qini_comparison_sprint1.csv` trong khi script ghi ra
   `output/qini_comparison_sprint1.csv`.
3. **Số test trong tài liệu lệch số test thật** — xảy ra mỗi lần thêm test mà quên sửa
   README/CLAUDE.md.

Test cố ý **không** kiểm tài liệu lịch sử và tài liệu scoping cho bài toán chưa mở: chúng
mô tả cấu trúc dự kiến hoặc liệt kê những thứ *chưa* tồn tại, nên đường dẫn không resolve
là đúng chứ không phải lỗi.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

import pytest

from tests.repo_state import ignored_paths

REPO_ROOT = Path(__file__).resolve().parent.parent

# Tài liệu mô tả cấu trúc dự kiến hoặc liệt kê thứ chưa tồn tại.
PROSPECTIVE = (
    "docs/archive",
    "report/archive",
    "benchmarks/archive",
    "planning/incremental_value_product",
    "planning/CAUSAL_UPLIFT_PLAN.md",
    "planning/RUN_PLAN.md",
    "planning/SPRINT_PLAN_6_WEEKS.md",
)

# Trước 06/08/2026 hai đường dẫn này chỉ tồn tại sau khi chạy Kaggle. Chúng đã tồn tại
# từ khi Causal Forest chạy xong, nên danh sách miễn trừ này rỗng. Giữ lại cấu trúc vì
# tình huống "tài liệu trỏ tới artifact của một lần chạy chưa diễn ra" sẽ lặp lại.
CREATED_BY_FUTURE_RUN: tuple[str, ...] = ()

# Đường dẫn được nhắc tới **đúng vì nó không tồn tại**: tài liệu đang giải thích rằng
# kế hoạch ban đầu dự kiến file này nhưng hiện thực đặt ở chỗ khác.
DELIBERATELY_ABSENT = {
    "src/rlearner.py",   # thực tế nằm ở src/candidates.py::build_r_learner
}

PATH_IN_BACKTICKS = re.compile(
    r"`((?:src|scripts|tests|configs|webapp|docs|report|planning|output|benchmarks|notebooks)"
    r"/[A-Za-z0-9_./-]+)`"
)
MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def markdown_files() -> list[Path]:
    return sorted(
        p
        for p in REPO_ROOT.rglob("*.md")
        if ".venv" not in p.parts and ".git" not in p.parts
    )


def is_prospective(path: Path) -> bool:
    relative = path.relative_to(REPO_ROOT).as_posix()
    return any(relative.startswith(prefix) for prefix in PROSPECTIVE)


def repo_relative(path: Path, target: str) -> str:
    """Đích của một link, quy về đường dẫn tương đối so với repo root."""
    directory = path.parent.relative_to(REPO_ROOT).as_posix()
    joined = target if directory == "." else posixpath.join(directory, target)
    return posixpath.normpath(joined)


def test_every_relative_markdown_link_resolves():
    """Mọi link tương đối trong mọi file .md phải trỏ tới file có thật.

    Ngoại lệ duy nhất: đích bị `.gitignore` loại khỏi repo. Trên máy dev nó vẫn tồn tại
    nên link bấm được; trên CI nó vắng mặt đúng theo thiết kế, không phải lỗi tài liệu.
    """
    absent: dict[str, list[str]] = {}
    checked = 0
    for path in markdown_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in MARKDOWN_LINK.finditer(text):
            target = match.group(2).split("#")[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            checked += 1
            if (path.parent / target).exists():
                continue
            resolved = repo_relative(path, target)
            absent.setdefault(resolved, []).append(
                f"{path.relative_to(REPO_ROOT).as_posix()} -> {target}"
            )

    by_design = ignored_paths(absent)
    broken = sorted(
        message
        for resolved, messages in absent.items()
        if resolved not in by_design
        for message in messages
    )
    assert checked > 100, f"Chi kiem duoc {checked} link, nghi ngo regex hong"
    assert not broken, "Link hong:\n" + "\n".join(f"  {b}" for b in broken)


def test_backtick_paths_in_current_docs_exist():
    """Đường dẫn trong backtick ở tài liệu hiện hành phải tồn tại.

    Bỏ qua tài liệu lịch sử và scoping: chúng cố ý nhắc tới file chưa có.
    """
    absent: dict[str, list[str]] = {}
    for path in markdown_files():
        if is_prospective(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in PATH_IN_BACKTICKS.finditer(text):
            target = match.group(1)
            if any(target.startswith(p) for p in CREATED_BY_FUTURE_RUN):
                continue
            if target in DELIBERATELY_ABSENT:
                continue
            if (REPO_ROOT / target).exists():
                continue
            absent.setdefault(target, []).append(
                f"{path.relative_to(REPO_ROOT).as_posix()}: {target}"
            )

    # Đường dẫn bị `.gitignore` loại vắng mặt trên CI là đúng thiết kế, không phải lỗi.
    by_design = ignored_paths(absent)
    missing = sorted(
        message
        for target, messages in absent.items()
        if target not in by_design
        for message in messages
    )
    assert not missing, "Duong dan khong ton tai:\n" + "\n".join(
        f"  {m}" for m in missing
    )


def test_documented_test_count_matches_reality():
    """Số test ghi trong README và CLAUDE.md phải khớp số test thật."""
    import subprocess
    import sys

    # Đếm bằng chính pytest: `def test_` bỏ sót phần nhân của @parametrize.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    assert match, "Khong doc duoc so test tu pytest:\n" + result.stdout[-500:]
    actual = int(match.group(1))
    documented = []
    for name in ("README.md", "CLAUDE.md"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        documented += [
            (name, int(value))
            for value in re.findall(r"pytest[^\n]*?(\d{2,4})\s*(?:test|/)", text)
        ]
        documented += [
            (name, int(value)) for value in re.findall(r"(\d{2,4})/\1\s*pass", text)
        ]
    assert documented, "Khong tim thay so test nao trong README/CLAUDE.md"
    wrong = [(where, value) for where, value in documented if value != actual]
    assert not wrong, (
        f"So test thuc te = {actual}, nhung tai lieu ghi: {wrong}. "
        "Cap nhat README.md va CLAUDE.md."
    )


def test_every_directory_index_exists():
    """Mỗi thư mục lớn phải có README.md chỉ mục."""
    for directory in ("docs", "planning", "report", "scripts", "output"):
        index = REPO_ROOT / directory / "README.md"
        assert index.exists(), f"Thieu chi muc {directory}/README.md"
        assert len(index.read_text(encoding="utf-8")) > 200


@pytest.mark.parametrize(
    "banned",
    ["state of the art", "production-ready", "SOTA"],
)
def test_no_overclaiming_language_in_current_docs(banned):
    """Ba cụm từ này chỉ được xuất hiện trong câu phủ định chúng."""
    offenders = []
    for path in markdown_files():
        if is_prospective(path):
            continue
        in_code_block = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lstrip().startswith("```"):
                in_code_block = not in_code_block
                continue
            # Lệnh shell đi tìm chính những cụm từ này là hợp lệ, không phải claim.
            if in_code_block:
                continue
            if banned.lower() not in line.lower():
                continue
            # Câu phủ định là hợp lệ: "không có claim SOTA", "khong phai production-ready".
            if re.search(r"khong|không|no claim|not\b", line, re.I):
                continue
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {line.strip()}")
    assert not offenders, f"Claim vuot bang chung ({banned}):\n" + "\n".join(
        f"  {o}" for o in offenders
    )
