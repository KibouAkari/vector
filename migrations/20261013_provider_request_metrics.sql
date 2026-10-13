-- Review and apply separately before enabling telemetry.
-- Does not contain prompts, responses or credentials.

CREATE TABLE IF NOT EXISTS provider_request_metrics (
  id TEXT PRIMARY KEY,
  provider_config_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  adapter TEXT,
  success BOOLEAN NOT NULL,
  elapsed_ms INTEGER NOT NULL CHECK (elapsed_ms >= 0),
  http_status INTEGER,
  error_category TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cached_tokens INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS
  provider_request_metrics_provider_time_idx
ON provider_request_metrics(
  provider_config_id,
  model,
  created_at DESC
);

CREATE INDEX IF NOT EXISTS
  provider_request_metrics_created_idx
ON provider_request_metrics(created_at);
