"""Step 1 — Publish events onto the stream.

Goal: prove the stream side works end to end. We set up the producer, publish a few sensor
readings, and confirm they became queryable in ClickHouse.

Run:  python demo/01_hello_publish.py
"""
import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search

import sensors  # demo/sensors.py (this dir is on sys.path when run as a script)


def main() -> None:
    # Point the SDK at the local stack (these are the defaults; shown for clarity).
    stream.setup(bootstrap_servers="localhost:29092", topic="events")
    search.setup(host="localhost", port=8123)

    # Publish 5 normal readings for sensor-1. publish() is synchronous: it blocks until the
    # broker acks and returns a Watermark (the Kafka offsets this batch wrote).
    events = [sensors.normal_reading("sensor-1") for _ in range(5)]
    watermark = stream.publish(events)
    print(f"published {watermark.count} events; watermark offsets = {watermark.offsets}")

    # find_anomalies(wait_for=...) blocks until ClickHouse has ingested past that watermark.
    # Here nothing is anomalous — the point is simply that the data is now queryable.
    anomalies = search.find_anomalies(wait_for=watermark)
    print(f"anomalies among these normal readings: {len(anomalies)}  (expected 0)")
    print("\nStream side works. Next: demo/02_detect_sync.py")


if __name__ == "__main__":
    main()
