# Architecture: Governed Technology-Company Research Agents

## 1. Purpose and how to use this reference

This project demonstrates an agentic research system that combines technology-company news, SEC filing context, and current market information. A News Expert and a Financial Expert own separate domains; an Orchestrator delegates work, evaluates completion, and composes the result. The system can relate reported company developments to financial evidence, but does not establish that a news event caused a financial outcome.

The **Mixture of Experts (MoE)** pattern here operates at the application level: requests are routed to independently governed specialist agents. It is not an implementation of sparse neural-network MoE layers. The **Orchestrator reinforcement loop** means bounded runtime feedback and completion decisions; this repository does not train a routing policy or update model weights during requests.

Use this document as an architecture and source-navigation reference for coding agents, CLI assistants, plugins, and Agent Skills. It is not an installable plugin manifest or a `SKILL.md` entry point. Read the system contract first, then use the task map to open only the implementation files relevant to the requested change.

**Source-of-truth order:** executable implementation and configuration loaders, then Makefiles and dependency declarations, then this document and other explanatory material. Inspect function bodies rather than trusting comments when they disagree. Examples below describe the inspected implementation, not guarantees about an arbitrary later revision.

Paths are relative to the repository root containing `news_agent/`, `financials_agent/`, and `orchestrator_agent/`. If these components have been moved, locate the named modules and symbols in the current checkout; do not recreate old directories to match this document. The inspected source snapshot does not contain Dockerfiles, Compose definitions, datasets, model weights, or test directories.

## 2. System contract

| Concern | Architectural rule |
|---|---|
| Authority | Application code constrains routing, source categories, tool selection, and release; model output is a proposal, not permission. |
| Domain ownership | News owns company developments and reporting; Financial owns filing analysis, public-security identity, and market information. |
| Delegation | The Orchestrator calls specialists over A2A. It does not query their OpenSearch indices or MCP tools directly. |
| Planning versus generation | Nemotron proposes plans and completion decisions and supplies advisory review; Qwen generates evidence-grounded prose. These roles have separate model gateways. |
| Evidence ownership | Specialists assign evidence identifiers and render source metadata. Models may reference registered evidence, not invent its provenance. |
| Current versus historical data | Corpus retrieval and live tools remain separate evidence channels, even when both contribute to one answer. |
| Bounded execution | Orchestration and correction attempts have explicit limits. No open-ended autonomous execution loop is implemented. |
| Identity | The Orchestrator supports one primary company per request; Financial uses a user-supplied or approved-resolver ticker, not a model-invented symbol. |
| Failure | Preserve explicit failure, evidence-gap, clarification, and withholding outcomes instead of generating unsupported replacement facts. |

These rules describe the default configuration, with all three governance check categories enabled. They are application-level controls, not a substitute for authentication, authorization, network isolation, or exhaustive factual verification.

### Runtime topology

```text
Client / CLI
  -> Orchestrator :10000  [OpenAI-compatible chat-completions subset]
       -> News Expert :9001  [A2A]
            -> OpenSearch :9200 / techcomp-vector-chunks
            -> News MCP :8765/mcp -> current-news provider
       -> Financial Expert :9002  [A2A]
            -> OpenSearch :9200 / financial-filings-vector-chunks
            -> Financial MCP :8766/mcp -> market-data provider

All three agents -> planning/review model :8002/v1
All three agents -> answer-generation model :8001/v1
Specialist RAG pipelines -> local embedding model
```

Default model identifiers are `nvidia/Nemotron-Orchestrator-8B`, `Qwen/Qwen2.5-7B-Instruct`, and `Qwen/Qwen3-Embedding-0.6B`. These are configuration defaults, not proof that particular weights are installed. The local model servers have their own artifact-path settings, and agents can target external compatible endpoints.

**Source:** [News settings](news_agent/src/common/config.py), [Financial settings](financials_agent/src/common/config.py), [Orchestrator settings](orchestrator_agent/src/host_agent/config.py), and [`create_routing_agent`](orchestrator_agent/src/host_agent/routing_agent.py).

## 3. Task-to-source map

Open the listed files before implementing the corresponding component. The specialists intentionally have separate packages and contracts; there is no shared universal agent base class.

