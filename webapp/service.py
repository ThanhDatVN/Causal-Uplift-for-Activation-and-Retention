"""Tầng dịch vụ: đọc artifact release và tính các đại lượng phái sinh.

Nguyên tắc:

- không train khi phục vụ request; ``/api/score`` dùng scorer đã fit sẵn;
- mọi con số trả về đều kèm ``source`` chỉ đúng file artifact sinh ra nó;
- artifact thiếu thì trả trạng thái ``unavailable`` thay vì tự bịa giá trị;
- giá trị tiền tệ luôn được đánh dấu là kịch bản giả định, không phải doanh thu.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import OUTPUT_DIR, REPO_ROOT

WEBAPP_DIR = OUTPUT_DIR / "webapp"
SCORER_PATH = WEBAPP_DIR / "champion_scorer.joblib"

SCHEMA_VERSION = "causal-uplift-webapp-v1"


def _clean(value):
    """Chuyển giá trị numpy/NaN thành dạng JSON hợp lệ."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return [_clean(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if value is None or isinstance(value, str):
        return value
    if pd.isna(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    return [_clean(record) for record in frame.to_dict(orient="records")]


def _relative(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class ArtifactStatus:
    name: str
    path: str
    available: bool


class ArtifactRepository:
    """Đọc và cache artifact; cache tự làm mới khi file thay đổi mtime."""

    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir
        self.sprint1_dir = output_dir / "sprint1"
        self.sprint2_dir = output_dir / "sprint2"
        self.sprint3_dir = output_dir / "sprint3"
        self.improvement_dir = output_dir / "improvement"
        self.webapp_dir = output_dir / "webapp"
        self._cache: dict[str, tuple[float, object]] = {}

    # ------------------------------------------------------------------ utils
    def _cached(self, path: Path, loader):
        if not path.exists():
            return None
        stamp = path.stat().st_mtime_ns
        key = str(path)
        hit = self._cache.get(key)
        if hit is not None and hit[0] == stamp:
            return hit[1]
        value = loader(path)
        self._cache[key] = (stamp, value)
        return value

    def csv(self, path: Path) -> pd.DataFrame | None:
        return self._cached(path, pd.read_csv)

    def json(self, path: Path) -> dict | None:
        return self._cached(
            path,
            lambda p: json.loads(p.read_text(encoding="utf-8")),
        )

    # --------------------------------------------------------------- status
    def artifact_status(self) -> list[ArtifactStatus]:
        entries = {
            "sprint1_final_test": self.output_dir
            / "optimization"
            / "final_test_results_sprint1_release_5models.csv",
            "sprint1_policy_deciles": self.sprint1_dir / "policy_deciles_release.csv",
            "sprint1_pairwise": self.sprint1_dir
            / "model_pairwise_bootstrap_release.csv",
            "sprint1_balance": self.sprint1_dir / "balance_smd.csv",
            "sprint2_manifest": self.sprint2_dir / "protocol_manifest.json",
            "sprint2_metrics": self.sprint2_dir / "calibration_comparison.csv",
            "sprint2_policy": self.sprint2_dir / "policy_value_comparison.csv",
            "sprint2_budget_curve": self.sprint2_dir / "policy_budget_curve.csv",
            "sprint3_manifest": self.sprint3_dir / "protocol_manifest.json",
            "sprint3_metrics": self.sprint3_dir / "confirmation_metrics.csv",
            "sprint3_pairwise": self.sprint3_dir / "paired_comparisons.csv",
            "sprint3_budget_curve": self.sprint3_dir / "policy_budget_curve.csv",
            "sprint3_promotion": self.sprint3_dir / "promotion_decision.csv",
            "improvement_registry": self.improvement_dir / "registry.csv",
            "champion_scorer": self.webapp_dir / "champion_scorer.joblib",
        }
        return [
            ArtifactStatus(name=name, path=_relative(path), available=path.exists())
            for name, path in entries.items()
        ]

    # ----------------------------------------------------------------- meta
    def meta(self) -> dict:
        sprint2 = self.json(self.sprint2_dir / "protocol_manifest.json") or {}
        sprint3 = self.json(self.sprint3_dir / "protocol_manifest.json") or {}
        scorer_meta = self.json(self.webapp_dir / "champion_scorer.json") or {}
        champion = (
            sprint3.get("final_champion")
            or scorer_meta.get("champion")
            or "Response"
        )
        return _clean(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "champion": champion,
                "champion_selection_note": (
                    "Champion được chốt bằng promotion rule đăng ký trước. Nếu "
                    "không challenger nào đạt rule, champion giữ nguyên Response "
                    "đã chọn trên validation Sprint 2."
                ),
                "data": {
                    "dataset": "Criteo Uplift Prediction Dataset v2.1",
                    "sha256": sprint2.get("data", {}).get("sha256"),
                    "rows": sprint2.get("data", {})
                    .get("schema_contract", {})
                    .get("row_count"),
                    "outcome": "conversion",
                    "excluded_post_treatment": ["visit", "exposure"],
                },
                "sprints": {
                    "sprint1": {
                        "status": "released",
                        "test_rows": 2_096_940,
                        "evidence": "output/sprint1/, output/optimization/",
                    },
                    "sprint2": {
                        "status": sprint2.get("status", "unavailable"),
                        "run_id": sprint2.get("run_id"),
                        "confirmation_rows": sprint2.get("split", {})
                        .get("rows", {})
                        .get("confirmation"),
                        "split_protocol": sprint2.get("split", {}).get("protocol"),
                        "index_sha256": sprint2.get("split", {}).get(
                            "source_index_sha256"
                        ),
                    },
                    "sprint3": {
                        "status": sprint3.get(
                            "status",
                            "not_run",
                        ),
                        "run_id": sprint3.get("run_id"),
                        "evidence_class": sprint3.get("evidence_class"),
                        "evidence_note": sprint3.get("evidence_note"),
                        "development_rows": sprint3.get("development_rows"),
                        "confirmation_rows": sprint3.get("confirmation_rows"),
                        "promoted_challengers": sprint3.get("promoted_challengers", []),
                        "protocol_id": sprint3.get("protocol_id"),
                    },
                },
                "causal_forest": {
                    "status": "pending_external_kaggle_session",
                    "local_smoke": "code path only at 0.1 percent",
                    "release_result_available": False,
                },
                "artifacts": [
                    {
                        "name": status.name,
                        "path": status.path,
                        "available": status.available,
                    }
                    for status in self.artifact_status()
                ],
            }
        )

    # --------------------------------------------------------------- models
    def models(self) -> dict:
        sprint2 = self.csv(self.sprint2_dir / "calibration_comparison.csv")
        sprint3 = self.csv(self.sprint3_dir / "confirmation_metrics.csv")
        payload: dict = {"sources": {}}

        if sprint2 is not None:
            confirmation = sprint2.loc[sprint2["split"] == "confirmation"]
            payload["sprint2_confirmation"] = _records(
                confirmation[
                    [
                        "model",
                        "model_label",
                        "qini_score",
                        "auuc_score",
                        "uplift_calibration_error",
                        "score_mean",
                        "unique_score_count",
                    ]
                ].sort_values("qini_score", ascending=False)
            )
            payload["sources"]["sprint2_confirmation"] = _relative(
                self.sprint2_dir / "calibration_comparison.csv"
            )
        if sprint3 is not None:
            payload["sprint3_confirmation"] = _records(
                sprint3.sort_values("policy_area_dr", ascending=False)
            )
            payload["sources"]["sprint3_confirmation"] = _relative(
                self.sprint3_dir / "confirmation_metrics.csv"
            )

        oof = self.csv(self.improvement_dir / "screen" / "oof_metrics.csv")
        finalist = self.csv(self.improvement_dir / "finalist" / "oof_metrics.csv")
        for label, frame, path in (
            ("screen", oof, self.improvement_dir / "screen" / "oof_metrics.csv"),
            (
                "finalist",
                finalist,
                self.improvement_dir / "finalist" / "oof_metrics.csv",
            ),
        ):
            if frame is None:
                continue
            columns = [
                column
                for column in (
                    "candidate",
                    "status",
                    "pool_fraction",
                    "fold_seed",
                    "policy_area_dr",
                    "autoc_dr",
                    "qini_score",
                    "auuc_score",
                    "doubly_robust_risk",
                    "fit_seconds",
                    "peak_process_rss_gb",
                    "failure_reason",
                )
                if column in frame.columns
            ]
            payload[f"oof_{label}"] = _records(
                frame[columns].sort_values("policy_area_dr", ascending=False)
            )
            payload["sources"][f"oof_{label}"] = _relative(path)
        return payload

    def pairwise(self) -> dict:
        payload: dict = {"sources": {}}
        sprint1 = self.csv(
            self.sprint1_dir / "model_pairwise_bootstrap_release.csv"
        )
        if sprint1 is not None:
            payload["sprint1_qini"] = _records(sprint1)
            payload["sources"]["sprint1_qini"] = _relative(
                self.sprint1_dir / "model_pairwise_bootstrap_release.csv"
            )
        sprint2 = self.csv(self.sprint2_dir / "paired_qini_bootstrap.csv")
        if sprint2 is not None:
            payload["sprint2_qini"] = _records(sprint2)
            payload["sources"]["sprint2_qini"] = _relative(
                self.sprint2_dir / "paired_qini_bootstrap.csv"
            )
        sprint3 = self.csv(self.sprint3_dir / "paired_comparisons.csv")
        if sprint3 is not None:
            payload["sprint3_policy_area"] = _records(sprint3)
            payload["sources"]["sprint3_policy_area"] = _relative(
                self.sprint3_dir / "paired_comparisons.csv"
            )
        promotion = self.csv(self.sprint3_dir / "promotion_decision.csv")
        if promotion is not None:
            payload["promotion_decision"] = _records(promotion)
            payload["sources"]["promotion_decision"] = _relative(
                self.sprint3_dir / "promotion_decision.csv"
            )
        return payload

    # --------------------------------------------------------------- policy
    def budget_curve(self) -> dict:
        sprint3 = self.csv(self.sprint3_dir / "policy_budget_curve.csv")
        if sprint3 is not None:
            return {
                "source": _relative(self.sprint3_dir / "policy_budget_curve.csv"),
                "evidence_class": "retrospective_confirmation",
                "rows": _records(sprint3.sort_values(["model", "budget_fraction"])),
            }
        sprint2 = self.csv(self.sprint2_dir / "policy_budget_curve.csv")
        if sprint2 is not None:
            frame = sprint2.rename(
                columns={
                    "gross_incremental_conversions_per_customer_dr": (
                        "gross_value_per_customer"
                    ),
                    "gross_dr_ci_low": "ci_low",
                    "gross_dr_ci_high": "ci_high",
                    "break_even_contact_cost_per_target_conversion_equivalent": (
                        "break_even_contact_cost"
                    ),
                }
            )
            frame["model"] = frame["policy"]
            return {
                "source": _relative(self.sprint2_dir / "policy_budget_curve.csv"),
                "evidence_class": "sprint2_confirmation",
                "rows": _records(
                    frame[
                        [
                            "model",
                            "budget_fraction",
                            "gross_value_per_customer",
                            "ci_low",
                            "ci_high",
                            "break_even_contact_cost",
                        ]
                    ].sort_values(["model", "budget_fraction"])
                ),
            }
        return {"source": None, "evidence_class": "unavailable", "rows": []}

    def policy_comparison(self) -> dict:
        sprint3 = self.csv(self.sprint3_dir / "policy_value_comparison.csv")
        if sprint3 is not None:
            return {
                "source": _relative(self.sprint3_dir / "policy_value_comparison.csv"),
                "evidence_class": "retrospective_confirmation",
                "rows": _records(
                    sprint3.sort_values(
                        "dr_net_scenario_value_per_customer",
                        ascending=False,
                    )
                ),
            }
        sprint2 = self.csv(self.sprint2_dir / "policy_value_comparison.csv")
        if sprint2 is not None:
            return {
                "source": _relative(self.sprint2_dir / "policy_value_comparison.csv"),
                "evidence_class": "sprint2_confirmation",
                "rows": _records(
                    sprint2.sort_values(
                        "dr_net_scenario_value_per_customer",
                        ascending=False,
                    )
                ),
            }
        return {"source": None, "evidence_class": "unavailable", "rows": []}

    def sensitivity(self) -> dict:
        for directory, label in (
            (self.sprint3_dir, "retrospective_confirmation"),
            (self.sprint2_dir, "sprint2_confirmation"),
        ):
            frame = self.csv(directory / "policy_sensitivity.csv")
            if frame is not None:
                return {
                    "source": _relative(directory / "policy_sensitivity.csv"),
                    "evidence_class": label,
                    "rows": _records(frame),
                }
        return {"source": None, "evidence_class": "unavailable", "rows": []}

    def deciles(self) -> dict:
        frame = self.csv(self.sprint1_dir / "policy_deciles_release.csv")
        if frame is None:
            return {"source": None, "rows": []}
        columns = [
            "model",
            "decile",
            "target_fraction",
            "n_decile",
            "mean_score_decile",
            "decile_observed_uplift_rate",
            "decile_uplift_ci_low",
            "decile_uplift_ci_high",
            "cumulative_observed_uplift_rate",
            "estimated_incremental_conversions_cumulative",
            "incremental_conversions_ci_low",
            "incremental_conversions_ci_high",
            "share_of_full_incremental_estimate",
        ]
        return {
            "source": _relative(self.sprint1_dir / "policy_deciles_release.csv"),
            "evidence_class": "sprint1_final_test",
            "note": (
                "Decile duoc tinh tren final test Sprint 1 (2.096.940 dong). "
                "Day la bang chung lich su, khong phai confirmation Sprint 2/3."
            ),
            "rows": _records(frame[columns]),
        }

    def diagnostics(self) -> dict:
        payload: dict = {"sources": {}}
        balance = self.csv(self.sprint1_dir / "balance_smd.csv")
        if balance is not None:
            payload["balance_smd"] = _records(balance)
            payload["sources"]["balance_smd"] = _relative(
                self.sprint1_dir / "balance_smd.csv"
            )
        arms = self.csv(self.sprint1_dir / "arm_outcome_summary.csv")
        if arms is not None:
            payload["arm_summary"] = _records(arms)
            payload["sources"]["arm_summary"] = _relative(
                self.sprint1_dir / "arm_outcome_summary.csv"
            )
        scores = self.csv(self.sprint1_dir / "score_diagnostics_release.csv")
        if scores is not None:
            payload["score_diagnostics"] = _records(scores)
            payload["sources"]["score_diagnostics"] = _relative(
                self.sprint1_dir / "score_diagnostics_release.csv"
            )
        payload["balance_note"] = (
            "SMD va propensity AUC la balance diagnostic. Chung khong tu chung "
            "minh randomization; can provenance tu nguon du lieu."
        )
        return payload

    def registry(self, limit: int | None = None) -> dict:
        frame = self.csv(self.improvement_dir / "registry.csv")
        if frame is None:
            return {"source": None, "rows": [], "row_count": 0}
        columns = [
            column
            for column in (
                "run_id",
                "created_utc",
                "status",
                "candidate",
                "candidate_family",
                "config_hash",
                "pool_fraction",
                "fold_seed",
                "n_rows",
                "n_conversion_control",
                "policy_area_dr",
                "autoc_dr",
                "qini_score",
                "fit_seconds",
                "peak_process_rss_gb",
                "failure_reason",
            )
            if column in frame.columns
        ]
        selected = frame[columns].iloc[::-1]
        if limit:
            selected = selected.head(limit)
        return {
            "source": _relative(self.improvement_dir / "registry.csv"),
            "row_count": int(len(frame)),
            "rows": _records(selected),
        }

    # ------------------------------------------------------------ simulation
    def simulate(
        self,
        budget_fraction: float,
        audience: int = 1_000_000,
        value_per_conversion: float = 1.0,
        contact_cost: float = 0.0005,
        model: str | None = None,
    ) -> dict:
        """Nội suy budget curve rồi quy đổi sang kịch bản value/cost.

        Giá trị trả về là **conversion-equivalent scenario**. Criteo không có
        doanh thu, margin hay chi phí liên hệ thực tế, nên không có con số nào ở
        đây là profit quan sát được.
        """
        if not 0 <= budget_fraction <= 1:
            raise ValueError("budget_fraction phải nằm trong [0, 1]")
        if audience < 1:
            raise ValueError("audience phải >= 1")
        if value_per_conversion <= 0:
            raise ValueError("value_per_conversion phải > 0")
        if contact_cost < 0:
            raise ValueError("contact_cost phải >= 0")

        curve = self.budget_curve()
        if not curve["rows"]:
            raise FileNotFoundError("Chưa có budget curve artifact để mô phỏng")
        frame = pd.DataFrame(curve["rows"])
        available = sorted(frame["model"].unique())
        champion = self.meta()["champion"]
        preferred = [
            model,
            champion,
            f"{champion} top-k",
            "Response",
            "Response top-k",
        ]
        selected = next(
            (name for name in preferred if name and name in available),
            available[0],
        )
        subset = frame.loc[frame["model"] == selected].sort_values("budget_fraction")
        budgets = subset["budget_fraction"].to_numpy(dtype="float64")
        values = subset["gross_value_per_customer"].to_numpy(dtype="float64")
        low = subset["ci_low"].astype("float64").to_numpy()
        high = subset["ci_high"].astype("float64").to_numpy()

        if budget_fraction == 0:
            gross = gross_low = gross_high = 0.0
        else:
            gross = float(np.interp(budget_fraction, budgets, values))
            gross_low = float(np.interp(budget_fraction, budgets, low))
            gross_high = float(np.interp(budget_fraction, budgets, high))

        targeted = audience * budget_fraction
        cost_total = targeted * contact_cost
        net_per_customer = gross * value_per_conversion - budget_fraction * contact_cost
        net_low = gross_low * value_per_conversion - budget_fraction * contact_cost
        net_high = gross_high * value_per_conversion - budget_fraction * contact_cost
        break_even = (
            gross * value_per_conversion / budget_fraction
            if budget_fraction > 0
            else None
        )
        return _clean(
            {
                "model": selected,
                "available_models": available,
                "evidence_class": curve["evidence_class"],
                "source": curve["source"],
                "inputs": {
                    "budget_fraction": budget_fraction,
                    "audience": audience,
                    "value_per_conversion": value_per_conversion,
                    "contact_cost": contact_cost,
                },
                "gross_incremental_conversions_per_customer": gross,
                "gross_ci_low": gross_low,
                "gross_ci_high": gross_high,
                "targeted_customers": targeted,
                "total_incremental_conversions": audience * gross,
                "total_incremental_conversions_ci_low": audience * gross_low,
                "total_incremental_conversions_ci_high": audience * gross_high,
                "net_scenario_value_per_customer": net_per_customer,
                "net_scenario_value_ci_low": net_low,
                "net_scenario_value_ci_high": net_high,
                "total_net_scenario_value": audience * net_per_customer,
                "total_contact_cost": cost_total,
                "break_even_contact_cost": break_even,
                "decision": (
                    "positive_scenario_value"
                    if net_per_customer > 0
                    else "non_positive_scenario_value"
                ),
                "is_monetary_observation": False,
                "interpretation": (
                    "Conversion-equivalent scenario. Value va cost la input gia "
                    "dinh cua nguoi dung, khong phai doanh thu hay chi phi quan sat."
                ),
            }
        )

    # ------------------------------------------------------------- limitations
    def _registered_promotion_rule(self) -> dict:
        """Promotion rule lấy thẳng từ protocol khi Sprint 3 chưa sinh manifest.

        Luật phải hiển thị được trước khi chạy, nếu không người đọc không kiểm tra
        được rằng nó đã đăng ký trước chứ không viết sau khi xem kết quả.
        """
        protocol = self.json(
            REPO_ROOT / "configs" / "sprint3_improvement_protocol.json"
        )
        return (protocol or {}).get("promotion_rule", {})

    def evidence(self) -> dict:
        sprint3 = self.json(self.sprint3_dir / "protocol_manifest.json") or {}
        return _clean(
            {
                "limitations": [
                    "Ước lượng policy offline trên RCT; chưa có A/B test production.",
                    "Criteo có conversion nhưng không có revenue, margin hay contact cost.",
                    "Không quan sát được principal stratum của từng cá nhân.",
                    "Response là ranking policy score, không phải calibrated CATE.",
                    "Causal Forest chưa có kết quả cloud; không nằm trong release.",
                    "Confirmation Sprint 2 đã được quan sát nên kết quả Sprint 3 trên "
                    "tập đó là retrospective confirmation.",
                ],
                "assumptions": [
                    "Propensity là hằng số của thiết kế randomized.",
                    "Feature f0..f11 là tiền treatment; visit/exposure bị loại.",
                    "Value và cost do người dùng nhập và cùng đơn vị tiền tệ.",
                ],
                "evidence_hierarchy": [
                    {
                        "level": "sprint1_final_test",
                        "rows": 2_096_940,
                        "use": "bằng chứng lịch sử, không tái sử dụng để chọn model",
                    },
                    {
                        "level": "sprint3_development_oof",
                        "rows": sprint3.get("development_rows"),
                        "use": "chọn shortlist và học ensemble weights",
                    },
                    {
                        "level": "retrospective_confirmation",
                        "rows": sprint3.get("confirmation_rows"),
                        "use": "áp promotion rule đúng một lần",
                    },
                ],
                "promotion_rule": sprint3.get("promotion_rule")
                or self._registered_promotion_rule(),
                "final_champion": sprint3.get("final_champion"),
            }
        )


@lru_cache(maxsize=1)
def get_repository() -> ArtifactRepository:
    return ArtifactRepository()


@lru_cache(maxsize=1)
def get_scorer():
    """Nạp scorer đã fit; trả ``None`` nếu chưa build artifact."""
    if not SCORER_PATH.exists():
        return None
    from src.scoring import PersistedScorer

    return PersistedScorer.load(SCORER_PATH)
