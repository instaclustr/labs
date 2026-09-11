"""Synchronous demo flow — mirrors the vision in Purpose.md.

Publish a baseline series plus one injected spike, then immediately find anomalies.
The SDK waits for the just-published batch to become queryable (offset watermark), so a
publish() -> find_anomalies() loop is deterministic and feels instant.

Run (after `docker compose up -d` and `pip install -e .`):
    python examples/demo_sync.py
"""
import random

import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search
from instaclustr_sdk import Event


def main() -> None:
    stream.setup(bootstrap_servers="localhost:29092", topic="events")
    search.setup(host="localhost", port=8123)

    # A normal signal for one entity/metric ...
    events = [
        Event(entity="sensor-1", metric="temperature", value=random.gauss(20, 0.5))
        for _ in range(200)
    ]
    # ... plus a single, obvious spike.
    spike = Event(entity="sensor-1", metric="temperature", value=95.0)
    events.append(spike)

    wm = stream.publish(events)  # synchronous: blocks until brokers ack
    print(f"published {wm.count} events; watermark offsets={wm.offsets}")

    anomalies = search.find_anomalies(wait_for=wm)  # blocks until queryable, then detects
    print(f"found {len(anomalies)} anomaly(ies):")
    for a in anomalies:
        marker = "  <-- injected spike" if a.event_id == spike.event_id else ""
        print(f"  {a.entity}/{a.metric} value={a.value:.2f} zscore={a.zscore:.2f}{marker}")


if __name__ == "__main__":
    main()
