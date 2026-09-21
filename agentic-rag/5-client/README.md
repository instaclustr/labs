# Episode 5: Run the Client End-to-End

A useful research answer needs more than fluent writing. We need to understand which information supports it, which checks ran, and what the system could not establish. The client is where those decisions become visible to the person asking the question.

In this final episode, you use the command-line client to ask one technology-company research question. You then follow the response through its citations, execution metadata, and audit records. The goal is to connect the answer you see with the evidence and policy decisions behind it.

The previous episodes assembled the lab's **Mixture of Experts (MoE)** solution. Here, MoE refers to separately governed agent applications that cooperate on a request. This episode does not rebuild or explain their internal workflows. It focuses on the client experience and the **chain of custody** for one completed request: what was requested, what evidence was used, which checks applied, and what was returned.

> **IMPORTANT:** This is a demonstration of inspectable AI governance. It is not an investment-advice application, an authenticated multi-user service, or a production compliance system. Connecting a news article with a stock quote does not establish that the article's subject caused the price.

## What you will learn

| Step | Activity | Checkpoint |
|---|---|---|
| 1 | Open the client workspace in the existing development container. | The client files and Make target are present. |
| 2 | Start the client and submit the research question. | The interactive `You:` prompt is available. |
| 3 | Read the answer, citations, and routing trace. | Supported observations are distinguishable from unsupported causal claims. |
| 4 | Compare client output with existing process logs. | Transport success, elapsed time, and application outcomes are distinguishable. |
| 5 | Match the request to its persisted audit records. | Audit identifiers connect the response to its checks and evidence metadata. |
| 6 | Interpret integrity checks and data-retention limits. | The audit's guarantees and limitations are understood. |

## Before you begin

Complete Episode 1's environment and model validation. Leave the services established in [Episode 2](../2-news-agent/README.md), [Episode 3](../3-financials-agent/README.md), and [Episode 4](../4-orchestrator-agent/README.md) running.

The existing Compose environment must contain the `lab`, `opensearch`, and `dashboards` services.

## Step 1: enter the client workspace

Open two additional **host terminals**. From the host directory containing the Compose file, enter the existing development container in each:

```bash
podman compose exec lab bash
```

In **both container shells**, run:

```bash
cd /workspace/agentic-rag/5-client
pwd
```

| Terminal | Purpose |
|---|---|
| **Client** | Run `make client` and enter the research question. |
| **Inspection** | Read the records produced by that request without sending another question. |

These are two shells in the same container. An export in one shell does not modify another shell or an already-running process.

## Step 2: start the client and submit the question

### Why keep the client separate from the research workflow?

The client collects a question, sends a conversation to one application endpoint, and displays the returned text. It does not retrieve documents, choose tools, verify citations, or decide whether an answer is safe to release. Those responsibilities stay behind the application's API boundary.

That separation is important for governance. A user interface should not need to reproduce the rules that control evidence access and answer release. It should preserve the result and its limitations rather than silently replace a withheld response with another model call.

The supplied client has the following behavior:

| Client behavior | What it means in this lab |
|---|---|
| Uses the OpenAI Python SDK with base URL `http://127.0.0.1:10000/v1`. | The question goes to the local application through `POST /v1/chat/completions`, not directly to a model provider. |
| Supplies `api_key="not-needed"`. | This is a placeholder for the local demo endpoint, not an authenticated identity or a provider credential. |
| Sends a fixed application `model` label. | The label identifies the public API request; it does not select the underlying planning or answer model. |
| Keeps a `messages` list in memory. | The client appends the user turn before the request and the returned assistant text afterward. It does not save a conversation file. |
| Sends `user="instaclustr-labs"`. | This is a shared demo session label. It is not a login, authorization decision, or unique identity for each attendee. |
| Waits for a non-streaming completion. | The answer appears after the request returns, rather than token by token. |

