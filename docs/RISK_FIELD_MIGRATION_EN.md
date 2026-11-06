# Risk field migration contract

**Status:** `/v2` API, planner exports, and packet replay implemented and locally verified on 2 October 2026. `/v1` and packet version 1 remain supported.

The legacy `/v1` response uses `risk_30d` for historical compatibility. The IBM sample has no validated 30-day prediction horizon, so consumers must read this as a static sample churn score. Both preview responses and exported evidence packets include the full model bundle SHA-256; that digest is the immutable artifact identifier even when multiple bundles share version `1.0.0`.

## Compatible path

1. `/v1` and packet version 1 remain deterministic and retain `risk_30d` for existing consumers. The UI continues to disclose the unvalidated horizon.
2. `/v2/predict` and `/v2/campaigns/preview` use `churn_risk_probability` and a structured `score_scope`: `dataset`, `label_description`, `horizon_status: unvalidated`, `model_sha256`, and `training_protocol`. No numeric horizon is populated. `/v2` refuses a bundle without a SHA-256 identifier.
3. The planner now exports packet version 2 with the new field and scope. Replay dispatches by packet version, compares the bundle digest and scope, and rejects unknown versions. Frozen fictional [v1](../tests/fixtures/replay_packet_v1.json) and [v2](../tests/fixtures/replay_packet_v2.json) packets guard compatibility.
4. [API tests](../tests/test_api.py) and [replay tests](../tests/test_replay.py) verify v1/v2 numeric parity, request validation, digest mismatch, and the renamed field. A [Chrome desktop/mobile run](../reports/v4/browser_smoke_v2_20261002/result.json) completed the v2 preview, export, and replay flow. `/v1` is **not deprecated**; any deprecation requires an observed consumer transition window.

Do not backfill a 30-day clock from IBM's static records. A dated score requires a source dataset with timestamped feature snapshots and outcomes, a declared observation window, point-in-time validation, and calibration on the intended population.

Replay verifies the exported `input_records` serialization as well as the decisions. Keep the original packet file: sorting the keys of its nested customer objects changes the input checksum even if the values look identical. The frozen test packets preserve the exported key order.