| Task | Start here | Main symbols or contracts |
|---|---|---|
| Change client-facing HTTP behavior | [Orchestrator entry point](orchestrator_agent/src/host_agent/__main__.py), [client](orchestrator_agent/client.py) | `ChatCompletionRequest`, `create_app`, `_session_id` |
| Change routing or identity policy | [Policy manager](orchestrator_agent/src/host_agent/policy_manager.py), [routing workflow](orchestrator_agent/src/host_agent/routing_agent.py) | `NewsFinancePolicyManager.assess`, `validate_plan`, `_canonicalize_specialist_requests` |
| Change orchestration contracts or model calls | [Models](orchestrator_agent/src/host_agent/models.py), [model gateway](orchestrator_agent/src/host_agent/llm_client.py) | `RoutingPlan`, `CompletionDecision`, `NemotronOrchestrator` |
| Change specialist delegation or result parsing | [A2A connection](orchestrator_agent/src/host_agent/remote_agent_connection.py) | `RemoteAgentConnection`, `normalize_specialist_response` |
| Build a news-like expert | [News workflow](news_agent/src/news_agent/news_agent.py), [contracts](news_agent/src/news_agent/models.py), [governance](news_agent/src/news_agent/governance.py) | `NewsAgent`, `RoutePlan`, `EvidenceItem` |
| Build a financial-like expert | [Financial workflow](financials_agent/src/financials_agent/financials_agent.py), [planner](financials_agent/src/financials_agent/planner.py), [governance](financials_agent/src/financials_agent/governance.py) | `FinancialsAgent`, `deterministic_plan`, `merge_model_plan`, `verify_answer` |
| Change corpus ingestion or retrieval | [News ingestion](news_agent/src/ingest.py), [News retrieval](news_agent/src/news_agent/rag.py), [Financial ingestion](financials_agent/src/ingest.py), [Financial retrieval](financials_agent/src/financials_agent/retrieval.py) | `ingest`, `HistoricalNewsRetriever`, `FinancialFilingsRAG` |
| Change index mappings or vector queries | [News OpenSearch helpers](news_agent/src/common/opensearch_client.py), [Financial OpenSearch helpers](financials_agent/src/common/opensearch_client.py) | `ensure_index`, `knn_search`; implementations differ |
| Replace a live-data provider | [News MCP client](news_agent/src/news_agent/mcp_news.py), [News MCP server](news_agent/src/tavily_mcp_server.py), [Financial MCP client](financials_agent/src/financials_agent/mcp_client.py), [Financial MCP server](financials_agent/src/financials_agent/finnhub_server.py) | Tool signatures, result normalization, timeouts, error traces |
| Expose a specialist through A2A | [News entry point](news_agent/src/news_agent/__main__.py), [News executor](news_agent/src/news_agent/agent_executor.py), [Financial entry point](financials_agent/src/financials_agent/__main__.py), [Financial executor](financials_agent/src/financials_agent/financials_executor.py) | Agent cards, executors, task lifecycle, artifacts |
| Change audit persistence | [News audit](news_agent/src/news_agent/audit.py), [Financial audit](financials_agent/src/financials_agent/audit.py), [Orchestrator audit](orchestrator_agent/src/host_agent/audit.py) | `AuditLogger`, `AuditLog`, hash-chain verification |
| Change local model serving | [Generator service](slm_service/slm_service.py), [planning service](orch_service/orch_service.py) | `create_app`, local GGUF/MLX loading |

## 4. Interfaces and data crossing each boundary

### 4.1 Client to Orchestrator

The Flask application exposes `POST /v1/chat/completions` on port `10000`. It accepts text messages with `system`, `user`, or `assistant` roles and requires at least one nonempty user message.

Example request body:

```json
{
  "model": "vertical-api-orchestrator",
  "messages": [
    {
      "role": "user",
      "content": "What is NVIDIA doing in AI, and what is NVDA's current stock price?"
    }
  ],
  "stream": false,
  "user": "research-session-001"
}
```

This is a compatible subset, not a complete implementation of the public API. Streaming requests receive HTTP `400`; response token-usage fields are zero placeholders. The request's `model` value is echoed in the response rather than selecting the internal planning or generation endpoint. Accepted `temperature` and `max_tokens` fields are not forwarded as agent configuration overrides.

