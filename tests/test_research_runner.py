"""Stage gates and failure propagation for the research runner (session 9, Q17)."""

from __future__ import annotations

import hashlib
import json
import sys

import pytest

from telco_churn.research_runner import (
    COMPLETION_MARKER,
    RunReport,
    Stage,
    build_profile,
    main,
    run_stage,
    run_stages,
)

PYTHON = sys.executable or "python"


def _ok(name: str = "ok") -> Stage:
    return Stage(name, [PYTHON, "-c", "print('fine')"])


def _fails(code: int = 3) -> Stage:
    return Stage("boom", [PYTHON, "-c", f"raise SystemExit({code})"])


def test_clean_run_is_complete_with_exit_code_zero() -> None:
    report = run_stages([_ok("first"), _ok("second")])
    assert report.status == "COMPLETE"
    assert report.exit_code == 0
    assert [result.status for result in report.results] == ["SUCCESS", "SUCCESS"]


def test_a_non_zero_exit_never_reports_success() -> None:
    report = run_stages([_ok(), _fails(), _ok("never_runs")])
    assert report.status == "FAILED"
    assert report.exit_code == 1
    assert [result.status for result in report.results] == ["SUCCESS", "FAILED", "SKIPPED"]
    assert report.failures[0].returncode == 3
    assert "did not complete" in report.render()


def test_skipped_stages_stay_visible_in_the_report() -> None:
    report = run_stages([_fails(), _ok("a"), _ok("b")])
    assert len(report.skipped) == 2
    assert report.to_dict()["n_skipped"] == 2


def test_continuing_past_a_failure_still_fails_the_run() -> None:
    report = run_stages([_fails(), _ok()], stop_on_failure=False)
    assert [result.status for result in report.results] == ["FAILED", "SUCCESS"]
    assert report.status == "FAILED"


def test_a_missing_artifact_fails_a_stage_that_exited_zero(tmp_path) -> None:
    stage = Stage("silent", [PYTHON, "-c", "pass"], required_artifacts=("reports/never.json",))
    result = run_stage(stage, cwd=tmp_path)
    assert result.returncode == 0
    assert result.status == "MISSING_ARTIFACT"
    assert result.missing_artifacts == ("reports/never.json",)
    assert result.ok is False


def test_a_declared_artifact_that_appears_passes(tmp_path) -> None:
    stage = Stage(
        "writes",
        [PYTHON, "-c", "open('out.txt', 'w').write('x')"],
        required_artifacts=("out.txt",),
    )
    assert run_stage(stage, cwd=tmp_path).status == "SUCCESS"


def test_stderr_tail_is_kept_for_a_failure() -> None:
    stage = Stage("noisy", [PYTHON, "-c", "import sys; sys.stderr.write('bad thing'); sys.exit(1)"])
    result = run_stage(stage)
    assert result.status == "FAILED"
    assert "bad thing" in result.stderr_tail


def test_unfrozen_profiles_refuse_to_run_a_smaller_pipeline() -> None:
    assert [stage.name for stage in build_profile("smoke")][:2] == ["lint", "unit_tests"]
    # 'confirm' is still unfrozen: R09 needs a shortlist that does not exist yet.
    with pytest.raises(NotImplementedError, match="not\nfrozen|not frozen"):
        build_profile("confirm")
    with pytest.raises(ValueError, match="unknown profile"):
        build_profile("whatever")


def test_the_screen_profile_runs_the_declared_r02_stages() -> None:
    """R02's protocol is frozen, so this profile is real rather than a placeholder."""

    stages = build_profile("screen")
    assert [stage.name for stage in stages] == [
        "lint",
        "environment_lock",
        "contract_validation",
        "model_screening",
        "evidence_index",
    ]
    screening = next(stage for stage in stages if stage.name == "model_screening")
    assert screening.required_artifacts == ("reports/screening/screening.json",)


