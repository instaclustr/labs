"""The anomaly-detection rule, in one place.

`zscore_sql()` is the single source of truth for the SYNC path (run on demand by
search.find_anomalies). The SAME z-score logic is mirrored in
clickhouse/init/02_anomalies.sql for the ASYNC path (a refreshable materialized view).
If you change the rule here, change it there too.

A point is anomalous when its value is more than `threshold` standard deviations from the
per-(entity, metric) mean, where mean/stddev are computed over a trailing `window`.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

DEFAULT_THRESHOLD = 3.0
"""How many standard deviations from the mean make a point anomalous."""

DEFAULT_WINDOW = "1 HOUR"
"""The trailing interval that the mean and standard deviation cover."""


def zscore_sql(
    *,
    events_table: str = "events",
    threshold: float = DEFAULT_THRESHOLD,
    window: str = DEFAULT_WINDOW,
    recent: Optional[str] = None,
    entity: Optional[str] = None,
) -> Tuple[str, Dict[str, object]]:
    """Build the detection query.

    Returns (sql, parameters) for use with clickhouse_connect's server-side binding.
    `window`/`recent` are code-controlled interval literals (e.g. "1 HOUR"); `entity`
    is bound as a parameter to stay injection-safe.
    """
    conditions = [f"abs((e.value - s.mu) / nullIf(s.sigma, 0)) > {float(threshold)}"]
    params: Dict[str, object] = {}

    if entity is not None:
        conditions.append("e.entity = {entity:String}")
        params["entity"] = entity
    if recent is not None:
        conditions.append(f"e.ts > now() - INTERVAL {recent}")

    where = " AND ".join(conditions)
    sql = f"""
WITH stats AS (
    SELECT entity, metric, avg(value) AS mu, stddevPop(value) AS sigma
    FROM {events_table}
    WHERE ts > now() - INTERVAL {window}
    GROUP BY entity, metric
)
SELECT e.event_id, e.entity, e.metric, e.value, e.ts,
       (e.value - s.mu) / nullIf(s.sigma, 0) AS zscore
FROM {events_table} AS e
INNER JOIN stats AS s USING (entity, metric)
WHERE {where}
ORDER BY e.ts
""".strip()
    return sql, params
