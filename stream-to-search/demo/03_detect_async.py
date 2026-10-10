"""Step 3 — Asynchronous detection (the "production" flow).

Goal: run detection continuously. A producer streams the fleet non-blockingly; detection runs
inside ClickHouse on a timer (the refreshable materialized view) and is republished to the Kafka
"anomalies" topic. We consume that topic two ways at once — an async generator and a callback.

This script runs for ~40 seconds and then stops on its own. With --forever it keeps streaming
until Ctrl-C, which is handy while watching the Grafana dashboard.

Run:  python demo/03_detect_async.py [--forever]
"""
import asyncio
import random
import sys

import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search
from instaclustr_sdk import Event

import sensors

RUN_SECONDS = 40


async def produce(stop: asyncio.Event) -> None:
    """Stream mostly-normal readings, injecting a disconnect spike every few seconds."""
    i = 0
    while not stop.is_set():
        entity = random.choice(sensors.SENSORS)
        value = random.gauss(20.0, 0.5)
        if i and i % 40 == 0:  # ~every 4s at 0.1s cadence
            value = 95.0
            print(f"  · injected spike on {entity}")
        await stream.publish_async([Event(entity, sensors.METRIC, value)])
        i += 1
        await asyncio.sleep(0.1)


async def consume(stop: asyncio.Event) -> None:
    """Tail the anomalies topic via the async generator."""
    try:
        async for a in search.stream_anomalies(from_beginning=False):
            print(f"[generator] {a.entity} value={a.value:.1f} z={a.zscore:.1f}")
            if stop.is_set():
                break
    except asyncio.CancelledError:
        pass


async def main(forever: bool) -> None:
    stream.setup()
    search.setup()

    # Establish a healthy baseline first so per-sensor z-scores are meaningful.
    print("seeding baseline...")
    stream.publish(sensors.baseline(per_sensor=200))

    # Callback delivery (background thread) — sees every anomaly, same as the generator.
    sub = search.on_anomaly(
        lambda a: print(f"[callback]  {a.entity} value={a.value:.1f} z={a.zscore:.1f}")
    )

    duration = "until Ctrl-C" if forever else f"for {RUN_SECONDS}s"
    print(f"streaming {duration} (detection lags ~5s behind — the MV refresh interval)\n")
    stop = asyncio.Event()
    producer = asyncio.create_task(produce(stop))
    consumer = asyncio.create_task(consume(stop))
    try:
        if forever:
            await asyncio.Event().wait()  # nothing sets it; Ctrl-C cancels this wait
        else:
            await asyncio.sleep(RUN_SECONDS)
    finally:
        stop.set()
        producer.cancel()
        consumer.cancel()
        await asyncio.gather(producer, consumer, return_exceptions=True)
        sub.stop()
    print("\ndone. Next: demo/04_explain_with_ai.py")


if __name__ == "__main__":
    try:
        asyncio.run(main(forever="--forever" in sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nstopped")
