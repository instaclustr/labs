# Build an anomaly-detection app with `instaclustr_sdk` — a step-by-step guide

This walkthrough takes you from an empty stack to a working anomaly-detection app for a fleet
of temperature sensors. You'll publish events, detect anomalies both **synchronously** (great for
demos and tests) and **asynchronously** (the production pattern), and finally have an **AI agent
explain** the anomalies using a **RAG** knowledge base. Each step links to the section of
[`ARCHITECTURE.md`](../ARCHITECTURE.md) that explains what's happening under the hood.

**The scenario.** A handful of temperature sensors normally read ~20 °C. Two things can go wrong,
and the interesting part is that a plain statistical rule flags *both* — but only one is a real
problem:

| Failure | What it looks like | Verdict |
|---|---|---|
| Disconnect | one wild reading (~95 °C) | benign — the sensor briefly dropped out |
| Overheating | many readings sustained ~34 °C | genuine — real heat |

By the end you'll see the same z-score algorithm flag both, and the AI layer correctly tell them apart.

Each step has a runnable script in this folder. Run them from the **repository root**.

---

## Step 0 — Start the stack

Follow steps 1–2 of the [README Quickstart](../README.md#quickstart): start the stack and
`pip install -e ".[ai]"`. Then set your API keys for Step 4:

```bash
export ANTHROPIC_API_KEY=...               # required for Step 4
export VOYAGE_API_KEY=...                  # optional; better embeddings for RAG
```

Confirm ClickHouse created the eight tables and views listed in
[`ARCHITECTURE.md`](../ARCHITECTURE.md) §2:

```bash
docker exec s2s-clickhouse clickhouse-client -q "SHOW TABLES"
```

---

## Step 1 — Publish events onto the stream

**Goal:** prove the stream side works end to end.

```bash
python demo/01_hello_publish.py
```

**You'll see** something like:

```
published 5 events; watermark offsets = {0: 4}
anomalies among these normal readings: 0  (expected 0)
Stream side works. Next: demo/02_detect_sync.py
```

**How it works.** `stream.publish(events)` is **synchronous**: it blocks until the broker acks and
returns a **`Watermark`**, the Kafka offsets this batch wrote. From Kafka, ClickHouse's Kafka engine
lands the events in the queryable `events` table ([`ARCHITECTURE.md`](../ARCHITECTURE.md) §3a).

---

## Step 2 — Synchronous detection (the demo flow)

**Goal:** publish a healthy history plus one obvious spike, and detect it immediately.

```bash
python demo/02_detect_sync.py
```

**You'll see:**

```
published 601 readings (incl. one 95 C spike on sensor-1)

detected 1 anomaly(ies):
  sensor-1/temperature  value= 95.00  z-score= ...  <-- the spike we injected

Note: the algorithm flagged the spike, but it can't tell you *why*.
```

An extra line or two is normal. A healthy reading occasionally lands past |z| > 3 (the ~0.3% tail
of Gaussian noise), and on a reused stack earlier hits come back too
([`ARCHITECTURE.md`](../ARCHITECTURE.md) §5).

**How it works.** `find_anomalies(wait_for=watermark)` waits until ClickHouse has ingested past the
watermark, then runs the z-score query, so publish → detect is deterministic without a `sleep()`
([`ARCHITECTURE.md`](../ARCHITECTURE.md) §4–5). This is the ideal shape for **demos, notebooks, and
tests**: call and get an answer back.

---

## Step 3 — Asynchronous detection (the production flow)

**Goal:** run detection continuously, the way you would in production.

```bash
python demo/03_detect_async.py        # runs ~40s, then stops
```

**You'll see** a baseline get seeded, then injected spikes surfacing as anomalies from *both*
delivery styles:

```
seeding baseline...
streaming for 40s (detection lags ~5s behind — the MV refresh interval)

  · injected spike on sensor-2
[callback]  sensor-2 value=95.0 z=...
[generator] sensor-2 value=95.0 z=...
  · injected spike on sensor-1
[callback]  sensor-1 value=95.0 z=...
[generator] sensor-1 value=95.0 z=...
[callback]  sensor-2 value=95.0 z=...      (the same sensor-2 spike again, from the next refresh)
[generator] sensor-2 value=95.0 z=...
...
done.
```

**How it works.**
- `await stream.publish_async(events)` publishes **without blocking** the event loop.
- Detection runs **inside ClickHouse**: a refreshable materialized view re-runs the Step 2 rule
  every 5 s and republishes the hits to the Kafka `anomalies` topic
  ([`ARCHITECTURE.md`](../ARCHITECTURE.md) §3b).
- Your app consumes that topic two ways, both shown here:
  - `async for a in search.stream_anomalies():` — an async generator.
  - `search.on_anomaly(callback)` — a background thread that invokes your callback.
- Each spike arrives about 5 s late and **several times**; [`ARCHITECTURE.md`](../ARCHITECTURE.md)
  §9 explains why and what consumers do about it.

> **Troubleshooting:** if the `[callback]`/`[generator]` lines never appear but the `anomalies`
> table is filling (check `docker exec s2s-clickhouse clickhouse-client -q "SELECT count() FROM anomalies"`),
> the ClickHouse → Kafka output MV isn't firing in your build; see
> [`ARCHITECTURE.md`](../ARCHITECTURE.md) §7.

### Watch it live in Grafana (recommended for this step)

The async flow is far more convincing as a live chart than scrolling console lines. The stack
ships an optional Grafana service, pre-provisioned with a ClickHouse datasource and a dashboard:

1. Open **http://localhost:3000** (anonymous admin — no login).
2. Open the **"Anomaly Detection — sensor fleet"** dashboard.
3. Re-run `python demo/03_detect_async.py` and watch the sensor lines move and red anomaly dots
   appear (the dashboard auto-refreshes every 5 s).

The dashboard polls ClickHouse directly: the `events` table for the per-sensor lines and the
`anomalies` table for the red markers. The Kafka `anomalies` topic is for programmatic consumers
like the two above. Provisioning lives in `grafana/`, and the dashboard is editable in place.

---

## Step 4 — Explain anomalies with AI + RAG

**Goal:** turn statistical flags into verdicts. The algorithm flags both a disconnect spike and
a sustained overheating stretch; the AI layer tells them apart.

```bash
python demo/04_explain_with_ai.py
```

**You'll see** two typed verdicts with *different* conclusions — roughly:

```
=== sensor-1-3f9a (single 95 C spike) — explain_anomaly ===
Verdict: benign
Cause: A single 95 C reading with the sensor otherwise in its 18-22 C band matches a disconnect, not real temperature.
Action: Ignore; check the sensor's connection...

=== sensor-2-3f9a (sustained ~34 C) — investigate_anomaly ===
Verdict: genuine
Cause: Recent stats show the mean elevated with many readings in the low-30s: sustained overheating, not a one-off glitch.
Action: Investigate cooling...
```

**How it works.**
- First the script seeds the RAG knowledge base with domain rules (`rag.add_knowledge(...)`): what a
  disconnect looks like vs. what genuine overheating looks like.
- `agent.explain_anomaly(anomaly, remember=True)` judges the disconnect in one Claude call,
  grounded in the retrieved rules, and stores its verdict as a finding.
- `agent.investigate_anomaly(anomaly)` gives Claude tools instead. For the overheating case it pulls
  the sensor's recent stats, sees the sustained elevation, and concludes "genuine".
- Both return a typed `Verdict`; the agent's design is in [`ARCHITECTURE.md`](../ARCHITECTURE.md)
  §3c.
- Each run uses a fresh fleet (`sensor-1-<run id>`, …), so Step 3's spikes stay out of this step's
  per-sensor statistics.

This is the payoff: **same algorithm, two verdicts.** The stream+search layer finds *what* is
unusual; the AI layer, grounded in your domain knowledge, decides whether it *matters*.

---

## Recap — which SDK surface each step used

| Step | You called | SDK surface |
|---|---|---|
| 1 | `stream.setup`, `stream.publish`, `search.setup` | producer + ingestion pipeline |
| 2 | `search.find_anomalies(wait_for=...)` | synchronous detection (watermark wait + on-demand SQL) |
| 3 | `stream.publish_async`, `search.stream_anomalies`, `search.on_anomaly` | async detection (refreshable MV → Kafka topic) |
| 4 | `rag.add_knowledge/retrieve`, `agent.explain_anomaly/investigate_anomaly` | RAG memory + Claude analysis |

## Make it your own

[`ARCHITECTURE.md`](../ARCHITECTURE.md) §8 covers changing the events, the detection rule, the
domain knowledge, and the model, and scaling out.

## Reset

```bash
docker compose down -v      # stop and wipe all data (ClickHouse re-runs the DDL on next up)
```
