# stream-to-search

A controlled, demo-able environment showing a **seamlessly simple developer experience**
for problems that need both **real-time event streaming** (Kafka) and **search & analytics**
(ClickHouse). The flagship use case is **anomaly detection**, with an AI layer that explains the
anomalies it finds.

```python
import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search

stream.setup(bootstrap_servers="localhost:29092")
search.setup(host="localhost", port=8123)

wm = stream.publish(my_events)                 # onto Kafka
anomalies = search.find_anomalies(wait_for=wm) # out of ClickHouse
```

> **New here? Start with the guided walkthrough: [`demo/README.md`](demo/README.md)** — it builds
> a full anomaly-detection app step by step (publish → sync detect → async detect → AI-explained findings).

## Two flows, one pipeline

Ingestion is identical for both. Only the *detection & delivery* path differs.

| | Synchronous (demo) | Asynchronous (production) |
|---|---|---|
| Publish | `stream.publish(events)` — blocks until acked | `await stream.publish_async(events)` — non-blocking |
| Detect | `search.find_anomalies(wait_for=wm)` — waits for the batch to be queryable, then runs detection **on demand** | ClickHouse **refreshable materialized view** detects continuously and republishes to a Kafka topic |
| Consume | return value (`list[Anomaly]`) | `async for a in search.stream_anomalies()` **and/or** `search.on_anomaly(cb)` |

How the pieces fit — the pipeline, the offset watermark that makes the sync flow deterministic, and
each flow's caveats — is in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## AI agent + RAG

A z-score flag is a statistical signal, not a verdict. The AI layer has Claude, driven by
[Pydantic AI](https://github.com/pydantic/pydantic-ai), judge whether a flagged point is a genuine
anomaly or a benign artifact, grounded in a RAG knowledge base stored in ClickHouse.

```python
import instaclustr_sdk.rag as rag
import instaclustr_sdk.agent as agent

rag.setup()        # local embedder unless VOYAGE_API_KEY is set
agent.setup()      # Claude Opus 5 via Pydantic AI; uses ANTHROPIC_API_KEY

rag.add_knowledge("Spikes above 90C on sensor-1 are disconnects, not real heat.",
                  kind="domain", entity="sensor-1", metric="temperature")

verdict = agent.explain_anomaly(anomaly, remember=True)  # one call + retrieved context; stores the finding
verdict = agent.investigate_anomaly(anomaly)             # agentic: Claude calls metric-stats + memory-search tools
verdict.verdict                                           # "genuine" | "benign" | "uncertain"
```

How it works: [`ARCHITECTURE.md`](ARCHITECTURE.md) §3c.

## Quickstart

Needs Python 3.10+ and Docker Compose or podman-compose; [`DEPENDENCIES.md`](DEPENDENCIES.md) has
the details. With Podman, use `podman-compose` and `podman exec` wherever the commands below say
`docker compose` and `docker exec`.

```bash
# 1. Start Kafka + ClickHouse (+ Grafana)
docker compose up -d
curl -s localhost:8123/ping                      # -> Ok. once it's ready

# 2. Install the SDK with the AI extras
pip install -e ".[ai]"

# 3. Run the examples
python examples/demo_sync.py                     # publish, then detect synchronously
python examples/prod_async.py                    # continuous async flow (Ctrl-C to stop)
export ANTHROPIC_API_KEY=...                     # for the agent; VOYAGE_API_KEY optionally improves RAG
python examples/agent_explain.py                 # detect -> explain -> remember

# (optional) watch the raw anomalies topic
docker exec s2s-kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --topic anomalies --bootstrap-server localhost:29092 --from-beginning
```

An optional live dashboard runs at http://localhost:3000; Step 3 of
[`demo/README.md`](demo/README.md) shows it in action.

### Tests

```bash
pip install -e ".[ai,dev]"
pytest                           # offline unit tests (no API key, Kafka, or ClickHouse)
RUN_INTEGRATION=1 pytest         # + integration tests against a running stack
scripts/smoke_test.sh            # everything, from a fresh stack (wipes stack data)
```

The smoke test starts Kafka + ClickHouse from scratch, then runs the unit tests, the demo
walkthrough, and the integration tests. With `ANTHROPIC_API_KEY` set (in the environment or a
`.env` file) it also makes a few cents of live Claude calls; `--no-ai` skips them.

## Layout

```
docker-compose.yml           Kafka (KRaft, single node) + ClickHouse + optional Grafana
clickhouse/init/             DDL auto-run on first ClickHouse start
  01_events.sql              events table + Kafka engine + ingestion MV
  02_anomalies.sql           anomalies table + refreshable detect MV + Kafka output MV
  03_knowledge.sql           RAG knowledge base (vector-embedded domain context + findings)
instaclustr_sdk/
  stream.py                  setup(), publish() [sync], publish_async()
  search.py                  setup(), find_anomalies() [sync], stream_anomalies()/on_anomaly(), metric_stats()
  detection.py               the z-score detection SQL (source of truth for the sync path)
  agent.py                   AI agent on Pydantic AI: explain_anomaly() [single call], investigate_anomaly() [agentic] -> Verdict
  rag.py                     RAG memory over ClickHouse: add_knowledge/add_finding/retrieve
  models.py                  Event, Anomaly, Watermark
  config.py                  StreamConfig / SearchConfig
examples/                    demo_sync.py, prod_async.py, agent_explain.py
demo/                        guided step-by-step walkthrough (start here)
grafana/                     optional live dashboard (datasource + dashboard provisioning)
tests/                       test_agent.py, test_rag.py, test_search.py (offline); test_end_to_end.py (RUN_INTEGRATION=1)
scripts/smoke_test.sh        fresh stack + demos + all tests, end to end
ARCHITECTURE.md              how it works: data flow, design decisions, extending it, limitations & caveats
DEPENDENCIES.md              Python packages, container images, credentials, licensing
```

## License

Apache-2.0 — see [`LICENSE`](LICENSE). Dependency licenses are in
[`DEPENDENCIES.md`](DEPENDENCIES.md#licensing).
