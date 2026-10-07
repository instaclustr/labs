[1. Introduction to the Solution and Prerequisites](../tasks/introduction.md)

### Troubleshoot the failed check, not a different layer

| Symptom | Likely issue and action |
|---|---|
| Native setup only: OpenSearch logs mention `vm.max_map_count` | The Linux environment running native OpenSearch needs `vm.max_map_count` of at least `262144`; on macOS/Windows this is the Podman VM. Follow the [OpenSearch installation guidance](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/) and return to [native setup](../references/NATIVE_SETUP.md). This kernel prerequisite does not apply to the default hosted-corpus path. |
| Container exits with code 137 or a service repeatedly restarts | Inspect logs and available VM/host memory; increase the allocation before rerunning. |
| Workspace container name already in use | Check for an existing `agentic-lab` container and reuse the intended workspace or stop the earlier instance. Preserve local work before removing it. The default path does not need a second workspace or local database stack. |
| Hosted OpenSearch cannot resolve or connect | Run the task probes inside `lab`; check outbound connectivity, DNS, and workshop access. If the effective address still points to a local database, confirm the supplied development image and configuration with the workshop maintainer rather than starting local OpenSearch. |
| OpenSearch returns HTTP 401/403 or a TLS error | Confirm hosted-service access and the supplied connection configuration with the workshop maintainer. Keep credentials private and do not disable certificate verification to bypass a failed check. |
| Validation still requires local OpenSearch or Dashboards | Verify that the current supplied development image is in use. The default Compose file contains only `lab`, and the runtime validator is supplied by that image rather than this archive. Resolve the image/runtime mismatch with the workshop maintainer; do not create local services or write test data into the hosted corpus as a workaround. |
| Workspace is unwritable | Check permissions on the workspace path and any separately configured mounts. The supplied Compose definition does not declare persistent mounts; do not solve a permissions failure by making directories world-writable. |
| Provider HTTP 401/403 | Check the selected provider, key, project permissions, and access to the exact model. Keep the key private. |
| Provider HTTP 404 | Check the model identifier and API base URL; do not append `/chat/completions` to a base URL variable. |
| Provider HTTP 429 | Inspect quota, account billing status, or rate limits; repeated immediate retries will not repair missing quota. |
| Provider rejects `max_tokens`, `temperature`, or `top_p` | This is an application/provider request-compatibility issue, not an OpenSearch failure. The archived clients send those fields. Use a source revision with reviewed provider-aware request handling or an accepted model configuration, then rerun. The setup scripts do not rewrite agent source or silently strip parameters. |
| Provider rejects a token budget | Lower `EXTERNAL_ORCH_MAX_TOKENS` and/or `EXTERNAL_LLM_MAX_TOKENS` to supported output limits, then recreate `lab`. Context-window size is not the output limit. |
| Provider TLS or connection error | Check outbound HTTPS, DNS, proxy settings, and trusted certificate configuration. Do not disable TLS verification to bypass the error. |
| An embedding download or inference fails | Check internet access, cache disk space, package imports, and available memory; rerun `--check-embeddings`. |

After changing provider variables in the **host** `.env` file, recreate only the workspace container. Preserve local changes and audit files first; the supplied Compose definition does not mount persistent workspace storage:

```bash
podman compose up -d --force-recreate --no-deps lab
podman compose exec lab bash
```

**Expected:** `lab` is recreated and a new workspace shell opens. Container recreation terminates any running application processes and existing shells; it does not change the hosted corpora. Do not assume local changes, audit files, or downloaded caches survive replacement. Reopen shells and restart any later-task services. `podman compose restart lab` does **not** apply a changed container environment.

