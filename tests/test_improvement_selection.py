import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from scripts.compare_improvement_candidates import (
    advancement_table,
    assert_comparable_runs,
    assert_manifest_matches_protocol,
    block_legacy_advancement,
    registered_fold_seeds,
    restrict_advancement_to_registered,
    validate_run_manifest,
)
from scripts.merge_oof_runs import (
    legacy_candidate_config_hashes,
    merge_candidate_config_hashes,
    merge_oof_payloads,
)
from scripts.analyze_causal_foundation import stability_label


def _comparison_data(
    source=None,
    *,
    treatment=None,
    outcome=None,
    score_names=("Response",),
):
    source = np.asarray([3, 5, 8] if source is None else source)
    n_rows = len(source)
    return {
        "source_index": source,
        "treatment": np.asarray(
            [0, 1, 1] if treatment is None else treatment,
            dtype="float64",
        ),
        "outcome": np.asarray(
            [0, 0, 1] if outcome is None else outcome,
            dtype="float64",
        ),
        "scores": {
            name: np.linspace(0.0, 1.0, n_rows, dtype="float64")
            for name in score_names
        },
    }


def test_advancement_requires_a_win_on_every_fold_seed():
    ranking = pd.DataFrame(
        [
            {"model": "Response", "fold_seed": 101, "policy_area_dr": 0.10},
            {"model": "Response", "fold_seed": 202, "policy_area_dr": 0.11},
            {"model": "stable", "fold_seed": 101, "policy_area_dr": 0.12},
            {"model": "stable", "fold_seed": 202, "policy_area_dr": 0.13},
            {"model": "mean-only", "fold_seed": 101, "policy_area_dr": 0.20},
            {"model": "mean-only", "fold_seed": 202, "policy_area_dr": 0.10},
        ]
    )

    decisions = advancement_table(
        ranking,
        reference="Response",
        require_all_fold_seeds=True,
        required_fold_seeds=(101, 202),
    ).set_index("model")

    assert bool(decisions.loc["stable", "advance"])
    assert not bool(decisions.loc["mean-only", "advance"])


def test_advancement_rejects_a_single_seed_when_protocol_requires_two():
    ranking = pd.DataFrame(
        [
            {"model": "Response", "fold_seed": 101, "policy_area_dr": 0.10},
            {"model": "challenger", "fold_seed": 101, "policy_area_dr": 0.12},
        ]
    )

    decisions = advancement_table(
        ranking,
        reference="Response",
        require_all_fold_seeds=True,
        required_fold_seeds=(101, 202),
    ).set_index("model")

    assert not bool(decisions.loc["challenger", "advance"])
    assert decisions.loc["challenger", "reason"] == "missing_fold_seed"


def test_advancement_requires_the_exact_registered_seed_set():
    ranking = pd.DataFrame(
        [
            {"model": model, "fold_seed": seed, "policy_area_dr": value}
            for model, value in (("Response", 0.10), ("challenger", 0.12))
            for seed in (101, 202, 303)
        ]
    )

    decisions = advancement_table(
        ranking,
        reference="Response",
        require_all_fold_seeds=True,
        required_fold_seeds=(101, 202),
    ).set_index("model")

    assert not bool(decisions.loc["challenger", "advance"])
    assert decisions.loc["challenger", "reason"] == "missing_fold_seed"


def test_advancement_rejects_duplicate_model_fold_seed_rows():
    ranking = pd.DataFrame(
        [
            {"model": "Response", "fold_seed": 101, "policy_area_dr": 0.10},
            {"model": "Response", "fold_seed": 101, "policy_area_dr": 0.11},
            {"model": "challenger", "fold_seed": 101, "policy_area_dr": 0.12},
        ]
    )

    with pytest.raises(ValueError, match="duplicate model/fold_seed"):
        advancement_table(
            ranking,
            reference="Response",
            require_all_fold_seeds=False,
        )


