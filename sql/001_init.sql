-- Sentinel schema v1
-- One file, idempotent, runnable via psql or asyncpg.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Agents registered with Sentinel. JWTs identify (agent_id, bu, role).
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    bu              TEXT NOT NULL,
    role            TEXT NOT NULL,
    declared_goal   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Policy documents indexed by PolicyPipe. cache_id / gemini_file_id populated
-- after ingestion. domain_tags drives loader.fetch().
CREATE TABLE IF NOT EXISTS policy_docs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    version         TEXT NOT NULL,
    effective_date  DATE,
    superseded_by   UUID REFERENCES policy_docs(id),
    gemini_file_id  TEXT,
    cache_id        TEXT,
    cache_expires_at TIMESTAMPTZ,
    domain_tags     TEXT[] NOT NULL DEFAULT '{}',
    summary         TEXT,
    source_sha256   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
CREATE INDEX IF NOT EXISTS policy_docs_tags_idx ON policy_docs USING GIN (domain_tags);

-- Hash-chained audit ledger. prev_hash binds each receipt to the prior receipt
-- for the same agent. args_hash and rationale_hash keep PII out of plaintext.
CREATE TABLE IF NOT EXISTS audit_receipts (
    receipt_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id            TEXT NOT NULL REFERENCES agents(agent_id),
    session_id          TEXT NOT NULL,
    tool                TEXT NOT NULL,
    args_hash           TEXT NOT NULL,
    decision            TEXT NOT NULL CHECK (decision IN ('allow','deny','rewrite')),
    decided_by          TEXT NOT NULL CHECK (decided_by IN ('static','flash','pro')),
    confidence          REAL,
    escalated           BOOLEAN NOT NULL DEFAULT false,
    rationale           TEXT NOT NULL,
    rationale_hash      TEXT NOT NULL,
    policy_versions_used JSONB NOT NULL DEFAULT '[]'::jsonb,
    gemini_cache_ids    TEXT[] NOT NULL DEFAULT '{}',
    gemini_trace_id     TEXT,
    prev_hash           TEXT,
    self_hash           TEXT NOT NULL,
    signature           TEXT NOT NULL,
    latency_ms          INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_receipts_agent_time_idx ON audit_receipts (agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_receipts_session_idx ON audit_receipts (session_id);
CREATE INDEX IF NOT EXISTS audit_receipts_tool_idx ON audit_receipts (tool);

-- One cost_event per receipt. Rolled up nightly into bu_spend_daily.
CREATE TABLE IF NOT EXISTS cost_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id      UUID NOT NULL REFERENCES audit_receipts(receipt_id),
    bu              TEXT NOT NULL,
    tool            TEXT NOT NULL,
    base_cost_usd   NUMERIC(10,6) NOT NULL DEFAULT 0,
    gemini_cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
    total_cost_usd  NUMERIC(10,6) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cost_events_bu_time_idx ON cost_events (bu, created_at DESC);

-- Seed three demo agents that map to the demo script.
INSERT INTO agents (agent_id, name, bu, role, declared_goal) VALUES
  ('agent-sales-01',   'Sales Researcher',  'Sales',         'researcher', 'Find competitor pricing for Q3 strategy review.'),
  ('agent-finance-01', 'Finance Analyst',   'Finance',       'analyst',    'Prepare monthly close package; do not exfiltrate customer PII.'),
  ('agent-ops-01',     'Customer Ops Bot',  'CustomerOps',   'ops',        'Process customer refund requests within approval limits.')
ON CONFLICT (agent_id) DO NOTHING;
