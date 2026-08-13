"""Migrate frozen Sprint 3 artifacts to the audited v2 schemas.

The migration does not recompute model estimates. It joins already-frozen
confirmation metrics into the experiment registry, labels historical provenance
that was not captured at run time, and separates random-policy sensitivity ranges
from confidence intervals.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.experiment import (  # noqa: E402
    CRITEO_V2_1_SHA256,
    REGISTRY_COLUMNS,
    config_hash,
)
from src.paths import OUTPUT_DIR, REPO_ROOT  # noqa: E402


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(".tmp.csv")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _read_git_head_csv(path: Path, *, required: bool) -> pd.DataFrame | None:
    """Read the pre-migration tracked artifact without modifying the worktree."""
    relative = path.relative_to(REPO_ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode == 0:
        return pd.read_csv(io.StringIO(result.stdout))
    if required:
        raise RuntimeError(f"Cannot read legacy artifact from git HEAD: {relative}")
    return None


def _registry_identity(frame: pd.DataFrame) -> pd.Series:
    fold = frame["fold_seed"].astype(object).where(
        frame["fold_seed"].notna(), "<none>"
    )
    outcome = frame["outcome"].astype(object).where(
        frame["outcome"].notna(), "conversion"
    )
    return (
        frame["run_id"].astype(str)
        + "|"
        + fold.astype(str)
        + "|"
        + outcome.astype(str)
    )


def migrate_registry() -> None:
    path = OUTPUT_DIR / "improvement" / "registry.csv"
    metrics_path = OUTPUT_DIR / "sprint3" / "confirmation_metrics.csv"
    manifest_path = OUTPUT_DIR / "sprint3" / "protocol_manifest.json"
    registry = pd.read_csv(path)
    metrics = pd.read_csv(metrics_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for column in REGISTRY_COLUMNS:
        if column not in registry:
            registry[column] = np.nan
    registry["outcome"] = registry["outcome"].fillna("conversion")

    # A prior two-column de-duplication could collapse the visit diagnostic into
    # the conversion run because both reused run_id/fold_seed. Merge the tracked
    # pre-migration log back in and retain the latest timestamp per full identity.
    # On equal timestamps, the current v2 row wins so enriched fields are kept.
    historical = _read_git_head_csv(path, required=False)
    if historical is not None:
        for column in REGISTRY_COLUMNS:
            if column not in historical:
                historical[column] = np.nan
        historical["outcome"] = historical["outcome"].fillna("conversion")
        historical = historical[registry.columns]
        historical["_source_priority"] = 0
        registry["_source_priority"] = 1
        registry = pd.concat([historical, registry], ignore_index=True)
        registry["_identity"] = _registry_identity(registry)
        registry["_created_sort"] = pd.to_datetime(
            registry["created_utc"],
            utc=True,
            errors="coerce",
        )
        registry = (
            registry.sort_values(
                ["_identity", "_created_sort", "_source_priority"],
                kind="stable",
            )
            .drop_duplicates("_identity", keep="last")
            .drop(columns=["_identity", "_created_sort", "_source_priority"])
            .reset_index(drop=True)
        )
    registry["data_sha256"] = registry["data_sha256"].replace(
        {"not_recomputed": CRITEO_V2_1_SHA256}
    )
    registry["working_tree_diff_sha256"] = registry[
        "working_tree_diff_sha256"
    ].fillna("not_recorded_historical")

    run_prefix = manifest["run_id"]
    confirmation_rows = registry["run_id"].astype(str).str.startswith(run_prefix)
    template = registry.loc[confirmation_rows].iloc[0].copy()
    weights = manifest.get("ensemble_weights", {})
    metric_columns = [
        column
        for column in metrics.columns
        if column in REGISTRY_COLUMNS and column != "run_id"
    ]

    for _, metric in metrics.iterrows():
        model = metric["model"]
        run_id = f"{run_prefix}-{model}"
        match = registry["run_id"] == run_id
        if not match.any():
            row = template.copy()
            row["run_id"] = run_id
            row["candidate"] = model
            row["candidate_family"] = "ensemble"
            row["fit_seconds"] = np.nan
            row["predict_seconds"] = np.nan
            definition = weights.get(model, {})
            row["config_hash"] = config_hash(definition)
            row["config_json"] = json.dumps(
                definition,
                ensure_ascii=False,
                sort_keys=True,
            )
            registry = pd.concat([registry, row.to_frame().T], ignore_index=True)
            match = registry["run_id"] == run_id
        for column in metric_columns:
            registry.loc[match, column] = metric[column]

    confirmation_rows = registry["status"] == "retrospective_confirmation"
    registry.loc[confirmation_rows, "run_id"] = registry.loc[
        confirmation_rows, "candidate"
    ].map(lambda candidate: f"{run_prefix}-{candidate}")
    registry = registry.drop_duplicates(
        subset=["run_id", "fold_seed", "outcome"],
        keep="last",
    ).reset_index(drop=True)

    ordered = REGISTRY_COLUMNS + [
        column for column in registry.columns if column not in REGISTRY_COLUMNS
    ]
    _atomic_csv(registry[ordered], path)


def migrate_promotion_and_manifest() -> None:
    protocol = json.loads(
        (REPO_ROOT / "configs" / "sprint3_improvement_protocol.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_path = OUTPUT_DIR / "sprint3" / "protocol_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = pd.read_csv(OUTPUT_DIR / "sprint3" / "confirmation_metrics.csv").set_index(
        "model"
    )
    decisions_path = OUTPUT_DIR / "sprint3" / "promotion_decision.csv"
    decisions = pd.read_csv(decisions_path)

    # max memory percent was not captured by the historical run. Condition 4
    # therefore fails conservatively rather than inventing a pass after the fact.
    decisions["resource_gate_passed"] = False
    decisions["score_guardrail_passed"] = decisions["challenger"].map(
        lambda name: bool(
            np.isfinite(metrics.loc[name, "score_std"])
            and metrics.loc[name, "unique_score_count"]
            >= protocol["early_stop"]["constant_score_unique_threshold"]
        )
    )
    decisions["calibration_guardrail_passed"] = decisions["challenger"].map(
        lambda name: bool(
            not metrics.loc[name, "is_cate_scale"]
            or np.isfinite(metrics.loc[name, "uplift_calibration_error"])
        )
    )
    decisions["condition_4_operational_guardrails_passed"] = False
    decisions["condition_4_evaluation"] = (
        "conservative_fail_historical_max_memory_percent_not_recorded"
    )
    decisions["promoted"] = (
        decisions["condition_1_oof_wins_all_seeds"]
        & decisions["condition_2_confirmation_same_sign"]
        & decisions["condition_3_paired_ci_lower_bound_positive"]
        & decisions["condition_4_operational_guardrails_passed"]
    )
    _atomic_csv(decisions, decisions_path)

    manifest["promotion_rule"] = protocol["promotion_rule"]
    manifest["protocol_integrity_revision"] = protocol["integrity_revision"]
    manifest["resource_gate_passed"] = False
    manifest["max_system_memory_percent"] = None
    manifest["resource_gate_evaluation"] = (
        "historical run did not capture max memory percent; conservative fail"
    )
    temporary = manifest_path.with_suffix(".tmp.json")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(manifest_path)


def migrate_random_policy_ranges() -> None:
    path = OUTPUT_DIR / "sprint3" / "policy_budget_curve.csv"
    curve = pd.read_csv(path)
    random_rows = curve["model"] == "Expected random (stochastic policy)"
    if "sensitivity_low" not in curve:
        curve["sensitivity_low"] = np.nan
        curve["sensitivity_high"] = np.nan

    # Idempotence matters: after the first migration ci_low/ci_high are empty.
    # Preserve already-migrated sensitivity values and only fill missing cells
    # from the legacy CI columns. If an interrupted/older v2 migration cleared
    # both sets of columns, recover the original frozen values from git HEAD;
    # this reads history only and does not recompute any estimate.
    for target, source in (
        ("sensitivity_low", "ci_low"),
        ("sensitivity_high", "ci_high"),
    ):
        current = pd.to_numeric(curve.loc[random_rows, target], errors="coerce")
        legacy = pd.to_numeric(curve.loc[random_rows, source], errors="coerce")
        curve.loc[random_rows, target] = current.fillna(legacy).to_numpy()

    missing = random_rows & (
        curve["sensitivity_low"].isna() | curve["sensitivity_high"].isna()
    )
    if missing.any():
        legacy_curve = _read_git_head_csv(path, required=True)
        assert legacy_curve is not None
        legacy_random = legacy_curve.loc[
            legacy_curve["model"] == "Expected random (stochastic policy)",
            ["run_id", "model", "budget_fraction", "ci_low", "ci_high"],
        ].rename(
            columns={
                "ci_low": "recovered_sensitivity_low",
                "ci_high": "recovered_sensitivity_high",
            }
        )
        curve = curve.merge(
            legacy_random,
            on=["run_id", "model", "budget_fraction"],
            how="left",
            validate="many_to_one",
        )
        for target, recovered in (
            ("sensitivity_low", "recovered_sensitivity_low"),
            ("sensitivity_high", "recovered_sensitivity_high"),
        ):
            curve[target] = curve[target].fillna(curve[recovered])
            curve = curve.drop(columns=recovered)

    unresolved = random_rows & (
        curve["sensitivity_low"].isna() | curve["sensitivity_high"].isna()
    )
    if unresolved.any():
        raise RuntimeError("Random-policy sensitivity migration left missing ranges")
    curve.loc[random_rows, ["ci_low", "ci_high"]] = np.nan
    _atomic_csv(curve, path)


def main() -> None:
    migrate_registry()
    migrate_promotion_and_manifest()
    migrate_random_policy_ranges()
    print("Migrated Sprint 3 registry, promotion, manifest and random-policy ranges.")


if __name__ == "__main__":
    main()