The client URL is fixed in `client.py`; this implementation does not read a client endpoint setting from the environment. The supplied Compose file does not publish port `10000` to the host. Running inside `lab` makes `127.0.0.1:10000` refer to the container where the application is already listening.

In the **Client terminal**:

```bash
make client
```

**Expected:** the client displays:

```text
AI Investment Orchestrator
Ask about one company's news, financials, or both. Type exit to stop.

You:
```

The banner is the supplied application's label, not permission to provide investment advice. Reaching `You:` confirms that the client started. It has not yet tested the research endpoint or its dependencies.

[Implementation: client](client.py)
[Launch target](Makefile)
[HTTP boundary](../4-orchestrator-agent/src/host_agent/__main__.py)

### ask the single research question

At the **`You:` prompt**, paste the following as one input and press Enter:

```text
Can you tell me what NVIDIA is doing in the Artificial Intelligence space in news articles? How that work has affected their current stock price (ticker symbol: NVDA)?
```

This is the only research question for this episode. Do not paste it into the Bash inspection shell. After receiving the response, leave the client open and use the other terminal for the remaining exercises.

The question brings together a company's AI activity, its current market information, and a request to explain their relationship. The explicitly supplied company name and ticker identify one intended subject. The words **has affected** also create an important evidence test: the answer must not assume a causal relationship merely because the user asked for one.

**Expected:** after the request returns, the client prints `Response time: ... seconds`, followed by `Orchestrator:` and the application response. A normal response can combine supported observations with citations and an explanation of what cannot be concluded. An evidence limitation, separate-section fallback, or withholding notice is also meaningful output to inspect.

There is no fixed expected price, article list, response duration, or citation count. Those depend on the available evidence, configured models, provider responses, and checks during this run. Do not treat a different price or wording as a failed exercise by itself.

If the client raises a connection, timeout, or API exception, inspect the already-running service terminals. The supplied client does not catch these request exceptions, so the process can exit. Do not submit a modified question or disable governance to make the walkthrough appear successful; diagnose the recorded failure first.

## Step 3: read the answer as evidence

### Check what the answer can actually establish

Read the response in three parts: the reported company developments, the market observation, and the explanation connecting them.

For the developments, look for identifiable articles and their publication dates. For the stock information, look for the supplied ticker and the quote's time boundary. Retrieval time is not necessarily the market timestamp. An old article and a newly fetched quote describe different points in time.

For the explanation, ask whether the sources document a price reaction or whether the answer is only placing two observations beside each other. **A current quote alone cannot show how much a particular AI announcement changed the price.** A satisfactory answer can explicitly say that the available evidence does not establish that effect. It should not manufacture a causal explanation or a trading recommendation to satisfy the wording of the question.

This is the practical consequence of preserving authority and evidence boundaries: missing support remains a visible limitation rather than becoming plausible-sounding filler.

### Read the citation namespaces

| Marker | Evidence provenance |
|---|---|
| `[H#]` | Historical news evidence retrieved from the OpenSearch corpus. |
| `[W#]` | Current news evidence obtained through the news-search MCP path. |
| `[F#]` | SEC filing evidence retrieved from OpenSearch. |
| `[M#]` | Structured market evidence obtained through the financial MCP path. |

The number identifies an item within that request's evidence registry. `[M1]` in another request is not necessarily the same item. Use the owning audit record together with the citation ID when tracing a claim.

Do not expect all four namespaces. This question requests news and a current stock price, not a filing analysis. Filing retrieval can legitimately be absent. The actual records show which sources were selected, what succeeded, and what evidence was available.

A citation establishes a reference to an evidence item; it does not by itself prove that the cited item supports every statement attached to it. The final composition checks recognized citation provenance, not every claim's meaning. Read the evidence limits even when the answer has many citations.

### Save the routing-trace audit identifier

A normal combined response includes a trace with this **illustrative shape**, not a captured result:

```text
route=combined | company=NVIDIA | specialists=news,financial |
execution=parallel | composition=synthesized | rounds=3 |
policy=passed | audit_id=<this-request-audit-id>
```

