# Dependencies

## At a glance

| To use | Install | Python packages | Services | Credentials |
|---|---|---|---|---|
| Core SDK: stream + detect (demo steps 1–3) | `pip install -e .` | `confluent-kafka`, `clickhouse-connect` | Kafka, ClickHouse | — |
| RAG memory (`instaclustr_sdk.rag`) | the core; `[ai]` adds the optional Voyage embedder | `clickhouse-connect` (+ optional `voyageai`) | ClickHouse | optional `VOYAGE_API_KEY` |
| AI agent (`instaclustr_sdk.agent`, demo step 4) | `pip install -e ".[ai]"`, plus a [provider extra](#other-model-providers) for a non-Anthropic model | `pydantic-ai-slim[anthropic]` (+ the provider's) | — (calls the model provider's API) | `ANTHROPIC_API_KEY` for the default model, else the provider's key |
| Live dashboard | nothing; Grafana starts with the stack | — | Grafana + ClickHouse plugin | — |
| Tests | `pip install -e ".[ai,dev]"` | `pytest` | none for unit tests; the stack for integration tests | a configured model for the live agent test (as for the AI agent row) |
| API reference (`scripts/docs.sh`) | `pip install -e ".[ai,docs]"` | `pdoc` | — | — |

## System prerequisites

- **Python ≥ 3.10** (`requires-python = ">=3.10"`; required by `pydantic-ai` and `anthropic` 1.x).
- **Docker + Docker Compose**, or **Podman + podman-compose** — to run the Kafka + ClickHouse
  (+ Grafana) stack. The images in `docker-compose.yml` are fully qualified (`docker.io/...`), so
  Podman pulls them without prompting.
- **Internet access** on first run — to pull the images, install the Grafana ClickHouse plugin, and
  reach the model provider's API and Voyage. The core stream + detect path needs no internet once the
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
| `pydantic-ai-slim[anthropic]` | `>=2.42,<3` | MIT (brings `anthropic` 1.x, MIT) | `agent` | Agent loop, tool calling, typed `Verdict` output, and the Claude client. Pinned below 3 because v2 moves fast.
| `voyageai` | `>=0.3` | MIT | `rag` (optional) | Embeddings via Voyage AI (Anthropic's recommended partner); used only with `VOYAGE_API_KEY` (below). |

### `[dev]` extra

| Package | Version | License | Purpose |
|---|---|---|---|
| `pytest` | `>=7` | MIT | Runs the offline unit tests (`test_agent.py` needs `[ai]`; `test_rag.py` and `test_search.py` don't) and `tests/test_end_to_end.py` (integration; needs the live stack, and a model for its agent test). |
| `pydantic-ai-slim[openai]` | `>=2.42,<3` | MIT (brings `openai`, Apache-2.0) | Lets the cross-provider request-shape test in `test_agent.py` run. |

### `[docs]` extra

| Package | Version | License | Purpose |
|---|---|---|---|
| `pdoc` | `>=16` | MIT-0 (brings Jinja2, MarkupSafe, and Pygments, BSD; `markdown2`, MIT) | Renders the API reference from the docstrings (`scripts/docs.sh`). It imports every module it documents, so it's installed alongside `[ai]`. |

Don't confuse it with `pdoc3`, a separate fork that is AGPL-3.0 and installs under the same `pdoc`
import name.

### Other model providers

The agent runs on any provider Pydantic AI supports. Pick the model with
`INSTACLUSTR_SDK_AGENT_MODEL` (or `agent.setup(model=...)`), install its extra alongside `[ai]`, and
set its credentials:

| Provider | Install | Model name, for example | Credentials |
|---|---|---|---|
| Anthropic (default) | `pip install -e ".[ai]"` | `anthropic:claude-opus-5` | `ANTHROPIC_API_KEY` |
| OpenAI | `pip install -e ".[ai,openai]"` | `openai:gpt-5.2` | `OPENAI_API_KEY` |
| Google Gemini | `pip install -e ".[ai,google]"` | `google:gemini-3-flash-preview` | `GOOGLE_API_KEY` |
| Ollama (local) | `pip install -e ".[ai,openai]"` | `ollama:qwen3` | `OLLAMA_BASE_URL`, e.g. `http://localhost:11434/v1` |
| Any other | `pip install "pydantic-ai-slim[<provider>]"` | see [Pydantic AI's model docs](https://github.com/pydantic/pydantic-ai/blob/main/docs/models/overview.md) | the provider's own |

Verdict quality varies by model. Before relying on a switch, run `scripts/smoke_test.sh`; its live
agent test uses whichever model is configured.

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
| `INSTACLUSTR_SDK_AGENT_MODEL` | choosing the agent's model (optional) | The model `agent.setup()` uses when called without one, e.g. `openai:gpt-5.2`; the default is `anthropic:claude-opus-5`. A non-Anthropic model needs its provider's extra and key instead of `ANTHROPIC_API_KEY` ([Other model providers](#other-model-providers)). |
| `ANTHROPIC_API_KEY` | `instaclustr_sdk.agent` with the default model (Step 4 of the demo) | Read by Pydantic AI's Anthropic provider. For other auth or platforms (Bedrock, Vertex, Foundry), pass your own Pydantic AI `Model` to `agent.setup()`. Without it, the agent can't run; the rest of the SDK is unaffected. |
| `VOYAGE_API_KEY` | `instaclustr_sdk.rag` embeddings (optional) | If set **and** `voyageai` is installed, Voyage is used; otherwise the local fallback embedder runs — lower quality, but no key and no network. |

## Licensing

This project is licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)).

Every direct Python dependency is permissive (Apache-2.0, MIT, or MIT-0), and so are almost all
transitive ones (BSD, ISC, and PSF as well). The exceptions are MPL-2.0, a weak, file-level
copyleft: `certifi` (via `clickhouse-connect`), plus `orjson` and `tqdm` (via `voyageai`); the
`[openai]`, `[google]`, and `[docs]` extras add only permissive packages. Using and
redistributing them unmodified is fine; MPL obligations apply only to changes you make to those
files. Among the infrastructure images, **Grafana is AGPL-3.0** — the only strong-copyleft
component. It's optional (nothing in the SDK depends on it) and using it locally is fine; AGPL
obligations only matter if you redistribute a modified Grafana or offer it to others as a network
service. Kafka and ClickHouse are Apache-2.0.
