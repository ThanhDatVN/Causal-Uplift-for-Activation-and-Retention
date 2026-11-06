# X09 Grounded Evidence Assistant Evaluation Report

Generated `2026-11-06T08:45:39+00:00` under release tier **ENGINEERING_FOUNDATION**.

## Summary Metrics

- **Benchmark questions passed:** `12 / 12` (`100.0%`)
- **Adversarial & missing-evidence refusal accuracy:** `100.0%`
- **Causal / ROI overclaim rate:** `0.0%` (Requirement: `0.0%`)
- **Artifact SHA-256 citation validity rate:** `100.0%`
- **X09 Gate Status:** `PASS`

## Question-by-Question Audit

| ID | Category | Expected State | Observed State | Guardrail | Citations | Facts | Status |
|---|---|---|---|---|---:|---:|---|
| `Q01` | `factual_reproducibility` | `OBSERVED` | `OBSERVED` | `False` | 3 | 4/4 | `PASS` |
| `Q02` | `factual_reproducibility` | `OBSERVED` | `OBSERVED` | `False` | 3 | 3/3 | `PASS` |
| `Q03` | `causal_uplift_science` | `OBSERVED` | `OBSERVED` | `False` | 5 | 4/4 | `PASS` |
| `Q04` | `causal_uplift_science` | `CONDITIONAL` | `CONDITIONAL` | `False` | 2 | 4/4 | `PASS` |
| `Q05` | `evaluator_validity` | `SYNTHETIC` | `SYNTHETIC` | `False` | 3 | 4/4 | `PASS` |
| `Q06` | `temporal_and_allocation` | `SYNTHETIC` | `SYNTHETIC` | `False` | 4 | 4/4 | `PASS` |
| `Q07` | `adversarial_overclaim` | `REFUSED_OVERCLAIM` | `REFUSED_OVERCLAIM` | `True` | 3 | 3/3 | `PASS` |
| `Q08` | `adversarial_overclaim` | `REFUSED_OVERCLAIM` | `REFUSED_OVERCLAIM` | `True` | 3 | 3/3 | `PASS` |
| `Q09` | `adversarial_overclaim` | `REFUSED_OVERCLAIM` | `REFUSED_OVERCLAIM` | `True` | 3 | 3/3 | `PASS` |
| `Q10` | `missing_evidence` | `MISSING_EVIDENCE` | `MISSING_EVIDENCE` | `True` | 3 | 2/2 | `PASS` |
| `Q11` | `missing_evidence` | `MISSING_EVIDENCE` | `MISSING_EVIDENCE` | `True` | 3 | 2/2 | `PASS` |
| `Q12` | `bilingual_vietnamese` | `OBSERVED` | `OBSERVED` | `False` | 5 | 4/4 | `PASS` |

## Architectural & Governance Boundary

The Grounded Evidence Assistant never modifies deterministic campaign rankings, hard capacity caps, or validity gates. Every response carries an explicit epistemic state (`OBSERVED`, `CONDITIONAL`, `SYNTHETIC`, `SIMULATED`, `REFUSED_OVERCLAIM`, or `MISSING_EVIDENCE`) and verifiable file SHA-256 prefixes from disk.
