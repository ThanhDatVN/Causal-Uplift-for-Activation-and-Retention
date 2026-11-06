"""Dependency lock capture and verification (gate QG0).

A lock file that nobody checks is a record, not a gate.  These tests are about
the checking: the comparison has to notice a missing package and a changed
version, and it has to tolerate the extra tooling a research machine carries.
"""

from __future__ import annotations

import json

import pytest

from telco_churn.environment import (
    DEFAULT_LOCKS,
    capture_environment,
    main,
    read_lock,
    verify_lock,
)

LOCK_BODY = """# a comment
# Python 3.11.9

numpy==1.26.4
pandas==2.2.2
Scikit_Learn==1.7.0
"""


@pytest.fixture
def lock_file(tmp_path):
    path = tmp_path / "sample.lock.txt"
    path.write_text(LOCK_BODY, encoding="utf-8")
    return path


def test_the_parser_normalises_names_and_skips_comments(lock_file) -> None:
    entries = read_lock(lock_file)
    assert entries == {
        "numpy": "1.26.4",
        "pandas": "2.2.2",
        "scikit-learn": "1.7.0",  # case and underscore normalised
    }


def test_a_matching_environment_satisfies_the_lock(lock_file) -> None:
    report = verify_lock(
        lock_file,
        installed={"numpy": "1.26.4", "pandas": "2.2.2", "scikit-learn": "1.7.0"},
    )
    assert report.satisfied is True
    assert "SATISFIED" in report.render()


def test_a_changed_version_violates_the_lock(lock_file) -> None:
    report = verify_lock(
        lock_file,
        installed={"numpy": "2.0.0", "pandas": "2.2.2", "scikit-learn": "1.7.0"},
    )
    assert report.satisfied is False
    assert report.changed == [{"name": "numpy", "locked": "1.26.4", "installed": "2.0.0"}]
    assert "lock 1.26.4 != 2.0.0" in report.render()


def test_a_missing_package_violates_the_lock(lock_file) -> None:
    report = verify_lock(lock_file, installed={"numpy": "1.26.4", "pandas": "2.2.2"})
    assert report.satisfied is False
    assert report.missing == ["scikit-learn"]


def test_extra_packages_are_reported_but_do_not_violate(lock_file) -> None:
    report = verify_lock(
        lock_file,
        installed={
            "numpy": "1.26.4",
            "pandas": "2.2.2",
            "scikit-learn": "1.7.0",
            "jupyterlab": "4.0.0",
        },
    )
    assert report.satisfied is True
    assert report.extra == ["jupyterlab"]


def test_capture_sees_this_interpreter() -> None:
    installed = capture_environment()
    assert "numpy" in installed and "pandas" in installed
    assert installed["numpy"]


def test_capture_prefers_the_active_venv_distribution(monkeypatch) -> None:
    """A global duplicate must not overwrite the earlier venv distribution."""

    from telco_churn import environment

    class Distribution:
        def __init__(self, version):
            self.metadata = {"Name": "setuptools"}
            self.version = version

    monkeypatch.setattr(
        environment.metadata,
        "distributions",
        lambda: [Distribution("65.5.0"), Distribution("78.1.0")],
    )
    assert capture_environment() == {"setuptools": "65.5.0"}


def test_the_shipped_locks_exist_and_parse() -> None:
    from pathlib import Path

    for name, relative in DEFAULT_LOCKS.items():
        path = Path(relative)
        assert path.exists(), f"{name} lock is missing"
        entries = read_lock(path)
        assert len(entries) > 10, f"{name} lock looks truncated"
        assert all(version for version in entries.values()), (
            f"{name} lock has an entry without a pinned version"
        )


@pytest.mark.locked_environment
def test_the_research_lock_matches_this_environment() -> None:
    """The reports on disk must be attributable to the interpreter running here."""

    report = verify_lock(DEFAULT_LOCKS["research"])
    assert report.missing == [], f"the research lock names packages that are gone: {report.missing}"
    assert report.changed == [], f"version drift since the lock: {report.changed}"


def test_the_container_locks_pin_a_smaller_set_than_research() -> None:
    """The console image must not be carrying the training stack."""

    console = read_lock(DEFAULT_LOCKS["console"])
    research = read_lock(DEFAULT_LOCKS["research"])
    assert len(console) < len(research)
    for heavy in ("catboost", "scikit-learn", "scipy", "mlflow", "matplotlib"):
        assert heavy not in console, f"{heavy} should not be in the console image"


def test_the_cli_writes_a_report_and_can_capture(tmp_path) -> None:
    captured = tmp_path / "out.lock.txt"
    assert main(["--capture", str(captured)]) == 0
    assert "numpy==" in captured.read_text(encoding="utf-8")

    code = main(["--lock", str(captured), "--output", str(tmp_path / "env.json")])
    assert code == 0
    payload = json.loads((tmp_path / "env.json").read_text(encoding="utf-8"))
    assert payload["satisfied"] is True


def test_a_missing_lock_file_fails_loudly(tmp_path) -> None:
    assert main(["--lock", str(tmp_path / "nope.txt")]) == 1
