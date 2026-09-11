"""instaclustr_sdk — a seamless streaming-to-search SDK (Kafka + ClickHouse).

    import instaclustr_sdk.stream as stream
    import instaclustr_sdk.search as search

The AI layer is imported on its own: `instaclustr_sdk.agent` (needs the `[ai]` extra) explains
anomalies, grounded in the `instaclustr_sdk.rag` knowledge base. `import instaclustr_sdk` loads
neither, so the core needs no AI packages.
"""
from __future__ import annotations

from . import detection, search, stream
from .models import Anomaly, Event, Watermark

__all__ = ["stream", "search", "detection", "Event", "Anomaly", "Watermark"]
__version__ = "0.1.0"