The actual trace is usually one line. Copy its `audit_id` for Step 5. A separate **Specialist audit IDs** line can identify the two source records; those identifiers are different from the routing-trace identifier.

`composition=specialist_fallback` means separate results were returned instead of a validated combined narrative. That is not automatically an HTTP failure or a claim that both parts of the question were answered.

The trace is a summary, not a certificate. In particular, `policy=passed` is derived from the policy-check configuration in this implementation. Inspect the individual audit check results before concluding which checks passed. `rounds=3` is also not a count of model calls.

A withholding or audit-failure notice can replace the normal response and omit this trace. Step 5 explains how to inspect candidate records without issuing another question.

[Implementation: response traces and composition checks](../4-orchestrator-agent/src/host_agent/routing_agent.py)

## Step 4: distinguish observability from successful execution

Keep the **Client terminal** open. Look at the existing service terminals from the previous episodes; do not launch additional services or run direct expert queries.

| Observation | What it tells you | What it does not establish |
|---|---|---|
| Client `Response time` | Elapsed wall-clock time around the SDK request. | Per-model speed, token cost, or time spent at each dependency. |
| HTTP `200` in a service log | That HTTP exchange returned successfully. | That evidence was sufficient or a research answer was released. |
| A warning or retry message | A particular stage encountered a condition that needs inspection. | That the final answer necessarily failed; a bounded recovery or fallback may have occurred. |
| An audit identifier | A lookup key for a request's record. | That the record was successfully persisted or its content is correct. |
| A returned answer or stop notice | The application outcome presented to the client. | That every downstream operation succeeded. |

The outer HTTP response reports zero token-usage values as placeholders. Those are not measured aggregate usage and do not mean that the work consumed no tokens or incurred no provider cost. Some downstream audit fields record model usage when returned, but the supplied client does not calculate a complete cost report.

Use audit timing fields to investigate where time was spent. Parallel work overlaps, and the client, model calls, retrieval, and audit records measure different boundaries. Adding every recorded duration does not necessarily reproduce the client's elapsed time.

The **Orchestrator reinforcement loop** discussed in this lab is runtime feedback within a bounded workflow. In this episode, its observable evidence is recorded model attempts, completion decisions, verification results, and correction or fallback outcomes. It is not a training run, and the client does not update model weights. A successful request need not use a correction attempt.

The observation surfaces used here are terminal output and local JSONL audit files. The supplied Compose configuration does not ship these audit files into OpenSearch Dashboards or configure a distributed-tracing backend. Dashboards is not automatically a viewer for the request's audit history.

[Implementation: HTTP response metadata](../4-orchestrator-agent/src/host_agent/__main__.py)

## Step 5: follow this request through its audit records

A citation connects a statement to a source reference. An audit connects the request to its execution, evidence registry, checks, and outcome. Following both is more useful than reading the final paragraph alone.

### Locate records by identifier, not by "the last line"

By default, records are written relative to each service's working directory:

| Record owner | Default path from the repository root |
|---|---|
| Request coordination | `4-orchestrator-agent/logs/orchestrator-audit.jsonl` |
| News evidence | `2-news-agent/logs/news-agent-audit.jsonl` |
| Financial evidence | `3-financials-agent/logs/financials-audit.jsonl` |

The inspection script below loads each package's configured audit path in a separate Python process. This avoids mixing the packages' similarly named `src` modules. It reads the coordination record by the ID you provide, then follows its `specialist_audit_id` values to the evidence-owner records. It also runs the two available hash-chain verifiers. It does not submit another application request or modify an audit file.

A newly opened shell cannot recover exports made only in another shell. If a service was started with a shell-only `AUDIT_LOG_PATH` override, enter that service's **actual absolute audit path** in `path_overrides` below. Those overrides affect only this inspection script. Otherwise, leave the dictionary empty. The printed paths let you check what is being read.

In the **Inspection terminal**:

