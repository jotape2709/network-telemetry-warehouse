CREATE OR REPLACE TABLE mart_device_daily AS
WITH flow_daily AS (
    SELECT
        date_key,
        device_key,
        site_key,
        count(*) AS flow_count,
        sum(bytes) / 1000000000.0 AS traffic_gb,
        avg(latency_ms) AS avg_latency_ms,
        quantile_cont(latency_ms, 0.95) AS p95_latency_ms,
        avg(packet_loss_pct) AS avg_packet_loss_pct,
        avg(CASE WHEN throughput_mbps >= s.capacity_mbps * 0.8 THEN 1.0 ELSE 0.0 END) AS saturation_rate
    FROM fact_network_flow f
    JOIN dim_site s USING (site_key)
    GROUP BY 1, 2, 3
),
incident_daily AS (
    SELECT
        date_key,
        device_key,
        site_key,
        count(*) AS incident_count,
        sum(downtime_minutes) AS downtime_minutes
    FROM fact_incident
    GROUP BY 1, 2, 3
)
SELECT
    f.*,
    coalesce(i.incident_count, 0) AS incident_count,
    coalesce(i.downtime_minutes, 0.0) AS downtime_minutes,
    greatest(0.0, 100.0
        - least(f.p95_latency_ms, 200.0) * 0.22
        - least(f.avg_packet_loss_pct, 3.0) * 12.0
        - least(coalesce(i.downtime_minutes, 0.0), 240.0) * 0.08
    ) AS service_quality_score
FROM flow_daily f
LEFT JOIN incident_daily i USING (date_key, device_key, site_key);

CREATE OR REPLACE TABLE mart_site_daily AS
WITH flow_site_daily AS (
    SELECT
        date_key,
        site_key,
        count(*) AS flow_count,
        sum(bytes) / 1000000000.0 AS traffic_gb,
        avg(latency_ms) AS avg_latency_ms,
        quantile_cont(latency_ms, 0.95) AS p95_latency_ms,
        avg(packet_loss_pct) AS avg_packet_loss_pct
    FROM fact_network_flow
    GROUP BY 1, 2
),
incident_site_daily AS (
    SELECT
        date_key,
        site_key,
        count(*) AS incident_count,
        sum(downtime_minutes) AS observed_downtime_minutes
    FROM fact_incident
    GROUP BY 1, 2
)
SELECT
    f.*,
    coalesce(i.incident_count, 0) AS incident_count,
    coalesce(i.observed_downtime_minutes, 0.0) AS observed_downtime_minutes
FROM flow_site_daily f
LEFT JOIN incident_site_daily i USING (date_key, site_key);