def test_registered_fold_seeds_are_resolved_from_protocol():
    protocol = {
        "cross_fitting": {
            "primary_fold_seed": 101,
            "secondary_fold_seed": 202,
        },
        "selection_rule": {"advance_all_fold_seeds": True},
    }

    assert registered_fold_seeds(protocol) == (101, 202)


def test_diagnostic_ensemble_cannot_advance_a_registered_protocol():
    decisions = pd.DataFrame(
        [
            {
                "model": "registered",
                "advance": True,
                "reason": "beats_reference_on_every_fold_seed",
            },
            {
                "model": "Ensemble-QAgg",
                "advance": True,
                "reason": "beats_reference_on_every_fold_seed",
            },
        ]
    )

    restricted = restrict_advancement_to_registered(decisions, {"registered"})
    result = restricted.set_index("model")

    assert bool(result.loc["registered", "advance"])
    assert not bool(result.loc["Ensemble-QAgg", "advance"])
    assert (
        result.loc["Ensemble-QAgg", "reason"]
        == "diagnostic_ensemble_not_eligible"
    )


def test_comparison_rejects_different_oof_populations():
    manifest = {
        "manifest_schema_version": 2,
        "protocol_id": "p1",
        "protocol_sha256": "protocol-abc",
        "stage": "screen",
        "outcome": "conversion",
        "development_index_sha256": "abc",
        "pool_fraction": 0.15,
        "pool_seed": 77,
        "model_seed": 42,
        "n_folds": 3,
        "propensity": 0.85,
        "budget_grid": [0.01, 0.02],
        "candidate_config_hashes": {"Response": "response-v1"},
    }
    data = _comparison_data()

    assert_comparable_runs(manifest, dict(manifest), data, _comparison_data())

    changed = dict(manifest, pool_seed=78)
    try:
        assert_comparable_runs(manifest, changed, data, _comparison_data())
    except ValueError as error:
        assert "comparison contract" in str(error)
    else:
        raise AssertionError("Expected a different pool seed to be rejected")

    try:
        assert_comparable_runs(
            manifest,
            dict(manifest),
            data,
            _comparison_data(source=[8, 5, 3]),
        )
    except ValueError as error:
        assert "source_index" in str(error)
    else:
        raise AssertionError("Expected a reordered OOF population to be rejected")


def test_comparison_rejects_protocol_stage_and_candidate_config_drift():
    manifest = {
        "manifest_schema_version": 2,
        "protocol_id": "p1",
        "protocol_sha256": "protocol-abc",
        "stage": "screen",
        "outcome": "conversion",
        "development_index_sha256": "data-abc",
        "pool_fraction": 0.15,
        "pool_seed": 77,
        "model_seed": 42,
        "n_folds": 3,
        "propensity": 0.85,
        "budget_grid": [0.01, 0.02],
        "candidate_config_hashes": {"Response": "response-v1"},
    }
    data = _comparison_data()

    for field, value in (
        ("protocol_sha256", "protocol-def"),
        ("stage", "finalist"),
        ("n_folds", 5),
        ("propensity", 0.5),
        ("budget_grid", [0.01]),
    ):
        changed = {**manifest, field: value}
        try:
            assert_comparable_runs(manifest, changed, data, _comparison_data())
        except ValueError as error:
            assert "comparison contract" in str(error)
        else:
            raise AssertionError(f"Expected drift in {field} to be rejected")

    changed_config = {
        **manifest,
        "candidate_config_hashes": {"Response": "response-v2"},
    }
    try:
        assert_comparable_runs(manifest, changed_config, data, _comparison_data())
    except ValueError as error:
        assert "config hash" in str(error)
    else:
        raise AssertionError("Expected candidate config drift to be rejected")


