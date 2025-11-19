-- Migration 002: Enhance request tracking for analytics
-- Phase 1, Task 3: Instrument request loop
-- Date: 2024-11-19

-- Add session tracking (gig identifier)
ALTER TABLE requests ADD COLUMN session_id TEXT;

-- Add status tracking (pending/fulfilled/cancelled)
ALTER TABLE requests ADD COLUMN status TEXT DEFAULT 'pending';

-- Add tip amount for future tipping feature
ALTER TABLE requests ADD COLUMN tip_amount REAL DEFAULT 0.0;

-- Add played timestamp
ALTER TABLE requests ADD COLUMN played_at TIMESTAMP;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_requests_tenant_status ON requests(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_requests_session ON requests(session_id);
CREATE INDEX IF NOT EXISTS idx_requests_timestamp ON requests(request_time);

-- Notes:
-- session_id: Unique identifier for each gig/performance session
--             Format: tenant_id-YYYYMMDD-HHMMSS or similar
-- status: 'pending' (default) | 'fulfilled' (played) | 'cancelled'
-- tip_amount: Amount in dollars/euros (0.0 for no tip)
-- played_at: Timestamp when marked as fulfilled

