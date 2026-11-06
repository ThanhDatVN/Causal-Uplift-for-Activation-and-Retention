# Deployment smoke

Run 2026-09-21T02:40:23+00:00. Status **PASS** over 12 checks.

These checks say the deployed services answer and agree with the host. They say nothing about whether the research conclusions are stronger: the console serves the same conditional evidence it did before it was containerised.

| Check | Result | Detail |
|---|---|---|
| api_live | pass | GET /health/live -> 200 |
| api_ready | pass | GET /health/ready -> 200 |
| api_model_info | pass | artifact_version 1.0.0 |
| api_rejects_invalid_input | pass | inconsistent phone/lines record -> 422 (expected 422) |
| host_container_parity | pass | max |host - container| = 1.110e-16 over 50 records (tolerance 1e-12) |
| console_live | pass | GET /health/live -> 200 |
| console_ready | pass | GET /health/ready -> 200, release tier ENGINEERING_FOUNDATION |
| console_deployment_info | pass | snapshot cd1feaf04ea897fb, 13/13 artifacts, tier ENGINEERING_FOUNDATION |
| evidence_snapshot_matches_host | pass | container cd1feaf04ea897fb vs host cd1feaf04ea897fb |
| console_exposes_no_write_path | pass | POST /api/evidence -> 405 (expected 405 or 404) |
| locked_decision_reproduced | pass | deployed DR 0.0333090725 vs published 0.0333090725 (gap 1.4e-17), decision no_launch |
| database_schema | pass | 4 tables present; migration applied |
