[Task 2: News Expert](../tasks/news-agent.md)

## Corpus availability

The default workshop uses the pre-populated news corpus and document embeddings on OpenSearch hosted by Instaclustr. The News Expert uses its configured connection and index; the source default is `agenticrag-technews-vector-chunks`. The task's read-only probes inspect the effective index rather than assuming a local database address. No local OpenSearch or Dashboards startup, corpus-file preparation, or `make ingest` is required for this path. The ingestion implementation remains available for learning and for the required [native-only ingestion](NATIVE_SETUP.md#native-only-ingestion-for-tasks-2-and-3).

## Source map

These are the implementation files used by this task. When the overview and code differ, follow the current code and rerun the relevant local probe.

| File | Responsibility |
|---|---|
| [`Makefile`](../scripts/news-agent/Makefile) | Dependency installation, ingestion, MCP and A2A startup, client queries, and local check targets. |
| [`requirements.txt`](../scripts/news-agent/requirements.txt) | Python dependency declarations used by the task. |
| [`src/common/config.py`](../scripts/news-agent/src/common/config.py) | Environment and optional .env loading, model-provider selection, service endpoints, retrieval settings, and governance controls. |
| [`src/common/embeddings.py`](../scripts/news-agent/src/common/embeddings.py) | Lazy-loaded sentence-transformers embeddings, runtime device and dtype selection, and vector conversion. |
| [`src/common/opensearch_client.py`](../scripts/news-agent/src/common/opensearch_client.py) | OpenSearch connection settings, news-index mappings and dimension checks, and vector-search requests. |
| [`src/common/logging.py`](../scripts/news-agent/src/common/logging.py) | Shared console logger configuration. |
| [`src/ingest.py`](../scripts/news-agent/src/ingest.py) | Historical-news CSV normalization, overlapping character chunking, metadata-aware embedding inputs, and bulk indexing. |
| [`src/news_agent/__main__.py`](../scripts/news-agent/src/news_agent/__main__.py) | A2A Agent Card, Starlette routes, and News Expert server startup. |
| [`src/news_agent/agent_executor.py`](../scripts/news-agent/src/news_agent/agent_executor.py) | A2A task lifecycle, progress updates, and result-artifact handling around the NewsAgent workflow. |
| [`src/news_agent/models.py`](../scripts/news-agent/src/news_agent/models.py) | Typed route, evidence, verification, and host-facing result contracts. |
| [`src/news_agent/news_agent.py`](../scripts/news-agent/src/news_agent/news_agent.py) | Bounded routing, retrieval, synthesis, deterministic and advisory verification, correction, response outcomes, and audit-write handling. |
| [`src/news_agent/governance.py`](../scripts/news-agent/src/news_agent/governance.py) | News-domain routing boundaries, citation-ID assignment, evidence serialization, deterministic citation checks, and release formatting. |
| [`src/news_agent/rag.py`](../scripts/news-agent/src/news_agent/rag.py) | Historical OpenSearch retrieval, article-diversity selection, and conversion of ranked chunks into evidence items. |
| [`src/news_agent/mcp_news.py`](../scripts/news-agent/src/news_agent/mcp_news.py) | MCP client for search_technology_news and conversion of current-search results into news evidence. |
| [`src/tavily_mcp_server.py`](../scripts/news-agent/src/tavily_mcp_server.py) | Streamable HTTP MCP server exposing search_technology_news with the incoming question and retrieval metadata. |
| [`src/common/tavily_client.py`](../scripts/news-agent/src/common/tavily_client.py) | Tavily SDK calls, question-based time-range selection, and normalization of returned URLs and content. |
| [`src/news_agent/llm.py`](../scripts/news-agent/src/news_agent/llm.py) | OpenAI-compatible model clients for routing and advisory review, and for answer generation. |
| [`src/news_agent/audit.py`](../scripts/news-agent/src/news_agent/audit.py) | Append-only JSONL audit persistence, permitted request metadata, query hashes, and evidence metadata. |
| [`src/news_agent/utils.py`](../scripts/news-agent/src/news_agent/utils.py) | Host-envelope extraction, model-JSON parsing, citation parsing, text normalization, hashing, and JSON-safe audit values. |
| [`src/query.py`](../scripts/news-agent/src/query.py) | A2A command-line client, Agent Card validation, status and artifact collection, and final-answer output. |