Clients send the conversation on every request. A stable `user` value supplies the session key; without one, the server hashes the entire transcript, so the key changes as the conversation grows. This field is a session identifier, not authenticated identity. The included demo client uses a fixed session value; a multi-user deployment must not reuse it for every user.

**Source:** [`ChatCompletionRequest`, `_session_id`, `create_app`](orchestrator_agent/src/host_agent/__main__.py), [demo client](orchestrator_agent/client.py).

### 4.2 Orchestrator to specialists: A2A

Each specialist runs a Starlette/Uvicorn A2A server with an agent card, JSON-RPC interface at `/`, in-memory task storage, and streamed task events. The current agent cards advertise protocol version `1.0`; requirements pin `a2a-sdk[http-server]==1.1.2`. The SDK release number and advertised protocol version are different values.

The Orchestrator discovers each specialist, sends a text message, consumes task/status/artifact events, and normalizes the result. News publishes a `news_result` artifact with governance metadata. Financial publishes a `financial_analysis` text artifact; its full internal metadata dictionary is not transmitted as a shared structured result contract.

The host's `SpecialistResponse` is therefore an **internal normalized envelope**, not the specialist's native wire schema. It contains `agent`, `status`, `summary`, `facts`, `data`, `citations`, `as_of`, `warnings`, `raw_text`, `context_id`, `task_id`, and `latency_ms`. Current normalization sets `facts=[]` and extracts citations, audit identifiers, dates, and private/unlisted signals from text. Do not build a downstream consumer that assumes a populated structured financial-facts list.

A2A task completion means the task reached a terminal response. That response may contain a scope redirect, withheld answer, or evidence limit, not a successful factual answer. Artifact/status handling must preserve this distinction.

**Source:** [specialist response contract](orchestrator_agent/src/host_agent/models.py), [`normalize_specialist_response`](orchestrator_agent/src/host_agent/remote_agent_connection.py), and the specialist entry points/executors in the source map.

### 4.3 Specialists to tools: MCP

Both MCP servers use Streamable HTTP at `/mcp`. Requirements pin the Python package `mcp==2.0.0`; do not treat that package version as a separately verified wire-protocol version.

The News tool is `search_technology_news(question: str)`. It receives the extracted user question and returns bounded news results with provenance. The adapter converts them into `EvidenceItem` objects before generation. The current provider implementation is in [`tavily_client.py`](news_agent/src/common/tavily_client.py).

Financial exposes the following bounded interfaces:

```text
resolve_public_symbol(company_or_symbol: str)
get_company_profile(symbol: str)
get_stock_quote(symbol: str)
get_company_metrics(symbol: str)
get_recent_quarterly_earnings(symbol: str, limit: int = 4)
get_earnings_calendar(symbol: str, from_date: str = "", to_date: str = "")
```

The allowed names live in `planner.ALLOWED_TOOLS`; the MCP client produces `ToolCallTrace` records with success, error, latency, arguments, and structured data. The current market provider uses HTTP GET requests in [`FinnhubService`](financials_agent/src/financials_agent/finnhub.py). There is no arbitrary URL-fetch tool or unrestricted shell tool in these specialist interfaces.

MCP is the tool/data boundary; A2A is the delegation boundary. The A2A SDK's `AgentSkill` card metadata is also distinct from a coding assistant's installable Agent Skill.

## 5. News Expert

**Responsibility:** historical and current technology-company reporting, including AI activity, products, research, partnerships, acquisitions, and strategy. Financial metrics, public-market status, SEC analysis, valuation, and investment recommendations belong elsewhere.

`NewsAgent.ainvoke` extracts the user question from the host envelope, checks input, and obtains a retrieval plan. `fallback_route` supplies deterministic temporal/domain signals; `_route` constrains Nemotron's proposal through `enforce_route_boundaries`. Under enabled policy checks, a financial-only request returns a redirect without retrieval.

Historical retrieval and current-news MCP search run concurrently when both are selected. The workflow deduplicates evidence, assigns `H#` and `W#` identifiers, and supplies a JSON Lines evidence registry to Qwen. Source text is designated untrusted data; JSON serialization is a formatting boundary, not a complete prompt-injection defense.

