"""Hạ tầng cross-fitting, tài nguyên và registry cho vòng cải tiến Sprint 3.

Ba nguyên tắc được cố định ở đây:

1. **Mỗi dòng chỉ được chấm bởi model không fit trên dòng đó.** Toàn bộ điểm số
   dùng để so sánh là out-of-fold.
2. **Mọi candidate dùng chung một effect signal.** Nuisance ``mu0``/``mu1`` được
   cross-fit một lần trên đúng bộ fold đó và tái sử dụng, nên chênh lệch giữa hai
   model không bị lẫn với chênh lệch giữa hai tín hiệu đánh giá khác nhau.
3. **Mọi run đều ghi registry**, kể cả run bị dừng sớm, kèm resource và lý do dừng.

Development pool là ``fit + validation`` của Sprint 2. Confirmation Sprint 2 nằm
ngoài module này và chỉ được đọc ở bước retrospective confirmation.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import lightgbm
import numpy as np
import pandas as pd
import psutil
import sklearn
from sklearn.model_selection import StratifiedKFold

from src.data import (
    FEATURES,
    load_criteo_full,
    stratified_complement,
    train_test_holdout,
    validate_criteo_schema,
)
from src.paths import OUTPUT_DIR

# Hằng số tái dựng đúng split Sprint 2. Không đổi các seed này: chúng quyết định
# nội dung của development pool và confirmation.
SPRINT1_SELECTED_FRACTION = 0.50
SPRINT1_SAMPLING_SEED = 42
SPRINT2_SPLIT_SEED = 52
SPRINT2_CONFIRMATION_SEED = 53
SPRINT2_SPLIT_HASHES = {
    "fit": "eb1d34c9db92ce42eabff7266b9c220c50417fef2cdcdb33dd1d348351ef51ac",
    "validation": "33622532d96c649dab244005942f96467e403e13f6635983c0d349380934098f",
    "confirmation": "6d846e155171a87d5629cd8275697dcc3cabbfc813ec5f6a0ebd7a1f2c0280be",
}

IMPROVEMENT_DIR = OUTPUT_DIR / "improvement"
CACHE_DIR = IMPROVEMENT_DIR / "cache"
REGISTRY_PATH = IMPROVEMENT_DIR / "registry.csv"

REGISTRY_COLUMNS = [
    "run_id",
    "created_utc",
    "status",
    "outcome",
    "candidate",
    "candidate_family",
    "config_hash",
    "config_json",
    "commit_sha",
    "data_sha256",
    "development_index_sha256",
    "eval_index_sha256",
    "fold_seed",
    "n_folds",
    "pool_fraction",
    "n_rows",
    "n_treated",
    "n_control",
    "n_conversion_treated",
    "n_conversion_control",
    "policy_area_dr",
    "policy_area_dr_adjusted",
    "autoc_dr",
    "autoc_dr_adjusted",
    "rate_qini_dr",
    "qini_score",
    "auuc_score",
    "uplift_calibration_error",
    "doubly_robust_risk",
    "score_mean",
    "score_std",
    "negative_score_fraction",
    "unique_score_count",
    "fit_seconds",
    "predict_seconds",
    "peak_process_rss_gb",
    "min_system_available_ram_gb",
    "python_version",
    "numpy_version",
    "pandas_version",
    "sklearn_version",
    "lightgbm_version",
    "econml_version",
    "failure_reason",
]


def commit_sha() -> str:
    """SHA của commit hiện tại; trả ``unknown`` nếu không đọc được."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def sha256_indices(index: np.ndarray) -> str:
    values = np.sort(np.asarray(index, dtype="<i8"))
    return hashlib.sha256(values.tobytes()).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ResourceGateBreached(RuntimeError):
    """RAM khả dụng tụt dưới ngưỡng đã đăng ký trong lúc chạy."""


