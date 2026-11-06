"""Single index of what evidence exists, how fresh it is and what it licenses.

The repository holds three kinds of statement at once: results that were
measured, results that hold only under an assumption nobody has checked, and
designs that have never been run.  They live in different files, and reading
them in the wrong order is how a plan turns into a claim.

This module builds one machine-readable index over the artifacts on disk and
answers three questions about each of them:

* **does it exist**, with a SHA-256 so a report can cite a specific version;
* **is it older than the code that produces it** -- an artifact whose producer
  module was edited afterwards is evidence about a pipeline that no longer
  exists, and is flagged ``producer_newer`` (QG0);
* **what gate does it feed**, and is that gate ``PASS``, ``FAIL``, ``NOT_RUN``
  or ``NOT_MET``.

``NOT_MET`` is deliberately not a failure.  The coverage gate has never been
run at its declared size; saying so is the honest state, and pretending the
one-scenario smoke run satisfies it would be the dishonest one.  The release
tier at the bottom is computed from the gates, not asserted: it is the highest
tier whose requirements are all satisfied by artifacts in this index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "ArtifactRecord",
    "EvidenceIndex",
    "GateRecord",
    "build_index",
    "main",
]

GateStatus = Literal["PASS", "FAIL", "NOT_RUN", "NOT_MET", "UNVERIFIED"]

#: Release tiers in ascending order, with the gates each one requires.
RELEASE_TIERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "ENGINEERING_FOUNDATION",
        ("contracts", "mutation_suite", "runner_failure_propagation", "environment_lock"),
    ),
    (
        "RESEARCH_INTERIM",
        (
            "contracts",
            "mutation_suite",
            "runner_failure_propagation",
            "environment_lock",
            "inference_coverage",
            "real_domain_identification",
        ),
    ),
    (
        "RESEARCH_REPLICATED",
        (
            "contracts",
            "mutation_suite",
            "runner_failure_propagation",
            "environment_lock",
            "inference_coverage",
            "real_domain_identification",
            "external_replication",
        ),
    ),
    (
        "BUSINESS_VALIDATED",
        (
            "contracts",
            "mutation_suite",
            "runner_failure_propagation",
            "environment_lock",
            "inference_coverage",
            "real_domain_identification",
            "external_replication",
            "partner_trial",
        ),
    ),
)

#: ``artifact key -> (path, producer modules, one-line role)``.
ARTIFACTS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "contracts",
        "reports/v4/contracts.json",
        ("src/telco_churn/problem_contract.py", "configs/problem_contracts.toml"),
        "Validated problem/action/timing contracts",
    ),
    (
        "challenge_suite",
        "reports/v4/challenge_suite.json",
        ("src/telco_churn/challenge_suite.py",),
        "Falsification suite: declared mutations and whether they were caught",
    ),
    (
        "hillstrom_manifest",
        "reports/hillstrom/dataset_manifest.json",
        ("src/telco_churn/hillstrom_data.py",),
        "Real-data primary: provenance, arms and the frozen split",
    ),
    (
        "screening",
        "reports/screening/screening.json",
        ("src/telco_churn/screening.py", "src/telco_churn/candidates.py"),
        "R02 model screening over the declared candidates",
    ),
    (
        "environment_lock",
        "locks/research.lock.txt",
        ("src/telco_churn/environment.py",),
        "Exact dependency set the reports were produced under",
    ),
    (
        "lenta_manifest",
        "reports/v4/lenta_manifest.json",
        ("src/telco_churn/lenta_data.py",),
        "Replication domain: provenance, arms and the frozen split",
    ),
    (
        "external_replication",
        "reports/v4/replication_lenta/external_replication.json",
        ("src/telco_churn/external_replication.py", "src/telco_churn/screening.py"),
        "R10: the Hillstrom protocol, unchanged, on an independent domain",
    ),
    (
        "assignment_audit_lenta",
        "reports/v4/assignment_audit_lenta.json",
        ("src/telco_churn/assignment_audit.py",),
        "Whether Lenta's treatment assignment survives a predictability audit",
    ),
    (
        "temporal_replay",
        "reports/v4/temporal_replay/temporal_replay.json",
        ("src/telco_churn/temporal_replay.py",),
        "R07: refresh strategies replayed in their own trajectories",
    ),
    (
        "learning_curves",
        "reports/v4/learning_curves/learning_curves.json",
        ("src/telco_churn/learning_curves.py",),
        "R05: whether the result is the data budget or the seed",
    ),
    (
        "sampling_economics",
        "reports/v4/sampling_economics/sampling_economics.json",
        ("src/telco_churn/sampling_economics.py", "src/telco_churn/policy_comparison.py"),
        "R08: what the enriched sampling design costs at matched precision",
    ),
    (
        "selection_stress",
        "reports/v4/selection_stress/selection_stress.json",
        ("src/telco_churn/selection_stress.py",),
        "R06: what selecting the best of four costs in false promotion and regret",
    ),
    (
        "component_factorial",
        "reports/v4/factorial/component_factorial.json",
        ("src/telco_churn/component_factorial.py", "src/telco_churn/candidates.py"),
        "R04: which component of the pipeline is doing the work",
    ),
    (
        "bounded_tuning",
        "reports/v4/tuning/bounded_tuning.json",
        ("src/telco_churn/bounded_tuning.py", "src/telco_churn/candidates.py"),
        "R03: whether tuning changes the screening verdict",
    ),
    (
        "validity_v08",
        "reports/v4/validity_v08/v08_batch_cap.json",
        ("src/telco_churn/batch_validation.py", "src/telco_churn/policy_comparison.py"),
        "V08: coverage of the capped batch-policy interval, both targets",
    ),
    (
        "asymmetry_transfer",
        "reports/v4/asymmetry_transfer/asymmetry_transfer.json",
        ("src/telco_churn/asymmetry_transfer.py", "src/telco_churn/policy_comparison.py"),
        "Whether the asymmetry index transfers to frames the sweep never saw",
    ),
    (
        "figures",
        "reports/v4/figures/figures.json",
        ("src/telco_churn/figures.py",),
        "Figures for the boundary result, drawn from artifacts only",
    ),
    (
        "overlap_boundary",
        "reports/v4/overlap_boundary/overlap_boundary.json",
        ("src/telco_churn/overlap_boundary.py", "src/telco_churn/policy_comparison.py"),
        "Where the DR interval stops covering, as a function of design imbalance",
    ),
    (
        "validity_v09",
        "reports/v4/validity_v09/v09_recruitment.json",
        ("src/telco_churn/recruitment_validation.py", "src/telco_churn/policy_comparison.py"),
        "V09 two-stage recruitment: superpopulation interval vs its negative control",
    ),
    (
        "validity_suite",
        "reports/v4/validity/validity_suite.json",
        ("src/telco_churn/validity_suite.py", "src/telco_churn/policy_comparison.py"),
        "R00 exact identities and R01 evaluator validation",
    ),
    (
        "fresh_evaluator_diagnostic",
        "reports/v4/fresh_evaluator/FRESH_EVALUATOR.json",
        ("src/telco_churn/fresh_evaluator.py", "src/telco_churn/policy_comparison.py"),
        "Two new generator families: transfer diagnostic, not a release gate",
    ),
    (
        "next_evaluator_transfer",
        "reports/v4/next_evaluator_transfer/TRANSFER_RESULT.json",
        ("src/telco_churn/next_evaluator_transfer.py",),
        "R1 six-cell known-truth transfer; failed cells block method promotion",
    ),
    (
        "r1_repair_validation",
        "reports/v4/r1_repair_20261002/RESULT.json",
        ("src/telco_churn/r1_repair.py", "src/telco_churn/policy_comparison.py"),
        "New 2,000-world six-cell repair validation; candidate coverage gate failed",
    ),
    (
        "next_evaluator_negative_controls",
        "reports/v4/next_evaluator_transfer/NEGATIVE_CONTROL_RESULT.json",
        ("reports/v4/next_evaluator_transfer/negative_controls.py",),
        "R1 separate broken-control diagnostic; row-IID control did not discriminate",
    ),
    (
        "r4_learner_mens",
        "reports/v4/learner_comparison/hillstrom_mens.json",
        ("reports/v4/learner_comparison/PRODUCER_SOURCE.py",),
        "R4 nested-fold Hillstrom Mens development comparison only",
    ),
    (
        "r4_learner_womens",
        "reports/v4/learner_comparison/hillstrom_womens.json",
        ("reports/v4/learner_comparison/PRODUCER_SOURCE.py",),
        "R4 nested-fold Hillstrom Womens development sensitivity only",
    ),
    (
        "r4_learner_lenta",
        "reports/v4/learner_comparison/lenta_sms.json",
        ("reports/v4/learner_comparison/PRODUCER_SOURCE.py",),
        "R4 Lenta development subsample; assumed propensity, exploratory only",
    ),
    (
        "r4_allocator",
        "reports/v4/exact_allocator_study/RESULT.json",
        ("src/telco_churn/exact_allocator_study.py",),
        "R4 frozen synthetic allocator comparison; rank and exact agree",
    ),
    (
        "r4b_allocator_exploratory",
        "reports/v4/exact_allocator_study/r4b/RESULT.json",
        ("src/telco_churn/exact_allocator_followup.py",),
        "R4b post-R4 synthetic cost revision; exploratory, no promotion",
    ),
    (
        "inference_smoke",
        "reports/v4/inference_smoke.json",
        ("src/telco_churn/inference_smoke.py", "src/telco_churn/policy_comparison.py"),
        "Known-truth estimator smoke run (one scenario)",
    ),
    (
        "inference_smoke_misspecified",
        "reports/v4/inference_smoke_misspecified.json",
        ("src/telco_churn/inference_smoke.py",),
        "Same smoke run with a deliberately wrong outcome model",
    ),
    (
        "assignment_audit",
        "reports/v4/assignment_audit.json",
        ("src/telco_churn/assignment_audit.py",),
        "Orange treatment-predictability audit and permutation null",
    ),
    (
        "assignment_audit_hillstrom",
        "reports/v4/assignment_audit_hillstrom.json",
        ("src/telco_churn/assignment_audit.py", "src/telco_churn/hillstrom_data.py"),
        "Hillstrom treatment-predictability audit and permutation null",
    ),
    (
        "run_report",
        "reports/v4/run_report.json",
        ("src/telco_churn/research_runner.py",),
        "Last staged run and its per-stage status",
    ),
    (
        "orange_policy_decision",
        "reports/uplift/locked_policy_decision.json",
        ("src/telco_churn/orange_benchmark.py",),
        "Locked Orange policy decision (NO_LAUNCH gate)",
    ),
    (
        "temporal_lab",
        "reports/temporal_lab/summary.json",
        ("src/telco_churn/temporal_lab.py", "src/telco_churn/simulation.py"),
        "Known-counterfactual temporal lab summary",
    ),
    (
        "predictive_benchmark",
        "reports/benchmark/BENCHMARK_REPORT.md",
        ("src/telco_churn/train.py",),
        "IBM predictive benchmark report",
    ),
    (
        "planner_v2_browser",
        "reports/v4/browser_smoke_v2_20261002/result.json",
        ("src/telco_churn/api.py", "src/telco_churn/planner/app.js", "scripts/browser_smoke.py"),
        "Chrome desktop/mobile v2 preview and packet replay; automated smoke only",
    ),
    (
        "api_latency",
        "reports/api/latency.json",
        ("src/telco_churn/performance.py", "src/telco_churn/api.py"),
        "API latency and parity measurements",
    ),
    (
        "deployment_smoke",
        "reports/deployment/deployment_smoke.json",
        ("src/telco_churn/deployment_smoke.py", "Dockerfile", "compose.yaml"),
        "Acceptance checks against a running deployment",
    ),
    (
        "claim_ledger",
        "docs/CLAIM_LEDGER_V4.md",
        (),
        "Human claim ledger: observed / conditional / planned",
    ),
)

_CLAIM_STATES = ("OBSERVED", "CONDITIONAL", "PLANNED")


def _utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ArtifactRecord:
    key: str
    path: str
    role: str
    exists: bool
    sha256: str | None = None
    size_bytes: int | None = None
    modified_at: str | None = None
    producers: tuple[str, ...] = ()
    producer_newer: tuple[str, ...] = ()

    @property
    def is_stale_against_code(self) -> bool:
        return bool(self.producer_newer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "path": self.path,
            "role": self.role,
            "exists": self.exists,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
            "producers": list(self.producers),
            "producer_newer": list(self.producer_newer),
            "stale_against_code": self.is_stale_against_code,
        }


@dataclass(frozen=True)
class GateRecord:
    gate_id: str
    title: str
    status: GateStatus
    summary: str
    evidence: tuple[str, ...] = ()
    blocker: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "blocker": self.blocker,
        }


@dataclass
class EvidenceIndex:
    root: str
    generated_at: str
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    gates: list[GateRecord] = field(default_factory=list)
    claims: dict[str, int] = field(default_factory=dict)

    def gate(self, gate_id: str) -> GateRecord | None:
        for record in self.gates:
            if record.gate_id == gate_id:
                return record
        return None

    @property
    def failing_gates(self) -> list[GateRecord]:
        return [gate for gate in self.gates if gate.status == "FAIL"]

    @property
    def release_tier(self) -> str:
        achieved = "NONE"
        for tier, required in RELEASE_TIERS:
            if all((gate := self.gate(gate_id)) and gate.status == "PASS" for gate_id in required):
                achieved = tier
            else:
                break
        return achieved

    def tier_blockers(self) -> list[dict[str, str]]:
        """What stands between the achieved tier and the next one up."""

        tiers = [name for name, _ in RELEASE_TIERS]
        current = self.release_tier
        index = tiers.index(current) + 1 if current in tiers else 0
        if index >= len(tiers):
            return []
        next_tier, required = RELEASE_TIERS[index]
        blockers = []
        for gate_id in required:
            gate = self.gate(gate_id)
            if gate is None:
                blockers.append({"tier": next_tier, "gate": gate_id, "reason": "gate not scored"})
            elif gate.status != "PASS":
                blockers.append(
                    {
                        "tier": next_tier,
                        "gate": gate_id,
                        "reason": gate.blocker or f"{gate.title} is {gate.status}",
                    }
                )
        return blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "root": self.root,
            "release_tier": self.release_tier,
            "tier_blockers": self.tier_blockers(),
            "n_failing_gates": len(self.failing_gates),
            "claims": self.claims,
            "gates": [gate.to_dict() for gate in self.gates],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _scan_artifacts(root: Path) -> list[ArtifactRecord]:
    records: list[ArtifactRecord] = []
    for key, relative, producers, role in ARTIFACTS:
        target = root / relative
        if not target.exists():
            records.append(
                ArtifactRecord(key=key, path=relative, role=role, exists=False, producers=producers)
            )
            continue
        stat = target.stat()
        newer = tuple(
            producer
            for producer in producers
            if (root / producer).exists() and (root / producer).stat().st_mtime > stat.st_mtime
        )
        records.append(
            ArtifactRecord(
                key=key,
                path=relative,
                role=role,
                exists=True,
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                size_bytes=stat.st_size,
                modified_at=_utc(stat.st_mtime),
                producers=producers,
                producer_newer=newer,
            )
        )
    return records


def _count_claims(root: Path) -> dict[str, int]:
    """Token counts from the human claim ledger, not a re-derivation of it."""

    path = root / "docs/CLAIM_LEDGER_V4.md"
    counts = dict.fromkeys(_CLAIM_STATES, 0)
    if not path.exists():
        return counts
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        for state in _CLAIM_STATES:
            if re.search(rf"\b{state}\b", line):
                counts[state] += 1
                break
    return counts


def _gate_contracts(payload: dict[str, Any] | None) -> GateRecord:
    if payload is None:
        return GateRecord(
            "contracts",
            "Problem contracts validated",
            "NOT_RUN",
            "no contract manifest on disk",
            blocker="run python -m telco_churn.problem_contract_cli",
        )
    total = payload.get("n_contracts", 0)
    promotable = payload.get("n_promotable", 0)
    return GateRecord(
        "contracts",
        "Problem contracts validated",
        "PASS" if total else "FAIL",
        f"{total} contract revision(s) load and validate; {promotable} promotable, "
        f"{total - promotable} declared negative control(s)",
        evidence=("reports/v4/contracts.json",),
    )


def _gate_mutations(payload: dict[str, Any] | None) -> GateRecord:
    if payload is None:
        return GateRecord(
            "mutation_suite",
            "Declared mutations are caught",
            "NOT_RUN",
            "no challenge-suite report on disk",
            blocker="run python -m telco_churn.challenge_suite",
        )
    passed = bool(payload.get("gate_passed"))
    detected = payload.get("detected_critical", 0)
    declared = payload.get("declared_critical", 0)
    return GateRecord(
        "mutation_suite",
        "Declared mutations are caught",
        "PASS" if passed else "FAIL",
        f"{detected}/{declared} critical mutations detected across "
        f"{payload.get('n_executed', 0)} declared cases; "
        f"{len(payload.get('false_blocks', []))} clean fixture(s) blocked. "
        "Covers declared faults only.",
        evidence=("reports/v4/challenge_suite.json",),
        blocker="" if passed else f"undetected: {payload.get('undetected')}",
    )


def _best_powered_validity(root: Path) -> dict[str, Any] | None:
    """The R01 verdict from the largest run available.

    Runs at different sizes and with different interval methods accumulate on
    disk.  Taking whichever was written last would let a small exploratory run
    override a large confirmation; taking the largest is the honest default,
    and the summary names which one it used.
    """

    from .screening import _read_gate

    return _read_gate(root)[0]


def _gate_coverage(
    smoke: dict[str, Any] | None,
    validity: dict[str, Any] | None,
    recruitment: dict[str, Any] | None = None,
    boundary: dict[str, Any] | None = None,
    batch_cap: dict[str, Any] | None = None,
    root: Path | str = ".",
) -> GateRecord:
    """R01 scores this gate; the one-scenario smoke only reports mechanics."""

    if validity is not None:
        run = list(validity.get("scenarios_run", ()))
        declared = list(validity.get("scenarios_declared", ()))
        missing = [name for name in declared if name not in run]
        not_run = dict(validity.get("not_run", {}))
        if recruitment is not None:
            # V09 has its own artifact; drop it from the not-run list and fold
            # its verdict into this gate instead.
            not_run.pop("V09_two_stage_recruitment", None)
        if batch_cap is not None:
            # Same for V08: the suite still declares it as blocked on G06, but
            # G06 exists and the scenario has run, so the declaration is stale.
            not_run.pop("V08_batch_cap", None)
        worlds = validity.get("worlds_per_scenario", 0)
        coverage_failures = validity.get("coverage_failures", [])
        promotion_failures = validity.get("promotion_failures", [])
        passed = bool(validity.get("gate_passed"))
        status: GateStatus = "PASS" if passed else ("FAIL" if worlds >= 1_000 else "NOT_MET")
        blockers = []
        selected_among = validity.get("_selected_among", [])
        if selected_among and passed:
            status = "NOT_MET"
            blockers.append(
                "mechanical coverage passed, but the interval was selected after equally "
                "powered runs disagreed; independent confirmation is missing"
            )
        if missing:
            blockers.append(f"declared but not run: {', '.join(missing)}")
        if coverage_failures:
            blockers.append(f"undercovering: {', '.join(coverage_failures)}")
        if promotion_failures:
            blockers.append(f"false promotion: {', '.join(promotion_failures)}")
        if worlds < 1_000:
            blockers.append(f"{worlds} worlds per scenario, gate requires 1,000")
        # An unrun declared scenario is a hole in the evidence, not a footnote
        # on a pass.  Listing it in `blocker` while still reporting PASS is how
        # a gate quietly grades itself on the subset that happened to run.
        if not_run:
            blockers.extend(f"{key} not run" for key in not_run)
            passed = False
            status = "NOT_MET"
        if batch_cap is not None and not batch_cap.get("gate_passed"):
            blockers.append(
                f"V08 {batch_cap.get('status')}: "
                f"{len(batch_cap.get('failures', []))} readout(s) under-covering, "
                f"{len(batch_cap.get('controls_that_did_not_fire', []))} control(s) "
                "that failed to fire"
            )
            passed = False
            status = "FAIL" if worlds >= 1_000 else "NOT_MET"
        if recruitment is not None and not recruitment.get("gate_passed"):
            blockers.append(
                f"V09 {recruitment.get('status')}: "
                f"{len(recruitment.get('failures', []))} readout(s) under-covering, "
                f"{len(recruitment.get('controls_that_did_not_break', []))} control(s) "
                "that failed to break"
            )
            passed = False
            status = "FAIL" if worlds >= 1_000 else "NOT_MET"
        # Two statements of where this evaluator is usable.  The sweep's is
        # the better one -- it varied the event rate as well as the design,
        # and found that imbalance alone does not order the cells -- so it is
        # reported first and the scenario-level region is kept only as the
        # coarse fallback it is.
        # Where the evaluator was shown to work is *scope*, not a blocker: a
        # gate can pass and still be valid only over part of the design space.
        # Mixing the two would mean a passing gate could never report an empty
        # blocker, which makes the field useless for deciding anything.
        scope: list[str] = []
        # Report the threshold the gate actually *enforces*, not the sweep's
        # raw one: the transfer study tightened it, and an index that quoted
        # the looser number would disagree with the code that refuses cohorts.
        from .screening import _licensed_asymmetry

        method = validity.get("interval_method", "normal")
        enforced, provenance = _licensed_asymmetry(root, method)
        measured = ((boundary or {}).get("boundary_by_asymmetry") or {}).get(method)
        if enforced is not None:
            scope.append(
                f"measured design region: asymmetry index up to {enforced:.3f} "
                f"for the {method} interval ({provenance})"
            )
        elif measured and not measured.get("separates"):
            scope.append(
                "the boundary sweep found the asymmetry index does not order its cells, "
                "so no measured region is licensed"
            )
        region = validity.get("validated_design_region") or {}
        if region.get("validated_scenarios"):
            scope.append(
                "scenario-level region (coarse; ignores event rate and frame size): "
                "propensity imbalance up to "
                f"{region['max_propensity_imbalance_validated']:.2f} "
                f"({', '.join(region['validated_scenarios'])}); "
                + (
                    "no scenario failed"
                    if not math.isfinite(region["smallest_failing_imbalance"])
                    else f"failing at {region['smallest_failing_imbalance']:.2f}"
                )
            )
        return GateRecord(
            "inference_coverage",
            "Estimator coverage gate (R00/R01)",
            status,
            f"{validity.get('_artifact', 'validity')}: "
            f"{len(run)}/{len(declared)} declared scenarios at {worlds:,} worlds each; "
            f"R00 identities {'pass' if validity.get('r00_identities_passed') else 'FAIL'}; "
            f"{len(coverage_failures)} undercovering mode(s), "
            f"{len(promotion_failures)} false-promotion failure(s); "
            f"negative controls fired: {len(validity.get('negative_controls_detected', []))}; "
            f"independent confirmation: {'required' if selected_among else 'no selection conflict detected'}"
            + ("; valid over: " + "; ".join(scope) if scope else ""),
            evidence=("reports/v4/validity/validity_suite.json",),
            blocker="; ".join(blockers),
        )
    if smoke is None:
        return GateRecord(
            "inference_coverage",
            "Estimator coverage gate (R00/R01)",
            "NOT_RUN",
            "neither the R01 validity suite nor the smoke run is on disk",
            blocker="run python -m telco_churn.validity_suite",
        )
    covered = set(smoke.get("scenarios_covered", ()))
    required = list(smoke.get("scenarios_required_for_gate", ()))
    missing = [scenario for scenario in required if scenario not in covered]
    paired = smoke.get("paired", {})
    return GateRecord(
        "inference_coverage",
        "Estimator coverage gate (R00/R01)",
        "NOT_MET" if missing else "PASS",
        f"{len(covered)}/{len(required)} canonical scenarios exercised; "
        f"paired coverage {paired.get('coverage', float('nan')):.3f} over "
        f"{paired.get('worlds', 0)} worlds on the scenarios that did run",
        evidence=("reports/v4/inference_smoke.json",),
        blocker=f"never run for: {', '.join(missing)}" if missing else "",
    )


def _gate_identification(audits: dict[str, dict[str, Any] | None]) -> GateRecord:
    """Does any dataset pass the recorded assignment diagnostics?

    The audit cannot prove randomisation; it can only fail to detect a
    violation, and only with the resolution its sample size affords.  The gate
    therefore asks two things of a dataset: the permutation test does not
    reject exchangeability, and reweighting by the fitted propensity leaves an
    effective sample size worth having.  This diagnostic does not recover a
    missing randomizer log or prove a known design probability. Orange fails
    the second badly enough that the first would not matter.
    """

    scored: list[str] = []
    usable: list[str] = []
    for name, payload in audits.items():
        if payload is None:
            continue
        predictability = payload.get("treatment_predictability", {})
        permutation = payload.get("permutation_test", {})
        propensity = payload.get("estimated_propensity", {})
        auc = predictability.get("oof_roc_auc")
        p_value = permutation.get("p_value_add_one")
        ess = propensity.get("effective_sample_size_estimated_e")
        total = propensity.get("effective_sample_size_constant_e") or 0
        ratio = (ess / total) if (ess and total) else 0.0
        rejected = isinstance(p_value, (int, float)) and p_value <= 0.05
        scored.append(
            f"{name}: AUC {auc:.4f}, p {p_value:.4f}, ESS kept {ratio:.1%}"
            if isinstance(auc, (int, float)) and isinstance(p_value, (int, float))
            else f"{name}: unreadable"
        )
        if not rejected and ratio > 0.5:
            usable.append(name)

    if not scored:
        return GateRecord(
            "real_domain_identification",
            "Real-domain assignment diagnostics",
            "NOT_RUN",
            "no assignment audit on disk",
            blocker="run python -m telco_churn.assignment_audit",
        )
    return GateRecord(
        "real_domain_identification",
        "Real-domain assignment diagnostics",
        "PASS" if usable else "NOT_MET",
        "; ".join(scored)
        + (
            f". Assignment diagnostics passed: {', '.join(usable)}; "
            "verify design probabilities separately"
            if usable
            else ". No dataset survives both checks"
        ),
        evidence=(
            "reports/v4/assignment_audit.json",
            "reports/v4/assignment_audit_hillstrom.json",
        ),
        blocker=""
        if usable
        else "every audited dataset either rejects exchangeability or collapses its "
        "effective sample size under reweighting",
    )


def _gate_runner(payload: dict[str, Any] | None) -> GateRecord:
    if payload is None:
        return GateRecord(
            "runner_failure_propagation",
            "Runner propagates failure",
            "NOT_RUN",
            "no run report on disk",
            blocker="run python -m telco_churn.research_runner --profile smoke",
        )
    status = payload.get("status")
    stages = payload.get("stages", [])
    return GateRecord(
        "runner_failure_propagation",
        "Runner propagates failure",
        "PASS" if status == "COMPLETE" else "FAIL",
        f"last {payload.get('profile', '?')} run is {status} over {len(stages)} stage(s); "
        f"run_id {payload.get('run_id', 'n/a')}",
        evidence=("reports/v4/run_report.json",),
        blocker="" if status == "COMPLETE" else f"last run status {status}",
    )


def _gate_environment(root: Path) -> GateRecord:
    """QG0: the run must be able to say what it was produced with."""

    from .environment import DEFAULT_LOCKS, verify_lock

    lock = root / DEFAULT_LOCKS["research"]
    if not lock.exists():
        return GateRecord(
            "environment_lock",
            "Dependency lock is present and satisfied",
            "NOT_RUN",
            "no research lock on disk",
            blocker="run python -m telco_churn.environment --capture locks/research.lock.txt",
        )
    report = verify_lock(lock)
    present = [name for name, path in DEFAULT_LOCKS.items() if (root / path).exists()]
    return GateRecord(
        "environment_lock",
        "Dependency lock is present and satisfied",
        "PASS" if report.satisfied else "FAIL",
        f"{report.n_locked} packages locked for the research environment "
        f"({len(present)} lock file(s): {', '.join(present)}); "
        f"live interpreter {'matches' if report.satisfied else 'differs'}",
        evidence=tuple(DEFAULT_LOCKS[name] for name in present),
        blocker=""
        if report.satisfied
        else f"{len(report.missing)} missing, {len(report.changed)} version mismatch(es)",
    )


def _gate_deployment(payload: dict[str, Any] | None) -> GateRecord:
    """QG7: does a running deployment agree with the host and with the ledger?"""

    if payload is None:
        return GateRecord(
            "deployment_replay",
            "Deployment agrees with the host",
            "NOT_RUN",
            "no deployment has been checked from this working copy",
            blocker="start the stack and run python -m telco_churn.deployment_smoke",
        )
    failed = payload.get("n_failed", 0)
    skipped = payload.get("n_skipped", 0)
    parity = next(
        (
            check
            for check in payload.get("checks", ())
            if check["name"] == "host_container_parity" and check["passed"]
        ),
        None,
    )
    detail = ""
    if parity:
        gap = parity.get("measured", {}).get("max_absolute_gap")
        if isinstance(gap, (int, float)):
            detail = f"; host/container score gap {gap:.1e}"
    return GateRecord(
        "deployment_replay",
        "Deployment agrees with the host",
        "PASS" if failed == 0 else "FAIL",
        f"{payload.get('n_checks', 0) - failed - skipped}/{payload.get('n_checks', 0)} checks "
        f"passed on {payload.get('started_at', 'an unknown date')}{detail}",
        evidence=("reports/deployment/deployment_smoke.json",),
        blocker="" if failed == 0 else f"{failed} check(s) failed",
    )


def _gate_screening(root: Path, payload: dict[str, Any] | None) -> GateRecord:
    """R02: has the declared candidate set been screened, and behind an open gate?"""

    from .screening import gate_status

    if payload is None:
        passed, detail = gate_status(root)
        return GateRecord(
            "model_screening",
            "Declared candidates screened (R02)",
            "NOT_RUN",
            "no screening report on disk",
            blocker=(
                "R02 is gated on R01: " + detail
                if not passed
                else "the gate is open; run python -m telco_churn.screening"
            ),
        )
    failed = payload.get("n_failed", 0)
    ungated = "GATE NOT PASSED" in str(payload.get("gate", ""))
    return GateRecord(
        "model_screening",
        "Declared candidates screened (R02)",
        "FAIL" if (failed or ungated) else "PASS",
        f"{payload.get('n_completed', 0)} candidates completed, {failed} failed on "
        f"{payload.get('dataset', 'an unknown cohort')}; shortlist "
        f"{', '.join(payload.get('shortlist', [])) or 'none'}",
        evidence=("reports/screening/screening.json",),
        blocker="run behind a failed R01 gate" if ungated else "",
    )


def _gate_external_replication(payload: dict[str, Any] | None) -> GateRecord:
    """R10 passes only if the recipe was *reused*, not re-implemented.

    A replication that quietly swapped the protocol would be worse than no
    replication, so the gate checks what the artifact says it ran rather
    than trusting that it ran something. A domain that shares the customers
    with the primary study -- the Womens arm, for instance -- is not a second
    domain and cannot satisfy this.
    """

    if payload is None:
        return GateRecord(
            "external_replication",
            "Independent-domain replication (R10)",
            "NOT_RUN",
            "no second domain has been run under the same method recipe",
            blocker="R10 needs source/license/compute confirmation first",
        )
    if not payload.get("is_independent_domain"):
        return GateRecord(
            "external_replication",
            "Independent-domain replication (R10)",
            "FAIL",
            f"{payload.get('dataset')} is not declared an independent domain",
            blocker="a second slice of the primary study is not a replication",
        )

    predictions = payload.get("predictions", {})
    held = [name for name, item in predictions.items() if item.get("held")]
    failed = [name for name, item in predictions.items() if not item.get("held")]
    replicated = payload.get("stages_replicated", [])
    cohort = payload.get("cohort", {})
    detail = (
        f"{payload.get('dataset')}: {cohort.get('n_units', 0):,} units, "
        f"{cohort.get('n_events', 0):,} events, stages {', '.join(replicated)}; "
        f"{len(held)}/{len(predictions)} registered predictions held"
    )
    # Running the stage is what the gate is about. A falsified prediction is
    # a result, not a failed gate -- the stage exists to find out, and
    # marking it FAIL would reward studies that predict nothing.
    blockers = []
    if failed:
        blockers.append(f"registered predictions falsified: {', '.join(failed)}")
    for stage, reason in (payload.get("stages_not_transferable") or {}).items():
        blockers.append(f"{stage} not transferable: {reason}")
    return GateRecord(
        "external_replication",
        "Independent-domain replication (R10)",
        "PASS",
        detail,
        evidence=("reports/v4/replication_lenta/external_replication.json",),
        blocker="; ".join(blockers),
    )


def _static_gates() -> list[GateRecord]:
    return [
        GateRecord(
            "partner_trial",
            "Prospective partner trial",
            "NOT_RUN",
            "no partner, no live campaign, no cost ledger",
            blocker="business validation needs an owner, a budget and a mature follow-up window",
        ),
    ]


def build_index(root: Path | str = ".") -> EvidenceIndex:
    """Collect artifacts, score gates and derive the release tier."""

    base = Path(root)
    index = EvidenceIndex(
        root=str(base),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        artifacts=_scan_artifacts(base),
        claims=_count_claims(base),
    )
    index.gates = [
        _gate_contracts(_read_json(base / "reports/v4/contracts.json")),
        _gate_mutations(_read_json(base / "reports/v4/challenge_suite.json")),
        _gate_runner(_read_json(base / "reports/v4/run_report.json")),
        _gate_environment(base),
        _gate_coverage(
            _read_json(base / "reports/v4/inference_smoke.json"),
            _best_powered_validity(base),
            _read_json(base / "reports/v4/validity_v09/v09_recruitment.json"),
            _read_json(base / "reports/v4/overlap_boundary/overlap_boundary.json"),
            _read_json(base / "reports/v4/validity_v08/v08_batch_cap.json"),
            root=base,
        ),
        _gate_external_replication(
            _read_json(base / "reports/v4/replication_lenta/external_replication.json")
        ),
        _gate_identification(
            {
                "Orange": _read_json(base / "reports/v4/assignment_audit.json"),
                "Hillstrom": _read_json(base / "reports/v4/assignment_audit_hillstrom.json"),
                "Lenta": _read_json(base / "reports/v4/assignment_audit_lenta.json"),
            }
        ),
        _gate_screening(base, _read_json(base / "reports/screening/screening.json")),
        _gate_deployment(_read_json(base / "reports/deployment/deployment_smoke.json")),
        *_static_gates(),
    ]
    return index


def render_markdown(index: EvidenceIndex) -> str:
    lines = [
        "# Evidence index",
        "",
        f"Generated {index.generated_at} from artifacts on disk. "
        "`NOT_MET` means the gate was defined and has not been satisfied; it is not a "
        "failure, and it is not a pass either.",
        "",
        f"- release tier: **{index.release_tier}**",
        f"- failing gates: {len(index.failing_gates)}",
        "- claim ledger tokens: "
        + ", ".join(f"{state} {count}" for state, count in index.claims.items()),
        "",
        "## Gates",
        "",
        "| Gate | Status | Summary | Blocker |",
        "|---|---|---|---|",
    ]
    for gate in index.gates:
        lines.append(f"| {gate.title} | `{gate.status}` | {gate.summary} | {gate.blocker or '—'} |")
    lines.extend(
        ["", "## Artifacts", "", "| Key | Path | Modified | Fresh vs code |", "|---|---|---|---|"]
    )
    for artifact in index.artifacts:
        if not artifact.exists:
            lines.append(f"| {artifact.key} | `{artifact.path}` | missing | — |")
            continue
        fresh = "stale: " + ", ".join(artifact.producer_newer) if artifact.producer_newer else "ok"
        lines.append(f"| {artifact.key} | `{artifact.path}` | {artifact.modified_at} | {fresh} |")
    blockers = index.tier_blockers()
    if blockers:
        lines.extend(["", "## What the next tier needs", ""])
        for blocker in blockers:
            lines.append(f"- **{blocker['tier']}** / `{blocker['gate']}`: {blocker['reason']}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="reports/v4/evidence_index.json")
    parser.add_argument("--markdown", default="reports/v4/EVIDENCE_INDEX.md")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when a gate is FAIL; off by default because reporting a "
        "failed research gate is this tool's job, not its own failure",
    )
    args = parser.parse_args(argv)

    index = build_index(args.root)
    destination = Path(args.root) / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(index.to_dict(), indent=2), encoding="utf-8")
    (Path(args.root) / args.markdown).write_text(render_markdown(index), encoding="utf-8")

    print(f"release tier: {index.release_tier}")
    for gate in index.gates:
        print(f"  [{gate.status:<9}] {gate.title}: {gate.summary}")
    stale = [artifact.key for artifact in index.artifacts if artifact.is_stale_against_code]
    if stale:
        print(f"artifacts older than their producer module: {', '.join(stale)}")
    for gate in index.failing_gates:
        print(f"GATE FAILED: {gate.title} -- {gate.blocker or gate.summary}")
    print(f"Evidence index: {destination}")
    return 1 if (args.strict and index.failing_gates) else 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