Deterministic checks reject recognized unknown citations, the absence of a valid citation when evidence exists, and configured financial-domain output patterns. Nemotron supplies advisory review. A failed deterministic check or generation attempt can trigger correction; the default is one correction after the initial attempt. Application code renders the final Sources section and audit identifier.

With evidence checks enabled, zero evidence produces a terminal no-evidence response. If only one of two requested source channels succeeds, the answer may use that evidence with an explicit gap notice. Historical retrieval is not automatically a fallback for live-tool failure; selected channels come from the plan.

**Source:** [`NewsAgent`](news_agent/src/news_agent/news_agent.py), [News governance](news_agent/src/news_agent/governance.py).

## 6. Financial Expert

**Responsibility:** SEC filing context, financial performance, public-security resolution, quotes, company metrics, and earnings. It does not use the News corpus or news tools to supply financial evidence.

`deterministic_plan` identifies requested source categories and extracts company/ticker identity. `merge_model_plan` allows model refinements inside the baseline policy. With policy checks enabled, the model cannot add a new source category or replace the parsed identity. Tool names remain constrained to the allowlist.

When the user has not supplied a ticker, the approved resolver establishes one or returns an explicit unresolved/private/unlisted outcome. The agent does not substitute a similarly named issuer. Resolver evidence establishes identity; it is not sufficient evidence for a requested stock price or filing analysis.

After identity resolution, selected filing retrieval and market-tool work run concurrently. Filing retrieval applies an exact `symbol` term filter inside the OpenSearch k-NN query. Filing evidence receives `F#` identifiers; market and resolver evidence receives `M#` identifiers. The MCP client processes its requested tool sequence in order.

Qwen generates from the assembled registry. `normalize_generated_answer` rebuilds source metadata and the assigned audit ID without adding missing claim citations. Deterministic verification checks response structure, recognized citation IDs/namespaces, and prohibited output patterns; Nemotron review is advisory. A deterministic rejection permits one bounded correction, followed by release or withholding.

For a ticker-based quote-only request, the baseline selects market data without SEC retrieval. A company-name quote additionally needs symbol resolution. Combined filing/market requests may proceed with partial evidence and warnings when at least some requested evidence exists; the current gate is not a guarantee that every requested source category succeeded.

**Source:** [Financial workflow](financials_agent/src/financials_agent/financials_agent.py), [planner](financials_agent/src/financials_agent/planner.py), [retrieval](financials_agent/src/financials_agent/retrieval.py), [governance](financials_agent/src/financials_agent/governance.py).

## 7. Orchestrator and bounded feedback loop

### Routing

Supported routes are `news`, `financial`, `combined`, `clarification`, and `unsupported`. Routing centers on the newest user request; prior turns supply bounded identity continuity or clarification context rather than automatically preserving an earlier combined route.

```text
Assess newest request and identity
  -> obtain and validate a routing plan, or use deterministic fallback
  -> construct specialist request envelopes in application code
  -> call selected specialists, concurrently for combined routes
  -> request one bounded completion decision from Nemotron
  -> optionally call one unused specialist within the remaining budget
  -> synthesize when both specialists contributed
  -> perform enabled checks, compose output, and append audit
```

`RoutingPlan` is a strict Pydantic contract: unexpected fields and duplicate specialists are rejected, and route/action/call shape must agree. `_canonicalize_specialist_requests` replaces model-written call text with application-owned envelopes. Financial envelopes preserve explicit ticker, current-data, and filing-context signals.

| Limit | Current implementation |
|---|---|
| Orchestration rounds | At most three reported logical stages: planning, initial delegation, completion/composition. |
| Specialist calls | At most two distinct logical specialist calls; repeated calls to the same expert are rejected by enabled completion validation. |
| Clarifications | One before the clarification-exhausted response. |
| Structured model calls | One retry after the initial routing/completion-model attempt. |
| Combined synthesis | Up to two attempts, currently derived from `max_specialist_calls`. |

These are implementation contracts, not environment-backed tuning knobs. `handle_messages` is a bounded sequence, not a loop that repeatedly runs all three stages until a model decides to stop. A continuation retry at the transport layer can add a network attempt without adding another logical specialist entry.

