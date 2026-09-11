"""Asynchronous production flow.

One task publishes a continuous stream (non-blocking). Detection runs continuously inside
ClickHouse (a refreshable materialized view) and every anomaly is republished to the Kafka
"anomalies" topic. Here we consume that topic two ways at once:
  * an `async for` over search.stream_anomalies()
  * an on_anomaly(callback) background subscription

Run (after `docker compose up -d` and `pip install -e .`):
    python examples/prod_async.py        # Ctrl-C to stop
"""
import asyncio
import random

import instaclustr_sdk.stream as stream
import instaclustr_sdk.search as search
from instaclustr_sdk import Event


async def produce_forever() -> None:
    i = 0
    while True:
        value = random.gauss(20, 0.5)
        if i > 0 and i % 50 == 0:
            value = random.uniform(80, 120)  # inject an anomaly periodically
        await stream.publish_async(
            [Event(entity="sensor-1", metric="temperature", value=value)]
        )
        i += 1
        await asyncio.sleep(0.1)


async def consume_stream() -> None:
    async for a in search.stream_anomalies(from_beginning=False):
        print(f"[generator] {a.entity}/{a.metric} value={a.value:.2f} zscore={a.zscore:.2f}")


def on_hit(a) -> None:
    print(f"[callback]  {a.entity}/{a.metric} value={a.value:.2f} zscore={a.zscore:.2f}")


async def main() -> None:
    stream.setup(bootstrap_servers="localhost:29092", topic="events")
    search.setup(host="localhost", port=8123)

    sub = search.on_anomaly(on_hit)  # background thread; both consumers see every anomaly
    try:
        await asyncio.gather(produce_forever(), consume_stream())
    finally:
        sub.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped")
