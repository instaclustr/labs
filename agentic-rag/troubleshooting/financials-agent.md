[Task 3: Financials Expert](../tasks/financials-agent.md)

## Troubleshooting reference

| Symptom | Check and next action |
|---|---|
| Financial module cannot be found | Re-enter the expert directory in Step 1. Run Make targets from the directory containing its `Makefile`, not the repository root. |
| Hosted OpenSearch cannot resolve or connect | Run the probe inside `lab`, inspect the effective connection settings, and verify outbound connectivity and workshop access. Confirm the supplied workspace image/configuration with the maintainer if it still points to a local database. |
| Filing index is missing or empty | Confirm the effective index and access to the pre-populated corpus on OpenSearch hosted by Instaclustr with the workshop maintainer, then repeat the task's read-only corpus inspection. Do not run `make ingest`, recreate the index, or overwrite the dataset as a repair step. |
| OpenSearch returns HTTP 401/403 or a TLS error | Confirm hosted-service access and the supplied connection configuration with the maintainer. Keep credentials private; do not disable certificate verification to bypass the error. |
| Wrong issuer, irrelevant passage, or missing period | Inspect stored `symbol`, path, text, and period metadata. The filter cannot repair incorrect ingestion labels or absent evidence. |
| Embedding model load or vector-dimension error | Check cache access, memory, and embedding compatibility. Do not substitute a different embedding model or delete vectors. |
| Finnhub MCP starts but quotes fail | Test the adapter, not only startup. Check the key in Terminal A, provider authorization/quota, and its error logs. |
| Quote timestamp is old or price fields are absent | Treat the result as limited evidence. The code has no hard freshness threshold; do not relabel retrieval time as market time. |
| Port `8766` or `9002` is occupied | Reuse or stop the earlier foreground process before starting another. |
| Health passes but expert requests fail | Health does not probe dependencies. Use the direct retrieval/MCP checks and the validated Task 1 model profile. |
| Model provider rejects parameters or token budget | Inspect Terminal B and the effective model settings. Restore the validated profile rather than disabling governance or upgrading dependencies during the lab. |
| Direct query times out during a slow request | The client uses a 120-second HTTP timeout; model loading/calls can take longer. Check Terminal B for completion and the audit before submitting another request. |
| No quote after a company-name request | Inspect symbol-resolution evidence. A failed lookup is not permission to substitute a similarly named issuer. |
| A2A reports completion but the answer is withheld | Inspect `outcome`, final verification reasons, warnings, and source availability. Task completion is not release approval. |
| `make audit` cannot find the file | Direct probes do not create it. Check the server's configured path; the Make target always uses `./logs/financials-audit.jsonl`. |
| Audit chain fails or the latest answer has no record | Preserve the file and inspect Terminal B for append errors, permissions, disk space, or corruption. Do not edit/re-hash the active log to make it pass. |
| `make test` reports no tests | A Make target exists, but the supplied source archive contains no financial test suite. This walkthrough uses the local governance checks above and does not require test installation. |
