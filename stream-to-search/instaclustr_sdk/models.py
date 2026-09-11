"""Plain data types shared across the SDK."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Union


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_ts(ts: datetime) -> str:
    """Render a datetime as a ClickHouse DateTime64(3)-friendly string (millisecond precision)."""
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts.strftime("%Y-%m-%d %H:%M:%S.") + f"{ts.microsecond // 1000:03d}"


@dataclass
class Event:
    """A single measurement to publish onto the stream."""

    entity: str
    metric: str
    value: float
    ts: datetime = field(default_factory=_now)
    """When the measurement was taken; defaults to now. A naive datetime is taken as UTC."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique id, carried through to any `Anomaly` for this event; defaults to a random UUID."""

    def to_json_row(self) -> Dict[str, object]:
        """Serialize to a JSONEachRow-compatible dict matching the `events` table columns."""
        return {
            "event_id": self.event_id,
            "entity": self.entity,
            "metric": self.metric,
            "value": self.value,
            "ts": _format_ts(self.ts),
        }


@dataclass
class Anomaly:
    """A detected outlier, from either the sync query or the async Kafka topic."""

    event_id: str
    entity: str
    metric: str
    value: float
    ts: Union[datetime, str]
    """UTC timestamp: a `datetime` from `find_anomalies()`, a string from the async topic."""
    zscore: float
    """Standard deviations from the entity/metric's trailing mean; negative means below it."""


@dataclass
class Watermark:
    """Per-partition max Kafka offset produced by a publish() call.

    Used by the synchronous flow to wait until ClickHouse has ingested a batch.
    """

    offsets: Dict[int, int] = field(default_factory=dict)
    """Partition number -> the highest offset this batch wrote to it."""
    count: int = 0
    """How many events Kafka acknowledged."""
