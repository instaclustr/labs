"""instaclustr_sdk — a seamless streaming-to-search SDK (Kafka + ClickHouse).

    import instaclustr_sdk.stream as stream
    import instaclustr_sdk.search as search
"""
from __future__ import annotations

from . import detection, search, stream
from .models import Anomaly, Event, Watermark

__all__ = ["stream", "search", "detection", "Event", "Anomaly", "Watermark"]
__version__ = "0.1.0"
