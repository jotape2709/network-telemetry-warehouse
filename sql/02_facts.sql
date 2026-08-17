CREATE OR REPLACE TABLE fact_network_flow AS
SELECT
    f.flow_id,
    CAST(f.observed_at AS TIMESTAMP) AS observed_at,
    CAST(strftime(f.observed_at, '%Y%m%d') AS INTEGER) AS date_key,
    d.device_key,
    CAST(f.site_key AS INTEGER) AS site_key,
    CAST(f.protocol_key AS INTEGER) AS protocol_key,
    CAST(f.bytes AS BIGINT) AS bytes,
    CAST(f.packets AS BIGINT) AS packets,
    CAST(f.duration_seconds AS DOUBLE) AS duration_seconds,
    CAST(f.throughput_mbps AS DOUBLE) AS throughput_mbps,
    CAST(f.latency_ms AS DOUBLE) AS latency_ms,
    CAST(f.packet_loss_pct AS DOUBLE) AS packet_loss_pct
FROM raw_flows f
JOIN dim_device d
  ON f.device_id = d.device_id
 AND f.observed_at >= d.valid_from
 AND (d.valid_to IS NULL OR f.observed_at < d.valid_to);

CREATE OR REPLACE TABLE fact_incident AS
SELECT
    i.incident_id,
    CAST(i.started_at AS TIMESTAMP) AS started_at,
    CAST(i.ended_at AS TIMESTAMP) AS ended_at,
    CAST(strftime(i.started_at, '%Y%m%d') AS INTEGER) AS date_key,
    d.device_key,
    CAST(i.site_key AS INTEGER) AS site_key,
    i.severity,
    i.category,
    CAST(i.downtime_minutes AS DOUBLE) AS downtime_minutes
FROM raw_incidents i
JOIN dim_device d
  ON i.device_id = d.device_id
 AND i.started_at >= d.valid_from
 AND (d.valid_to IS NULL OR i.started_at < d.valid_to);