```bash
cd /workspace/agentic-rag/5-client
read -r -p "Routing-trace audit_id (Enter to list recent records): " ORCH_AUDIT_ID
export ORCH_AUDIT_ID
```

Paste only the identifier, without backticks or the `audit_id=` prefix. Then run:

```bash
python - <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path.cwd().parent
packages = {
    "orchestrator": ("4-orchestrator-agent", "src.host_agent.config",
                     "src.host_agent.audit"),
    "news": ("2-news-agent", "src.common.config", None),
    "financial": ("3-financials-agent", "src.common.config",
                  "src.financials_agent.audit"),
}
# Only needed for service paths configured in a different shell.
# Example entry: "financial": "/absolute/path/to/financials-audit.jsonl"
path_overrides = {}


def read_records(owner):
    folder, config_module, verifier = packages[owner]
    cwd = root / folder
    if not cwd.is_dir():
        raise RuntimeError(f"Missing workshop package: {cwd}")
    if owner in path_overrides:
        path = Path(path_overrides[owner])
        if not path.is_absolute():
            raise RuntimeError("Inspection path overrides must be absolute.")
    else:
        probe = (
            "from pathlib import Path; "
            f"from {config_module} import load_settings; "
            "path = Path(load_settings().audit_log_path); "
            + ("path = path.expanduser(); " if owner == "news" else "")
            + "print(path.resolve())"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe], cwd=cwd,
            text=True, capture_output=True, check=True,
        )
        path = Path(result.stdout.strip())
    print(f"\n{owner} audit: {path}", flush=True)
    if not path.is_file():
        raise RuntimeError(f"No persisted audit file at {path}")
    if verifier:
        subprocess.run(
            [sys.executable, "-m", verifier, str(path)],
            cwd=cwd, check=True,
        )
    else:
        print("Append-only JSONL; no hash-chain verifier for this file.")
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise RuntimeError(f"Not a JSON object: {path}:{line_number}")
            records.append(record)
    return records


def find_record(records, audit_id):
    matches = [r for r in records if r.get("audit_id") == audit_id]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one record for {audit_id}; found {len(matches)}. "
            "Check the identifier, configured path, and service logs."
        )
    return matches[0]


try:
    records = read_records("orchestrator")
    audit_id = os.environ.get("ORCH_AUDIT_ID", "").strip()
    if not audit_id:
        print("Recent record metadata; these are candidates, not an automatic match:")
        for record in records[-10:]:
            routing = record.get("routing", {})
            plan = routing.get("validated_plan", {})
            print(json.dumps({
                "timestamp": record.get("timestamp"),
                "audit_id": record.get("audit_id"),
                "request_id": record.get("request_id"),
                "company": plan.get("company"),
                "route": plan.get("request_type"),
                "outcome": record.get("outcome"),
            }))
        raise SystemExit(
            "Match the request using its time and service-log identifiers, "
            "then repeat the read/export command and this script. "
            "Do not assume the newest record is yours."
        )
    coordination = find_record(records, audit_id)
    print("\n=== Matching coordination record ===")
    print(json.dumps(coordination, indent=2, ensure_ascii=False))
    unresolved = []
    for result in coordination.get("specialists", []):
        owner = result.get("agent")
        source_id = result.get("specialist_audit_id")
        if owner not in {"news", "financial"} or not source_id:
            unresolved.append(str(owner))
            continue
        evidence_record = find_record(read_records(owner), source_id)
        print(f"\n=== Matching {owner} record: {source_id} ===")
        print(json.dumps(evidence_record, indent=2, ensure_ascii=False))
    if unresolved:
        raise RuntimeError(
            "Cannot follow an evidence-owner audit ID for: "
            + ", ".join(unresolved)
        )
except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
    raise SystemExit(f"Audit inspection stopped: {exc}")
PY
```

**Expected:** for a completed two-expert request with successfully persisted records, you see the matching coordination record and the two matching evidence-owner records. The identifiers differ, but the recorded links connect them. Earlier requests or recovery attempts can leave other records in the same files; the script does not assume there are only three records in total.