class ResourceMonitor:
    """Lấy mẫu peak RSS của process và RAM khả dụng thấp nhất của hệ thống.

    Ngoài việc đo, monitor còn theo dõi ngưỡng RAM khả dụng đã đăng ký. Khi
    ``min_available_gb`` được đặt và RAM khả dụng tụt xuống dưới ngưỡng đó, cờ
    :attr:`breached` được bật.

    **Cờ này không tự dừng công việc đang chạy.** Một thread nền không thể ngắt
    an toàn một lệnh fit LightGBM đang giữ bộ nhớ; ngắt giữa chừng còn dễ để lại
    artifact hỏng. Thay vào đó, caller gọi :meth:`raise_if_breached` tại các
    **điểm dừng an toàn** — giữa hai fold và giữa hai candidate — nơi có thể
    dừng mà vẫn ghi được registry đầy đủ.

    Trước Sprint 3, resource gate chỉ được kiểm tra một lần trước khi chạy. Ở các
    stage full-data, RAM khả dụng đã tụt xuống 1,55 GB, dưới ngưỡng 2,0 GB đã
    đăng ký, mà không có gì dừng lại. Lớp này đóng đúng khoảng trống đó.
    """

    def __init__(
        self,
        interval_seconds: float = 0.25,
        min_available_gb: float | None = None,
    ):
        self.interval_seconds = interval_seconds
        self.min_available_gb = min_available_gb
        self.peak_process_rss = psutil.Process().memory_info().rss
        self.minimum_system_available = psutil.virtual_memory().available
        self.breached = False
        self.breach_available_gb: float | None = None
        self.breach_utc: str | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        process = psutil.Process()
        while not self._stop.wait(self.interval_seconds):
            self.peak_process_rss = max(
                self.peak_process_rss,
                process.memory_info().rss,
            )
            available = psutil.virtual_memory().available
            self.minimum_system_available = min(
                self.minimum_system_available,
                available,
            )
            if self.min_available_gb is not None and not self.breached:
                available_gb = available / 2**30
                if available_gb < self.min_available_gb:
                    self.breached = True
                    self.breach_available_gb = available_gb
                    self.breach_utc = datetime.now(timezone.utc).isoformat()

    def raise_if_breached(self, context: str = "") -> None:
        """Dừng tại điểm an toàn nếu ngưỡng đã bị vi phạm."""
        if not self.breached:
            return
        where = f" tại {context}" if context else ""
        raise ResourceGateBreached(
            f"RAM khả dụng đã tụt xuống {self.breach_available_gb:.2f} GB "
            f"(ngưỡng đăng ký {self.min_available_gb:.2f} GB) lúc "
            f"{self.breach_utc}. Dừng{where} để giữ registry và artifact "
            "nhất quán. Giảm --pool-frac hoặc đóng ứng dụng khác rồi chạy lại."
        )

    def __enter__(self) -> "ResourceMonitor":
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self.peak_process_rss = max(
            self.peak_process_rss,
            psutil.Process().memory_info().rss,
        )

    @property
    def peak_process_rss_gb(self) -> float:
        return self.peak_process_rss / 2**30

    @property
    def min_system_available_ram_gb(self) -> float:
        return self.minimum_system_available / 2**30


def environment_versions() -> dict[str, str]:
    try:
        import econml

        econml_version = econml.__version__
    except ImportError:  # pragma: no cover - econml là dependency bắt buộc
        econml_version = "missing"
    return {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "sklearn_version": sklearn.__version__,
        "lightgbm_version": lightgbm.__version__,
        "econml_version": econml_version,
    }


