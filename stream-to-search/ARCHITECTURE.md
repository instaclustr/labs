# Architecture

## 1. Overview

The system demonstrates a seamless path from **event streaming** (Kafka) to **search & analytics**
(ClickHouse), with **anomaly detection** as the use case and an **AI + RAG layer** that explains
the anomalies. The guiding principle is **one shared pipeline, two delivery modes**: ingestion is
identical for everyone; only *how anomalies are detected and delivered* differs between a
synchronous "demo" mode and an asynchronous "production" mode.

Everything a developer touches is the Python SDK (`instaclustr_sdk`); everything else is infrastructure the
SDK talks to.

## 2. Components

| Component | What it is | Where |
|---|---|---|
| **`instaclustr_sdk.stream`** | Kafka producer — sync + async publish | `instaclustr_sdk/stream.py` |
| **`instaclustr_sdk.search`** | ClickHouse queries + anomalies-topic consumer + `metric_stats` | `instaclustr_sdk/search.py` |
| **`instaclustr_sdk.detection`** | the z-score detection SQL (source of truth for the sync path) | `instaclustr_sdk/detection.py` |
| **`instaclustr_sdk.agent`** | AI analysis of anomalies via Claude, on Pydantic AI; returns a typed `Verdict` | `instaclustr_sdk/agent.py` |
| **`instaclustr_sdk.rag`** | vector memory (domain context + past findings) in ClickHouse | `instaclustr_sdk/rag.py` |
| **`instaclustr_sdk.models` / `instaclustr_sdk.config`** | `Event`/`Anomaly`/`Watermark`; config dataclasses | `instaclustr_sdk/models.py`, `config.py` |
| **Kafka** | event transport; topics `events` and `anomalies` | single-node KRaft |
| **ClickHouse** | ingestion, detection, analytics, and the vector store | tables + materialized views |
| **Grafana** | optional live dashboard | `grafana/` |

### ClickHouse objects (created by `clickhouse/init/*.sql`)

| Object | Kind | Role |
|---|---|---|
| `events` | MergeTree | queryable event table; carries `kafka_partition` / `kafka_offset` |
| `events_kafka` | Kafka engine | consumes the `events` topic |
| `events_mv` | materialized view | `events_kafka` → `events` (+ virtual offset columns) |
| `anomalies` | ReplacingMergeTree | detected anomalies; repeats of an event collapse at merge time |
| `anomalies_detect_mv` | **refreshable** MV | runs the detection SQL every 5s, `APPEND`s hits |
| `anomalies_kafka_out` | Kafka engine | producer to the `anomalies` topic |
| `anomalies_out_mv` | materialized view | `anomalies` → `anomalies_kafka_out` |
| `knowledge` | MergeTree | RAG store: text + `Array(Float32)` embedding |

## 3. Data flow

### 3a. Ingestion (shared by both modes)

```
producer app ──Event──▶ instaclustr_sdk.stream.publish / publish_async
                              │
                              ▼
                     Kafka topic "events"
                              │
                              ▼
              events_kafka (Kafka engine)
                              │  events_mv
                              ▼
                     events (MergeTree)   ◀── each row tagged with its Kafka _partition/_offset
```

Nothing here changes between demo and production. The producer serializes `Event`s as JSONEachRow;
ClickHouse's Kafka table engine consumes them and a materialized view lands them in the queryable
`events` table, tagging each row with its Kafka offset (the basis for the sync watermark).

### 3b. Detection & delivery — the fork

```
                              events (MergeTree)
        ┌───────────────────────────┴───────────────────────────────┐
  SYNC (demo)                                                  ASYNC (production)
  search.find_anomalies(wait_for=wm):                   anomalies_detect_mv (REFRESH EVERY 5s):
    1. poll until ingested offsets ≥ watermark            runs the SAME z-score logic
    2. run detection.zscore_sql() on demand                        │ APPEND
    3. return list[Anomaly]                                        ▼
                                                        anomalies (ReplacingMergeTree)
                                                                   │ anomalies_out_mv
                                                                   ▼
                                                          Kafka topic "anomalies"
                                                                   │
                                        search.stream_anomalies()  /  search.on_anomaly(cb)
```