Inspect this output locally before sharing it. The script displays the actual records, including metadata, warning text, and any raw-query fields explicitly enabled in the service configuration.

If no routing trace was returned, pressing Enter at the ID prompt lists recent coordination metadata. Match it to the run's time and available service-log identifiers before repeating the read-only inspection. If several records fit and no identifier distinguishes them, correlation remains uncertain. A missing file or missing match is not evidence that auditing succeeded.

### Read the coordination record

| Field | Question to answer |
|---|---|
| `audit_id`, `request_id`, `request` | Is this the response you are investigating, and what request metadata was recorded? |
| `routing.validated_plan` and `specialists` | Which participants were planned, and which results actually returned? |
| `models` and `synthesis` | Which models were used, how many attempts occurred, and was a combined narrative produced? |
| `governance.check_configuration` and `governance.checks` | Were all three categories enabled, and what did each enabled check report? |
| `outcome.status` | Was the outcome completed, withheld, or unable to produce a combined narrative? |

`completed` can include evidence limitations. `synthesis_unavailable` can accompany released separate sections. Likewise, `synthesis.released` means non-empty synthesized text was obtained; it is not an independent guarantee that later checks and audit persistence allowed release to the client.

Read the actual model identifiers in these records rather than inferring them from the client banner or the architecture diagram. The configured model provider can differ from the original demo while the application responsibilities remain the same.

### Trace one news citation and one market citation

Choose a news citation and a market citation that actually appear in your response. Find their matching entries in the records printed above. Do not substitute a citation from another request.

| Record | Fields to inspect | What they connect |
|---|---|---|
| News | `retrieval.evidence[].citation_id`, source identifiers, URL/path, dates, and `content_sha256` | The citation to the retrieved source metadata and the hash of its evidence text. |
| News | `route`, `retrieval`, `generation`, `verification`, `outcome` | Selected source paths, failures or missing evidence, generation attempts, checks, and release outcome. |
| Financial | `evidence[].evidence_id`, `kind`, `source`, `as_of`, `metadata`, and `evidence_content_sha256` | The citation to its source kind, time boundary, provenance, and content hash. |
| Financial | `execution_plan`, `tool_calls`, `retrieval`, `verification`, `outcome` | Symbol and source intent, recorded tool success/failure, any filing retrieval, checks, and release outcome. |

For the market portion, inspect whether a `get_stock_quote` tool call succeeded and whether the evidence is associated with `NVDA`. The audit retains argument-key names and hashes rather than a raw copy of every tool argument and result. A financial `retrieval` value of `null` means the filing retrieval path did not run; it does not imply that the market-data call was missing.

For the news portion, compare publication and retrieval dates and inspect missing-source or retrieval-error information. Do not relabel historical corpus evidence as current news because the request was made today.

The schemas are intentionally different. News records retain per-attempt generation verification. Financial records expose correction calls in `model_calls`, but the completion record's `verification` is the final result, not a full archive of every draft verdict. The coordination record does not duplicate the entire source evidence registry.

**Checkpoint:** you can connect an actual citation to its owning audit record and explain the recorded evidence path, time boundary, and check outcome. If one side returned no usable evidence, document that gap instead of claiming the research request was fully answered.

## Step 6: understand what the audit protects

### Hash consistency is not proof of truth

Step 5 invokes the existing verifiers for the coordination and financial files. A successful coordination check reports `valid: true` with a record count. A successful financial check reports `Audit chain is valid; records=<count>`. News uses append-only JSONL and does not provide the same hash-chain verification.

The two chain formats differ: coordination uses `previous_hash` and `entry_hash`; financial records use `previous_record_hash` and `record_hash`. Their verifiers check that the stored record content and links agree with the computed hashes.

