CREATE OR REPLACE TABLE dim_date AS
SELECT
    CAST(strftime(full_date, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(full_date AS DATE) AS full_date,
    year(full_date) AS year,
    month(full_date) AS month,
    week(full_date) AS week_of_year,
    dayofweek(full_date) AS day_of_week,
    dayofweek(full_date) IN (0, 6) AS is_weekend
FROM raw_dates;

CREATE OR REPLACE TABLE dim_site AS
SELECT
    CAST(site_key AS INTEGER) AS site_key,
    site_id,
    site_name,
    region,
    CAST(capacity_mbps AS DOUBLE) AS capacity_mbps
FROM raw_sites;

CREATE OR REPLACE TABLE dim_protocol AS
SELECT
    CAST(protocol_key AS INTEGER) AS protocol_key,
    protocol_name,
    CAST(port AS INTEGER) AS port,
    traffic_class
FROM raw_protocols;

CREATE OR REPLACE TABLE dim_device AS
SELECT
    CAST(row_number() OVER (ORDER BY device_id, valid_from) AS BIGINT) AS device_key,
    device_id,
    CAST(site_key AS INTEGER) AS site_key,
    device_type,
    vendor,
    firmware_version,
    CAST(valid_from AS TIMESTAMP) AS valid_from,
    CAST(valid_to AS TIMESTAMP) AS valid_to,
    CAST(is_current AS BOOLEAN) AS is_current
FROM raw_device_history;

