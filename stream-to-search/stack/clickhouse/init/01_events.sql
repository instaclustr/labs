-- Shared ingestion pipeline (identical for the sync/demo and async/production flows).
--
--   Kafka topic "events"  -->  events_kafka (Kafka engine, the consumer)
--                              --> events_mv (materialized view)
--                                  --> events (MergeTree, the queryable table)
--
-- The queryable `events` table carries the Kafka partition/offset of each row so the
-- synchronous flow can wait for a published batch to become queryable (offset watermark).

CREATE TABLE IF NOT EXISTS events
(
    event_id        UUID,
    entity          String,
    metric          String,
    value           Float64,
    ts              DateTime64(3),
    kafka_partition UInt64,
    kafka_offset    UInt64
)
ENGINE = MergeTree
ORDER BY (entity, metric, ts);

-- The consumer. `kafka_flush_interval_ms` is kept low so the demo feels responsive.
CREATE TABLE IF NOT EXISTS events_kafka
(
    event_id UUID,
    entity   String,
    metric   String,
    value    Float64,
    ts       DateTime64(3)
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list      = 'kafka:9092',
    kafka_topic_list       = 'events',
    kafka_group_name       = 'ch_events',
    kafka_format           = 'JSONEachRow',
    kafka_flush_interval_ms = 500;

-- Pump consumed rows into the queryable table, capturing Kafka virtual columns
-- (_partition / _offset) so we can build an ingestion watermark.
CREATE MATERIALIZED VIEW IF NOT EXISTS events_mv TO events AS
SELECT
    event_id,
    entity,
    metric,
    value,
    ts,
    _partition AS kafka_partition,
    _offset    AS kafka_offset
FROM events_kafka;
