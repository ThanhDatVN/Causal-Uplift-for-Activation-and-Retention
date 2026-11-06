# Planner packet replay check

**Run:** 29 September 2026, local Windows Python 3.11.9. The eight `DEMO-*` customers are fictional test records. This packet was generated through the real local model bundle and the preview API. It demonstrates the packet schema and replay command; it was not downloaded from a browser or used to execute a campaign.

- [Packet](DEMO_PACKET.json): `packet_version=1`, model version `1.0.0`, model bundle SHA-256 `7e14cf28518edf4494ae039fba9a29eea4d11f510946865023c5d6a48746caa7`, eight input rows, two selected contacts.
- Browser-compatible `JSON.stringify(input_records)` SHA-256: `586334884c51b53ca5f35f14091c4e1855c0cc40948d86be423ad2ad8a70040a`.
- [Replay result](REPLAY_RESULT.json): `MATCH`, zero differences, eight customers.
- [Wrong-bundle check](WRONG_MODEL_RESULT.json): `MISMATCH`, including `model_sha256`, when the independently retrained quick bundle is substituted even though both bundles report version `1.0.0`.

Reproduce from the repository root:

```powershell
python -m telco_churn.replay --packet reports/v4/planner_replay/DEMO_PACKET.json --model artifacts/models/champion.joblib
```

The match depends on the model bundle and code version. The packet is not signed. It records a simulated decision under assumed economics; it is not evidence of a treatment effect or measured financial return.
