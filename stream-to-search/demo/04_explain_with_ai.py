"""Step 4 — Explain anomalies with AI + RAG.

Goal: turn statistical flags into verdicts. We create TWO anomalies the algorithm flags
identically-looking (both high z-scores):

  * sensor-1: a single 95 C spike        -> benign (a disconnect)
  * sensor-2: a sustained ~34 C stretch  -> genuine (real overheating)

We seed the RAG knowledge base with the domain rules that tell them apart, then let Claude
judge each one. Watch the two verdicts diverge — that's the AI layer earning its keep.

Each run uses a fresh fleet (sensor-1-<run id>, ...), so readings left by earlier steps don't
leak into this one's per-sensor statistics.

Run (needs `pip install -e ".[ai]"` and ANTHROPIC_API_KEY):
    python demo/04_explain_with_ai.py
"""
import uuid

import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search
import instaclustr_sdk.rag as rag
import instaclustr_sdk.agent as agent

import sensors


def first_for(anomalies, entity):
    return next((a for a in anomalies if a.entity == entity), None)


def main() -> None:
    stream.setup()
    search.setup()
    rag.setup()    # local embedder unless VOYAGE_API_KEY is set
    agent.setup()  # uses ANTHROPIC_API_KEY

    # 1. Seed domain knowledge: what is / isn't a real anomaly for these sensors.
    rag.add_knowledge(
        "For the temperature sensors, the normal operating range is 18-22 C. A single isolated "
        "reading above 90 C is almost always a sensor disconnect, not real temperature.",
        kind="domain", metric=sensors.METRIC,
    )
    rag.add_knowledge(
        "Genuine overheating shows temperatures sustained above 30 C across many consecutive "
        "readings, not one isolated sample.",
        kind="domain", metric=sensors.METRIC,
    )

    # 2. Produce a baseline plus the two contrasting failure modes, then detect. The fleet gets
    #    fresh names: z-scores are per sensor over the last hour, and the stack still holds the
    #    earlier steps' readings (step 3 injects 95 C spikes into sensor-1..3), which would blur
    #    the statistics and hand us the wrong anomaly.
    run = uuid.uuid4().hex[:4]
    fleet = [f"{s}-{run}" for s in sensors.SENSORS]
    disconnected, overheating = fleet[0], fleet[1]

    batch = sensors.baseline(per_sensor=200, fleet=fleet)
    batch.append(sensors.disconnect_spike(disconnected))
    batch += sensors.overheating_run(overheating, n=15, temp=34.0)
    watermark = stream.publish(batch)
    anomalies = [a for a in search.find_anomalies(wait_for=watermark) if a.entity in fleet]
    print(f"algorithm flagged {len(anomalies)} point(s) across the fleet\n")

    # 3. Explain the disconnect (single call + RAG context; remember the finding).
    spike = first_for(anomalies, disconnected)
    if spike:
        print(f"=== {disconnected} (single 95 C spike) — explain_anomaly ===")
        print(agent.explain_anomaly(spike, remember=True))
        print()

    # 4. Investigate the overheating (agentic — Claude pulls stats + searches memory via tools).
    heat = first_for(anomalies, overheating)
    if heat:
        print(f"=== {overheating} (sustained ~34 C) — investigate_anomaly ===")
        print(agent.investigate_anomaly(heat))

    print("\nSame algorithm, two different verdicts. That's the point.")


if __name__ == "__main__":
    main()
