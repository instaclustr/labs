"""Streaming (producer) side of the SDK.

Module-level functions backed by a single module-global producer, so usage reads like:

    import instaclustr_sdk.stream as stream
    stream.setup(bootstrap_servers="localhost:29092")
    wm = stream.publish(events)            # synchronous (demo)
    await stream.publish_async(events)     # asynchronous (production)
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable, Iterable, List, Optional, Union

from confluent_kafka import Producer

from .config import StreamConfig
from .models import Event, Watermark

_producer: Optional[Producer] = None
_config: Optional[StreamConfig] = None

EventLike = Union[Event, dict]


def setup(bootstrap_servers: str = "localhost:29092", topic: str = "events", **producer_config):
    """Initialise the module-global Kafka producer."""
    global _producer, _config
    _config = StreamConfig(bootstrap_servers=bootstrap_servers, topic=topic)
    conf = {"bootstrap.servers": bootstrap_servers}
    conf.update(producer_config)
    _producer = Producer(conf)
    return _config


def _require():
    if _producer is None or _config is None:
        raise RuntimeError("instaclustr_sdk.stream.setup(...) must be called before publishing")
    return _producer, _config


def _as_events(events: Union[EventLike, Iterable[EventLike]]) -> List[Event]:
    if isinstance(events, (Event, dict)):
        events = [events]
    out: List[Event] = []
    for e in events:
        if isinstance(e, Event):
            out.append(e)
        elif isinstance(e, dict):
            out.append(Event(**e))
        else:
            raise TypeError(f"expected Event or dict, got {type(e).__name__}")
    return out


def _encode(ev: Event) -> bytes:
    return json.dumps(ev.to_json_row()).encode("utf-8")


def publish(events: Union[EventLike, Iterable[EventLike]], wait: bool = True) -> Watermark:
    """Publish events. Synchronous by default (blocks until brokers ack).

    With wait=True (demo): flushes and returns a fully-populated Watermark you can pass
    to search.find_anomalies(wait_for=...). With wait=False: fire-and-forget; the returned
    Watermark fills in as delivery callbacks arrive (prefer publish_async for async work).
    """
    producer, config = _require()
    batch = _as_events(events)
    if not batch:
        return Watermark()

    offsets: dict = {}
    delivered = {"count": 0}
    errors: list = []

    def _cb(err, msg):
        if err is not None:
            errors.append(err)
            return
        p, o = msg.partition(), msg.offset()
        if o is not None and o > offsets.get(p, -1):
            offsets[p] = o
        delivered["count"] += 1

    for ev in batch:
        producer.produce(config.topic, value=_encode(ev), on_delivery=_cb)
        producer.poll(0)

    if wait:
        producer.flush()
        if errors:
            raise RuntimeError(f"failed to deliver {len(errors)} message(s): {errors[0]}")

    return Watermark(offsets=offsets, count=delivered["count"])


async def publish_async(
    events: Union[EventLike, Iterable[EventLike]],
    on_delivery: Optional[Callable] = None,
) -> Watermark:
    """Publish without blocking the event loop; resolves to a Watermark once all rows ack."""
    producer, config = _require()
    batch = _as_events(events)
    if not batch:
        return Watermark()

    loop = asyncio.get_running_loop()
    fut: "asyncio.Future[Watermark]" = loop.create_future()
    offsets: dict = {}
    errors: list = []
    remaining = {"n": len(batch)}

    def _cb(err, msg):
        if on_delivery is not None:
            on_delivery(err, msg)
        if err is None:
            p, o = msg.partition(), msg.offset()
            if o is not None and o > offsets.get(p, -1):
                offsets[p] = o
        else:
            errors.append(err)
        remaining["n"] -= 1
        if remaining["n"] == 0 and not fut.done():
            wm = Watermark(offsets=offsets, count=len(batch) - len(errors))
            loop.call_soon_threadsafe(fut.set_result, wm)

    for ev in batch:
        producer.produce(config.topic, value=_encode(ev), on_delivery=_cb)
        producer.poll(0)

    async def _drive():
        # Service delivery callbacks cooperatively until the batch is fully acked.
        while not fut.done():
            producer.poll(0)
            await asyncio.sleep(0.01)

    driver = loop.create_task(_drive())
    try:
        return await fut
    finally:
        driver.cancel()


def flush(timeout: float = 10.0) -> int:
    """Block until all outstanding messages are delivered; returns messages still queued."""
    producer, _ = _require()
    return producer.flush(timeout)
