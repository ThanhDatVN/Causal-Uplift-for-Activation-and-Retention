"""Kiểm tra notebook trình bày thực sự đã được chạy, và thực sự có huấn luyện.

Hai lỗi mà test này bắt, cả hai đều đã xảy ra thật trong repo:

1. **Notebook commit lên mà không có output.** Người đọc mở ra thấy toàn cell rỗng và
   không có cách nào biết code từng chạy hay chưa. Tài liệu thì vẫn ghi "đã chạy".
2. **Notebook chạy lộn xộn rồi commit.** Execution count nhảy cóc nghĩa là kết quả trên
   màn hình đến từ một trạng thái kernel không tái lập được bằng `Run All`.

Notebook Kaggle nằm ngoài phạm vi hai kiểm tra trên: chúng chạy trên session Kaggle chứ
không chạy ở local, và trạng thái output của chúng được mô tả trong bảng notebook của
`README.md` thay vì bị cưỡng chế ở đây.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = REPO_ROOT / "notebooks"

# Notebook trình bày: chạy ở local, phải kèm output đã chạy.
PRESENTATION_NOTEBOOKS = (
    "01_eda_criteo.ipynb",
    "02_modeling_and_evaluation.ipynb",
)


def load_notebook(name: str) -> dict:
    return json.loads((NOTEBOOK_DIR / name).read_text(encoding="utf-8"))


def code_cells(notebook: dict) -> list[dict]:
    return [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]


@pytest.mark.parametrize("name", PRESENTATION_NOTEBOOKS)
def test_presentation_notebook_ran_top_to_bottom(name):
    """Mọi code cell phải có execution count, và phải tăng dần từ 1.

    Đây đúng là trạng thái sau một lần `Run All` trên kernel sạch. Test không đòi cell
    nào cũng phải in ra cái gì — một cell chỉ gán biến thì `outputs` rỗng là đúng.
    """
    cells = code_cells(load_notebook(name))
    assert cells, f"{name} khong co code cell nao"

    never_ran = [
        index
        for index, cell in enumerate(cells)
        if cell.get("execution_count") is None
    ]
    assert not never_ran, (
        f"{name}: {len(never_ran)}/{len(cells)} code cell chua chay "
        f"(execution_count = null) o vi tri {never_ran[:10]}. "
        "Chay lai Run All roi commit ban co output."
    )

    counts = [cell["execution_count"] for cell in cells]
    assert counts == list(range(1, len(cells) + 1)), (
        f"{name}: execution count khong phai 1..{len(cells)} tang dan ma la {counts}. "
        "Ket qua dang hien thi den tu mot trang thai kernel khong tai lap duoc."
    )


@pytest.mark.parametrize("name", PRESENTATION_NOTEBOOKS)
def test_presentation_notebook_stores_some_output(name):
    """Notebook phải mang theo kết quả, không chỉ mang theo code đã chạy."""
    cells = code_cells(load_notebook(name))
    with_output = [cell for cell in cells if cell.get("outputs")]
    assert len(with_output) >= len(cells) // 2, (
        f"{name}: chi {len(with_output)}/{len(cells)} code cell co output luu san."
    )


def test_modeling_notebook_actually_trains():
    """Notebook 02 phải huấn luyện model chứ không chỉ đọc lại artifact.

    Mục 7bis gọi đúng entrypoint mà `scripts/run_oof_experiment.py` dùng, rồi đối chiếu
    với artifact đã đóng băng. Nếu mục đó bị gỡ, notebook quay lại chỗ chỉ trình bày số
    người khác tính — và tài liệu mô tả nó sẽ sai.
    """
    notebook = load_notebook("02_modeling_and_evaluation.ipynb")
    source = "\n".join("".join(cell["source"]) for cell in code_cells(notebook))
    for required in ("cross_fit_nuisance(", "cross_fit_candidate("):
        assert required in source, (
            f"Notebook 02 khong con goi {required} — muc train thu nho da bi go?"
        )
    assert "data_opt_screen_seed101" in source, (
        "Notebook 02 khong con doi chieu voi artifact da dong bang."
    )