A valid chain does not establish that the sources were accurate or that the model interpreted them correctly. These chains are not signed or externally anchored. They do not independently detect an entire file replaced with a recomputed chain or records removed from the end. A missing coordination file is treated by its standalone verifier as an empty valid chain, which is why Step 6 also checks file existence and an exact record match.

Do not edit or re-hash an active audit file to make a failing check pass. Preserve the file and inspect the error, permissions, and available disk space.

### An Audit ID is not proof of persistence

The implementations do not have identical audit-failure behavior:

| Record owner | Behavior when its audit write fails |
|---|---|
| News | With release checks enabled, the answer is replaced with a withholding notice. |
| Financial | The append error is logged, but the existing answer and outcome can still be returned. |
| Request coordination | With release checks enabled, an audit verification/write failure replaces the would-be response with a stop notice. |

The financial behavior is an important limitation. An answer may carry its Audit ID even though no matching financial record was saved. Check the actual file and the existing service log for `Audit append failed`. A valid coordination record does not certify the persistence or integrity of the underlying evidence-owner records.

This is why the exercise follows the identifiers all the way to the files rather than treating their presence in an answer as sufficient proof.

### Data minimization is not anonymity or reproducibility

Default auditing avoids raw question text in the News and coordination request fields. Financial records use query/session hashes and omit dedicated raw answer and evidence-body fields. Nevertheless, records can retain company names, source URLs, task/session metadata, endpoints, rationale, and error messages. Those fields can contain sensitive information.

Keep normal processes at `INFO`. The financial implementation's `DEBUG` boundary logging can include questions, evidence, tool results, prompts, and answers. Review records and logs before sharing them; do not publish credentials or assume that hashes make all related metadata anonymous.

A content hash helps compare retained evidence with the recorded version. It cannot reconstruct a missing article, tool response, or generated answer. These data-minimized records are not a complete replay archive.

The client itself keeps its transcript only in memory, but its shared `api-world-demo` label is also used for server-side context continuity. Restarting the client clears its local message list; it does not establish a new authenticated user or guarantee that the running service's cached context is cleared. This is a single-user demonstration, not a session-isolated deployment.

Finally, the supplied Compose file mounts no persistent audit storage for `lab`. Container removal or replacement can lose these files. Preserve any records needed for your review before removing the environment. The logs are workshop-local evidence, not a durable compliance archive.

## Completion checkpoint

You have completed this lab!

While the client is waiting at `You:`, press **Ctrl+C** to close it without sending another question. This stops the client only; it does not stop the services or the Compose environment.

The central lesson is that **an inspectable answer preserves its chain of custody**. The client displays the result. Citations identify the evidence references. Audit records explain the recorded work and checks. None of those alone guarantees correctness, but together they let you investigate the result rather than trust its fluency.

Return to the [workshop episode index](../README.md).

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

## Source map

These links identify the implementation used by this episode. The audit references are for inspecting the completed client request, not for restarting or reimplementing the earlier components.

| File | Responsibility |
|---|---|
| [`client.py`](client.py) and [`Makefile`](Makefile) | Interactive input, conversation history, request timing, and client startup. |
| [`HTTP entry point`](../4-orchestrator-agent/src/host_agent/__main__.py) | Request/response contract, session-label handling, and placeholder usage fields. |
| [`Request records and response composition`](../4-orchestrator-agent/src/host_agent/routing_agent.py) | Routing trace, audit-ID links, check results, outcomes, and release behavior. |
| [`Coordination audit verifier`](../4-orchestrator-agent/src/host_agent/audit.py) | Coordination hash-chain validation. |
| [`News audit records`](../2-news-agent/src/news_agent/audit.py) and [`record completion`](../2-news-agent/src/news_agent/news_agent.py) | Evidence metadata, request outcomes, and audit-write handling. |
| [`Financial audit verifier`](../3-financials-agent/src/financials_agent/audit.py) and [`record completion`](../3-financials-agent/src/financials_agent/financials_agent.py) | Financial evidence/check records, hash validation, and audit-persistence limitation. |
