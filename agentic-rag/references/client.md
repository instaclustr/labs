[Task 5: Run the Client End-to-End](../tasks/client.md)

## Source map

These links identify the implementation used by this task. The audit references are for inspecting the completed client request, not for restarting or reimplementing the earlier components.

| File | Responsibility |
|---|---|
| [`client.py`](../scripts/client/client.py) and [`Makefile`](../scripts/client/Makefile) | Interactive input, conversation history, request timing, and client startup. |
| [`HTTP entry point`](../scripts/orchestrator-agent/src/host_agent/__main__.py) | Request/response contract, session-label handling, and placeholder usage fields. |
| [`Request records and response composition`](../scripts/orchestrator-agent/src/host_agent/routing_agent.py) | Routing trace, audit-ID links, check results, outcomes, and release behavior. |
| [`Coordination audit verifier`](../scripts/orchestrator-agent/src/host_agent/audit.py) | Coordination hash-chain validation. |
| [`News audit records`](../scripts/news-agent/src/news_agent/audit.py) and [`record completion`](../scripts/news-agent/src/news_agent/news_agent.py) | Evidence metadata, request outcomes, and audit-write handling. |
| [`Financial audit verifier`](../scripts/financials-agent/src/financials_agent/audit.py) and [`record completion`](../scripts/financials-agent/src/financials_agent/financials_agent.py) | Financial evidence/check records, hash validation, and audit-persistence limitation. |
