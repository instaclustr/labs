-- Asynchronous / production detection path + dual sink.
--
--   events (MergeTree)
--     --> anomalies_detect_mv (REFRESHABLE MV, runs the z-score detection on a timer)
--         --> anomalies (ReplacingMergeTree, the queryable sink)
--             --> anomalies_out_mv (materialized view)
--                 --> anomalies_kafka_out (Kafka engine)  --> Kafka topic "anomalies"
--
-- The detection SQL below is the SAME z-score logic as instaclustr_sdk/detection.py::zscore_sql().
-- The synchronous flow runs that query on demand; here it runs on a timer for the
-- continuous production flow. Keep the two in sync if you change the detection rule.

-- Refreshable materialized views are gated behind this setting on 24.9.
SET allow_experimental_refreshable_materialized_view = 1;

CREATE TABLE IF NOT EXISTS anomalies
(
    event_id    UUID,
    entity      String,
    metric      String,
    value       Float64,
    ts          DateTime64(3),
    zscore      Float64,
    detected_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(detected_at)
ORDER BY (entity, metric, event_id);   -- de-dupes rows re-emitted across refreshes, at merge time

-- Recompute recent anomalies every 5s and APPEND them. ReplacingMergeTree collapses the table's
-- dupes at merge time, but anomalies_out_mv forwards every re-append to Kafka, so the topic
-- carries each hit repeatedly; consumers deduplicate on event_id.
-- Baseline stats (mean/stddev) are computed over a 1h window per (entity, metric);
-- only points from the last minute are emitted so each refresh stays cheap.
CREATE MATERIALIZED VIEW IF NOT EXISTS anomalies_detect_mv
REFRESH EVERY 5 SECOND
APPEND TO anomalies AS
WITH stats AS
(
    SELECT
        entity,
        metric,
        avg(value)       AS mu,
        stddevPop(value) AS sigma
    FROM events
    WHERE ts > now() - INTERVAL 1 HOUR
    GROUP BY entity, metric
)
SELECT
    e.event_id,
    e.entity,
    e.metric,
    e.value,
    e.ts,
    (e.value - s.mu) / nullIf(s.sigma, 0) AS zscore
FROM events AS e
INNER JOIN stats AS s USING (entity, metric)
WHERE abs((e.value - s.mu) / nullIf(s.sigma, 0)) > 3
  AND e.ts > now() - INTERVAL 1 MINUTE;

-- Producer side: republish every anomaly row to the Kafka "anomalies" topic so
-- downstream services (and the Python async consumer) can subscribe.
CREATE TABLE IF NOT EXISTS anomalies_kafka_out
(
    event_id UUID,
    entity   String,
    metric   String,
    value    Float64,
    ts       DateTime64(3),
    zscore   Float64
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list  = 'anomalies',
    kafka_group_name  = 'ch_anomalies_out',  -- required by the Kafka engine; unused for producing
    kafka_format      = 'JSONEachRow';

CREATE MATERIALIZED VIEW IF NOT EXISTS anomalies_out_mv TO anomalies_kafka_out AS
SELECT event_id, entity, metric, value, ts, zscore
FROM anomalies;
