SELECT 'flow_primary_key_duplicates' AS check_name, count(*) AS failures
FROM (SELECT flow_id FROM fact_network_flow GROUP BY 1 HAVING count(*) > 1)
UNION ALL
SELECT 'incident_primary_key_duplicates', count(*)
FROM (SELECT incident_id FROM fact_incident GROUP BY 1 HAVING count(*) > 1)
UNION ALL
SELECT 'flow_orphan_device', count(*)
FROM fact_network_flow f LEFT JOIN dim_device d USING (device_key) WHERE d.device_key IS NULL
UNION ALL
SELECT 'flow_orphan_site', count(*)
FROM fact_network_flow f LEFT JOIN dim_site s USING (site_key) WHERE s.site_key IS NULL
UNION ALL
SELECT 'flow_orphan_protocol', count(*)
FROM fact_network_flow f LEFT JOIN dim_protocol p USING (protocol_key) WHERE p.protocol_key IS NULL
UNION ALL
SELECT 'invalid_measure_bounds', count(*)
FROM fact_network_flow WHERE bytes < 0 OR packets < 0 OR latency_ms < 0 OR packet_loss_pct < 0 OR packet_loss_pct > 100
UNION ALL
SELECT 'multiple_current_device_rows', count(*)
FROM (SELECT device_id FROM dim_device GROUP BY 1 HAVING sum(CASE WHEN is_current THEN 1 ELSE 0 END) <> 1)
UNION ALL
SELECT 'overlapping_device_versions', count(*)
FROM dim_device a JOIN dim_device b ON a.device_id = b.device_id AND a.device_key < b.device_key
WHERE a.valid_from < coalesce(b.valid_to, TIMESTAMP '9999-12-31')
  AND b.valid_from < coalesce(a.valid_to, TIMESTAMP '9999-12-31');

