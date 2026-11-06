"""Environment capture and verification (gate QG0).

QG0 asks for a dependency lock *and* the ability to fail when a run cannot say
what it used.  A lock file alone does not do that: it is a record nobody
checks.  This module makes the record checkable.

``capture`` writes the exact installed set for an environment.  ``verify``
compares a live environment against a lock and classifies every difference:

* **missing** -- the lock names a package that is not installed.  A run in this
  state is not the run the lock describes.
* **changed** -- installed at a different version.  This is the case that
  silently changes results, so it is a failure by default.
* **extra** -- installed but not in the lock.  Reported, not failed: a research
  environment legitimately carries tools the lock was not taken over.

The comparison covers only what the lock declares, because the question is not
"is this machine tidy" but "could this run have produced that artifact".
"""

from __future__ import annotations

import argparse
import json
import platform
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

__all__ = [
    "EnvironmentReport",
    "capture_environment",
    "main",
    "read_lock",
    "verify_lock",
]

DEFAULT_LOCKS = {
    "research": "locks/research.lock.txt",
    "api": "locks/api.lock.txt",
    "console": "locks/console.lock.txt",
}


def read_lock(path: Path | str) -> dict[str, str]:
    """Parse ``name==version`` lines, ignoring comments and blank lines."""

    entries: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "==" not in stripped:
            # Editable installs and VCS pins are recorded but not comparable
            # by version, so they are kept under their own key.
            entries[stripped] = ""
            continue
        name, version = stripped.split("==", 1)
        entries[name.strip().lower().replace("_", "-")] = version.strip()
    return entries


def capture_environment() -> dict[str, str]:
    """Every distribution installed in the interpreter running this code."""

    installed: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata["Name"]
        if not name:
            continue
        # importlib.metadata searches distributions in sys.path order.  A venv
        # created with --system-site-packages can see both its local pin and a
        # different global version; the first one is the active distribution.
        installed.setdefault(name.lower().replace("_", "-"), distribution.version)
    return installed


@dataclass
class EnvironmentReport:
    lock_path: str
    python_version: str
    platform_name: str
    n_locked: int
    missing: list[str] = field(default_factory=list)
    changed: list[dict[str, str]] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)

    @property
    def satisfied(self) -> bool:
        return not self.missing and not self.changed

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "satisfied": self.satisfied}

    def render(self) -> str:
        lines = [
            f"lock: {self.lock_path}",
            f"python: {self.python_version} on {self.platform_name}",
            f"locked packages: {self.n_locked}",
            f"status: {'SATISFIED' if self.satisfied else 'VIOLATED'}",
        ]
        for name in self.missing:
            lines.append(f"  missing  {name}")
        for entry in self.changed:
            lines.append(
                f"  changed  {entry['name']}: lock {entry['locked']} != {entry['installed']}"
            )
        if self.extra:
            lines.append(f"  extra    {len(self.extra)} package(s) not in the lock (not a failure)")
        return "\n".join(lines)


def verify_lock(path: Path | str, installed: dict[str, str] | None = None) -> EnvironmentReport:
    """Check a live environment against a lock file."""

    locked = read_lock(path)
    present = capture_environment() if installed is None else dict(installed)
    missing = sorted(name for name in locked if name not in present)
    changed = [
        {"name": name, "locked": version, "installed": present[name]}
        for name, version in sorted(locked.items())
        if name in present and version and present[name] != version
    ]
    extra = sorted(name for name in present if name not in locked)
    return EnvironmentReport(
        lock_path=str(path),
        python_version=platform.python_version(),
        platform_name=platform.platform(),
        n_locked=len(locked),
        missing=missing,
        changed=changed,
        extra=extra,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock",
        default=DEFAULT_LOCKS["research"],
        help="lock file to verify the current interpreter against",
    )
    parser.add_argument(
        "--capture",
        default=None,
        help="instead of verifying, write the current environment to this path",
    )
    parser.add_argument("--output", default="reports/v4/environment.json")
    parser.add_argument(
        "--allow-changed",
        action="store_true",
        help="report version drift without failing (use only for an exploratory run)",
    )
    args = parser.parse_args(argv)

    if args.capture:
        destination = Path(args.capture)
        destination.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Captured with python -m telco_churn.environment --capture",
            f"# Python {platform.python_version()} on {platform.platform()}",
        ]
        lines.extend(
            f"{name}=={version}" for name, version in sorted(capture_environment().items())
        )
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Captured {len(lines) - 2} packages to {destination}")
        return 0

    if not Path(args.lock).exists():
        print(f"lock file not found: {args.lock}")
        return 1
    report = verify_lock(args.lock)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    print(report.render())
    print(f"Report: {destination}")
    if report.satisfied:
        return 0
    return 0 if args.allow_changed and not report.missing else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
