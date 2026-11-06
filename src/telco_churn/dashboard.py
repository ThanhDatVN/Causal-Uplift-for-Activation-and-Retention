"""Retention decision console: a local read-only view over the evidence on disk.

The repository already answers "what did we measure"; it answers it across a
dozen JSON files, three report directories and two markdown ledgers.  This
serves the same artifacts as one page, with the evidence state attached to
every number, plus one live calculation -- the capacity curve -- that the
static reports cannot show.

Three rules the console follows, because a dashboard is exactly where they get
broken:

* **Nothing is computed from data the reports did not already open.**  The
  capacity curve re-reads the Orange holdout predictions that
  ``orange_benchmark`` wrote; it does not refit anything and it cannot see the
  raw features.
* **Moving the capacity slider is not a new study.**  The locked decision was
  declared at one model and one budget before the holdout was opened.  Every
  other point on the curve is exploratory and the API marks it as such, in the
  payload, not only in the page text.
* **A missing artifact renders as missing.**  There is no fallback that quietly
  shows an older number in place of one that was never produced.

Run it with ``python -m telco_churn.dashboard`` and open http://127.0.0.1:8050.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .allocation import allocate_batch, capacity_limit
from .assistant import answer_question, evaluate_assistant
from .evidence import build_index
from .resampling import bootstrap_selected_effect

__all__ = ["create_dashboard", "main"]

WEBUI_DIR = Path(__file__).parent / "webui"
HOLDOUT = "reports/uplift/holdout_predictions.csv"
LOCKED = "reports/uplift/locked_policy_decision.json"
TEMPORAL_TRUTH = "reports/temporal_lab/test_policy_truth.csv"

#: Budget fractions on the capacity curve.  Fixed, so the curve cannot be
#: quietly re-gridded around a favourable point.
CURVE_FRACTIONS: tuple[float, ...] = (
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.50,
    0.60,
    0.80,
    1.00,
)
BOOTSTRAP_REPEATS = 2_000
MIN_ARM_EVENTS = 20

#: Artifacts the console cannot render anything useful without.  Readiness is
#: about *this* deployment being able to answer, not about the research being
#: finished, so it checks for files, not for gate outcomes.
REQUIRED_FOR_READY: tuple[str, ...] = (
    "reports/v4/challenge_suite.json",
    "reports/v4/contracts.json",
)

_UNAUTHENTICATED_WARNING = (
    "This console has no authentication and serves evidence artifacts verbatim. "
    "Bind it to localhost or a trusted network; do not expose it to the public "
    "internet."
)


def _package_version() -> str:
    try:
        return metadata.version("telcochurn-decision-system")
    except metadata.PackageNotFoundError:  # pragma: no cover - source checkout
        return "0.0.0+unknown"


#: Excluded from the snapshot id: it describes a *deployment* of the evidence,
#: not the evidence.  Including it would make the address self-referential --
#: every smoke run would change the host snapshot and no already-built image
#: could ever match it again.
_SNAPSHOT_EXCLUDED: frozenset[str] = frozenset({"deployment_smoke"})


def _snapshot_id(index_payload: dict[str, Any]) -> str:
    """Content address of the evidence this deployment is serving.

    A deployment is identified by the artifacts inside it, not by when it was
    started: two containers built from the same reports answer identically and
    get the same id, and any artifact change produces a different one.
    """

    digest = hashlib.sha256()
    for artifact in sorted(index_payload["artifacts"], key=lambda item: item["key"]):
        if artifact["key"] in _SNAPSHOT_EXCLUDED:
            continue
        digest.update(artifact["key"].encode("utf-8"))
        digest.update((artifact["sha256"] or "absent").encode("utf-8"))
    return digest.hexdigest()[:16]


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(item) for item in obj]
    return obj


class ConsoleAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1_000)
    lang: Literal["en", "vi"] | None = None


def _read_json(root: Path, relative: str) -> dict[str, Any] | None:
    path = root / relative
    if not path.exists():
        return None
    try:
        return _json_safe(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:  # pragma: no cover - a corrupt artifact is not a fallback
        return None


@lru_cache(maxsize=4)
def _holdout(root: str) -> pd.DataFrame | None:
    path = Path(root) / HOLDOUT
    if not path.exists():
        return None
    return pd.read_csv(path)


def _score_columns(frame: pd.DataFrame) -> list[str]:
    return [column[len("score_") :] for column in frame.columns if column.startswith("score_")]


def _allocate(
    frame: pd.DataFrame, model: str, fraction: float, *, cap_rule: str, require_positive: bool
) -> np.ndarray:
    scores = frame[f"score_{model}"].to_numpy(dtype=float)
    ids = frame["row_id"].astype(str).to_numpy()
    if cap_rule == "ceil":
        limit = min(len(scores), max(1, int(np.ceil(len(scores) * fraction))))
    else:
        limit = capacity_limit(len(scores), fraction)
    allocation = allocate_batch(
        ids, scores, fraction=fraction, require_positive=require_positive, capacity=limit
    )
    return allocation.frame["selected"].to_numpy(dtype=bool)


def _evaluate(frame: pd.DataFrame, selected: np.ndarray, *, repeats: int) -> dict[str, Any]:
    """Doubly robust readout on the selected sub-cohort, with its event counts."""

    n_selected = int(selected.sum())
    payload: dict[str, Any] = {
        "n_selected": n_selected,
        "share_selected": n_selected / len(frame) if len(frame) else 0.0,
    }
    if n_selected < 2:
        payload.update(
            {
                "dr_uplift": None,
                "ci95_low": None,
                "ci95_high": None,
                "control_churn_events": 0,
                "treated_churn_events": 0,
                "gates": {},
                "decision": "no_launch",
                "note": "fewer than two selected units; no interval is defined",
            }
        )
        return payload
    interval = bootstrap_selected_effect(
        selected, frame["dr_effect"].to_numpy(dtype=float), repeats=repeats, seed=20260914 + 20_000
    )
    treatment = frame["treatment"].to_numpy(dtype=int)
    outcome = frame["outcome"].to_numpy(dtype=float)
    control_events = int(outcome[selected & (treatment == 0)].sum())
    treated_events = int(outcome[selected & (treatment == 1)].sum())
    gates = {
        "positive_dr_ci_lower": bool(interval["ci95_low"] > 0),
        "at_least_20_control_churn_events": control_events >= MIN_ARM_EVENTS,
        "at_least_20_treated_churn_events": treated_events >= MIN_ARM_EVENTS,
    }
    payload.update(
        {
            "dr_uplift": interval["estimate"],
            "ci95_low": interval["ci95_low"],
            "ci95_high": interval["ci95_high"],
            "control_churn_events": control_events,
            "treated_churn_events": treated_events,
            "gates": gates,
            "decision": "launch" if all(gates.values()) else "no_launch",
        }
    )
    return payload


def create_dashboard(root: Path | str = ".") -> FastAPI:
    """Build the console app over the artifacts under ``root``."""

    base = Path(root).resolve()
    application = FastAPI(
        title="Retention decision console",
        version="1.0.0",
        description=(
            "Read-only view of the evidence produced by this repository. "
            "Business value is simulated or conditional throughout; nothing here "
            "authorises a campaign."
        ),
    )
    application.state.root = base

    started_at = datetime.now(UTC).isoformat(timespec="seconds")

    @application.get("/health/live")
    def live() -> dict[str, str]:
        """Process is up.  Says nothing about the artifacts."""

        return {"status": "alive"}

    @application.get("/health/ready")
    def ready() -> dict[str, Any]:
        """Ready means this deployment can answer, not that the research is done."""

        missing = [name for name in REQUIRED_FOR_READY if not (base / name).exists()]
        if missing:
            raise HTTPException(
                status_code=503,
                detail=f"missing evidence artifacts: {missing}; the image was built "
                "without them or the mount is wrong",
            )
        try:
            index = build_index(base)
        except Exception as error:  # readiness must report, not crash the probe
            raise HTTPException(
                status_code=503, detail=f"evidence index could not be built: {error}"
            ) from error
        return {"status": "ready", "release_tier": index.release_tier}

    @application.get("/api/deployment")
    def deployment() -> dict[str, Any]:
        """What this instance is serving, and what it is not allowed to do."""

        index = build_index(base).to_dict()
        present = [item for item in index["artifacts"] if item["exists"]]
        return {
            "package_version": _package_version(),
            "evidence_snapshot": _snapshot_id(index),
            "release_tier": index["release_tier"],
            "artifacts_present": len(present),
            "artifacts_declared": len(index["artifacts"]),
            "artifacts_stale_against_code": [
                item["key"] for item in present if item["stale_against_code"]
            ],
            "generated_at": index["generated_at"],
            "started_at": started_at,
            "artifact_root": str(base),
            "read_only": True,
            "in_container": Path("/.dockerenv").exists(),
            "security_note": _UNAUTHENTICATED_WARNING,
            "operational_bounds": [
                "Serves stored artifacts and recomputes readouts from them; it never "
                "refits a model and never writes to the artifact root.",
                "Sends nothing to any customer and triggers no campaign action.",
                "Every readout other than the locked policy decision is exploratory.",
            ],
        }

    @application.get("/robots.txt", response_class=PlainTextResponse)
    def robots() -> str:
        """Unindexed by default: conditional research numbers are easy to misquote."""

        return "User-agent: *\nDisallow: /\n"

    @application.get("/api/evidence")
    def evidence() -> dict[str, Any]:
        """Gate statuses, release tier and artifact freshness, computed live."""

        return build_index(base).to_dict()

    @application.get("/api/report/{name}")
    def report(name: str) -> dict[str, Any]:
        known = {
            "challenge_suite": "reports/v4/challenge_suite.json",
            "inference_smoke": "reports/v4/inference_smoke.json",
            "inference_smoke_misspecified": "reports/v4/inference_smoke_misspecified.json",
            "assignment_audit": "reports/v4/assignment_audit.json",
            "contracts": "reports/v4/contracts.json",
            "run_report": "reports/v4/run_report.json",
            "locked_policy": LOCKED,
            "temporal_lab": "reports/temporal_lab/summary.json",
        }
        if name not in known:
            raise HTTPException(status_code=404, detail=f"unknown report {name!r}")
        payload = _read_json(base, known[name])
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"{known[name]} has not been produced; run the stage that writes it",
            )
        return {"artifact": known[name], "payload": payload}

    @application.get("/api/policy/cohort")
    def cohort() -> dict[str, Any]:
        """What the capacity explorer is allowed to read, and its limits."""

        frame = _holdout(str(base))
        if frame is None:
            raise HTTPException(
                status_code=404,
                detail=f"{HOLDOUT} is missing; run python -m telco_churn.orange_benchmark",
            )
        locked = _read_json(base, LOCKED) or {}
        treatment = frame["treatment"].to_numpy(dtype=int)
        outcome = frame["outcome"].to_numpy(dtype=float)
        return {
            "source": HOLDOUT,
            "n_units": len(frame),
            "n_control": int((treatment == 0).sum()),
            "n_treated": int((treatment == 1).sum()),
            "control_churn_events": int(outcome[treatment == 0].sum()),
            "treated_churn_events": int(outcome[treatment == 1].sum()),
            "models": sorted(_score_columns(frame)),
            "locked_decision": locked,
            "evidence_state": "CONDITIONAL",
            "scope_note": (
                "Orange assignment is a documented-but-unverified randomisation: the "
                "assignment audit rejects pooled-IID exchangeability, so every number "
                "here is conditional on the design assumption, not a measured causal "
                "effect. The holdout has already been opened, so only the locked "
                "combination (model and budget declared beforehand) is confirmatory-"
                "adjacent; every other point is exploratory."
            ),
        }

    @application.get("/api/policy/curve")
    def curve(
        model: str = Query("risk_logistic"),
        cap_rule: str = Query("floor", pattern="^(floor|ceil)$"),
        require_positive: bool = Query(False),
        repeats: int = Query(BOOTSTRAP_REPEATS, ge=200, le=5000),
    ) -> dict[str, Any]:
        """Doubly robust readout at each declared capacity, with the arm counts."""

        frame = _holdout(str(base))
        if frame is None:
            raise HTTPException(status_code=404, detail=f"{HOLDOUT} is missing")
        if f"score_{model}" not in frame.columns:
            raise HTTPException(status_code=404, detail=f"unknown model {model!r}")
        points = []
        for fraction in CURVE_FRACTIONS:
            selected = _allocate(
                frame, model, fraction, cap_rule=cap_rule, require_positive=require_positive
            )
            points.append(
                {
                    "fraction": fraction,
                    "capacity": int(
                        capacity_limit(len(frame), fraction)
                        if cap_rule == "floor"
                        else min(len(frame), max(1, int(np.ceil(len(frame) * fraction))))
                    ),
                    **_evaluate(frame, selected, repeats=repeats),
                }
            )
        locked = _read_json(base, LOCKED) or {}
        return {
            "model": model,
            "cap_rule": cap_rule,
            "require_positive": require_positive,
            "bootstrap_repeats": repeats,
            "unit": "incremental churn prevented per selected account",
            "points": points,
            "locked_model": locked.get("model"),
            "locked_fraction": locked.get("budget_fraction"),
            "locked_dr_uplift": locked.get("test_dr_uplift"),
            "locked_ci": [locked.get("test_ci95_low"), locked.get("test_ci95_high")],
            "locked_decision": locked.get("test_decision"),
            "evidence_state": "EXPLORATORY",
            "scope_note": (
                "One pre-declared point (the locked model and budget) plus a curve that "
                "was computed after the holdout was opened. Reading a maximum off this "
                "curve is selection on the evaluation set, not a result."
            ),
        }

    @application.get("/api/policy/allocation")
    def allocation(
        model: str = Query("risk_logistic"),
        fraction: float = Query(0.30, gt=0, le=1),
        cap_rule: str = Query("floor", pattern="^(floor|ceil)$"),
        require_positive: bool = Query(False),
        repeats: int = Query(BOOTSTRAP_REPEATS, ge=200, le=5000),
    ) -> dict[str, Any]:
        """One allocation: who is selected, why, and what the readout says."""

        frame = _holdout(str(base))
        if frame is None:
            raise HTTPException(status_code=404, detail=f"{HOLDOUT} is missing")
        if f"score_{model}" not in frame.columns:
            raise HTTPException(status_code=404, detail=f"unknown model {model!r}")
        scores = frame[f"score_{model}"].to_numpy(dtype=float)
        limit = (
            capacity_limit(len(frame), fraction)
            if cap_rule == "floor"
            else min(len(frame), max(1, int(np.ceil(len(frame) * fraction))))
        )
        result = allocate_batch(
            frame["row_id"].astype(str).to_numpy(),
            scores,
            fraction=fraction,
            require_positive=require_positive,
            capacity=limit,
        )
        selected = result.frame["selected"].to_numpy(dtype=bool)
        reasons = result.frame["reason"].value_counts().to_dict()
        agreement = None
        if "locked_selected" in frame.columns:
            locked_mask = frame["locked_selected"].to_numpy(dtype=bool)
            agreement = {
                "locked_selected": int(locked_mask.sum()),
                "both": int((locked_mask & selected).sum()),
                "only_locked": int((locked_mask & ~selected).sum()),
                "only_current": int((~locked_mask & selected).sum()),
            }
        return {
            "model": model,
            "allocation": result.to_dict(),
            "reasons": {str(key): int(value) for key, value in reasons.items()},
            "readout": _evaluate(frame, selected, repeats=repeats),
            "versus_locked_policy": agreement,
            "evidence_state": "EXPLORATORY",
        }

    @application.get("/api/temporal/policy-truth")
    def temporal_truth(budget_fraction: float = Query(0.2, ge=0, le=1)) -> dict[str, Any]:
        """Known-counterfactual policy values from the synthetic temporal lab."""

        path = base / TEMPORAL_TRUTH
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"{TEMPORAL_TRUTH} is missing; run python -m telco_churn.temporal_lab",
            )
        frame = pd.read_csv(path)
        available = sorted(frame["budget_fraction"].unique().tolist())
        subset = frame[np.isclose(frame["budget_fraction"], budget_fraction)]
        if subset.empty:
            raise HTTPException(
                status_code=404,
                detail=f"no rows at budget_fraction={budget_fraction}; have {available}",
            )
        columns = [
            "policy",
            "selected_n",
            "true_net_value",
            "true_net_value_per_contact",
            "estimated_net_value_per_contact",
            "harmful_offer_share",
            "regret_vs_oracle_value",
        ]
        return {
            "source": TEMPORAL_TRUTH,
            "budget_fraction": budget_fraction,
            "available_fractions": available,
            "rows": subset[columns].to_dict(orient="records"),
            "evidence_state": "SYNTHETIC",
            "scope_note": (
                "Value units are synthetic and the data generating process is written by "
                "this project. It measures how policies behave under a known mechanism; "
                "it is not evidence about any market."
            ),
        }

    @application.get("/api/research/cross-domain")
    def cross_domain() -> dict[str, Any]:
        """Cross-domain causal uplift vs. risk ranking and R1 repair evidence."""
        hillstrom = _read_json(base, "reports/screening/screening.json") or {}
        lenta_rep = _read_json(base, "reports/v4/replication_lenta/external_replication.json") or {}
        lenta_screen = lenta_rep.get("screening") or {}
        r1_repair = _read_json(base, "reports/v4/r1_repair_20261002/RESULT.json") or {}
        r4_mens = _read_json(base, "reports/v4/learner_comparison/hillstrom_mens.json") or {}
        r4_womens = _read_json(base, "reports/v4/learner_comparison/hillstrom_womens.json") or {}
        r4_lenta = _read_json(base, "reports/v4/learner_comparison/lenta_sms.json") or {}

        def _extract_candidates(screen_payload: dict[str, Any]) -> list[dict[str, Any]]:
            rows = []
            for item in screen_payload.get("results", []):
                mean_val = item.get("mean_value")
                mean_delta = item.get("mean_delta_vs_baseline")
                ci_low = item.get("delta_ci_low")
                ci_high = item.get("delta_ci_high")
                rows.append(
                    {
                        "candidate_id": item.get("candidate_id"),
                        "name": item.get("name"),
                        "family": item.get("family"),
                        "score_kind": item.get("score_kind"),
                        "value_per_1000": round(float(mean_val) * 1000.0, 3)
                        if isinstance(mean_val, (int, float))
                        else None,
                        "delta_vs_m01_per_1000": round(float(mean_delta) * 1000.0, 3)
                        if isinstance(mean_delta, (int, float))
                        else 0.0,
                        "delta_ci_low_per_1000": round(float(ci_low) * 1000.0, 3)
                        if isinstance(ci_low, (int, float))
                        else None,
                        "delta_ci_high_per_1000": round(float(ci_high) * 1000.0, 3)
                        if isinstance(ci_high, (int, float))
                        else None,
                    }
                )
            return rows

        r1_cells = []
        for cell_entry in r1_repair.get("cells", []):
            cell_meta = cell_entry.get("cell", {})
            cand = cell_entry.get("candidate", {})
            hist = cell_entry.get("historical_reference", {})
            bound = cell_entry.get("bounded_safety_reference", {})
            wilson = cand.get("coverage_wilson") or [None, None]
            r1_cells.append(
                {
                    "name": cell_meta.get("name"),
                    "policy": cell_meta.get("policy"),
                    "effect": cell_meta.get("effect"),
                    "truth": cell_entry.get("truth"),
                    "candidate_coverage": cand.get("coverage"),
                    "wilson_low": wilson[0],
                    "wilson_high": wilson[1],
                    "gate_pass": cand.get("coverage_gate_pass"),
                    "old_coverage": hist.get("coverage"),
                    "bounded_coverage": bound.get("coverage"),
                    "bounded_half_width_per_1000": cell_entry.get("bounded_half_width_per_1000"),
                }
            )

        return {
            "evidence_state": "OBSERVED",
            "hillstrom_r02": {
                "dataset": hillstrom.get("dataset", "Hillstrom Mens E-Mail vs No E-Mail"),
                "cohort": hillstrom.get("cohort", {}),
                "shortlist": hillstrom.get("shortlist", []),
                "candidates": _extract_candidates(hillstrom),
            },
            "lenta_r10": {
                "dataset": lenta_rep.get("dataset", "Lenta SMS campaign"),
                "cohort": lenta_rep.get("cohort", {}),
                "shortlist": lenta_screen.get("shortlist", []),
                "candidates": _extract_candidates(lenta_screen),
            },
            "r4_nested_summary": [
                {
                    "domain": "Hillstrom Mens (Primary Dev)",
                    "n_units": (r4_mens.get("checks") or {}).get("n", 34092),
                    "events": sum(
                        ((r4_mens.get("checks") or {}).get("events_by_arm") or {}).values()
                    ),
                    "mean_delta_vs_m01_per_1000": r4_mens.get("mean_delta_per_1000"),
                    "selected_recipes": r4_mens.get("selected_recipes", []),
                    "decision": r4_mens.get("development_priority", "RETAIN_M01_FOR_SCOPE"),
                },
                {
                    "domain": "Hillstrom Womens (Sensitivity)",
                    "n_units": (r4_womens.get("checks") or {}).get("n", 34193),
                    "events": sum(
                        ((r4_womens.get("checks") or {}).get("events_by_arm") or {}).values()
                    ),
                    "mean_delta_vs_m01_per_1000": r4_womens.get("mean_delta_per_1000"),
                    "selected_recipes": r4_womens.get("selected_recipes", []),
                    "decision": r4_womens.get("development_priority", "EXPLORATORY_SENSITIVITY"),
                },
                {
                    "domain": "Lenta Retail SMS (60k Subsample)",
                    "n_units": (r4_lenta.get("checks") or {}).get("n", 60000),
                    "events": sum(
                        ((r4_lenta.get("checks") or {}).get("events_by_arm") or {}).values()
                    ),
                    "mean_delta_vs_m01_per_1000": r4_lenta.get("mean_delta_per_1000"),
                    "selected_recipes": r4_lenta.get("selected_recipes", []),
                    "decision": r4_lenta.get(
                        "development_priority", "EXPLORATORY_ASSUMED_PROPENSITY"
                    ),
                },
            ],
            "r1_repair": {
                "status": r1_repair.get("status", "SYNTHETIC_GATE_FAILED"),
                "worlds_per_cell": r1_repair.get("worlds_per_cell", 2000),
                "cells": r1_cells,
            },
        }

    @application.post("/api/ai/ask")
    def console_ai_ask(request: ConsoleAskRequest) -> dict[str, Any]:
        return answer_question(request.question, root=base, lang=request.lang)

    @application.get("/api/ai/evaluation")
    def console_ai_evaluation() -> dict[str, Any]:
        return evaluate_assistant(base)

    if WEBUI_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(WEBUI_DIR)), name="static")

        @application.get("/")
        def index() -> FileResponse:
            return FileResponse(WEBUI_DIR / "index.html")

    return application


app = create_dashboard()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=os.getenv("TELCO_ARTIFACT_ROOT", "."),
        help="artifact root to read from (env: TELCO_ARTIFACT_ROOT)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("TELCO_CONSOLE_HOST", "127.0.0.1"),
        help="bind address; defaults to localhost (env: TELCO_CONSOLE_HOST)",
    )
    parser.add_argument("--port", type=int, default=int(os.getenv("TELCO_CONSOLE_PORT", "8050")))
    args = parser.parse_args(argv)

    import uvicorn

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"WARNING: {_UNAUTHENTICATED_WARNING}")
    uvicorn.run(create_dashboard(args.root), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
