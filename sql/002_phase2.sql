-- Phase 2 schema additions. Idempotent (safe to re-run).

-- A) Key rotation — every receipt carries the key_id that signed it,
-- so we can rotate the HMAC key without invalidating history.
ALTER TABLE audit_receipts
    ADD COLUMN IF NOT EXISTS key_id TEXT NOT NULL DEFAULT 'k1';

-- B) Observe-only mode — record agent activity without gating it.
-- Useful for organizations migrating from "log everything" to "enforce".
ALTER TABLE audit_receipts
    ADD COLUMN IF NOT EXISTS observed_only BOOLEAN NOT NULL DEFAULT FALSE;

-- C) Multi-policy conflict flag — Pro escalation may detect conflicts
-- between two policies that both apply to one call.
ALTER TABLE audit_receipts
    ADD COLUMN IF NOT EXISTS policy_conflict BOOLEAN NOT NULL DEFAULT FALSE;

-- D) Receipt anchoring — a periodic Merkle root over receipts is
-- emitted and (optionally) anchored on-chain. anchored_at marks
-- the row as "part of an anchored batch".
ALTER TABLE audit_receipts
    ADD COLUMN IF NOT EXISTS anchored_at TIMESTAMPTZ;

-- E) Anchor batches — one row per anchoring event with the Merkle
-- root and the underlying anchor pointer (URL, txn hash, etc.).
CREATE TABLE IF NOT EXISTS anchor_batches (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merkle_root       TEXT NOT NULL,
    range_start_ts    TIMESTAMPTZ NOT NULL,
    range_end_ts      TIMESTAMPTZ NOT NULL,
    receipt_count     INTEGER NOT NULL,
    anchor_target     TEXT,             -- 'local' | 'opentimestamps' | 'arc' | etc.
    anchor_pointer    TEXT,             -- file path, OTS proof, txn hash
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS anchor_batches_range_idx
    ON anchor_batches (range_end_ts DESC);

-- F) Policy authoring — `source_text` lets us round-trip authored
-- policies without re-rendering a PDF.
ALTER TABLE policy_docs
    ADD COLUMN IF NOT EXISTS source_text TEXT;

-- G) Slack alerts table — one row per fired alert, lets the dashboard
-- show whether a particular receipt has been alerted on.
CREATE TABLE IF NOT EXISTS alert_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id   UUID NOT NULL REFERENCES audit_receipts(receipt_id),
    target       TEXT NOT NULL,        -- 'slack' | 'teams' | 'pagerduty'
    sent_ok      BOOLEAN NOT NULL,
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS alert_events_receipt_idx
    ON alert_events (receipt_id);
