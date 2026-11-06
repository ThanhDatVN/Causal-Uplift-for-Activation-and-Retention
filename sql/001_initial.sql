CREATE TABLE IF NOT EXISTS model_versions (
    model_version TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    artifact_uri TEXT NOT NULL,
    dataset_sha256 CHAR(64) NOT NULL,
    split_sha256 CHAR(64) NOT NULL,
    metadata JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_runs (
    run_id UUID PRIMARY KEY,
    model_version TEXT NOT NULL REFERENCES model_versions(model_version),
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prediction_point DATE NOT NULL,
    input_rows INTEGER NOT NULL CHECK (input_rows >= 0),
    schema_failures INTEGER NOT NULL DEFAULT 0 CHECK (schema_failures >= 0)
);

CREATE TABLE IF NOT EXISTS churn_scores (
    run_id UUID NOT NULL REFERENCES scoring_runs(run_id),
    customer_key_hash CHAR(64) NOT NULL,
    risk_30d DOUBLE PRECISION NOT NULL CHECK (risk_30d BETWEEN 0 AND 1),
    scored_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, customer_key_hash)
);

CREATE TABLE IF NOT EXISTS campaign_decisions (
    campaign_id UUID NOT NULL,
    run_id UUID NOT NULL,
    customer_key_hash CHAR(64) NOT NULL,
    selected BOOLEAN NOT NULL,
    policy_version TEXT NOT NULL,
    scenario JSONB NOT NULL,
    simulated_expected_value NUMERIC,
    PRIMARY KEY (campaign_id, customer_key_hash),
    FOREIGN KEY (run_id, customer_key_hash)
        REFERENCES churn_scores(run_id, customer_key_hash)
);

CREATE INDEX IF NOT EXISTS churn_scores_rank_idx
    ON churn_scores (run_id, risk_30d DESC);

