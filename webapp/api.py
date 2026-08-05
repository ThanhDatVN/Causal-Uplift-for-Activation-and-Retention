"""FastAPI application cho Causal Targeting Lab.

App phục vụ artifact release và một scorer đã fit sẵn. Không có endpoint nào
train model khi nhận request.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.data import FEATURES
from webapp.service import (
    SCHEMA_VERSION,
    get_repository,
    get_scorer,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Causal Targeting Lab",
    version=SCHEMA_VERSION,
    description=(
        "API doc artifact release cua du an causal uplift tren Criteo v2.1. "
        "Moi gia tri tien te la kich ban gia dinh, khong phai doanh thu quan sat."
    ),
)


class SimulateRequest(BaseModel):
    budget_fraction: float = Field(0.10, ge=0.0, le=1.0)
    audience: int = Field(1_000_000, ge=1)
    value_per_conversion: float = Field(1.0, gt=0.0)
    contact_cost: float = Field(0.0005, ge=0.0)
    model: str | None = None


class ScoreRequest(BaseModel):
    rows: list[list[float]] = Field(
        ...,
        description=f"Mỗi dòng là {len(FEATURES)} giá trị theo thứ tự f0..f11.",
    )
    budget_fraction: float = Field(0.10, ge=0.0, le=1.0)


def _repository():
    return get_repository()


@app.get("/api/health")
def health() -> dict:
    repository = _repository()
    statuses = repository.artifact_status()
    required = {"sprint2_manifest", "sprint2_metrics", "sprint2_policy"}
    missing = [
        status.name
        for status in statuses
        if status.name in required and not status.available
    ]
    return {
        "status": "degraded" if missing else "ok",
        "schema_version": SCHEMA_VERSION,
        "missing_required_artifacts": missing,
        "scorer_loaded": get_scorer() is not None,
        "artifacts": [
            {"name": s.name, "path": s.path, "available": s.available}
            for s in statuses
        ],
    }


@app.get("/api/meta")
def meta() -> dict:
    return _repository().meta()


@app.get("/api/models")
def models() -> dict:
    return _repository().models()


@app.get("/api/models/pairwise")
def pairwise() -> dict:
    return _repository().pairwise()


@app.get("/api/policy/curve")
def policy_curve() -> dict:
    return _repository().budget_curve()


@app.get("/api/policy/comparison")
def policy_comparison() -> dict:
    return _repository().policy_comparison()


@app.get("/api/policy/sensitivity")
def policy_sensitivity() -> dict:
    return _repository().sensitivity()


@app.post("/api/policy/simulate")
def simulate(request: SimulateRequest) -> dict:
    try:
        return _repository().simulate(
            budget_fraction=request.budget_fraction,
            audience=request.audience,
            value_per_conversion=request.value_per_conversion,
            contact_cost=request.contact_cost,
            model=request.model,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/segments/deciles")
def deciles() -> dict:
    return _repository().deciles()


@app.get("/api/diagnostics")
def diagnostics() -> dict:
    return _repository().diagnostics()


@app.get("/api/registry")
def registry(limit: int = Query(200, ge=1, le=5000)) -> dict:
    return _repository().registry(limit=limit)


@app.get("/api/evidence")
def evidence() -> dict:
    return _repository().evidence()


def _score_matrix(matrix: np.ndarray, budget_fraction: float) -> dict:
    scorer = get_scorer()
    if scorer is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Chưa có champion scorer. Chạy "
                "scripts/build_champion_scorer.py trước khi dùng /api/score."
            ),
        )
    try:
        scores = scorer.score(matrix)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    reference = scorer.metadata.get("score_percentiles")
    if reference:
        grid = np.asarray(reference["values"], dtype="float64")
        quantiles = np.asarray(reference["quantiles"], dtype="float64")
        percentile = np.interp(scores, grid, quantiles) * 100.0
        population_threshold = float(
            np.interp(1.0 - budget_fraction, quantiles, grid)
        )
        targeted = scores >= population_threshold
        threshold_basis = "population_reference"
    else:
        order = np.argsort(-scores, kind="mergesort")
        percentile = np.empty(len(scores), dtype="float64")
        percentile[order] = 100.0 * (
            1.0 - np.arange(len(scores)) / max(len(scores), 1)
        )
        n_target = int(np.floor(len(scores) * budget_fraction))
        targeted = np.zeros(len(scores), dtype=bool)
        targeted[order[:n_target]] = True
        population_threshold = (
            float(scores[order[n_target - 1]]) if n_target > 0 else float("inf")
        )
        threshold_basis = "uploaded_batch_only"

    return {
        "model": scorer.name,
        "family": scorer.family,
        "is_cate_scale": scorer.is_cate_scale,
        "budget_fraction": budget_fraction,
        "threshold_basis": threshold_basis,
        "score_threshold": population_threshold,
        "n_rows": int(len(scores)),
        "n_targeted": int(targeted.sum()),
        "scores": [float(value) for value in scores],
        "population_percentile": [float(value) for value in percentile],
        "targeted": [bool(value) for value in targeted],
        "score_note": (
            "Score la diem uu tien de xep hang. No khong phai xac suat "
            "conversion ca nhan va khong xac dinh principal stratum."
        ),
        "fitted_on": scorer.metadata.get("fitted_on"),
    }


@app.post("/api/score")
def score_json(request: ScoreRequest) -> dict:
    if not request.rows:
        raise HTTPException(status_code=422, detail="rows không được rỗng")
    try:
        matrix = np.asarray(request.rows, dtype="float64")
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURES):
        raise HTTPException(
            status_code=422,
            detail=f"Mỗi dòng phải có đúng {len(FEATURES)} giá trị f0..f11",
        )
    return _score_matrix(matrix, request.budget_fraction)


@app.post("/api/score/csv")
async def score_csv(
    file: UploadFile = File(...),
    budget_fraction: float = Query(0.10, ge=0.0, le=1.0),
    max_rows: int = Query(200_000, ge=1, le=1_000_000),
) -> dict:
    raw = await file.read()
    try:
        frame = pd.read_csv(io.BytesIO(raw))
    except Exception as error:  # noqa: BLE001 - mọi lỗi parse đều là lỗi input
        raise HTTPException(
            status_code=422,
            detail=f"Không đọc được CSV: {error}",
        ) from error
    missing = [column for column in FEATURES if column not in frame.columns]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CSV thiếu cột bắt buộc: {missing}",
        )
    if len(frame) > max_rows:
        raise HTTPException(
            status_code=413,
            detail=f"File có {len(frame):,} dòng, vượt giới hạn {max_rows:,}",
        )
    if frame[FEATURES].isna().any().any():
        raise HTTPException(
            status_code=422,
            detail="CSV có giá trị thiếu ở f0..f11; scorer yêu cầu giá trị hữu hạn",
        )
    result = _score_matrix(
        frame[FEATURES].to_numpy(dtype="float64"),
        budget_fraction,
    )
    result["filename"] = file.filename
    return result


EXPORTABLE = {
    "sprint3_confirmation_metrics": ("sprint3", "confirmation_metrics.csv"),
    "sprint3_paired_comparisons": ("sprint3", "paired_comparisons.csv"),
    "sprint3_policy_budget_curve": ("sprint3", "policy_budget_curve.csv"),
    "sprint3_policy_value_comparison": ("sprint3", "policy_value_comparison.csv"),
    "sprint3_policy_sensitivity": ("sprint3", "policy_sensitivity.csv"),
    "sprint3_promotion_decision": ("sprint3", "promotion_decision.csv"),
    "sprint2_calibration_comparison": ("sprint2", "calibration_comparison.csv"),
    "sprint2_paired_qini_bootstrap": ("sprint2", "paired_qini_bootstrap.csv"),
    "sprint2_policy_value_comparison": ("sprint2", "policy_value_comparison.csv"),
    "sprint2_policy_budget_curve": ("sprint2", "policy_budget_curve.csv"),
    "sprint1_policy_deciles": ("sprint1", "policy_deciles_release.csv"),
    "sprint1_pairwise_bootstrap": ("sprint1", "model_pairwise_bootstrap_release.csv"),
    "improvement_registry": ("improvement", "registry.csv"),
}


@app.get("/api/export")
def export_index() -> dict:
    repository = _repository()
    available = {}
    for key, (directory, filename) in EXPORTABLE.items():
        path = repository.output_dir / directory / filename
        available[key] = {
            "available": path.exists(),
            "path": f"{directory}/{filename}",
            "url": f"/api/export/{key}.csv",
        }
    return {"datasets": available}


@app.get("/api/export/{dataset}.csv")
def export_csv(dataset: str) -> Response:
    if dataset not in EXPORTABLE:
        raise HTTPException(
            status_code=404,
            detail=f"dataset không hợp lệ; có {sorted(EXPORTABLE)}",
        )
    directory, filename = EXPORTABLE[dataset]
    path = _repository().output_dir / directory / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifact chưa tồn tại: {directory}/{filename}",
        )
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"{dataset}.csv",
    )


@app.get("/api/bundle")
def bundle() -> JSONResponse:
    """Toàn bộ payload cho frontend trong một request."""
    repository = _repository()
    payload = {
        "meta": repository.meta(),
        "models": repository.models(),
        "pairwise": repository.pairwise(),
        "budget_curve": repository.budget_curve(),
        "policy_comparison": repository.policy_comparison(),
        "sensitivity": repository.sensitivity(),
        "deciles": repository.deciles(),
        "diagnostics": repository.diagnostics(),
        "evidence": repository.evidence(),
        "registry": repository.registry(limit=200),
        "scorer_available": get_scorer() is not None,
        "feature_names": list(FEATURES),
    }
    return JSONResponse(content=json.loads(json.dumps(payload, default=str)))


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