### Completion and composition

Nemotron's completion decision consumes specialist status/evidence-availability metadata, not raw filings or tool results. A combined result is generated by Qwen from specialist response text, citations, timestamps, and warnings. Validation rejects introduced citations and requires citation representation from each specialist that supplied cited text; it does not require every source citation to appear in the final prose.

When combined synthesis fails, the Orchestrator can return separately labeled specialist sections rather than discard them. A failed specialist remains an explicit limit; the host does not compensate by directly querying its data sources.

### Session continuity and lifecycle

A2A context IDs are cached in memory under `(session_id, specialist, normalized_company)`. A failed stored-context communication attempt can be retried once without the context ID. This is not durable cross-process memory or a replacement for sending the conversation.

The Orchestrator's A2A and model clients are created and closed for each request/call rather than reused across Flask request event loops. Preserve this lifecycle when replacing gateways.

**Source:** [`RoutingAgent.handle_messages`, `_validate_completion`, `_validate_synthesized_content`](orchestrator_agent/src/host_agent/routing_agent.py), [policy manager](orchestrator_agent/src/host_agent/policy_manager.py), [model gateway](orchestrator_agent/src/host_agent/llm_client.py), [A2A connection](orchestrator_agent/src/host_agent/remote_agent_connection.py).

## 8. Retrieval and ingestion contracts

### Shared choices

Both ingestion CLIs default to **2,048-character chunks, 256-character overlap, and embedding batches of 16**. These are characters, not tokens. The callable `ingest` functions separately default to batches of 32; pass explicit values when invoking them programmatically.

Both embedding wrappers request L2-normalized vectors, and the indices use Lucene HNSW with cosine similarity. The model supplies the embedding dimension. Keep ingestion and query encoders compatible and re-embed the corpus when changing embedding models, even when vector dimensions happen to match.

The chunk choices trade local context against retrieval granularity, duplicated overlap, and indexing cost. They are demonstration settings, not universal optima.

| Property | News | Financial |
|---|---|---|
| Input | CSV requiring `title` and `content`; optional identity, URL, date, domain, and tags | Recursively discovered `.md` filings with optional JSON sidecars |
| Default location | `./ai_media_dataset_20250911-1000lines.csv` | `./quarterly_filings` |
| Index | `techcomp-vector-chunks` | `financial-filings-vector-chunks` |
| Embedding input | Title/date/domain/tags plus chunk | Chunk text |
| Evidence text | Original chunk, trimmed for prompts | Original chunk, trimmed for prompts |
| Default `RAG_TOP_K` / `RAG_NUM_CANDIDATES` | `5` / `5` | `3` / `3` |
| Entity constraint | No exact company metadata filter in the vector query | Exact uppercase `symbol` filter inside k-NN |
| Re-ingestion | Deletes prior chunks for the logical `dataset_id` before replacement | Deletes prior chunks matching each incoming filing `path` before replacement |

Financial sidecars may provide `symbol`/`ticker`, company, filing type/date, fiscal period, accession number, and source URL. Without an explicit symbol, ingestion attempts the filename prefix, then a ticker-shaped parent directory. Missing valid identity is an error. The ingester consumes converted Markdown; it does not fetch or convert SEC documents.

### Differences a reusable retriever must preserve

Both index-creation functions set `knn.algo_param.ef_search=256`, but candidate handling is not identical. News supplies query-time `method_parameters.ef_search` and can fetch more chunks before diversity selection. Financial uses `rescore.oversample_factor` when `num_candidates > k`. Do not describe the two `RAG_NUM_CANDIDATES` settings as interchangeable implementations.

News's `RAG_MAX_CHUNKS_PER_SOURCE=2` is a **first-pass diversity preference**, not an absolute cap: `_select_diverse_evidence` can backfill deferred chunks when slots remain. At the default settings, the fetch count is five, so the candidate pool is not automatically larger than the final evidence count.

News checks existing vector dimensions and can add missing mapping fields. Financial leaves an existing mapping untouched. Validate existing financial mappings explicitly before relying on them.

