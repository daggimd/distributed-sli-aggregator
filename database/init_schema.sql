-- 1. Master Service Registry & Service Level Objective (SLO) Targets
CREATE TABLE IF NOT EXISTS services_master (
    service_id VARCHAR(32) PRIMARY KEY,
    service_name VARCHAR(64) NOT NULL UNIQUE,
    tier VARCHAR(16) NOT NULL CHECK (tier IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    target_slo_percent NUMERIC(5, 2) NOT NULL DEFAULT 99.90,
    target_p95_ms INTEGER NOT NULL DEFAULT 200,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Raw High-Throughput Telemetry Logs
CREATE TABLE IF NOT EXISTS raw_telemetry (
    request_id UUID PRIMARY KEY,
    service_id VARCHAR(32) NOT NULL REFERENCES services_master(service_id) ON DELETE CASCADE,
    endpoint VARCHAR(128) NOT NULL,
    http_status SMALLINT NOT NULL,
    latency_ms NUMERIC(8, 2) NOT NULL,
    timestamp_utc TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_telemetry_svc_time 
ON raw_telemetry (service_id, timestamp_utc DESC);

CREATE INDEX IF NOT EXISTS idx_raw_telemetry_status 
ON raw_telemetry (http_status) 
WHERE http_status >= 500;

-- 3. Pre-Aggregated Hourly Analytical Mart
CREATE TABLE IF NOT EXISTS service_hourly_rollups (
    rollup_id BIGSERIAL PRIMARY KEY,
    service_id VARCHAR(32) NOT NULL REFERENCES services_master(service_id) ON DELETE CASCADE,
    timestamp_hour TIMESTAMP WITH TIME ZONE NOT NULL,
    total_requests INTEGER NOT NULL DEFAULT 0,
    successful_requests INTEGER NOT NULL DEFAULT 0,
    failed_requests INTEGER NOT NULL DEFAULT 0,
    avg_latency_ms NUMERIC(8, 2) NOT NULL,
    p90_latency_ms NUMERIC(8, 2) NOT NULL,
    p95_latency_ms NUMERIC(8, 2) NOT NULL,
    p99_latency_ms NUMERIC(8, 2) NOT NULL,
    availability_percent NUMERIC(5, 2) NOT NULL,
    slo_met BOOLEAN NOT NULL,
    CONSTRAINT uq_service_hour UNIQUE (service_id, timestamp_hour)
);

-- Seed Initial Microservices Fleet
INSERT INTO services_master (service_id, service_name, tier, target_slo_percent, target_p95_ms)
VALUES 
    ('svc-auth-01', 'User Authentication Service', 'CRITICAL', 99.95, 120),
    ('svc-cat-02', 'Product Catalog Service', 'HIGH', 99.90, 180),
    ('svc-chk-03', 'Google Checkout Engine', 'CRITICAL', 99.99, 250),
    ('svc-rec-04', 'Search Recommendation API', 'MEDIUM', 99.50, 350)
ON CONFLICT (service_id) DO NOTHING;
