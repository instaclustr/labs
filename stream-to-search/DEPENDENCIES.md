# Dependencies

Everything the SDK and the demo need, and when. The design goal is a small core: the
streaming + detection path needs only two Python packages and the container stack; the AI layer
is additive and the RAG memory works offline without any extra API key.

## At a glance

| To use | Install | Python packages | Services | Credentials |
|---|---|---|---|---|
| Core SDK: stream + detect (demo steps 1–3) | `pip install -e .` | `confluent-kafka`, `clickhouse-connect` | Kafka, ClickHouse | — |
| RAG memory (`instaclustr_sdk.rag`) | the core; `[ai]` adds the optional Voyage embedder | `clickhouse-connect` (+ optional `voyageai`) | ClickHouse | optional `VOYAGE_API_KEY` |
| AI agent (`instaclustr_sdk.agent`, demo step 4) | `pip install -e ".[ai]"` | `pydantic-ai-slim[anthropic]` | — (calls the Anthropic API) | `ANTHROPIC_API_KEY` |
| Live dashboard | nothing; Grafana starts with the stack | — | Grafana + ClickHouse plugin | — |
| Tests | `pip install -e ".[ai,dev]"` | `pytest` | none for unit tests; the stack for integration tests | `ANTHROPIC_API_KEY` for the live agent test |

## System prerequisites

- **Python ≥ 3.10** (`requires-python = ">=3.10"`; required by `pydantic-ai` and `anthropic` 1.x).
- **Docker + Docker Compose**, or **Podman + podman-compose** — to run the Kafka + ClickHouse
  (+ Grafana) stack. The images in `docker-compose.yml` are fully qualified (`docker.io/...`), so
  Podman pulls them without prompting.
- **Internet access** on first run — to pull the images, install the Grafana ClickHouse plugin, and
  reach the Anthropic / Voyage APIs. The core stream + detect path needs no internet once the
  images are pulled.

## Python packages

Declared in `pyproject.toml`.

### Core (always installed)

| Package | Version | License | Used by | Purpose |
|---|---|---|---|---|
| `confluent-kafka` | `>=2.3` | Apache-2.0 (bundles `librdkafka`, BSD-2-Clause) | `stream`, `search` | Kafka producer/consumer. Wheels bundle `librdkafka` on common platforms — no separate system library needed in the usual case. |
| `clickhouse-connect` | `>=0.7` | Apache-2.0 | `search`, `rag` | ClickHouse HTTP client (queries, inserts). |

### `[ai]` extra (AI agent + better RAG embeddings)

| Package | Version | License | Used by | Purpose |
|---|---|---|---|---|
| `pydantic-ai-slim[anthropic]` | `>=2.42,<3` | MIT (brings `anthropic` 1.x, MIT) | `agent` | Agent loop, tool calling, typed `Verdict` output, and the Claude client. Pinned below 3 because v2 moves fast. See [`design/pydantic-ai-agent.md`](design/pydantic-ai-agent.md). |
| `voyageai` | `>=0.3` | MIT | `rag` (optional) | Embeddings via Voyage AI (Anthropic's recommended partner); used only with `VOYAGE_API_KEY` (below). |

### `[dev]` extra

| Package | Version | License | Purpose |
|---|---|---|---|
| `pytest` | `>=7` | MIT | Runs the offline unit tests (`test_agent.py` needs `[ai]`; `test_rag.py` and `test_search.py` don't) and `tests/test_end_to_end.py` (integration; needs the live stack, and `ANTHROPIC_API_KEY` for its agent test). |

### Standard library only

`instaclustr_sdk/models.py`, `config.py`, and `detection.py` have no third-party dependencies
(dataclasses, `uuid`, `datetime`; `detection.py` just builds SQL strings). `rag.py`'s local
fallback embedder uses only `hashlib`/`math`/`re`.

> **Import-time note.** `import instaclustr_sdk` (and the core demos) pull in only `stream`,
> `search`, `detection`, `models` — so they need just the two core packages. `agent` and `rag` are
> **not** imported by the package `__init__`; `pydantic-ai` is only needed once you explicitly
> `import instaclustr_sdk.agent`, and `voyageai` only once `instaclustr_sdk.rag` picks the Voyage
> embedder.

## Infrastructure services (container images)

Pinned in `docker-compose.yml`.

| Service | Image | License | Role | Notes |
|---|---|---|---|---|
| Kafka | `apache/kafka:3.8.0` | Apache-2.0 | event streaming | Single-node KRaft (no ZooKeeper). |
| ClickHouse | `clickhouse/clickhouse-server:24.9` | Apache-2.0 | search / analytics / vector store | **24.9+ required** — the async path uses refreshable materialized views. |
| Grafana | `grafana/grafana:11.3.0` | **AGPL-3.0** | optional live dashboard | Installs `grafana-clickhouse-datasource` (Apache-2.0) at startup (needs internet on first `up`). |

Implicit infra dependency: ClickHouse's built-in **Kafka table engine** connects ClickHouse to
Kafka (`kafka:9092` on the compose network). No connector/service to install.

## External APIs & credentials

| Variable | Required for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | `instaclustr_sdk.agent` (Step 4 of the demo) | Read by Pydantic AI's Anthropic provider (the default `agent.setup()` model). For other auth or platforms (Bedrock, Vertex, Foundry), pass your own Pydantic AI `Model` to `agent.setup()`. Without it, the agent can't run; the rest of the SDK is unaffected. |
| `VOYAGE_API_KEY` | `instaclustr_sdk.rag` embeddings (optional) | If set **and** `voyageai` is installed, Voyage is used; otherwise the local fallback embedder runs — lower quality, but no key and no network. |

## Licensing

This project is licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)).

Every direct Python dependency is permissive (Apache-2.0 or MIT), and so are almost all transitive
ones (BSD, ISC, and PSF as well). The exceptions are MPL-2.0, a weak, file-level copyleft:
`certifi` (via `clickhouse-connect`), plus `orjson` and `tqdm` (via `voyageai`). Using and
redistributing them unmodified is fine; MPL obligations apply only to changes you make to those
files. Among the infrastructure images, **Grafana is AGPL-3.0** — the only strong-copyleft
component. It's optional (nothing in the SDK depends on it) and using it locally is fine; AGPL
obligations only matter if you redistribute a modified Grafana or offer it to others as a network
service. Kafka and ClickHouse are Apache-2.0.