**Operational caution:** ingestion performs delete-then-index updates, not transactional dataset swaps. A failed re-ingestion can leave partial data; files removed from the Financial input tree are not automatically discovered and deleted from the index. News `--recreate-index` deletes the entire target index. Confirm the intended target and approval before running destructive operations against shared data.

**Source:** [News ingestion](news_agent/src/ingest.py), [Financial ingestion](financials_agent/src/ingest.py), [News diversity selection](news_agent/src/news_agent/rag.py), both OpenSearch helpers in the source map, and [embedding normalization](news_agent/src/common/embeddings.py).

## 9. Evidence, governance, and audit behavior

### Evidence contracts

| Namespace | Owner | Meaning |
|---|---|---|
| `H#` | News | Historical news corpus chunk |
| `W#` | News | Current-news tool result |
| `F#` | Financial | SEC filing chunk |
| `M#` | Financial | Structured market or symbol-resolution result |

Identifiers are assigned within a request, not globally durable citation keys. Preserve source identities, dates, and audit/context association when storing responses. Do not merge independent registries merely because they both contain an identifier such as `H1`.

News uses the Pydantic `EvidenceItem`; Financial uses the dataclass `Evidence`. Their field names differ (`citation_id` versus `evidence_id`, `text` versus `content`). Keep adapters explicit rather than assuming one interchangeable schema.

### Enabled check categories

All three agents default to:

```dotenv
POLICY_CHECKS_ENABLED=true
EVIDENCE_CHECKS_ENABLED=true
RELEASE_CHECKS_ENABLED=true
```

Policy checks constrain domain behavior; evidence checks validate recognized references and evidence availability; release checks govern component-specific structural/completion behavior. The switches are separate, and exact checks differ by component. Turning off release checks does not automatically disable policy and evidence checks.

**Important current behavior:** the specialist Nemotron verifier is advisory. A negative, unavailable, or malformed advisory verdict does not veto a deterministic pass. News records advisory issues; Financial merges them into verification reasons without replacing the deterministic approval result. Deterministic rejection still drives correction/withholding. Do not describe this as unanimous approval by two independent verifiers.

Current citation checks are pattern-based provenance/structure checks, not exhaustive claim-level entailment tests. A valid citation can still be attached to an unsupported claim. Citation presence, JSON evidence formatting, and a model-review prompt do not prove semantic correctness or resistance to prompt injection.

### Audit persistence and failure semantics

| Component | Storage | Audit-write failure in the current workflow |
|---|---|---|
| News | Append-only JSONL | Withholds when release checks are enabled; otherwise releases with an audit warning. |
| Financial | Hash-chained JSONL | Records a warning and retains the answer; `_finalize` does not fail closed on append failure. |
| Orchestrator | Hash-chained JSONL | Withholds when release checks are enabled; otherwise preserves content with a warning. |

Audit records include identifiers, policy/planning outcomes, evidence provenance, hashes, and component-specific model/retrieval/tool traces. News and Orchestrator default to excluding raw query text. Financial's audit record omits evidence content and hashes tool arguments/results, but its DEBUG logs can contain full prompts, evidence, and answers. Hashing selected fields is not a blanket anonymization guarantee.

Hash-chain verification checks local record consistency; it is not immutable external attestation. The in-process locks and in-memory task/context stores also do not establish a multi-worker durability design.

**Source:** [News contracts](news_agent/src/news_agent/models.py), [Financial contracts](financials_agent/src/financials_agent/models.py), the governance/audit files in the source map, [`FinancialsAgent._finalize`](financials_agent/src/financials_agent/financials_agent.py), and [Financial logging](financials_agent/src/common/logging.py).

## 10. Configuration and deployment boundaries

Configure each component in its own process environment or component-local `.env`. Shared variable names such as `OPENSEARCH_INDEX` and `AUDIT_LOG_PATH` have different intended values per specialist; do not accidentally override all components with one index or audit destination.

