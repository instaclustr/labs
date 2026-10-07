[Task 3: Financial Expert](../tasks/financials-agent.md)

## Corpus availability

The default workshop uses the pre-populated SEC-filing corpus and document embeddings on OpenSearch hosted by Instaclustr. The Financial Expert uses its configured connection and index; the source default is `agenticrag-finfile-vector-chunks`. The task's read-only probes inspect the effective index rather than assuming a local database address. No local OpenSearch or Dashboards startup, corpus-file preparation, or `make ingest` is required for this path. The ingestion implementation remains available for learning and for the required [native-only ingestion](NATIVE_SETUP.md#native-only-ingestion-for-tasks-2-and-3).

## Source map

These are the implementation files used by this task. When the overview and code differ, follow the current code and rerun the relevant local probe.

| File | Responsibility |
|---|---|
| [`Makefile`](../scripts/financials-agent/Makefile) | Dependency installation, ingestion, MCP and A2A startup, client queries, and audit-chain verification targets. |
| [`requirements.txt`](../scripts/financials-agent/requirements.txt) | Python dependency declarations used by the task. |
| [`src/common/config.py`](../scripts/financials-agent/src/common/config.py) | Environment and optional .env loading, model-provider selection, service endpoints, retrieval settings, and governance controls. |
| [`src/common/embeddings.py`](../scripts/financials-agent/src/common/embeddings.py) | Lazy-loaded sentence-transformers embeddings, runtime device and dtype selection, and vector conversion. |
| [`src/common/opensearch_client.py`](../scripts/financials-agent/src/common/opensearch_client.py) | OpenSearch connection settings, financial-filings index creation, and vector-search requests with optional filters. |
| [`src/common/logging.py`](../scripts/financials-agent/src/common/logging.py) | Log-level configuration, transport-log suppression, and optional DEBUG logging of component-boundary payloads. |
| [`src/ingest.py`](../scripts/financials-agent/src/ingest.py) | Text-converted filing discovery, metadata loading, overlapping character chunking, embedding, and indexing. |
| [`src/financials_agent/__main__.py`](../scripts/financials-agent/src/financials_agent/__main__.py) | A2A Agent Card, health and JSON-RPC routes, and Financial Expert server startup. |
| [`src/financials_agent/financials_executor.py`](../scripts/financials-agent/src/financials_agent/financials_executor.py) | A2A task lifecycle and result-artifact handling around the FinancialsAgent workflow. |
| [`src/financials_agent/models.py`](../scripts/financials-agent/src/financials_agent/models.py) | Typed plan, evidence, tool-call, retrieval, model-call, and verification contracts. |
| [`src/financials_agent/planner.py`](../scripts/financials-agent/src/financials_agent/planner.py) | Host-envelope parsing, conservative issuer extraction, deterministic authority and source selection, and constrained model-plan merging. |
| [`src/financials_agent/financials_agent.py`](../scripts/financials-agent/src/financials_agent/financials_agent.py) | Bounded planning, issuer resolution, filing and market evidence collection, synthesis, correction, release outcomes, and audit completion. |
| [`src/financials_agent/retrieval.py`](../scripts/financials-agent/src/financials_agent/retrieval.py) | Exact-symbol filtering of OpenSearch filing chunks, F-series evidence construction, and retrieval traces. |
| [`src/financials_agent/mcp_client.py`](../scripts/financials-agent/src/financials_agent/mcp_client.py) | MCP tool-call execution, timeouts, structured-result parsing, and tool-call traces. |
| [`src/financials_agent/finnhub_server.py`](../scripts/financials-agent/src/financials_agent/finnhub_server.py) | Streamable HTTP MCP server exposing public-symbol resolution, company profiles, quotes, metrics, quarterly earnings, and earnings-calendar tools. |
| [`src/financials_agent/finnhub.py`](../scripts/financials-agent/src/financials_agent/finnhub.py) | Typed Finnhub REST adapter, public-company symbol resolution, and normalization of market-data responses. |
| [`src/financials_agent/llm.py`](../scripts/financials-agent/src/financials_agent/llm.py) | OpenAI-compatible planning, synthesis, and review calls with model-call trace and error handling. |
| [`src/financials_agent/prompts.py`](../scripts/financials-agent/src/financials_agent/prompts.py) | Model instructions and evidence-bearing messages for planning, synthesis, and advisory release review. |
| [`src/financials_agent/governance.py`](../scripts/financials-agent/src/financials_agent/governance.py) | Answer normalization, application-owned source formatting, deterministic release checks, and advisory model-verdict merging. |
| [`src/financials_agent/audit.py`](../scripts/financials-agent/src/financials_agent/audit.py) | Hash-linked JSONL audit append, existing-chain validation, and command-line chain verification. |
| [`src/query.py`](../scripts/financials-agent/src/query.py) | A2A command-line client, Agent Card validation, request submission, and answer output. |
