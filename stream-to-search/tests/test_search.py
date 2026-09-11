"""Offline tests for instaclustr_sdk.search's Kafka consumers — no Kafka or ClickHouse needed."""
import asyncio
import contextlib
import threading
import time

from instaclustr_sdk import search
from instaclustr_sdk.config import SearchConfig


class SlowConsumer:
    """Stands in for confluent_kafka.Consumer, recording which thread does what, in order."""

    def __init__(self):
        self.events = []
        self.polling = threading.Event()

    def poll(self, timeout):
        self.events.append(("poll-start", threading.get_ident()))
        self.polling.set()
        time.sleep(0.2)
        self.events.append(("poll-end", threading.get_ident()))
        return None

    def close(self):
        self.events.append(("close", threading.get_ident()))


def test_stream_anomalies_closes_only_after_the_inflight_poll(monkeypatch):
    consumer = SlowConsumer()
    monkeypatch.setattr(search, "_client", object())
    monkeypatch.setattr(search, "_config", SearchConfig())
    monkeypatch.setattr(search, "_make_consumer", lambda group_id, from_beginning: consumer)

    async def consume_then_cancel():
        async def consume():
            async for _ in search.stream_anomalies():
                pass

        task = asyncio.create_task(consume())
        while not consumer.polling.is_set():  # cancel while a poll is in flight
            await asyncio.sleep(0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(consume_then_cancel())

    assert [kind for kind, _ in consumer.events] == ["poll-start", "poll-end", "close"]
    assert len({thread for _, thread in consumer.events}) == 1  # poll and close share a thread
