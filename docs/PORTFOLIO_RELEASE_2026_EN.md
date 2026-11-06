# Retention Decision Lab: local portfolio release

**Status on 2 October 2026:** a reviewable local prototype for junior ML Engineer, AI Engineer, and Data Scientist interviews. The planner and evaluator are separate demonstrations. The refreshed [evidence index](../reports/v4/EVIDENCE_INDEX.md), generated in the research-lock virtual environment, computes `ENGINEERING_FOUNDATION`; its independent causal evaluator gate is `NOT_MET` and its partner-trial gate is `NOT_RUN`. The [prospective R1 repair study](../reports/v4/r1_repair_20261002/REPORT.md) failed five candidate coverage gates. This repository does not establish a deployed retention intervention or measured return on investment.

The [current verification record](../reports/v4/portfolio_completion/FINAL_VERIFICATION_20261002.md) gives the final suite, browser, wheel, research-lock, and remaining-work status. The [implementation record](../reports/v4/portfolio_completion/IMPLEMENTATION_REPORT.md) and [30 September local reproducibility audit](../reports/v4/portfolio_completion/REPRODUCIBILITY_AUDIT_20260930.md) give the earlier data, model, and benchmark checksums. The earlier [verification record](../reports/v4/PORTFOLIO_RELEASE_VERIFICATION.md) remains archived.

## What an interviewer can run

From the repository root with Python 3.11:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/reproduce_benchmark.py --fetch
$env:TELCO_MODEL_PATH = "artifacts/reproduced_quick/champion.joblib"
.\.venv\Scripts\python.exe -m uvicorn telco_churn.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/planner/` and choose **Try the guided demo**. The eight customers are fictional. For your own snapshot, use **Download CSV template** and replace its fictional row before uploading. The one-row template previews successfully but permits zero contacts under the default 20% hard cap. Check the snapshot preview, set a 25% contact cap, a money cap of 30, and a 30-day contact cooldown. Preview the plan, inspect skipped-customer reasons and the three save-rate scenarios, then export the selected CSV, full audit CSV, and evidence JSON. The reproduction command verifies the IBM download and writes `RUN_MANIFEST.json` with the producer source, data, split, model, report and environment hashes. Its default quick run is a smoke reproduction, not a replacement for the archived full benchmark. On Unix, use `.venv/bin/python` and `export TELCO_MODEL_PATH=artifacts/reproduced_quick/champion.joblib`.

The planner calls `/v2/campaigns/preview` and exports packet version 2. Its `churn_risk_probability` field includes [structured score scope](RISK_FIELD_MIGRATION_EN.md) stating that the time horizon is unvalidated. The evidence JSON contains the input rows, analyst assumptions, complete ranked decisions, a model version, and the model bundle SHA-256. Replay it against the same model bundle:

```powershell
.\.venv\Scripts\python.exe -m telco_churn.replay --packet retention-draft-evidence.json --model artifacts/reproduced_quick/champion.joblib
```

`MATCH` means that this code and bundle reproduce the exported decision fields. `MISMATCH` reports changed inputs, model, or decisions. Replay is deterministic verification; the JSON is not digitally signed and does not prove that a campaign ran. The packet contains the uploaded customer rows, so use fictional or approved data for demonstrations and handle real exports as sensitive files.

A [checked fictional packet and replay result](../reports/v4/planner_replay/REPLAY_REPORT.md) are included as an example.

For the full frozen IBM protocol, run `python scripts/reproduce_benchmark.py --full --output reports/v4/reproduced_full --model-dir artifacts/reproduced_full`. The 30 September final-source full run took about 6 minutes 43 seconds on CPU; the quick run took about 2 minutes 24 seconds. No GPU or Kaggle session is needed for these baselines. The [full manifest](../reports/v4/reproduced_full/RUN_MANIFEST.json) and [comparison](../reports/v4/portfolio_completion/FULL_BENCHMARK_COMPARISON.md) show that all eight model metric rows and all 1,409 test predictions matched the archived run numerically. The hard contact scenario now uses `floor` at 10% capacity, so its 140-contact value table differs from the older 141-contact table; the ranking diagnostic retains its historical `ceil` convention.

For a real-browser check with the local API running, install the optional browser dependency and Chromium, then run the [browser smoke script](../scripts/browser_smoke.py):

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[browser]"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/browser_smoke.py --model artifacts/reproduced_quick/champion.joblib
```

