# stream-to-search

A controlled, demo-able environment showing a **seamlessly simple developer experience**
for problems that need both **real-time event streaming** (Kafka) and **search & analytics**
(ClickHouse). The flagship use case is **anomaly detection**, with an AI agent that explains the
anomalies it finds.

Using it looks like this, once the [Installing](#installing) below has the stack running:

```python
import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search
import instaclustr_sdk.rag as rag
import instaclustr_sdk.agent as agent

stream.setup(bootstrap_servers="localhost:29092")
search.setup(host="localhost", port=8123)
rag.setup()
agent.setup() 

# Stream events
wm = stream.publish(my_events)                 # onto Kafka

# Search anomalies
anomalies = search.find_anomalies(wait_for=wm) # out of ClickHouse

# Agent investigates
rag.add_knowledge("Spikes above 90C on sensor-1 are disconnects, not real heat.",
                  kind="domain", entity="sensor-1", metric="temperature")

anomaly = anomalies[0]                                  # a hit from search.find_anomalies() above
verdict = agent.explain_anomaly(anomaly, remember=True) # one call + retrieved context; stores the finding
verdict = agent.investigate_anomaly(anomaly)            # the model calls metric-stats + memory-search tools
verdict.verdict                                         # "genuine" | "benign" | "uncertain"
```

> **New here? Start with the guided walkthrough: [`demo/README.md`](demo/README.md)** — it builds
> a full anomaly-detection app step by step (publish → sync detect → async detect → AI-explained findings).

## Installing

You need **Python 3.10+** and a container runtime with Compose:
[Docker with Docker Compose](https://docs.docker.com/compose/install/), or
[Podman](https://podman.io/docs/installation) with
[`podman-compose`](https://pypi.org/project/podman-compose/) (`pip install podman-compose`). With
Podman, use `podman-compose` and `podman exec` wherever the commands below say `docker compose` and
`docker exec`.

```bash
# from the repo root
# 1. Install the Python dependencies into a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[ai]"                           # the SDK plus the AI agent and RAG extras

# 2. Start Kafka + ClickHouse (+ Grafana)
docker compose up -d
curl -s localhost:8123/ping                      # -> Ok. once it's ready
```

Other installs: 
- `pip install -e .` for just the core SDK (streaming and detection, no AI),
- `".[ai,dev]"` to run the [tests](#tests), and 
- `".[ai,openai]"` or `".[ai,google]"` to run the agent on [another model provider](DEPENDENCIES.md#other-model-providers).

[`DEPENDENCIES.md`](DEPENDENCIES.md) lists every package, image, and credential.

## Using the SDK

### Data flows

Ingestion is identical for both. Only the *detection & delivery* path differs.

| | Synchronous (demo) | Asynchronous (production) |
|---|---|---|
| Publish | blocks until acked | non-blocking |
| Detect | waits for the batch to be queryable, then runs detection **on demand** | ClickHouse **refreshable materialized view** detects continuously and republishes to a Kafka topic |
| Consume | return value (`list[Anomaly]`) | `async for a in search.stream_anomalies()` **and/or** `search.on_anomaly(cb)` |

How the pieces fit — the pipeline, the offset watermark that makes the sync flow deterministic, and
each flow's caveats — is in [`ARCHITECTURE.md`](ARCHITECTURE.md).

### AI agent + RAG

A z-score flag is a statistical signal, not a verdict. The AI layer has an LLM (Claude by
default, or any provider [Pydantic AI](https://github.com/pydantic/pydantic-ai) supports) judge
whether a flagged point is a genuine anomaly or a benign artifact, grounded in a RAG knowledge base
stored in ClickHouse.

How it works: [`ARCHITECTURE.md`](ARCHITECTURE.md) §3c. Using OpenAI, Gemini, Ollama, or another
provider: [`DEPENDENCIES.md`](DEPENDENCIES.md#other-model-providers). 

## Tests

```bash
pip install -e ".[ai,dev]"
pytest                           # offline unit tests (no API key, Kafka, or ClickHouse)
RUN_INTEGRATION=1 pytest         # + integration tests against a running stack
scripts/smoke_test.sh            # everything, from a fresh stack (wipes stack data)
```

The smoke test starts Kafka + ClickHouse from scratch, then runs the unit tests, the demo
walkthrough, and the integration tests. With a model configured (`ANTHROPIC_API_KEY`, or
`INSTACLUSTR_SDK_AGENT_MODEL` plus its provider's key, in the environment or a `.env` file) it also
makes a few cents of live model calls; `--no-ai` skips them.

## License

Apache-2.0 — see [`LICENSE`](LICENSE). Dependency licenses are in
[`DEPENDENCIES.md`](DEPENDENCIES.md#licensing).