@dataclass
class SplitArrays:
    """Mảng đã tách sẵn cho một split, giữ nguyên source index của Criteo."""

    X: np.ndarray
    treatment: np.ndarray
    outcome: np.ndarray
    source_index: np.ndarray
    name: str

    def __len__(self) -> int:
        return len(self.outcome)

    @property
    def index_sha256(self) -> str:
        return sha256_indices(self.source_index)

    def arm_counts(self) -> dict[str, int]:
        treated = self.treatment == 1
        control = ~treated
        return {
            "n_rows": int(len(self.outcome)),
            "n_treated": int(treated.sum()),
            "n_control": int(control.sum()),
            "n_conversion_treated": int(self.outcome[treated].sum()),
            "n_conversion_control": int(self.outcome[control].sum()),
        }

    def subsample(self, fraction: float, seed: int) -> "SplitArrays":
        """Lấy mẫu phân tầng theo (treatment, outcome) để screening nhanh."""
        if not 0 < fraction <= 1:
            raise ValueError("fraction phải nằm trong (0, 1]")
        if fraction == 1.0:
            return self
        rng = np.random.default_rng(seed)
        strata = self.treatment.astype("int64") * 2 + self.outcome.astype("int64")
        keep: list[np.ndarray] = []
        for value in np.unique(strata):
            members = np.flatnonzero(strata == value)
            size = max(1, int(round(len(members) * fraction)))
            keep.append(rng.choice(members, size=min(size, len(members)), replace=False))
        selected = np.sort(np.concatenate(keep))
        return SplitArrays(
            X=self.X[selected],
            treatment=self.treatment[selected],
            outcome=self.outcome[selected],
            source_index=self.source_index[selected],
            name=f"{self.name}@{fraction:g}",
        )


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.npz"


def _write_cache(split: SplitArrays) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        _cache_path(split.name),
        X=split.X,
        treatment=split.treatment,
        outcome=split.outcome,
        source_index=split.source_index,
    )


def _read_cache(name: str) -> SplitArrays | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    with np.load(path) as payload:
        return SplitArrays(
            X=payload["X"],
            treatment=payload["treatment"],
            outcome=payload["outcome"],
            source_index=payload["source_index"],
            name=name,
        )


def build_sprint3_splits(
    use_cache: bool = True,
    verify_hashes: bool = True,
    outcome: str = "conversion",
) -> dict[str, SplitArrays]:
    """Tái dựng development pool và confirmation của Sprint 2.

    ``development`` = ``fit + validation``. ``confirmation`` giữ nguyên và chỉ
    được dùng ở bước retrospective confirmation. Hash source index được đối chiếu
    với manifest Sprint 2 để bảo đảm không lệch split giữa các sprint.

    ``outcome`` cho phép chạy cùng split với một outcome khác. Chỉ có nghĩa cho
    **power diagnostic**: split được xác định bởi source index nên hash không
    đổi khi đổi outcome, và mọi so sánh vẫn nằm trên đúng những dòng đó.

    Cảnh báo phạm vi: đổi outcome là đổi **estimand**. Kết quả trên
    ``visit`` không so được với kết quả trên ``conversion`` và không phải kết
    quả sản phẩm của dự án. Dùng ``visit`` làm outcome hợp lệ; dùng nó làm
    feature vẫn là leakage và vẫn bị cấm.
    """
    if outcome not in {"conversion", "visit"}:
        raise ValueError(
            f"outcome phải là 'conversion' hoặc 'visit', nhận {outcome!r}"
        )
    suffix = "" if outcome == "conversion" else f"_{outcome}"
    names = (f"development{suffix}", f"confirmation{suffix}")
    if use_cache:
        cached = {name: _read_cache(name) for name in names}
        if all(value is not None for value in cached.values()):
            return {
                "development": cached[names[0]],
                "confirmation": cached[names[1]],
            }  # type: ignore[return-value]

    full = load_criteo_full(dtype_f32=True)
    schema = validate_criteo_schema(full)
    if not schema["valid"]:
        raise ValueError(f"Data contract failed: {schema}")
    pool = stratified_complement(
        full,
        selected_frac=SPRINT1_SELECTED_FRACTION,
        seed=SPRINT1_SAMPLING_SEED,
        preserve_index=True,
    )
    del full
    fit_df, remainder = train_test_holdout(
        pool,
        test_size=0.40,
        seed=SPRINT2_SPLIT_SEED,
        preserve_index=True,
    )
    validation_df, confirmation_df = train_test_holdout(
        remainder,
        test_size=0.50,
        seed=SPRINT2_CONFIRMATION_SEED,
        preserve_index=True,
    )
    del remainder, pool

    if verify_hashes:
        observed = {
            "fit": sha256_indices(fit_df.index.to_numpy(dtype="int64")),
            "validation": sha256_indices(
                validation_df.index.to_numpy(dtype="int64")
            ),
            "confirmation": sha256_indices(
                confirmation_df.index.to_numpy(dtype="int64")
            ),
        }
        mismatched = {
            name: (value, SPRINT2_SPLIT_HASHES[name])
            for name, value in observed.items()
            if value != SPRINT2_SPLIT_HASHES[name]
        }
        if mismatched:
            raise ValueError(
                "Split hash không khớp manifest Sprint 2; không được tiếp tục vì "
                f"development pool sẽ khác sprint trước: {mismatched}"
            )

    development_df = pd.concat([fit_df, validation_df])
    del fit_df, validation_df
    splits = {}
    for role, cache_name, frame in (
        ("development", names[0], development_df),
        ("confirmation", names[1], confirmation_df),
    ):
        split = SplitArrays(
            X=frame[FEATURES].to_numpy(dtype="float32"),
            treatment=frame["treatment"].to_numpy(dtype="int8"),
            outcome=frame[outcome].to_numpy(dtype="int8"),
            source_index=frame.index.to_numpy(dtype="int64"),
            name=cache_name,
        )
        _write_cache(split)
        splits[role] = split
    return splits