- **Sync** is *pull, on demand*: deterministic and immediate — ideal for demos, notebooks, tests.
- **Async** is *push, continuous*: detection runs inside ClickHouse on a timer and results are
  republished to Kafka for any number of downstream consumers — the production pattern.
- Both evaluate the **same** detection rule (see §5).
- **Async delivers repeats.** Each refresh re-emits every hit from the last minute, so one spike
  reaches the `anomalies` topic up to about 12 times (60 s window ÷ 5 s refresh).
  `ReplacingMergeTree` collapses the table's copies at merge time, but the Kafka output MV forwards
  every insert, so consumers should deduplicate on `event_id`.

### 3c. AI + RAG analysis

```
  Anomaly ─▶ instaclustr_sdk.agent.explain_anomaly / investigate_anomaly
                     │                         │
      retrieve ◀─────┤                         ├──▶ Pydantic AI Agent ──▶ Claude (Opus 5, adaptive thinking)
                     ▼                         │      ▲   tools (investigate_anomaly only):
        instaclustr_sdk.rag (knowledge table,  │      ├── search.metric_stats(entity, metric)
        cosineDistance search)  ◀── add_knowledge / add_finding
```

- `explain_anomaly` retrieves relevant context from `rag` and asks Claude once (grounded generation).
- `investigate_anomaly` gives Claude tools (`metric_stats`, `rag.retrieve`) and lets it drive the
  loop — deciding what evidence to gather before ruling.
- Both are runs of one Pydantic AI agent (the second with the toolset) and return a typed
  `Verdict`: `genuine` / `benign` / `uncertain`, plus cause and recommended action.
- Verdicts can be written back to `rag` as findings (`add_finding`), so the memory compounds.

## 4. The watermark (how sync stays consistent)

The ClickHouse Kafka engine consumes in batches, so a row published "now" isn't queryable for a
short interval. Rather than `sleep()`, the SDK uses an **offset watermark**:

1. `stream.publish(events)` returns a `Watermark` — the max Kafka offset per partition it wrote.
2. `search.find_anomalies(wait_for=wm)` polls `SELECT max(kafka_offset) ... GROUP BY kafka_partition`
   until every partition has caught up to the watermark, *then* runs the query.

This is what makes a `publish() → find_anomalies()` loop deterministic without faking it. The async
path skips the wait entirely (it never blocks on a specific batch).

## 5. Detection logic — one rule, two homes

The rule is a **z-score**: a point is anomalous when its value is more than `threshold` (default 3)
standard deviations from the trailing per-`(entity, metric)` mean.

- **Sync path:** `instaclustr_sdk/detection.py::zscore_sql()` builds the query, run on demand by `find_anomalies`.
- **Async path:** the *same* expression lives in `clickhouse/init/02_anomalies.sql` as the body of
  the refreshable MV.

The expression is kept identical by intent (cross-referenced in comments). What differs is which
points each path returns:

- The async MV emits only points from the last minute, so each refresh stays cheap.
- The sync query checks every row in `events` against the last hour's statistics, so on a
  long-lived stack it also returns earlier hits. Filter with `entity=`, as the tests do, or use
  fresh entity names, as `demo/04` does.

This duplication is a deliberate trade (§7); to change the rule, edit both homes (§8).

## 6. Deployment topology

`docker-compose.yml` runs three services on one network:

```
        host                         docker network
  localhost:29092 ─┐        ┌─ kafka:9092  (Kafka, KRaft single node)
  localhost:8123  ─┼─ SDK ──┤
  localhost:9000  ─┘        ├─ clickhouse:9000/8123  (auto-runs clickhouse/init/*.sql)
  localhost:3000  ── UI ────┴─ grafana:3000  (queries clickhouse:9000)
```

