"""AI agent + RAG demo: detect an anomaly, then have Claude analyze and explain it.

Flow:
  1. Seed the RAG knowledge base with domain context (what is / isn't a real anomaly).
  2. Publish a baseline series + a spike and detect it (same as demo_sync.py).
  3. explain_anomaly() — one Claude call grounded in retrieved context; remembers the finding.
  4. investigate_anomaly() — Claude pulls metric stats and searches memory via tools.

Run (after `docker compose up -d` and `pip install -e ".[ai]"`):
    export ANTHROPIC_API_KEY=...        # required
    export VOYAGE_API_KEY=...           # optional; better embeddings than the local fallback
    python examples/agent_explain.py
"""
import random

import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search
import instaclustr_sdk.rag as rag
import instaclustr_sdk.agent as agent
from instaclustr_sdk import Event


def main() -> None:
    stream.setup()
    search.setup()
    rag.setup()    # local hashing embedder unless VOYAGE_API_KEY is set
    agent.setup()  # uses ANTHROPIC_API_KEY

    # 1. Seed domain knowledge about what is / isn't an anomaly for this signal.
    rag.add_knowledge(
        "For sensor-1 temperature, the normal operating range is 18-22 C. Brief single-sample "
        "spikes above 90 C are almost always sensor disconnects, not real temperature.",
        kind="domain", entity="sensor-1", metric="temperature",
    )
    rag.add_knowledge(
        "A genuine overheating event shows values sustained above 30 C across many consecutive "
        "readings, not one isolated sample.",
        kind="domain", entity="sensor-1", metric="temperature",
    )

    # 2. Baseline + spike, then detect.
    events = [Event("sensor-1", "temperature", random.gauss(20, 0.5)) for _ in range(200)]
    events.append(Event("sensor-1", "temperature", 95.0))
    wm = stream.publish(events)
    anomalies = search.find_anomalies(wait_for=wm)
    if not anomalies:
        print("no anomalies detected")
        return
    a = anomalies[0]
    print(f"detected: {a.entity}/{a.metric} value={a.value:.2f} zscore={a.zscore:.2f}\n")

    # 3. Single-call explanation, grounded in the seeded context; remember the finding.
    print("=== explain_anomaly (single call + RAG) ===")
    print(agent.explain_anomaly(a, remember=True))

    # 4. Full agentic investigation (Claude calls tools to gather evidence first).
    print("\n=== investigate_anomaly (agentic, tool-using) ===")
    print(agent.investigate_anomaly(a))


if __name__ == "__main__":
    main()