| Concern | Configuration to inspect |
|---|---|
| Corpus | `OPENSEARCH_HOST`, `OPENSEARCH_PORT`, `OPENSEARCH_USER`, `OPENSEARCH_PASS`, `OPENSEARCH_SSL`, `OPENSEARCH_INDEX`, `EMBEDDING_MODEL`, `RAG_*` |
| Planning/review model | `ORCH_URL`, `ORCH_API_KEY`, `ORCH_MODEL` and the corresponding token/timeout settings |
| Answer model | `LLM_URL`, `LLM_API_KEY`, `LLM_MODEL` and the corresponding token/timeout settings |
| News service | `A2A_HOST`, `A2A_PORT`, `APP_URL`, `TAVILY_MCP_URL`, `TAVILY_API_KEY` |
| Financial service | `FINANCIALS_AGENT_HOST`, `FINANCIALS_AGENT_PORT`, `FINANCIALS_AGENT_URL`, `FINANCIALS_MCP_URL`, `FINNHUB_API_KEY` |
| Orchestrator | `ORCHESTRATOR_HOST`, `ORCHESTRATOR_PORT`, `NEWS_AGENT_URL`, `FINANCIAL_AGENT_URL` |
| Audit/governance | `AUDIT_LOG_PATH`, the three `*_CHECKS_ENABLED` switches, and component-specific audit settings |

The singular `FINANCIAL_AGENT_URL` in the host and plural `FINANCIALS_AGENT_URL` in the specialist are different existing keys. Model base URLs include `/v1`; MCP URLs include `/mcp`; specialist connection URLs identify the A2A service. Inspect each loader before changing external-model flags because loaders are not identical.

The intended workshop packaging includes a development environment and OpenSearch with preloaded data. Container definitions and preload artifacts are absent from this inspected source snapshot, so image names, mounted paths, dependency installation, and preload behavior cannot be derived from these Python packages. Do not invent a `docker compose` command or claim data is pre-ingested without checking the actual deployment files.

Loopback defaults only work when callers share the required network namespace. A separate OpenSearch container needs an address reachable from the agent process. Bind addresses such as `0.0.0.0` and advertised A2A URLs serve different purposes; clients need a reachable advertised URL.

The specialist `/health` routes report service configuration, not end-to-end dependency readiness. The Orchestrator entry point does not define a `/health` or `/v1/models` route. The separate local model services define their own health/model routes, but their weights must be provisioned independently.

**Source:** the three agent settings modules in Section 2, [specialist entry points](news_agent/src/news_agent/__main__.py), [Financial health payload](financials_agent/src/financials_agent/__main__.py), [host entry point](orchestrator_agent/src/host_agent/__main__.py), and local model services in the source map.

## 11. Building similar components

The following are **extension recommendations**, not claims that these features already exist.

### Select the right extension boundary

Use a new MCP tool when adding a bounded operation within an existing expert's authority. Use a new specialist when the domain needs its own policy, evidence lifecycle, release behavior, or independent delegation. Replace a model gateway when changing a compatible planner/generator, and replace an ingestion/retrieval adapter when changing the corpus. Avoid expanding the Orchestrator into a universal data-access agent.

### Implement a new expert

1. **Define its contract first.** State owned/excluded domains, required identity, allowed sources/tools, evidence schema, citation namespace, terminal outcomes, and retry limits. Choose fail-open versus fail-closed behavior explicitly for advisory review and audit failure.
2. **Build deterministic planning and evidence adapters.** Validate model proposals against policy; keep entity/tenant filters in retrieval; normalize provider data into bounded evidence with source IDs and timestamps. Never grant new tools based on instructions found in retrieved content.
3. **Add generation and release handling.** Generate only from the selected registry, validate recognized citations and required output structure, bound correction, and render provenance in application code. Add stronger semantic evaluation where the application requires it.
4. **Test the expert independently.** Inject fake retrievers, model gateways, tools, and audit writers through constructors. Cover success, missing evidence, malformed tool output, scope violations, and persistence failures before adding transport.
5. **Expose A2A deliberately.** Define the card and reachable URL, preserve task-before-update ordering and terminal states, publish a final artifact, and make downstream result normalization explicit.
6. **Integrate the host as a contract change.** Update the agent/route literals and validators, policy rules, specialist registry/prompts, request-envelope construction, connection configuration, completion actions, composition, citation handling, and tests. Adding a URL alone does not register a new expert. More than two specialists also requires revisiting the current call budget and route assumptions.

### Replace providers, models, or retrieval