def test_comparison_rejects_new_manifest_against_legacy_or_incomplete_manifest():
    current = {
        "manifest_schema_version": 2,
        "protocol_id": "p1",
        "protocol_sha256": "protocol-abc",
        "stage": "screen",
        "outcome": "conversion",
        "development_index_sha256": "data-abc",
        "pool_fraction": 0.15,
        "pool_seed": 77,
        "model_seed": 42,
        "n_folds": 3,
        "propensity": 0.85,
        "budget_grid": [0.01, 0.02],
        "candidate_config_hashes": {"Response": "response-v1"},
    }
    data = _comparison_data()

    legacy = {key: value for key, value in current.items() if key != "manifest_schema_version"}
    try:
        assert_comparable_runs(
            current,
            legacy,
            data,
            _comparison_data(),
            allow_legacy_manifests=True,
        )
    except ValueError as error:
        assert "manifest schema mode" in str(error)
    else:
        raise AssertionError("Expected schema mismatch to be rejected")

    incomplete = {**current, "protocol_sha256": None}
    try:
        assert_comparable_runs(current, incomplete, data, _comparison_data())
    except ValueError as error:
        assert "comparability provenance" in str(error)
    else:
        raise AssertionError("Expected missing strict provenance to be rejected")


def test_legacy_manifests_require_explicit_diagnostic_mode_and_cannot_advance():
    legacy = {
        "protocol_id": "p1",
        "stage": "screen",
        "outcome": "conversion",
        "development_index_sha256": "data-abc",
        "pool_fraction": 0.15,
        "pool_seed": 77,
        "model_seed": 42,
        "n_folds": 3,
        "propensity": 0.85,
        "budget_grid": [0.01, 0.02],
    }
    data = _comparison_data()

    with pytest.raises(ValueError, match="Legacy run manifest"):
        assert_comparable_runs(legacy, dict(legacy), data, _comparison_data())
    assert_comparable_runs(
        legacy,
        dict(legacy),
        data,
        _comparison_data(),
        allow_legacy_manifests=True,
    )

    decisions = pd.DataFrame(
        [{"model": "challenger", "advance": True, "reason": "point_win"}]
    )
    blocked = block_legacy_advancement(decisions).iloc[0]
    assert not bool(blocked["advance"])
    assert blocked["reason"] == "legacy_manifest_not_eligible"


def test_strict_manifest_is_bound_to_exact_cli_protocol_snapshot():
    protocol = {
        "protocol_id": "p1",
        "cross_fitting": {"n_folds": 3},
        "estimand": {"propensity_value": 0.85},
        "metrics": {"primary_budget_grid": [0.01, 0.02]},
    }
    protocol_bytes = json.dumps(protocol, sort_keys=True).encode("utf-8")
    protocol_sha = hashlib.sha256(protocol_bytes).hexdigest()
    manifest = {
        "protocol_id": "p1",
        "protocol_sha256": protocol_sha,
        "n_folds": 3,
        "propensity": 0.85,
        "budget_grid": [0.01, 0.02],
    }

    assert_manifest_matches_protocol(manifest, protocol, protocol_sha)
    for field, value in (
        ("protocol_id", "p2"),
        ("protocol_sha256", "wrong-sha"),
        ("n_folds", 5),
        ("propensity", 0.5),
        ("budget_grid", [0.01]),
    ):
        with pytest.raises(ValueError, match="CLI protocol snapshot"):
            assert_manifest_matches_protocol(
                {**manifest, field: value},
                protocol,
                protocol_sha,
            )


