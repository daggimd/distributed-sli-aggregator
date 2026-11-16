-- 1. Populate Hourly Analytical Rollups from Raw Telemetry
INSERT INTO service_hourly_rollups (
    service_id,
    timestamp_hour,
    total_requests,
    successful_requests,
    failed_requests,
    avg_latency_ms,
    p90_latency_ms,
    p95_latency_ms,
    p99_latency_ms,
    availability_percent,
    slo_met
)
SELECT 
    r.service_id,
    DATE_TRUNC('hour', r.timestamp_utc) AS timestamp_hour,
    COUNT(*) AS total_requests,
    COUNT(*) FILTER (WHERE r.http_status < 500) AS successful_requests,
    COUNT(*) FILTER (WHERE r.http_status >= 500) AS failed_requests,
    ROUND(AVG(r.latency_ms), 2) AS avg_latency_ms,
    ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY r.latency_ms)::NUMERIC, 2) AS p90_latency_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY r.latency_ms)::NUMERIC, 2) AS p95_latency_ms,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY r.latency_ms)::NUMERIC, 2) AS p99_latency_ms,
    ROUND((COUNT(*) FILTER (WHERE r.http_status < 500)::NUMERIC / COUNT(*)) * 100, 2) AS availability_percent,
    ((COUNT(*) FILTER (WHERE r.http_status < 500)::NUMERIC / COUNT(*)) * 100 >= s.target_slo_percent) AS slo_met
FROM raw_telemetry r
JOIN services_master s ON r.service_id = s.service_id
GROUP BY r.service_id, DATE_TRUNC('hour', r.timestamp_utc), s.target_slo_percent
ON CONFLICT (service_id, timestamp_hour) DO UPDATE SET
    total_requests = EXCLUDED.total_requests,
    successful_requests = EXCLUDED.successful_requests,
    failed_requests = EXCLUDED.failed_requests,
    avg_latency_ms = EXCLUDED.avg_latency_ms,
    p90_latency_ms = EXCLUDED.p90_latency_ms,
    p95_latency_ms = EXCLUDED.p95_latency_ms,
    p99_latency_ms = EXCLUDED.p99_latency_ms,
    availability_percent = EXCLUDED.availability_percent,
    slo_met = EXCLUDED.slo_met;

-- 2. Live View: SRE Error Budget & Burn Rate Calculation (48-Hour Window)
CREATE OR REPLACE VIEW vw_slo_error_budget AS
WITH service_summary AS (
    SELECT 
        s.service_id,
        s.service_name,
        s.tier,
        s.target_slo_percent,
        s.target_p95_ms,
        COALESCE(SUM(h.total_requests), 0) AS total_requests,
        COALESCE(SUM(h.failed_requests), 0) AS failed_requests,
        ROUND(AVG(h.p95_latency_ms), 2) AS avg_p95_latency_ms,
        ROUND(MAX(h.p99_latency_ms), 2) AS peak_p99_latency_ms
    FROM services_master s
    LEFT JOIN service_hourly_rollups h ON s.service_id = h.service_id
    GROUP BY s.service_id, s.service_name, s.tier, s.target_slo_percent, s.target_p95_ms
)
SELECT 
    service_id,
    service_name,
    tier,
    target_slo_percent,
    target_p95_ms,
    total_requests,
    failed_requests,
    CASE 
        WHEN total_requests = 0 THEN 100.00
        ELSE ROUND(((total_requests - failed_requests)::NUMERIC / total_requests) * 100, 3)
    END AS actual_availability_percent,
    avg_p95_latency_ms,
    peak_p99_latency_ms,
    ROUND((100.0 - target_slo_percent), 3) AS allowed_error_percent,
    CASE 
        WHEN total_requests = 0 THEN 0.000
        ELSE ROUND((failed_requests::NUMERIC / total_requests) * 100, 3)
    END AS observed_error_percent,
    CASE 
        WHEN total_requests = 0 OR (100.0 - target_slo_percent) = 0 THEN 0.00
        ELSE ROUND(
            ((failed_requests::NUMERIC / total_requests) * 100) / (100.0 - target_slo_percent),
            2
        )
    END AS error_budget_burn_rate
FROM service_summary;