The script checks desktop and mobile flows, CSV validation, a no-contact draft, export, and replay. It writes screenshots and a JSON result under `reports/v4/browser_smoke/`. The [latest Chrome v2 run](../reports/v4/browser_smoke_v2_20261002/result.json) passed ten checks with no page errors. A separate [real-browser template roundtrip](../reports/v4/template_flow/result.json) confirms keyboard download, upload, preview, and the one-row hard-cap explanation. These checks do not replace a screen-reader or first-user usability session.

For a separate **development-only** causal-method comparison, fetch the checksum-pinned Hillstrom file and run:

```powershell
.\.venv\Scripts\python.exe -m telco_churn.hillstrom_data fetch
.\.venv\Scripts\python.exe scripts/reproduce_screening.py
```

The [development manifest](../reports/v4/screening_reproduction/RUN_MANIFEST.json) records the input, split, source and report hashes. It also records that the evaluator variant was selected after inspecting earlier results and needs independent confirmation. The three-fold screen does not establish a population interval or open the one-use confirmation comparison.

The later [R1/R4 research execution summary](RESEARCH_EXECUTION_2026_EN.md) reports failed transfer coverage, the nested Hillstrom learner comparison, and two synthetic allocator protocols. Its failed and inconclusive gates are part of the portfolio result. None of them changes the planner into a treatment-effect model or validates its illustrative money values.

The [full IBM comparison protocol](FULL_BENCHMARK_REPRODUCTION_PROTOCOL_EN.md) records agreement tolerances against the archived benchmark before inspecting the new full report. The [first-user study script](USABILITY_SESSION_PROTOCOL_EN.md) is prepared for five sessions and a screen-reader pass; no participant results are claimed yet.

## Evidence and claims

| Component | Demonstrated claim | Boundary |
|---|---|
| IBM risk model | Frozen sample risk ranking and calibration metrics in the [benchmark report](../reports/benchmark/BENCHMARK_REPORT.md). | Static IBM sample has no validated 30-day horizon or treatment outcomes. `/v2` uses `churn_risk_probability` with explicit scope; `/v1` retains the legacy `risk_30d` field. |
| Planner | Hard contact and money caps, supplied eligibility and cooldown, stable ranking, sensitivity to assumed save rate, replayable exports. | Save rate, margin, offer cost, and value are user assumptions. The planner does not estimate individual treatment effects. |
| Causal development studies | The [research review](PROJECT_REVIEW_AND_EXPANSION_2026_EN.md) compares randomized and synthetic studies, including negative results. | The selected evaluator has a fresh diagnostic, but independent policy confirmation and a partner trial are absent. The engineering tier does not grant a causal claim. |
| [Fresh evaluator](../reports/v4/fresh_evaluator/FRESH_EVALUATOR_REPORT.md) | Six known-truth conditions, two generator families, 2,000 worlds per condition, plus sharp-null checks. | Generator validation is diagnostic. It cannot establish transport to a real customer population. |

The analyst must approve any draft. The application has no login, persistent campaign service, delivery integration, or real consent/eligibility source. Run it on localhost for the portfolio demonstration.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m telco_churn.environment --lock locks/research.lock.txt --output reports/v4/environment_locked.json
```

The historical research lock pins 180 packages and is checked in its own environment. Run `telco_churn.evidence` with that same interpreter: a system Python with different `setuptools` will correctly fail the environment gate. Generic CI runs its tests without the `locked_environment` marker because a normal `pip install -e ".[dev]"` does not promise the historical package versions. To validate the exact lock, install `locks/research.lock.txt` in an isolated Python 3.11 environment first. A pass on a different interpreter is not an exact-lock pass.

## Five-minute demonstration

1. State the decision: propose whom to contact under a hard cap; choose no contact if the assumed value is non-positive.
2. Load the fictional cohort, change capacity and cooldown, and show why individual customers were excluded.
3. Move the save-rate assumption and show how the draft value changes. Say plainly that these are scenarios, not confidence intervals.
4. Export and replay the packet. Show a changed row returning `MISMATCH`.
5. Open the [evidence index](../reports/v4/EVIDENCE_INDEX.md): engineering gates support `ENGINEERING_FOUNDATION`, while causal evaluator confirmation is `NOT_MET` and a partner trial is `NOT_RUN`.

## What remains before a real pilot

Collect time-stamped customer eligibility and consent, randomized offer/control assignment, actual costs, delivery logs, and mature outcomes from a partner. Preregister an estimand, capacity, policy, interval method, and launch gate. Validate assignment integrity, calibration, policy value, uncertainty, fairness-relevant slices, and operational monitoring on held-out data. Run first-user usability sessions and check keyboard and screen-reader interactions in a real browser before calling the interface production ready. GPU training is unnecessary for the current tabular baselines and known-truth simulations; prepare a Kaggle job only for a specific comparison whose compute need is demonstrated.
