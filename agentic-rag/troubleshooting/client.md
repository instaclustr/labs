[Task 5: Run the Client End-to-End](../tasks/client.md)

## Troubleshooting reference

| Symptom | Check and next action |
|---|---|
| `5-client`, `client.py`, or the `client` target is missing | Confirm the numbered workshop checkout. The source archive may package the client alongside the coordination service; this walkthrough requires the workshop client directory. |
| Client cannot connect to port `10000` | Confirm the client is inside `lab` and the earlier service is still running at the fixed client URL. Do not substitute a host URL or an invented environment setting. |
| Client exits with an API exception or timeout | Inspect the existing service logs for that attempt. The client has no request-error recovery handler. A client-side failure does not prove that all server-side work stopped. |
| Response contains a limitation or a stop notice | Inspect the recorded outcome and enabled checks. HTTP success does not mean a research answer was released. |
| Response contains separate sections | Check the composition notice, `synthesis`, and `outcome`. This can be the bounded fallback rather than a transport failure. |
| No routing-trace Audit ID is visible | Use Step 6's metadata listing and available service-log identifiers. Do not guess between indistinguishable requests. |
| Audit file or matching record is missing | Check the printed path against the service's actual startup settings. Inspect audit-write errors; an ID does not prove persistence. |
| A verifier reports a broken chain | Preserve the original file and inspect the failure. Do not alter the file or disable release checks to bypass it. |
| No `[F#]` citations appear | This question does not require filing analysis. Inspect the actual evidence paths rather than requiring every namespace. |
| Citation looks valid but the price-effect explanation is unsupported | Check the referenced evidence. Citation membership does not prove a causal claim. |

