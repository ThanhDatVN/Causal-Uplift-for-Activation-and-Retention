"""Hợp đồng API của web app.

Web app chỉ đọc artifact đã phát hành, nên rủi ro không nằm ở tính toán mà ở **hợp đồng**:
schema đổi, trường biến mất, hoặc endpoint trả số ngoài phạm vi bằng chứng.

Bốn nhóm:

**Schema.** Mỗi endpoint trả đủ trường, và toàn bộ bundle serialise được sang JSON.

**Phạm vi bằng chứng.** `simulate` phải **từ chối** budget ngoài lưới đã đánh giá và **cảnh
báo** khi chi phí nằm ngoài lưới sensitivity. Nội suy ngoài vùng có bằng chứng là cách một
sản phẩm âm thầm bịa số.

**Số học.** `test_simulate_matches_the_documented_arithmetic` tính lại công thức bằng tay và
so với API — nếu hai bên lệch thì công thức hiển thị trên giao diện không mô tả đúng thứ
đang chạy.

**Đầu vào xấu.** Sai số cột, sai content-type, budget bằng 0, chưa build scorer — tất cả
phải trả lỗi rõ ràng thay vì 500.
"""

import json

import pytest
from fastapi.testclient import TestClient

from src.data import FEATURES
from webapp.api import app
from webapp.service import get_repository, get_scorer


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_every_artifact(client):
    payload = client.get("/api/health").json()
    assert payload["status"] in {"ok", "degraded"}
    names = {item["name"] for item in payload["artifacts"]}
    assert {"sprint2_manifest", "sprint3_manifest", "improvement_registry"} <= names
    assert isinstance(payload["scorer_loaded"], bool)


def test_meta_declares_estimand_and_excluded_columns(client):
    payload = client.get("/api/meta").json()
    assert payload["data"]["outcome"] == "conversion"
    assert set(payload["data"]["excluded_post_treatment"]) == {"visit", "exposure"}
    assert payload["champion"]
    assert payload["causal_forest"]["release_result_available"] is True
    assert payload["causal_forest"]["status"] == "released"


def test_models_endpoint_returns_a_comparison_table(client):
    payload = client.get("/api/models").json()
    assert "sprint2_confirmation" in payload or "sprint3_confirmation" in payload
    table = payload.get("sprint3_confirmation") or payload["sprint2_confirmation"]
    assert table
    assert "model" in table[0]


def test_pairwise_endpoint_exposes_difference_intervals(client):
    payload = client.get("/api/models/pairwise").json()
    assert payload["sources"]
    any_table = next(
        (value for key, value in payload.items() if key != "sources" and value),
        None,
    )
    assert any_table is not None
    assert {"model_a", "model_b"} <= set(any_table[0])


def test_budget_curve_has_monotone_budget_grid_per_model(client):
    payload = client.get("/api/policy/curve").json()
    assert payload["rows"]
    by_model: dict[str, list[float]] = {}
    for row in payload["rows"]:
        by_model.setdefault(row["model"], []).append(row["budget_fraction"])
    for budgets in by_model.values():
        assert budgets == sorted(budgets)


def test_simulate_matches_the_documented_arithmetic(client):
    body = {
        "budget_fraction": 0.10,
        "audience": 1_000_000,
        "value_per_conversion": 1.0,
        "contact_cost": 0.0005,
    }
    payload = client.post("/api/policy/simulate", json=body).json()
    gross = payload["gross_incremental_conversions_per_customer"]
    expected_net = gross * body["value_per_conversion"] - (
        body["budget_fraction"] * body["contact_cost"]
    )
    assert payload["net_scenario_value_per_customer"] == pytest.approx(expected_net)
    assert payload["total_incremental_conversions"] == pytest.approx(
        body["audience"] * gross
    )
    assert payload["targeted_customers"] == pytest.approx(
        body["audience"] * body["budget_fraction"]
    )
    assert payload["break_even_contact_cost"] == pytest.approx(
        gross * body["value_per_conversion"] / body["budget_fraction"]
    )
    assert payload["is_monetary_observation"] is False


def test_simulate_at_zero_budget_returns_zero_value(client):
    payload = client.post(
        "/api/policy/simulate",
        json={"budget_fraction": 0.0, "audience": 1000},
    ).json()
    assert payload["gross_incremental_conversions_per_customer"] == 0.0
    assert payload["total_incremental_conversions"] == 0.0
    assert payload["break_even_contact_cost"] is None


def test_simulate_rejects_invalid_inputs(client):
    assert client.post("/api/policy/simulate", json={"budget_fraction": 1.5}).status_code == 422
    assert client.post("/api/policy/simulate", json={"audience": 0}).status_code == 422
    assert (
        client.post("/api/policy/simulate", json={"budget_fraction": 0.31}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/policy/simulate",
            json={"value_per_conversion": 0},
        ).status_code
        == 422
    )


def test_score_rejects_budget_outside_evidence_grid(client):
    response = client.post(
        "/api/score",
        json={"rows": [[0.0] * 12], "budget_fraction": 0.31},
    )
    assert response.status_code == 422


def test_simulate_warns_outside_cost_sensitivity_grid(client):
    payload = client.post(
        "/api/policy/simulate",
        json={"contact_cost": 0.002, "value_per_conversion": 1.0},
    ).json()
    assert payload["outside_sensitivity_grid"] is True
    assert "0,001" in payload["guardrail_warning"]