Kafka advertises dual listeners so both the host-side SDK (`localhost:29092`) and the ClickHouse
container (`kafka:9092`) can reach it. ClickHouse executes the DDL in `clickhouse/init/` on first
start. Grafana auto-provisions its datasource + dashboard from `grafana/`.

## 7. Design decisions & trade-offs

- **One pipeline, two modes.** Ingestion is shared; the sync/async split is purely in detection +
  delivery. Keeps the mental model small and the API symmetric.
- **Watermark over sleep.** Makes the demo flow honest and deterministic; costs a few cheap polls.
- **ClickHouse-native async detection.** A refreshable MV + Kafka-output MV means *no extra service*
  runs the continuous detector. The trade: it relies on the output MV firing on the rows a
  refreshable `APPEND` inserts. That holds on the pinned ClickHouse 24.9, and
  `scripts/smoke_test.sh` checks it end to end. On a build where it doesn't, the fallback would be
  a small Python service that reads `anomalies` and publishes to the topic; this repo doesn't
  include one. The costs, latency and repeated delivery, are in §9.
- **Detection SQL duplicated** in Python and SQL. Chosen for clarity over a templating layer; the
  rule is small and cross-referenced. Revisit if it grows.
- **RAG memory inside ClickHouse.** Reuses the same datastore (no vector DB to run); `cosineDistance`
  brute-forces over a demo-sized table. For scale, add a ClickHouse vector index.
- **Pluggable embeddings.** Voyage AI when a key is present, else a local fallback — the demo runs
  offline, and swapping embedders is a one-function change (all rows must share one embedder).
- **AI at the right altitude.** `explain_anomaly` is a single call (analysis is a single-call task);
  `investigate_anomaly` is the genuinely agentic path where tools earn their keep.
- **Pydantic AI for the model-facing half only.** `instaclustr_sdk` owns Kafka and ClickHouse;
  Pydantic AI owns every model call, and two functions exposed as tools are the only crossing. 

## 8. Extensibility & scaling

- **Different events:** change `Event.to_json_row()` (`instaclustr_sdk/models.py`) and the columns in
  `01_events.sql`. The Grafana dashboard's SQL uses the demo's fixed sensor names (`sensor-1..3`);
  generalize it for your own entities.
- **Different detection:** edit `detection.zscore_sql()` and mirror it in `02_anomalies.sql`.
  Quantiles, moving averages, and `seriesDecomposeSTL` are all native to ClickHouse.
- **Different domain knowledge:** seed your own `rag.add_knowledge(...)` rules for your metrics;
  `demo/04_explain_with_ai.py` shows the pattern.
- **Different model or provider:** `agent.setup(model=...)` accepts any Pydantic AI model name or
  `Model` instance.
- **Scale out:** add Kafka partitions and ClickHouse replicas — the SDK API is unchanged (the
  watermark is already per-partition).
- **More consumers:** anything can subscribe to the `anomalies` topic; the Python consumers are just
  two clients of it.

## 9. Limitations & caveats

- **A demonstration, not a production deployment:** single node, no auth, no retention policy.
- **Async latency** is about the 5 s refresh interval plus Kafka round-trips. Tune `REFRESH EVERY`
  in `02_anomalies.sql`.
- **Async repeats** each hit on the `anomalies` topic (§3b).
- **Sync returns earlier hits** on a long-lived stack (§5). Reset the stack to start clean.
- **RAG** brute-forces `cosineDistance` over a demo-sized table, and every row must come from the
  same embedder (§7).

The two runtime assumptions, the async output-MV hop and live Claude calls through Pydantic AI, are
exercised end to end on a fresh stack by `scripts/smoke_test.sh`. The request the agent sends is
also covered offline by `tests/test_agent.py`, against a mocked transport.
