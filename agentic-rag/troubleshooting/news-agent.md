[Task 2: News Expert](../tasks/news-agent.md)

## Troubleshooting reference

| Symptom | Check and next action |
|---|---|
| Hosted OpenSearch cannot resolve or connect | Run the probe inside `lab`, inspect the effective connection settings, and verify outbound connectivity and workshop access. Confirm the supplied workspace image/configuration with the maintainer if it still points to a local database. |
| News index is missing or empty | Confirm the effective index and access to the pre-populated corpus on OpenSearch hosted by Instaclustr with the workshop maintainer, then repeat the task's read-only corpus inspection. Do not run `make ingest`, recreate the index, or overwrite the dataset as a repair step. |
| OpenSearch returns HTTP 401/403 or a TLS error | Confirm hosted-service access and the supplied connection configuration with the maintainer. Keep credentials private; do not disable certificate verification to bypass the error. |
| Historical results are irrelevant | Inspect corpus coverage and query wording, then confirm embedding-model compatibility. A nearest neighbor is not necessarily useful evidence. |
| Server health passes but a question fails | Health reports server/configuration state; use the separate retrieval probes and Terminal B's error logs. |
| Port 8765 or 9001 is already in use | Check the existing foreground terminals. Reuse or stop the earlier process instead of launching another copy. |
| Tavily key remains "missing" after an export | Put the export in the MCP server's shell and restart that process; sibling shells retain their own environments. |
| Provider rejects credentials, parameters, or token budget | Revisit Task 1's validated provider profile. Avoid unreviewed dependency upgrades or disabling governance checks. |
| A2A card validation fails | Use `http://127.0.0.1:9001`, not an empty URL or the MCP endpoint. Check the advertised JSON-RPC protocol `1.0` interface. |
| An answer is withheld | Read the audit's attempt-level verification issues. A transport success is not proof of an approved application answer. |
| No audit file appears | Direct retrieval probes do not create request audits. After a full expert request, check the configured audit path, permissions, disk space, and server logs. |
| A sample-ingestion or test command is missing files | The hosted-corpus task does not require either. The supplied archive has no CSV data directory or test suite; do not assume a path or Make target from another document is present. The separate [native setup](../references/NATIVE_SETUP.md#native-only-ingestion-for-tasks-2-and-3) requires source datasets and `make ingest` for both agents. |