For a provider replacement, retain the MCP tool contract where feasible and translate provider-specific response/error fields inside the adapter. Preserve data timestamps, safe identity resolution, bounded results, and traceability. Keep secrets in provider configuration, not source evidence or generated prose.

For a model replacement, verify structured-output parsing, supported request parameters, timeout behavior, synthesis citations, and correction behavior against the existing gateway interface. A compatible HTTP route does not guarantee equivalent planning quality or parameter semantics.

For a retrieval replacement, preserve stable source identity, evidence provenance, and entity filtering. Validate both index dimensions and encoder identity. Stage data/index migrations rather than silently deleting shared indices, and keep metadata used for ranking separate from original evidence text.

For stronger cross-agent contracts, consider transmitting typed result artifacts with explicit release outcome and evidence metadata. This would replace current text extraction/marker heuristics and requires coordinated producer/consumer changes; it is not already implemented here.

## 12. Verification and development workflow

### Commands present in the source

Run these from the indicated component directory after provisioning dependencies, endpoints, credentials, and any required data. This is a command map, not a complete installation walkthrough.

| Directory | Existing targets | What they do |
|---|---|---|
| `news_agent/` | `make install`, `make ingest`, `make mcp`, `make agent`, `make query QUESTION="..."` | Install requirements, ingest CSV, start the tool server, start A2A, query the specialist. |
| `financials_agent/` | `make install`, `make ingest`, `make mcp`, `make agent`, `make query QUESTION="..."`, `make audit` | Install requirements, ingest filings, start services, query, verify the audit chain. |
| `orchestrator_agent/` | `make agent`, `make client`, `make audit` | Start the host, run the interactive client, verify its audit chain. |

All three Makefiles reference tests, but test directories are absent from the inspected snapshot. A test target existing does not mean a test suite is present or passing. The Orchestrator has no `make install` target; dependency declarations are in its `requirements.txt`.

A useful build sequence is infrastructure and model endpoints, then each specialist's data/tool path, direct specialist queries, A2A delegation, and finally the client. Use an existing populated index or ingest approved sample data; do not treat re-ingestion as a mandatory read-only readiness check.

**Source:** [News Makefile](news_agent/Makefile), [Financial Makefile](financials_agent/Makefile), [Orchestrator Makefile](orchestrator_agent/Makefile).

### Acceptance scenarios for derived implementations

These are recommended checks, not results of an executed test suite. Prefer deterministic fakes for assertions about call counts and policy behavior; live smoke tests also depend on data and model availability.

| Scenario | Expected observation |
|---|---|
| News-only company request | Valid initial plan delegates to News; with a terminal completion decision, no Financial call occurs. |
| Explicit ticker quote | Financial baseline selects the quote tool and no SEC retrieval; any model refinement stays inside approved market tools. |
| Filing question | Retrieval contains the exact symbol filter; a similarly worded filing from another issuer cannot enter the result set through an unfiltered query. |
| Combined question | Initial specialist calls run concurrently; synthesis preserves available specialist evidence and its limits. |
| Quote follow-up after a combined turn | Identity continuity is retained while the newest explicit financial intent determines the initial route. |
| Multiple companies or ambiguous identity | Clarification occurs before specialist delegation. |
| Missing news evidence | No unsupported news synthesis is released when evidence checks are enabled. |
| Resolver succeeds but requested financial evidence fails | Identity evidence alone does not authorize a quote/filing answer. |
| Recognized unknown citation | Deterministic validation rejects the candidate; correction is bounded. |
| Negative advisory review with deterministic pass | Current specialist behavior records the concern without a model veto. |
| Stored-context communication failure | At most one fresh-task retry; no unbounded reconnect loop. |
| Combined synthesis failure | Labeled specialist results/limits remain available rather than being replaced with invented facts. |
| Audit append failure | Verify the current component-specific behavior in Section 9, or explicitly test a deliberately changed policy. |
| Process restart | Do not assume in-memory task/context continuity survives. |

When modifying this code, keep changes scoped, preserve existing names and structure unless the task requires a change, and avoid adding configuration flags without a concrete need. Report exactly which static checks, mocked tests, and live checks ran. Do not claim production authentication, durable shared sessions, complete prompt-injection protection, causal inference, or exhaustive claim verification on the strength of this demonstration architecture.
