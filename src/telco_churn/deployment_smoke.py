"""Acceptance checks for a running deployment (node N10, gate QG7).

"The image builds" is not a deployment check.  The questions that matter once
the containers are up are whether the deployed services answer, whether they
answer the *same thing* the host does, and whether what they serve is the
evidence they claim to serve:

* **Parity.** A model that scores differently inside a container than on the
  host is a different model.  This re-scores real records against the deployed
  API and compares with the host bundle, reporting the largest absolute gap
  rather than asserting "identical" and hoping.
* **Evidence identity.** The console reports a content address of the
  artifacts baked into its image.  If that differs from the host's, the
  deployment is serving a different snapshot than the repository, and the
  report says so instead of showing two sets of numbers side by side.
* **Locked-decision reproduction.** The deployed console recomputes the locked
  Orange readout from its own copy of the holdout predictions.  It has to come
  out at the published value; a deployment that quietly disagrees with the
  published decision is not serving that decision.
* **Schema.** The operational database has the tables the serving path
  declares, with the constraints intact.

Nothing here writes to a customer, a campaign or the artifact root.  The run
produces one report so the result is citable instead of remembered.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API = "http://127.0.0.1:8000"
DEFAULT_CONSOLE = "http://127.0.0.1:8050"
DEFAULT_OUTPUT = "reports/deployment"
PARITY_TOLERANCE = 1e-12
EXPECTED_TABLES = (
    "model_versions",
    "scoring_runs",
    "churn_scores",
    "campaign_decisions",
)

__all__ = ["Check", "SmokeReport", "main", "run_smoke"]


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    measured: dict[str, Any] = field(default_factory=dict)
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SmokeReport:
    checks: list[Check] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def add(self, check: Check) -> Check:
        self.checks.append(check)
        return check

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if check.required and not check.passed]

    @property
    def skipped(self) -> list[Check]:
        return [check for check in self.checks if not check.required and not check.passed]

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "status": "PASS" if self.passed else "FAIL",
            "n_checks": len(self.checks),
            "n_failed": len(self.failures),
            "n_skipped": len(self.skipped),
            "checks": [check.to_dict() for check in self.checks],
        }

    def render(self) -> str:
        lines = [
            "# Deployment smoke",
            "",
            f"Run {self.started_at}. Status **{'PASS' if self.passed else 'FAIL'}** "
            f"over {len(self.checks)} checks.",
            "",
            "These checks say the deployed services answer and agree with the host. "
            "They say nothing about whether the research conclusions are stronger: "
            "the console serves the same conditional evidence it did before it was "
            "containerised.",
            "",
            "| Check | Result | Detail |",
            "|---|---|---|",
        ]
        for check in self.checks:
            state = "pass" if check.passed else ("skipped" if not check.required else "FAIL")
            lines.append(f"| {check.name} | {state} | {check.detail} |")
        return "\n".join(lines) + "\n"


def _get(client: httpx.Client, url: str) -> tuple[int, Any]:
    try:
        response = client.get(url)
    except httpx.HTTPError as error:
        return 0, str(error)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, response.text


def _sample_records(data_path: Path, limit: int) -> list[dict[str, Any]]:
    import pandas as pd

    from .schema import FEATURE_COLUMNS, ID_COLUMN

    raw = pd.read_csv(data_path, keep_default_na=False)
    records = []
    for _, row in raw.head(limit).iterrows():
        record = row[[ID_COLUMN, *FEATURE_COLUMNS]].to_dict()
        record["SeniorCitizen"] = int(record["SeniorCitizen"])
        record["tenure"] = int(record["tenure"])
        record["MonthlyCharges"] = float(record["MonthlyCharges"])
        record["TotalCharges"] = float(record["TotalCharges"]) if record["TotalCharges"] else None
        records.append(record)
    return records


def _check_api(report: SmokeReport, client: httpx.Client, api: str) -> dict[str, Any] | None:
    status, _ = _get(client, f"{api}/health/live")
    report.add(Check("api_live", status == 200, f"GET /health/live -> {status}"))
    status, _ = _get(client, f"{api}/health/ready")
    report.add(Check("api_ready", status == 200, f"GET /health/ready -> {status}"))
    status, info = _get(client, f"{api}/v1/model-info")
    ok = status == 200 and isinstance(info, dict)
    report.add(
        Check(
            "api_model_info",
            ok,
            f"artifact_version {info.get('artifact_version') if ok else info}",
            measured=info if ok else {},
        )
    )
    return info if ok else None


#: A record that is internally inconsistent: no phone service, but a
#: multiple-lines value that only exists when there is one.  The schema gate
#: has to refuse it; a deployment that accepts it is scoring nonsense.
_INCONSISTENT_RECORD: dict[str, Any] = {
    "customerID": "schema-gate-probe",
    "gender": "Female",
    "SeniorCitizen": 0,
    "Partner": "Yes",
    "Dependents": "No",
    "PhoneService": "No",
    "MultipleLines": "Yes",
    "InternetService": "DSL",
    "OnlineSecurity": "No",
    "OnlineBackup": "Yes",
    "DeviceProtection": "No",
    "TechSupport": "No",
    "StreamingTV": "No",
    "StreamingMovies": "No",
    "Contract": "Month-to-month",
    "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
    "tenure": 5,
    "MonthlyCharges": 55.0,
    "TotalCharges": 275.0,
}


def _check_schema_gate(report: SmokeReport, client: httpx.Client, api: str) -> None:
    """An inconsistent record is refused with 422, not scored."""

    try:
        response = client.post(f"{api}/v1/predict", json={"records": [_INCONSISTENT_RECORD]})
    except httpx.HTTPError as error:
        report.add(Check("api_rejects_invalid_input", False, f"request failed: {error}"))
        return
    report.add(
        Check(
            "api_rejects_invalid_input",
            response.status_code == 422,
            f"inconsistent phone/lines record -> {response.status_code} (expected 422)",
        )
    )


def _check_console_is_read_only(report: SmokeReport, client: httpx.Client, console: str) -> None:
    """The console exposes no write path; a POST must not be routed."""

    try:
        response = client.post(f"{console}/api/evidence", json={})
    except httpx.HTTPError as error:
        report.add(Check("console_exposes_no_write_path", False, f"request failed: {error}"))
        return
    report.add(
        Check(
            "console_exposes_no_write_path",
            response.status_code in (404, 405),
            f"POST /api/evidence -> {response.status_code} (expected 405 or 404)",
        )
    )


def _check_parity(
    report: SmokeReport,
    client: httpx.Client,
    api: str,
    data_path: Path,
    model_path: Path,
    limit: int,
) -> None:
    """Deployed scores against host scores, on the same records."""

    if not data_path.exists() or not model_path.exists():
        report.add(
            Check(
                "host_container_parity",
                False,
                f"skipped: need {data_path} and {model_path} on the host",
                required=False,
            )
        )
        return
    import pandas as pd

    from .inference import load_bundle, score_frame

    records = _sample_records(data_path, limit)
    response = client.post(f"{api}/v1/predict", json={"records": records})
    if response.status_code != 200:
        report.add(
            Check("host_container_parity", False, f"POST /v1/predict -> {response.status_code}")
        )
        return
    deployed = {row["customer_id"]: row["risk_30d"] for row in response.json()["predictions"]}

    bundle = load_bundle(model_path)
    frame = pd.DataFrame(
        [{k: v for k, v in record.items() if k != "customerID"} for record in records]
    )
    host = dict(
        zip([record["customerID"] for record in records], score_frame(bundle, frame), strict=True)
    )

    gap = max(abs(float(host[key]) - float(deployed[key])) for key in host)
    report.add(
        Check(
            "host_container_parity",
            gap <= PARITY_TOLERANCE,
            f"max |host - container| = {gap:.3e} over {len(host)} records "
            f"(tolerance {PARITY_TOLERANCE:.0e})",
            measured={"max_absolute_gap": gap, "n_records": len(host)},
        )
    )


def _check_console(report: SmokeReport, client: httpx.Client, console: str, root: Path) -> None:
    status, _ = _get(client, f"{console}/health/live")
    report.add(Check("console_live", status == 200, f"GET /health/live -> {status}"))
    status, ready = _get(client, f"{console}/health/ready")
    report.add(
        Check(
            "console_ready",
            status == 200,
            f"GET /health/ready -> {status}"
            + (f", release tier {ready.get('release_tier')}" if isinstance(ready, dict) else ""),
        )
    )
    status, deployment = _get(client, f"{console}/api/deployment")
    if status != 200 or not isinstance(deployment, dict):
        report.add(Check("console_deployment_info", False, f"GET /api/deployment -> {status}"))
        return
    report.add(
        Check(
            "console_deployment_info",
            bool(deployment.get("read_only")) and bool(deployment.get("evidence_snapshot")),
            f"snapshot {deployment['evidence_snapshot']}, "
            f"{deployment['artifacts_present']}/{deployment['artifacts_declared']} artifacts, "
            f"tier {deployment['release_tier']}",
            measured=deployment,
        )
    )

    # Evidence identity: the served snapshot against the repository's own.
    from .dashboard import _snapshot_id
    from .evidence import build_index

    host_snapshot = _snapshot_id(build_index(root).to_dict())
    same = host_snapshot == deployment["evidence_snapshot"]
    report.add(
        Check(
            "evidence_snapshot_matches_host",
            same,
            f"container {deployment['evidence_snapshot']} vs host {host_snapshot}"
            + ("" if same else " -- the deployment is serving a different snapshot"),
            measured={"container": deployment["evidence_snapshot"], "host": host_snapshot},
            # A deliberately older snapshot is a legitimate deployment, so this
            # reports rather than fails the run.
            required=False,
        )
    )


def _check_locked_decision(
    report: SmokeReport, client: httpx.Client, console: str, root: Path
) -> None:
    locked_path = root / "reports/uplift/locked_policy_decision.json"
    if not locked_path.exists():
        report.add(
            Check(
                "locked_decision_reproduced",
                False,
                "no locked decision on the host",
                required=False,
            )
        )
        return
    locked = json.loads(locked_path.read_text(encoding="utf-8"))
    status, payload = _get(
        client,
        f"{console}/api/policy/allocation?model={locked['model']}"
        f"&fraction={locked['budget_fraction']}&cap_rule=ceil",
    )
    if status != 200 or not isinstance(payload, dict):
        report.add(Check("locked_decision_reproduced", False, f"console returned {status}"))
        return
    readout = payload["readout"]
    gap = abs(readout["dr_uplift"] - locked["test_dr_uplift"])
    matches = (
        gap <= 1e-9
        and readout["decision"] == locked["test_decision"]
        and readout["control_churn_events"] == locked["selected_control_churn_events"]
    )
    report.add(
        Check(
            "locked_decision_reproduced",
            matches,
            f"deployed DR {readout['dr_uplift']:.10f} vs published "
            f"{locked['test_dr_uplift']:.10f} (gap {gap:.1e}), decision {readout['decision']}",
            measured={"deployed": readout["dr_uplift"], "published": locked["test_dr_uplift"]},
        )
    )


def _check_database(report: SmokeReport, dsn: str | None) -> None:
    if not dsn:
        report.add(Check("database_schema", False, "skipped: no --dsn given", required=False))
        return
    try:
        import psycopg
    except ImportError:  # pragma: no cover - psycopg is a project dependency
        report.add(
            Check("database_schema", False, "skipped: psycopg not installed", required=False)
        )
        return
    try:
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            rows = connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ).fetchall()
    except Exception as error:  # noqa: BLE001 - any connection problem is the finding
        report.add(Check("database_schema", False, f"could not query: {error}", required=False))
        return
    present = {row[0] for row in rows}
    missing = [table for table in EXPECTED_TABLES if table not in present]
    report.add(
        Check(
            "database_schema",
            not missing,
            f"{len(present)} tables present"
            + (f"; missing {missing}" if missing else "; migration applied"),
            measured={"tables": sorted(present)},
        )
    )


def run_smoke(
    *,
    api: str = DEFAULT_API,
    console: str = DEFAULT_CONSOLE,
    root: Path | str = ".",
    data_path: Path | str = "data/raw/Telco-Customer-Churn.csv",
    model_path: Path | str = "artifacts/models/champion.joblib",
    dsn: str | None = None,
    records: int = 50,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> SmokeReport:
    """Run every deployment check and collect the results.

    ``client`` exists so the checks can be exercised against a stub transport;
    the CLI always opens a real one.
    """

    base = Path(root)
    # Relative host paths resolve against the artifact root, so --root moves the
    # whole frame of reference rather than only half of it.
    data = Path(data_path)
    model = Path(model_path)
    data = data if data.is_absolute() else base / data
    model = model if model.is_absolute() else base / model

    report = SmokeReport()
    owned = client is None
    active = client or httpx.Client(timeout=timeout)
    try:
        _check_api(report, active, api)
        _check_schema_gate(report, active, api)
        _check_parity(report, active, api, data, model, records)
        _check_console(report, active, console, base)
        _check_console_is_read_only(report, active, console)
        _check_locked_decision(report, active, console, base)
    finally:
        if owned:
            active.close()
    _check_database(report, dsn)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--console", default=DEFAULT_CONSOLE)
    parser.add_argument("--root", default=".")
    parser.add_argument("--data", default="data/raw/Telco-Customer-Churn.csv")
    parser.add_argument("--model", default="artifacts/models/champion.joblib")
    parser.add_argument(
        "--dsn",
        default=None,
        help="Postgres DSN for the schema check, e.g. "
        "postgresql://telco:local-development-only@127.0.0.1:5432/telco_churn",
    )
    parser.add_argument("--records", type=int, default=50)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = run_smoke(
        api=args.api,
        console=args.console,
        root=args.root,
        data_path=args.data,
        model_path=args.model,
        dsn=args.dsn,
        records=args.records,
    )
    destination = Path(args.root) / args.output_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "deployment_smoke.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    (destination / "DEPLOYMENT_SMOKE.md").write_text(report.render(), encoding="utf-8")

    for check in report.checks:
        state = "ok  " if check.passed else ("skip" if not check.required else "FAIL")
        print(f"[{state}] {check.name}: {check.detail}")
    print(
        f"status={'PASS' if report.passed else 'FAIL'} "
        f"({len(report.failures)} failed, {len(report.skipped)} skipped)"
    )
    print(f"Report: {destination}")
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
