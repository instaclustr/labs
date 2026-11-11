"""Step 2 — Synchronous detection (the "demo" flow).

Goal: publish a healthy history plus one obvious spike, then detect it immediately. The
watermark returned by publish() makes the publish -> detect loop deterministic: find_anomalies
waits until exactly this batch is queryable before running the z-score query.

Run:  python demo/02_detect_sync.py
"""
import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search

import sensors


def main() -> None:
    stream.setup()
    search.setup()

    # A healthy baseline for the whole fleet, plus a single disconnect spike on sensor-1.
    batch = sensors.baseline(per_sensor=200)
    spike = sensors.disconnect_spike("sensor-1")
    batch.append(spike)

    watermark = stream.publish(batch)
    print(f"published {watermark.count} readings (incl. one 95 C spike on sensor-1)")

    # Synchronous, deterministic: block until ingested, then detect on demand.
    anomalies = search.find_anomalies(wait_for=watermark)
    print(f"\ndetected {len(anomalies)} anomaly(ies):")
    for a in anomalies:
        tag = "  <-- the spike we injected" if a.event_id == spike.event_id else ""
        print(f"  {a.entity}/{a.metric}  value={a.value:6.2f}  z-score={a.zscore:6.2f}{tag}")

    print("\nNote: the algorithm flagged the spike, but it can't tell you *why*.")
    print("Next: demo/03_detect_async.py (continuous) or demo/04_explain_with_ai.py (the 'why').")


if __name__ == "__main__":
    main()
