import json
import os

import numpy as np
import pytest

import src.experiment as experiment
from src.experiment import FullDataRunLock, SplitArrays, append_registry


def _split(name: str = "development") -> SplitArrays:
    return SplitArrays(
        X=np.arange(36, dtype="float32").reshape(3, 12),
        treatment=np.array([0, 1, 1], dtype="int8"),
        outcome=np.array([0, 0, 1], dtype="int8"),
        source_index=np.array([10, 20, 30], dtype="int64"),
        name=name,
    )


def test_cache_manifest_is_required_and_verified(tmp_path, monkeypatch):
    split = _split()
    split.auxiliary_outcomes["visit"] = np.array([0, 1, 1], dtype="int8")
    monkeypatch.setattr(experiment, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(
        experiment.SPRINT3_SPLIT_HASHES,
        "development",
        split.index_sha256,
    )
    experiment._write_cache(split, experiment.CRITEO_V2_1_SHA256)

    restored = experiment._read_cache("development", verify_hashes=True)
    assert restored is not None
    np.testing.assert_array_equal(restored.source_index, split.source_index)
    np.testing.assert_array_equal(
        restored.auxiliary_outcomes["visit"],
        split.auxiliary_outcomes["visit"],
    )

    manifest_path = tmp_path / "development.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["data_sha256"] = "wrong"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert experiment._read_cache("development", verify_hashes=True) is None


def test_cache_without_manifest_is_not_a_valid_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "CACHE_DIR", tmp_path)
    np.savez(tmp_path / "development.npz", X=np.zeros((1, 12)))
    assert experiment._read_cache("development", verify_hashes=True) is None


def test_cache_payload_tampering_is_detected(tmp_path, monkeypatch):
    split = _split()
    monkeypatch.setattr(experiment, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(
        experiment.SPRINT3_SPLIT_HASHES,
        "development",
        split.index_sha256,
    )
    experiment._write_cache(split, experiment.CRITEO_V2_1_SHA256)

    cache_path = tmp_path / "development.npz"
    payload = bytearray(cache_path.read_bytes())
    payload[-1] ^= 1
    cache_path.write_bytes(payload)

    assert experiment._read_cache("development", verify_hashes=True) is None


def test_v3_conversion_cache_is_upgraded_with_aligned_visit(tmp_path, monkeypatch):
    split = _split()
    monkeypatch.setattr(experiment, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(experiment, "CRITEO_PATH", tmp_path / "source.csv.gz")
    experiment.CRITEO_PATH.write_bytes(b"source-placeholder")
    monkeypatch.setitem(
        experiment.SPRINT3_SPLIT_HASHES,
        "development",
        split.index_sha256,
    )
    monkeypatch.setattr(
        experiment,
        "sha256_file",
        lambda _path: experiment.CRITEO_V2_1_SHA256,
    )
    source_visit = np.zeros(31, dtype="int8")
    source_visit[[20, 30]] = 1
    monkeypatch.setattr(
        experiment,
        "_load_binary_source_column",
        lambda column: source_visit,
    )

    cache_path = tmp_path / "development.npz"
    np.savez(
        cache_path,
        X=split.X,
        treatment=split.treatment,
        outcome=split.outcome,
        source_index=split.source_index,
    )
    manifest = {
        "cache_format_version": 3,
        "role": "development",
        "outcome": "conversion",
        "features": experiment.FEATURES,
        "data_sha256": experiment.CRITEO_V2_1_SHA256,
        "cache_file_sha256": experiment._sha256_file_uncached(cache_path),
    }
    (tmp_path / "development.manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    restored = experiment._read_cache("development", verify_hashes=True)

    assert restored is not None
    np.testing.assert_array_equal(
        restored.auxiliary_outcomes["visit"],
        source_visit[split.source_index],
    )
    upgraded = json.loads(
        (tmp_path / "development.manifest.json").read_text(encoding="utf-8")
    )
    assert upgraded["cache_format_version"] == experiment.CACHE_FORMAT_VERSION


def test_registry_upserts_same_run_and_fold(tmp_path):
    path = tmp_path / "registry.csv"
    append_registry(
        [{"run_id": "run-a", "fold_seed": 101, "status": "started"}],
        path=path,
    )
    append_registry(
        [
            {
                "run_id": "run-a",
                "fold_seed": 101,
                "status": "complete",
                "policy_area_dr": 0.25,
            }
        ],
        path=path,
    )
    frame = experiment.pd.read_csv(path)
    assert len(frame) == 1
    assert frame.loc[0, "status"] == "complete"
    assert frame.loc[0, "policy_area_dr"] == pytest.approx(0.25)


def test_registry_preserves_different_estimands_with_same_legacy_run_id(tmp_path):
    path = tmp_path / "registry.csv"
    append_registry(
        [
            {
                "run_id": "run-a",
                "fold_seed": 101,
                "outcome": "conversion",
                "status": "complete",
            },
            {
                "run_id": "run-a",
                "fold_seed": 101,
                "outcome": "visit",
                "status": "diagnostic",
            },
        ],
        path=path,
    )
    frame = experiment.pd.read_csv(path)
    assert len(frame) == 2
    assert set(frame["outcome"]) == {"conversion", "visit"}


def test_registry_upsert_normalizes_float_seed_from_csv_with_missing_values(tmp_path):
    path = tmp_path / "registry.csv"
    append_registry(
        [
            {"run_id": "run-a", "fold_seed": 101, "status": "failed"},
            {"run_id": "legacy", "fold_seed": None, "status": "complete"},
        ],
        path=path,
    )
    append_registry(
        [{"run_id": "run-a", "fold_seed": 101, "status": "complete"}],
        path=path,
    )

    frame = experiment.pd.read_csv(path)
    run = frame.loc[frame["run_id"] == "run-a"]
    assert len(run) == 1
    assert run.iloc[0]["status"] == "complete"


def test_full_data_run_lock_rejects_a_live_owner(tmp_path):
    path = tmp_path / "full.lock"
    first = FullDataRunLock(path)
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="đang giữ lock"):
            FullDataRunLock(path).acquire()
    finally:
        first.release()
    with FullDataRunLock(path):
        assert path.exists()
    assert not path.exists()


def test_full_data_run_lock_ignores_a_reused_pid(tmp_path):
    path = tmp_path / "full.lock"
    path.write_text(
        json.dumps({"pid": os.getpid(), "process_created_at": 0.0}),
        encoding="utf-8",
    )
    with FullDataRunLock(path):
        owner = json.loads(path.read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert owner["process_created_at"] > 0
