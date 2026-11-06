"""Staged research runner with explicit failure propagation and run identity.

The previous orchestration lived in a PowerShell script whose stages ran one
after another and printed a completion line at the end.  A non-zero exit code
from a nested ``python -m ...`` call could therefore end with "pipeline
complete" on screen.  This module makes that impossible:

* every stage records its return code;
* a stage that was expected to write an artifact and did not is a failure, even
  with return code zero;
* an artifact that already existed and was *not rewritten by this stage* is a
  failure too -- a file left over from an earlier run may not certify a new one
  (G04);
* a child that times out, cannot be launched or is interrupted still produces a
  manifest with that status rather than losing the run (G05);
* the run status is ``COMPLETE`` only when every required stage succeeded, and
  :meth:`RunReport.exit_code` is non-zero otherwise.

Run identity is content-addressed, not positional.  ``RunReport`` carries a
``run_id``, the resolved stage commands, the interpreter and platform, and a
SHA-256 fingerprint of every declared artifact.  The completion marker is
written last and only for a ``COMPLETE`` run, so an interrupted run cannot be
mistaken for a finished one by looking at the directory.

Profiles follow the V4 run-budget design.  ``smoke`` is the only populated one:
it runs the deterministic checks that do not need a fitted model.  ``screen``
and ``confirm`` refuse to run until their protocols are frozen, rather than
quietly doing something smaller and reporting success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "ArtifactFingerprint",
    "RunReport",
    "Stage",
    "StageResult",
    "build_profile",
    "fingerprint_artifact",
    "main",
    "run_stage",
    "run_stages",
]

StageStatus = Literal[
    "SUCCESS",
    "FAILED",
    "MISSING_ARTIFACT",
    "STALE_ARTIFACT",
    "TIMED_OUT",
    "LAUNCH_FAILED",
    "SKIPPED",
]
RunStatus = Literal["COMPLETE", "FAILED", "INCOMPLETE"]

_STDERR_TAIL_CHARS = 2000
_FAILURE_STATUSES: frozenset[str] = frozenset(
    {"FAILED", "MISSING_ARTIFACT", "STALE_ARTIFACT", "TIMED_OUT", "LAUNCH_FAILED"}
)
PROTOCOL_REVISION = "v4.1-draft"
COMPLETION_MARKER = "_COMPLETE.json"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Stage:
    """One executable step and the artifacts it must produce."""

    name: str
    command: Sequence[str]
    required_artifacts: tuple[str, ...] = ()
    required: bool = True
    timeout_s: float | None = None

    def validate(self) -> None:
        if not self.name:
            raise ValueError("stage name must be non-empty")
        if not self.command:
            raise ValueError(f"stage {self.name!r} has an empty command")


@dataclass(frozen=True)
class ArtifactFingerprint:
    """Identity of one declared artifact after a stage ran.

    ``written_by_this_stage`` is the difference between "the file is there" and
    "this run produced it".  Only the second one may certify a stage.
    """

    path: str
    exists: bool
    sha256: str | None = None
    size_bytes: int | None = None
    modified_at: str | None = None
    written_by_this_stage: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
            "written_by_this_stage": self.written_by_this_stage,
        }


def _signature(root: Path, relative_path: str) -> tuple[int, int, str] | None:
    """``(mtime_ns, size, sha256)`` for a file or a directory, or ``None``."""

    target = root / relative_path
    if not target.exists():
        return None
    if target.is_dir():
        digest = hashlib.sha256()
        newest_ns, size = 0, 0
        for child in sorted(target.rglob("*")):
            if child.is_file():
                stat = child.stat()
                digest.update(str(child.relative_to(target)).encode("utf-8"))
                digest.update(child.read_bytes())
                newest_ns = max(newest_ns, stat.st_mtime_ns)
                size += stat.st_size
        return newest_ns or target.stat().st_mtime_ns, size, digest.hexdigest()
    stat = target.stat()
    return stat.st_mtime_ns, stat.st_size, hashlib.sha256(target.read_bytes()).hexdigest()


def fingerprint_artifact(
    root: Path, relative_path: str, *, before: tuple[int, int, str] | None = None
) -> ArtifactFingerprint:
    """Hash one declared artifact and say whether this stage produced it.

    Freshness is decided by comparing the signature taken *before* the stage
    ran with the one taken after, not by a clock tolerance: a file is this
    stage's output when it did not exist before, or when its modification time,
    size or content changed while the stage ran.  A file that is byte-identical
    and untouched belongs to an earlier run.
    """

    after = _signature(root, relative_path)
    if after is None:
        return ArtifactFingerprint(path=relative_path, exists=False)
    mtime_ns, size, checksum = after
    return ArtifactFingerprint(
        path=relative_path,
        exists=True,
        sha256=checksum,
        size_bytes=size,
        modified_at=datetime.fromtimestamp(mtime_ns / 1e9, tz=UTC).isoformat(
            timespec="milliseconds"
        ),
        written_by_this_stage=before is None or before != after,
    )


@dataclass(frozen=True)
class StageResult:
    name: str
    command: tuple[str, ...]
    status: StageStatus
    returncode: int | None
    duration_s: float
    missing_artifacts: tuple[str, ...] = ()
    stale_artifacts: tuple[str, ...] = ()
    stderr_tail: str = ""
    artifacts: tuple[ArtifactFingerprint, ...] = ()
    started_at: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "status": self.status,
            "returncode": self.returncode,
            "duration_s": round(self.duration_s, 3),
            "missing_artifacts": list(self.missing_artifacts),
            "stale_artifacts": list(self.stale_artifacts),
            "stderr_tail": self.stderr_tail,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "started_at": self.started_at,
            "detail": self.detail,
        }


def run_stage(stage: Stage, *, cwd: Path | str = ".") -> StageResult:
    """Run one stage and classify the outcome.

    A zero return code is necessary but not sufficient.  The stage must also
    have written every artifact it declared, *during this execution*: a file
    inherited from an earlier run is reported as ``STALE_ARTIFACT`` rather than
    silently accepted as proof that the stage worked.
    """

    stage.validate()
    root = Path(cwd)
    started_at = _utc_now()
    started = time.perf_counter()
    before = {artifact: _signature(root, artifact) for artifact in stage.required_artifacts}

    def _result(status: StageStatus, **kwargs: Any) -> StageResult:
        return StageResult(
            name=stage.name,
            command=tuple(stage.command),
            status=status,
            duration_s=time.perf_counter() - started,
            started_at=started_at,
            **kwargs,
        )

    try:
        completed = subprocess.run(
            list(stage.command),
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=stage.timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        # The child was killed.  Whatever it managed to write is not evidence.
        stderr = expired.stderr or b""
        tail = stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else str(stderr)
        return _result(
            "TIMED_OUT",
            returncode=None,
            stderr_tail=tail[-_STDERR_TAIL_CHARS:],
            detail=f"timed out after {stage.timeout_s}s; partial output is not published",
        )
    except (FileNotFoundError, PermissionError, OSError) as error:
        return _result(
            "LAUNCH_FAILED",
            returncode=None,
            stderr_tail=str(error)[-_STDERR_TAIL_CHARS:],
            detail=f"could not launch {stage.command[0]!r}: {error}",
        )

    stderr_tail = (completed.stderr or "")[-_STDERR_TAIL_CHARS:]
    fingerprints = tuple(
        fingerprint_artifact(root, artifact, before=before[artifact])
        for artifact in stage.required_artifacts
    )
    if completed.returncode != 0:
        return _result(
            "FAILED",
            returncode=completed.returncode,
            stderr_tail=stderr_tail,
            artifacts=fingerprints,
            detail=f"exit code {completed.returncode}",
        )
    missing = tuple(item.path for item in fingerprints if not item.exists)
    if missing:
        return _result(
            "MISSING_ARTIFACT",
            returncode=completed.returncode,
            missing_artifacts=missing,
            stderr_tail=stderr_tail,
            artifacts=fingerprints,
            detail="declared artifacts were never written",
        )
    stale = tuple(
        item.path for item in fingerprints if item.exists and not item.written_by_this_stage
    )
    if stale:
        return _result(
            "STALE_ARTIFACT",
            returncode=completed.returncode,
            stale_artifacts=stale,
            stderr_tail=stderr_tail,
            artifacts=fingerprints,
            detail="artifact predates this run; an older file may not certify a new run",
        )
    return _result(
        "SUCCESS",
        returncode=0,
        stderr_tail="",
        artifacts=fingerprints,
    )


@dataclass
class RunReport:
    profile: str
    results: list[StageResult] = field(default_factory=list)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    protocol_revision: str = PROTOCOL_REVISION
    started_at: str = field(default_factory=_utc_now)
    finished_at: str = ""
    root: str = "."

    @property
    def failures(self) -> list[StageResult]:
        return [result for result in self.results if result.status in _FAILURE_STATUSES]

    @property
    def skipped(self) -> list[StageResult]:
        return [result for result in self.results if result.status == "SKIPPED"]

    @property
    def status(self) -> RunStatus:
        if self.failures:
            return "FAILED"
        if self.skipped or not self.results:
            return "INCOMPLETE"
        return "COMPLETE"

    @property
    def exit_code(self) -> int:
        return 0 if self.status == "COMPLETE" else 1

    @property
    def config_hash(self) -> str:
        """Content address of what was actually asked for, not of what ran."""

        payload = json.dumps(
            {
                "profile": self.profile,
                "protocol_revision": self.protocol_revision,
                "stages": [
                    {"name": result.name, "command": list(result.command)}
                    for result in self.results
                ],
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def environment(self) -> dict[str, Any]:
        return {
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "protocol_revision": self.protocol_revision,
            "profile": self.profile,
            "config_hash": self.config_hash,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "root": self.root,
            "environment": self.environment(),
            "n_stages": len(self.results),
            "n_failed": len(self.failures),
            "n_skipped": len(self.skipped),
            "stages": [result.to_dict() for result in self.results],
        }

    def render(self) -> str:
        lines = [
            f"profile={self.profile} status={self.status} "
            f"run_id={self.run_id} config={self.config_hash}"
        ]
        for result in self.results:
            detail = f" {result.detail}" if result.detail else ""
            if result.status == "MISSING_ARTIFACT":
                detail = f" missing={list(result.missing_artifacts)}"
            elif result.status == "STALE_ARTIFACT":
                detail = f" stale={list(result.stale_artifacts)}"
            lines.append(
                f"  [{result.status:<16}] {result.name}{detail} ({result.duration_s:.1f}s)"
            )
        if self.status != "COMPLETE":
            lines.append("Pipeline did not complete. No stage output may be published as evidence.")
        return "\n".join(lines)

    def write_run_directory(self, run_root: Path | str) -> Path:
        """Write an immutable run directory; mark completion last.

        The manifest is written whatever the outcome, including a timeout or a
        crash, so the run leaves a record.  The completion marker is written
        only for a ``COMPLETE`` run and only after the manifest is on disk, so
        a reader can never find a marker that describes an unfinished run.
        """

        directory = Path(run_root) / self.protocol_revision / self.run_id
        directory.mkdir(parents=True, exist_ok=True)
        manifest = directory / "manifest.json"
        temporary = manifest.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        temporary.replace(manifest)
        marker = directory / COMPLETION_MARKER
        if self.status == "COMPLETE":
            marker.write_text(
                json.dumps(
                    {
                        "run_id": self.run_id,
                        "config_hash": self.config_hash,
                        "finished_at": self.finished_at or _utc_now(),
                        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        elif marker.exists():  # pragma: no cover - defensive
            marker.unlink()
        return directory


def run_stages(
    stages: Sequence[Stage],
    *,
    cwd: Path | str = ".",
    stop_on_failure: bool = True,
    profile: str = "ad_hoc",
) -> RunReport:
    """Run stages in order, recording every outcome.

    With ``stop_on_failure`` the remaining stages are recorded as ``SKIPPED``
    rather than dropped, so the report still shows what was never attempted.
    A ``KeyboardInterrupt`` marks the rest of the run as skipped and re-raises
    with the report already populated by the caller.
    """

    report = RunReport(profile=profile, root=str(cwd))
    stopped = False
    for stage in stages:
        if stopped:
            report.results.append(
                StageResult(
                    name=stage.name,
                    command=tuple(stage.command),
                    status="SKIPPED",
                    returncode=None,
                    duration_s=0.0,
                )
            )
            continue
        result = run_stage(stage, cwd=cwd)
        report.results.append(result)
        if not result.ok and stage.required and stop_on_failure:
            stopped = True
    report.finished_at = _utc_now()
    return report


# -- profiles ---------------------------------------------------------------
_PY = sys.executable or "python"


def build_profile(profile: str) -> list[Stage]:
    """Stage list for a named run profile.

    ``screen`` and ``confirm`` are declared in the V4 design but their protocols
    are not frozen yet, so asking for them raises instead of silently running a
    smaller pipeline.
    """

    if profile == "smoke":
        return [
            Stage("lint", [_PY, "-m", "ruff", "check", "."]),
            Stage("unit_tests", [_PY, "-m", "pytest", "-q"]),
            Stage(
                "contract_validation",
                [_PY, "-m", "telco_churn.problem_contract_cli"],
                required_artifacts=("reports/v4/contracts.json",),
            ),
            Stage(
                "challenge_suite",
                [_PY, "-m", "telco_churn.challenge_suite"],
                required_artifacts=(
                    "reports/v4/challenge_suite.json",
                    "reports/v4/CHALLENGE_SUITE_REPORT.md",
                ),
            ),
            Stage(
                "evidence_index",
                [_PY, "-m", "telco_churn.evidence"],
                required_artifacts=("reports/v4/evidence_index.json",),
            ),
        ]
    if profile == "screen":
        # R02's protocol is frozen in runbook §3-§4 and implemented in
        # telco_churn.screening, so this profile is real.  It still fails while
        # the R01 gate is shut: the screening stage refuses and the run stops.
        return [
            Stage("lint", [_PY, "-m", "ruff", "check", "."]),
            Stage(
                "environment_lock",
                [_PY, "-m", "telco_churn.environment", "--lock", "locks/research.lock.txt"],
                required_artifacts=("reports/v4/environment.json",),
            ),
            Stage(
                "contract_validation",
                [_PY, "-m", "telco_churn.problem_contract_cli"],
                required_artifacts=("reports/v4/contracts.json",),
            ),
            Stage(
                "model_screening",
                [_PY, "-m", "telco_churn.screening"],
                required_artifacts=("reports/screening/screening.json",),
            ),
            Stage(
                "evidence_index",
                [_PY, "-m", "telco_churn.evidence"],
                required_artifacts=("reports/v4/evidence_index.json",),
            ),
        ]
    if profile == "confirm":
        raise NotImplementedError(
            "profile 'confirm' is declared in the V4 design but its protocol is not "
            "frozen: R09 needs a shortlist from R02 and a frozen final recipe first. "
            "Running a reduced pipeline under this name would misreport scope"
        )
    raise ValueError(f"unknown profile {profile!r}; expected smoke, screen or confirm")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a staged research profile.")
    parser.add_argument("--profile", default="smoke", choices=("smoke", "screen", "confirm"))
    parser.add_argument("--root", default=".", help="repository root to run stages in")
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="attempt every stage instead of stopping at the first failure",
    )
    parser.add_argument(
        "--report",
        default="reports/v4/run_report.json",
        help="where to write the machine-readable run report",
    )
    parser.add_argument(
        "--run-root",
        default="runs/research_v4_1",
        help="root of the immutable per-run directories",
    )
    parser.add_argument(
        "--no-run-directory",
        action="store_true",
        help="skip the immutable run directory (the flat report is still written)",
    )
    args = parser.parse_args(argv)

    stages = build_profile(args.profile)
    report = run_stages(
        stages,
        cwd=args.root,
        stop_on_failure=not args.continue_on_failure,
        profile=args.profile,
    )

    destination = Path(args.root) / args.report
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    print(report.render())
    print(f"Run report: {destination}")
    if not args.no_run_directory:
        directory = report.write_run_directory(Path(args.root) / args.run_root)
        marker = "with" if (directory / COMPLETION_MARKER).exists() else "without"
        print(f"Run directory: {directory} ({marker} completion marker)")

    # The evidence stage runs inside the pipeline, so the index it writes there
    # describes the *previous* run report.  Refresh it once the current report
    # is on disk, or the console would always be one run behind.
    from .evidence import build_index, render_markdown

    index = build_index(args.root)
    index_path = Path(args.root) / "reports/v4/evidence_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index.to_dict(), indent=2), encoding="utf-8")
    (Path(args.root) / "reports/v4/EVIDENCE_INDEX.md").write_text(
        render_markdown(index), encoding="utf-8"
    )
    print(f"Evidence index: {index_path} (release tier {index.release_tier})")
    return report.exit_code


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