def test_deciles_and_diagnostics_carry_scope_notes(client):
    deciles = client.get("/api/segments/deciles").json()
    assert deciles["rows"]
    assert "Sprint 1" in deciles["note"]
    diagnostics = client.get("/api/diagnostics").json()
    assert "randomization" in diagnostics["balance_note"]


def test_evidence_lists_limitations_and_hierarchy(client):
    payload = client.get("/api/evidence").json()
    assert len(payload["limitations"]) >= 4
    assert any("revenue" in item for item in payload["limitations"])
    levels = {item["level"] for item in payload["evidence_hierarchy"]}
    assert "retrospective_confirmation" in levels


def test_registry_endpoint_respects_limit(client):
    payload = client.get("/api/registry?limit=3").json()
    assert len(payload["rows"]) <= 3
    assert payload["row_count"] >= len(payload["rows"])


def test_export_index_and_download(client):
    index = client.get("/api/export").json()["datasets"]
    assert "sprint2_policy_value_comparison" in index
    available = [
        key for key, value in index.items() if value["available"]
    ]
    assert available
    response = client.get(f"/api/export/{available[0]}.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    header = response.text.splitlines()[0]
    assert "run_id" in header
    assert "monetary_outcome_available" in header
    assert "assumptions_json" in header
    assert client.get("/api/export/not_a_dataset.csv").status_code == 404


def test_bundle_is_json_serialisable_and_complete(client):
    payload = client.get("/api/bundle").json()
    required = {
        "meta",
        "models",
        "pairwise",
        "budget_curve",
        "policy_comparison",
        "sensitivity",
        "deciles",
        "diagnostics",
        "evidence",
        "registry",
        "feature_names",
    }
    assert required <= set(payload)
    assert payload["feature_names"] == list(FEATURES)
    json.dumps(payload)


def test_score_rejects_wrong_column_count(client):
    response = client.post(
        "/api/score",
        json={"rows": [[1.0, 2.0]], "budget_fraction": 0.1},
    )
    assert response.status_code == 422


def test_score_requires_a_built_scorer_or_returns_results(client):
    rows = [[float(index % 7) for index in range(len(FEATURES))] for _ in range(5)]
    response = client.post("/api/score", json={"rows": rows, "budget_fraction": 0.2})
    if get_scorer() is None:
        assert response.status_code == 503
        assert "build_champion_scorer" in response.json()["detail"]
        return
    payload = response.json()
    assert response.status_code == 200
    assert payload["n_rows"] == len(rows)
    assert len(payload["scores"]) == len(rows)
    assert len(payload["targeted"]) == len(rows)
    assert all(0.0 <= value <= 100.0 for value in payload["population_percentile"])


def test_csv_scoring_validates_required_columns(client):
    csv_bytes = b"f0,f1\n1,2\n"
    response = client.post(
        "/api/score/csv",
        files={"file": ("bad.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 422
    assert "thiếu cột" in response.json()["detail"]


def test_csv_scoring_rejects_non_csv_content_type(client):
    response = client.post(
        "/api/score/csv",
        files={"file": ("bad.json", b"{}", "application/json")},
    )
    assert response.status_code == 415


@pytest.mark.skipif(
    get_scorer() is None,
    reason="Cần output/product/webapp/champion_scorer.joblib; chạy scripts/build_champion_scorer.py.",
)
def test_scoring_separates_converters_on_real_confirmation_rows(client):
    """Chấm điểm thật trên dòng Criteo phải tách được nhóm có conversion.

    Test này đi xa hơn contract test: nó kiểm tra scorer đã lưu còn giữ được sức
    phân biệt, chứ không chỉ trả về đúng kiểu dữ liệu. Ngưỡng lấy từ lưới phân vị
    của population nên một mẫu ngẫu nhiên phải được target xấp xỉ đúng budget.
    """
    import numpy as np

    from src.experiment import build_sprint3_splits

    confirmation = build_sprint3_splits()["confirmation"]
    rng = np.random.default_rng(0)
    rows = rng.choice(len(confirmation), size=2000, replace=False)
    response = client.post(
        "/api/score",
        json={
            "rows": confirmation.X[rows].astype("float64").tolist(),
            "budget_fraction": 0.10,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    scores = np.asarray(payload["scores"])
    targeted = np.asarray(payload["targeted"])

    assert payload["threshold_basis"] == "uploaded_batch_exact_top_k"
    assert targeted.sum() == int(np.floor(len(rows) * 0.10))

    outcome = confirmation.outcome[rows]
    assert outcome[targeted].mean() > 5 * max(outcome[~targeted].mean(), 1e-6)

    percentile = np.asarray(payload["population_percentile"])
    assert np.all(np.diff(percentile[np.argsort(scores)]) >= -1e-9)


def test_static_index_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Causal Targeting Lab" in response.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/app.css").status_code == 200
    assert client.get("/charts.js").status_code == 200


def test_repository_simulate_raises_for_out_of_range_budget():
    repository = get_repository()
    with pytest.raises(ValueError):
        repository.simulate(budget_fraction=-0.1)
    with pytest.raises(ValueError, match="evidence grid"):
        repository.simulate(budget_fraction=0.8)
