"""Phân biệt hai loại "file không tồn tại".

Test tài liệu và test artifact chạy ở hai môi trường khác nhau:

- **Máy dev** có đủ working tree: dữ liệu Criteo, `*.npz`, scorer `.joblib`, và các
  tài liệu hướng dẫn chưa publish.
- **CI** chỉ có những gì nằm trong repo. Mọi thứ `.gitignore` loại ra đều vắng mặt.

Một đường dẫn vắng mặt vì `.gitignore` loại nó **không phải lỗi tài liệu** — đó là quyết
định có chủ đích, và ở đúng môi trường CI thì nó vắng mặt là điều đương nhiên. Trộn hai
loại này lại khiến CI đỏ vì lý do sai, và lâu dài dẫn tới thói quen bỏ qua CI đỏ.

Module này hỏi thẳng git thay vì giữ một danh sách cứng phải sửa tay mỗi lần
`.gitignore` đổi.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def git_available() -> bool:
    """True nếu chạy được `git` trong repo này."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=REPO_ROOT, capture_output=True, check=True, timeout=30,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# Windows giới hạn độ dài dòng lệnh khoảng 32k ký tự. Chia lô cho an toàn.
_BATCH = 200


def ignored_paths(paths: Iterable[str]) -> set[str]:
    """Tập con của `paths` bị `.gitignore` loại khỏi repo.

    Đường dẫn tương đối so với repo root, dùng dấu `/`. Trả về đúng dạng chuỗi đã
    truyền vào để gọi bên ngoài so sánh trực tiếp được, kể cả khi có đuôi `/`.

    Truyền path làm tham số dòng lệnh chứ không qua `--stdin`: trên Windows,
    `git check-ignore --stdin` gọi từ `subprocess` trả về rỗng và exit code 1 dù cùng
    lệnh đó chạy đúng trong shell.

    Không có git thì trả về tập rỗng: khi đó test kiểm nghiêm ngặt như cũ, thà báo thừa
    còn hơn bỏ sót lỗi tài liệu thật.
    """
    query = sorted({p for p in paths if p})
    if not query or not git_available():
        return set()

    ignored: set[str] = set()
    for start in range(0, len(query), _BATCH):
        batch = query[start : start + _BATCH]
        result = subprocess.run(
            ["git", "check-ignore", *batch],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
        # exit 0 = có ít nhất một path bị ignore, 1 = không có path nào, >1 = lỗi thật.
        if result.returncode > 1:
            continue
        for line in result.stdout.splitlines():
            key = line.strip().replace("\\", "/")
            if key:
                ignored.add(key)
    return ignored & set(query)


def missing_but_tracked(paths: Iterable[str]) -> list[str]:
    """Đường dẫn vừa không tồn tại vừa **không** bị `.gitignore` loại.

    Đây mới là lỗi thật: tài liệu trỏ tới một file lẽ ra phải có trong repo.
    """
    absent = [p for p in paths if not (REPO_ROOT / p).exists()]
    by_design = ignored_paths(absent)
    return sorted(p for p in absent if p not in by_design)