def test_cli_writes_a_report_and_returns_the_run_exit_code(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "telco_churn.research_runner.build_profile", lambda profile: [_ok(), _fails()]
    )
    code = main(["--root", str(tmp_path), "--report", "reports/v4/run_report.json"])
    assert code == 1
    payload = json.loads((tmp_path / "reports/v4/run_report.json").read_text(encoding="utf-8"))
    assert payload["status"] == "FAILED"
    assert payload["n_failed"] == 1


# -- A07-A09: run identity, freshness, timeouts and completion markers ------
def test_a07_an_artifact_from_an_earlier_run_does_not_certify_this_one(tmp_path) -> None:
    (tmp_path / "leftover.json").write_text('{"from": "yesterday"}', encoding="utf-8")
    stage = Stage("inherits", [PYTHON, "-c", "pass"], required_artifacts=("leftover.json",))
    result = run_stage(stage, cwd=tmp_path)
    assert result.returncode == 0
    assert result.status == "STALE_ARTIFACT"
    assert result.stale_artifacts == ("leftover.json",)
    assert result.artifacts[0].sha256  # the manifest still records which file it saw
    assert result.artifacts[0].written_by_this_stage is False


def test_a07_rewriting_identical_content_still_counts_as_produced(tmp_path) -> None:
    (tmp_path / "out.json").write_text("{}", encoding="utf-8")
    stage = Stage(
        "rewrites",
        [PYTHON, "-c", "open('out.json', 'w').write('{}')"],
        required_artifacts=("out.json",),
    )
    assert run_stage(stage, cwd=tmp_path).status == "SUCCESS"


def test_a08_a_timeout_is_recorded_rather_than_raised(tmp_path) -> None:
    stage = Stage("hangs", [PYTHON, "-c", "import time; time.sleep(30)"], timeout_s=0.5)
    result = run_stage(stage, cwd=tmp_path)
    assert result.status == "TIMED_OUT"
    assert result.returncode is None
    assert "timed out" in result.detail
    report = RunReport(profile="test", results=[result])
    assert report.status == "FAILED"
    assert report.to_dict()["stages"][0]["status"] == "TIMED_OUT"


def test_a08_a_missing_executable_is_recorded_as_a_launch_failure(tmp_path) -> None:
    stage = Stage("absent", ["telco-no-such-binary-xyz", "--go"])
    result = run_stage(stage, cwd=tmp_path)
    assert result.status == "LAUNCH_FAILED"
    assert result.returncode is None
    assert "could not launch" in result.detail


def test_a09_the_completion_marker_is_written_only_for_a_complete_run(tmp_path) -> None:
    good = run_stages([_ok()], cwd=tmp_path, profile="unit")
    directory = good.write_run_directory(tmp_path / "runs")
    assert (directory / "manifest.json").exists()
    assert (directory / COMPLETION_MARKER).exists()

    bad = run_stages([_fails()], cwd=tmp_path, profile="unit")
    bad_directory = bad.write_run_directory(tmp_path / "runs")
    assert (bad_directory / "manifest.json").exists(), "a failed run still leaves a manifest"
    assert not (bad_directory / COMPLETION_MARKER).exists()
    assert bad_directory != directory  # a retry never overwrites an earlier run


def test_a09_the_marker_pins_the_manifest_it_describes(tmp_path) -> None:
    report = run_stages([_ok()], cwd=tmp_path, profile="unit")
    directory = report.write_run_directory(tmp_path / "runs")
    marker = json.loads((directory / COMPLETION_MARKER).read_text(encoding="utf-8"))
    digest = hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()
    assert marker["manifest_sha256"] == digest
    assert marker["run_id"] == report.run_id


def test_run_identity_is_recorded_in_the_manifest(tmp_path) -> None:
    report = run_stages([_ok()], cwd=tmp_path, profile="unit")
    payload = report.to_dict()
    assert payload["run_id"] and payload["config_hash"]
    assert payload["environment"]["python"]
    assert payload["protocol_revision"]
    # The same stage list resolves to the same config hash, different ids.
    other = run_stages([_ok()], cwd=tmp_path, profile="unit")
    assert other.config_hash == report.config_hash
    assert other.run_id != report.run_id