def make_folds(
    treatment: np.ndarray,
    outcome: np.ndarray,
    n_folds: int = 3,
    seed: int = 101,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Fold phân tầng theo (treatment, outcome) để mỗi fold giữ đủ conversion control."""
    if n_folds < 2:
        raise ValueError("n_folds phải >= 2")
    strata = treatment.astype("int64") * 2 + outcome.astype("int64")
    splitter = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    placeholder = np.zeros(len(strata), dtype="int8")
    return list(splitter.split(placeholder, strata))


@dataclass
class RegistryRow:
    values: dict = field(default_factory=dict)

    def to_series(self) -> pd.Series:
        return pd.Series(
            {column: self.values.get(column) for column in REGISTRY_COLUMNS}
        )


def _migrate_registry_schema(path: Path, defaults: dict[str, object]) -> None:
    """Bổ sung cột mới vào registry cũ trước khi append.

    Append một DataFrame nhiều cột hơn header hiện có sẽ làm lệch cột và hỏng
    toàn bộ file. Hàm này đọc file cũ, thêm cột còn thiếu với giá trị mặc định
    đúng với ngữ cảnh lịch sử, rồi ghi lại một lần.

    Đây là **migration trung thực**, không phải sửa số: chỉ thêm cột mô tả điều
    vốn đã đúng cho mọi dòng cũ (ví dụ mọi run trước Sprint 3 đều dùng outcome
    ``conversion``). Không dòng metric nào bị thay đổi.
    """
    existing = pd.read_csv(path)
    missing = [column for column in REGISTRY_COLUMNS if column not in existing.columns]
    if not missing:
        return
    for column in missing:
        existing[column] = defaults.get(column)
    extra = [column for column in existing.columns if column not in REGISTRY_COLUMNS]
    existing = existing[REGISTRY_COLUMNS + extra]
    existing.to_csv(path, index=False)
    print(
        f"[registry] migrated schema, added columns: {missing}",
        flush=True,
    )


def append_registry(
    rows: list[dict],
    path: Path = REGISTRY_PATH,
    schema_defaults: dict[str, object] | None = None,
) -> Path:
    """Ghi thêm dòng vào registry, giữ nguyên thứ tự cột đã đăng ký."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _migrate_registry_schema(
            path,
            schema_defaults or {"outcome": "conversion"},
        )
    frame = pd.DataFrame(
        [RegistryRow(values=row).to_series() for row in rows],
        columns=REGISTRY_COLUMNS,
    )
    header = not path.exists()
    frame.to_csv(path, mode="a", header=header, index=False)
    return path


def base_registry_fields(
    run_id: str,
    status: str,
    development: SplitArrays,
    evaluation: SplitArrays | None = None,
    data_sha256: str | None = None,
) -> dict:
    evaluation = evaluation or development
    fields = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "commit_sha": commit_sha(),
        "data_sha256": data_sha256 or "not_recomputed",
        "development_index_sha256": development.index_sha256,
        "eval_index_sha256": evaluation.index_sha256,
    }
    fields.update(evaluation.arm_counts())
    fields.update(environment_versions())
    return fields
