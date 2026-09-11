"""Search / analytics side of the SDK.

Module-level functions backed by a module-global ClickHouse client:

    import instaclustr_sdk.search as search
    search.setup(host="localhost", port=8123)

    # SYNC (demo): wait for a published batch, then detect on demand
    anomalies = search.find_anomalies(wait_for=wm)

    # ASYNC (production): tail the "anomalies" Kafka topic
    async for a in search.stream_anomalies(): ...
    sub = search.on_anomaly(lambda a: ...)      # background thread; sub.stop() to end
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator, Callable, List, Optional

import clickhouse_connect
from confluent_kafka import Consumer

from . import detection
from .config import SearchConfig
from .models import Anomaly, Watermark

_client = None
_config: Optional[SearchConfig] = None


def setup(
    host: str = "localhost",
    port: int = 8123,
    username: str = "default",
    password: str = "",
    database: str = "default",
    bootstrap_servers: str = "localhost:29092",
    anomalies_topic: str = "anomalies",
):
    """Initialise the ClickHouse client and record Kafka settings for the async consumer."""
    global _client, _config
    _config = SearchConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        bootstrap_servers=bootstrap_servers,
        anomalies_topic=anomalies_topic,
    )
    _client = clickhouse_connect.get_client(
        host=host, port=port, username=username, password=password, database=database
    )
    return _config


def _require():
    if _client is None or _config is None:
        raise RuntimeError("instaclustr_sdk.search.setup(...) must be called before searching")
    return _client, _config


# --------------------------------------------------------------------------- sync path


def _wait_for_watermark(wm: Watermark, timeout: float) -> None:
    """Poll until ClickHouse has ingested past every partition offset in the watermark."""
    client, config = _require()
    if not wm or not wm.offsets:
        return
    deadline = time.monotonic() + timeout
    query = (
        f"SELECT kafka_partition, max(kafka_offset) "
        f"FROM {config.events_table} GROUP BY kafka_partition"
    )
    while True:
        rows = client.query(query).result_rows
        seen = {int(p): int(o) for p, o in rows}
        if all(seen.get(p, -1) >= target for p, target in wm.offsets.items()):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"events not fully ingested within {timeout}s "
                f"(target={wm.offsets}, seen={seen})"
            )
        time.sleep(0.1)


def _row_to_anomaly(row) -> Anomaly:
    event_id, entity, metric, value, ts, zscore = row
    return Anomaly(
        event_id=str(event_id),
        entity=entity,
        metric=metric,
        value=float(value),
        ts=ts,
        zscore=float(zscore),
    )


def find_anomalies(
    wait_for: Optional[Watermark] = None,
    timeout: float = 10.0,
    threshold: float = detection.DEFAULT_THRESHOLD,
    entity: Optional[str] = None,
) -> List[Anomaly]:
    """Synchronously detect anomalies.

    If `wait_for` is given, block until that batch is queryable (so a publish()+find loop
    is deterministic), then run the detection query on demand and return the hits.
    """
    client, _ = _require()
    if wait_for is not None:
        _wait_for_watermark(wait_for, timeout)
    sql, params = detection.zscore_sql(threshold=threshold, entity=entity)
    result = client.query(sql, parameters=params)
    return [_row_to_anomaly(r) for r in result.result_rows]


def metric_stats(entity: str, metric: str, window: str = "1 HOUR") -> dict:
    """Summary statistics for one entity/metric over a trailing window.

    Reusable analytics helper; also what the AI agent's investigation tool calls.
    """
    client, config = _require()
    sql = f"""
        SELECT count() AS n, avg(value) AS mean, stddevPop(value) AS stddev,
               min(value) AS min, max(value) AS max,
               argMax(value, ts) AS latest, max(ts) AS last_ts
        FROM {config.events_table}
        WHERE entity = {{entity:String}} AND metric = {{metric:String}}
          AND ts > now() - INTERVAL {window}
    """
    rows = client.query(sql, parameters={"entity": entity, "metric": metric}).result_rows
    if not rows or int(rows[0][0]) == 0:
        return {"entity": entity, "metric": metric, "window": window, "count": 0}
    n, mean, stddev, mn, mx, latest, last_ts = rows[0]
    return {
        "entity": entity,
        "metric": metric,
        "window": window,
        "count": int(n),
        "mean": float(mean),
        "stddev": float(stddev),
        "min": float(mn),
        "max": float(mx),
        "latest": float(latest),
        "last_ts": str(last_ts),
    }


# -------------------------------------------------------------------------- async path


def _make_consumer(group_id: str, from_beginning: bool) -> Consumer:
    _, config = _require()
    consumer = Consumer(
        {
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest" if from_beginning else "latest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([config.anomalies_topic])
    return consumer


def _msg_to_anomaly(msg) -> Anomaly:
    d = json.loads(msg.value())
    return Anomaly(
        event_id=str(d["event_id"]),
        entity=d["entity"],
        metric=d["metric"],
        value=float(d["value"]),
        ts=d.get("ts"),
        zscore=float(d["zscore"]),
    )


async def stream_anomalies(
    from_beginning: bool = False,
    group_id: Optional[str] = None,
    poll_timeout: float = 1.0,
) -> AsyncIterator[Anomaly]:
    """Async generator yielding anomalies as they arrive on the Kafka topic."""
    _require()
    group_id = group_id or f"instaclustr-sdk-stream-{uuid.uuid4()}"
    consumer = _make_consumer(group_id, from_beginning)
    loop = asyncio.get_running_loop()
    # The consumer gets its own thread: confluent-kafka consumers aren't thread-safe, and
    # closing one while another thread is inside poll() can leave that thread stuck forever,
    # which then blocks interpreter exit. Queued on the same thread, close() waits for the poll.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="instaclustr-sdk-stream")
    try:
        while True:
            msg = await loop.run_in_executor(executor, consumer.poll, poll_timeout)
            if msg is None or msg.error():
                continue
            yield _msg_to_anomaly(msg)
    finally:
        await loop.run_in_executor(executor, consumer.close)
        executor.shutdown(wait=False)


class Subscription:
    """Handle for an on_anomaly() background consumer; call stop() to end it."""

    def __init__(self, stop_event: threading.Event, thread: threading.Thread):
        self._stop = stop_event
        self._thread = thread

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._thread.join(timeout)


def on_anomaly(
    callback: Callable[[Anomaly], None],
    from_beginning: bool = False,
    group_id: Optional[str] = None,
) -> Subscription:
    """Invoke `callback(anomaly)` on a background thread for each anomaly on the topic."""
    _require()
    group_id = group_id or f"instaclustr-sdk-cb-{uuid.uuid4()}"
    consumer = _make_consumer(group_id, from_beginning)
    stop_event = threading.Event()

    def _run():
        try:
            while not stop_event.is_set():
                msg = consumer.poll(0.5)
                if msg is None or msg.error():
                    continue
                try:
                    callback(_msg_to_anomaly(msg))
                except Exception:  # a bad callback shouldn't kill the consumer loop
                    pass
        finally:
            consumer.close()

    thread = threading.Thread(target=_run, name="instaclustr-sdk-on-anomaly", daemon=True)
    thread.start()
    return Subscription(stop_event, thread)