def test_strict_manifest_requires_hash_for_every_oof_score():
    manifest = {
        "manifest_schema_version": 2,
        "protocol_id": "p1",
        "protocol_sha256": "protocol-abc",
        "stage": "screen",
        "outcome": "conversion",
        "development_index_sha256": "data-abc",
        "pool_fraction": 0.15,
        "pool_seed": 77,
        "model_seed": 42,
        "n_folds": 3,
        "propensity": 0.85,
        "budget_grid": [0.01, 0.02],
        "candidate_config_hashes": {"Response": "response-v1"},
    }
    data = _comparison_data(score_names=("Response", "Challenger"))

    with pytest.raises(ValueError, match="config hash"):
        validate_run_manifest(manifest, data)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("treatment", [1, 1, 1]),
        ("outcome", [1, 0, 1]),
    ],
)
def test_comparison_rejects_treatment_or_outcome_drift(field, replacement):
    manifest = {
        "manifest_schema_version": 2,
        "protocol_id": "p1",
        "protocol_sha256": "protocol-abc",
        "stage": "screen",
        "outcome": "conversion",
        "development_index_sha256": "data-abc",
        "pool_fraction": 0.15,
        "pool_seed": 77,
        "model_seed": 42,
        "n_folds": 3,
        "propensity": 0.85,
        "budget_grid": [0.01, 0.02],
        "candidate_config_hashes": {"Response": "response-v1"},
    }
    changed = {field: replacement}

    with pytest.raises(ValueError, match=field):
        assert_comparable_runs(
            manifest,
            dict(manifest),
            _comparison_data(),
            _comparison_data(**changed),
        )


def test_merge_candidate_config_hashes_unions_and_rejects_collisions():
    merged = merge_candidate_config_hashes(
        [
            {"candidate_config_hashes": {"Response": "response-v1"}},
            {"candidate_config_hashes": {"Challenger": "challenger-v1"}},
        ]
    )
    assert merged == {
        "Response": "response-v1",
        "Challenger": "challenger-v1",
    }

    with pytest.raises(ValueError, match="collision"):
        merge_candidate_config_hashes(
            [
                {"candidate_config_hashes": {"Response": "response-v1"}},
                {"candidate_config_hashes": {"Response": "response-v2"}},
            ]
        )


def test_legacy_merge_recovers_config_hashes_from_frozen_metrics(tmp_path):
    pd.DataFrame(
        [
            {"candidate": "Response", "config_hash": "response-v1"},
            {"candidate": "Response", "config_hash": "response-v1"},
            {"candidate": "failed", "config_hash": None},
        ]
    ).to_csv(tmp_path / "oof_metrics.csv", index=False)

    assert legacy_candidate_config_hashes(tmp_path) == {
        "Response": "response-v1"
    }


def test_process_isolated_oof_merge_requires_exact_shared_arrays():
    core = {
        "source_index": pd.Series([4, 8]).to_numpy(),
        "treatment": pd.Series([0, 1]).to_numpy(),
        "outcome": pd.Series([0, 1]).to_numpy(),
        "dr_signal": pd.Series([0.1, 0.2]).to_numpy(),
        "adjusted_signal": pd.Series([0.0, 0.3]).to_numpy(),
        "mu0": pd.Series([0.01, 0.02]).to_numpy(),
        "mu1": pd.Series([0.02, 0.04]).to_numpy(),
    }
    merged = merge_oof_payloads(
        [
            {**core, "Response": pd.Series([0.2, 0.4]).to_numpy()},
            {**core, "Challenger": pd.Series([0.3, 0.5]).to_numpy()},
        ]
    )
    assert set(merged) == set(core) | {"Response", "Challenger"}

    changed = {**core, "mu0": pd.Series([0.01, 0.03]).to_numpy()}
    try:
        merge_oof_payloads(
            [
                {**core, "Response": pd.Series([0.2, 0.4]).to_numpy()},
                {**changed, "Challenger": pd.Series([0.3, 0.5]).to_numpy()},
            ]
        )
    except ValueError as error:
        assert "mu0" in str(error)
    else:
        raise AssertionError("Expected different nuisance arrays to be rejected")


def test_causal_foundation_stability_label_does_not_average_away_a_loss():
    assert stability_label([1e-5, 2e-6]) == "beats_reference_on_every_fold_seed"
    assert stability_label([-1e-5, -2e-6]) == "systematic_policy_area_regression"
    assert stability_label([1e-5, -2e-6]) == "fold_seed_instability"
