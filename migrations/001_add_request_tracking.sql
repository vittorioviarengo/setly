-- Migration: Add tracking columns to requests table
-- Purpose: Enable metrics for request loop (conversion rate, tips, gig tracking)
-- Phase 1, Task 3: Instrument Request Loop

-- Add session_id to track which "gig" or session a request belongs to
-- This allows musicians to see "requests this evening" vs all-time
ALTER TABLE requests ADD COLUMN session_id TEXT DEFAULT 'default';

-- Add status to track request lifecycle
-- Values: 'pending', 'played', 'skipped', 'cancelled'
ALTER TABLE requests ADD COLUMN status TEXT DEFAULT 'pending';

-- Add played_at timestamp to track when song was actually played
ALTER TABLE requests ADD COLUMN played_at TIMESTAMP NULL;

-- Add tip_amount for future tipping feature
-- NULL means no tip, 0 means explicitly $0 tip, >0 means tip amount in cents
ALTER TABLE requests ADD COLUMN tip_amount INTEGER NULL;

-- Add indexes for performance (requests will be queried often)
CREATE INDEX IF NOT EXISTS idx_requests_tenant_status ON requests(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_requests_session ON requests(session_id);
CREATE INDEX IF NOT EXISTS idx_requests_played_at ON requests(played_at);

-- Notes:
-- - session_id can be generated per-gig by musician (e.g., "2025-01-15-evening")
-- - status transitions: pending -> played/skipped/cancelled
-- - played_at is set when musician marks song as played
-- - tip_amount in cents (e.g., 500 = $5.00)

