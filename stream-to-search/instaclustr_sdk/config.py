"""Configuration objects for the stream (producer) and search (ClickHouse + consumer) sides."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StreamConfig:
    bootstrap_servers: str = "localhost:29092"
    topic: str = "events"


@dataclass
class SearchConfig:
    host: str = "localhost"
    port: int = 8123
    username: str = "default"
    password: str = ""
    database: str = "default"
    # Kafka side, for consuming the "anomalies" topic in the async flow.
    bootstrap_servers: str = "localhost:29092"
    anomalies_topic: str = "anomalies"
    events_table: str = "events"
