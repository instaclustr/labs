"""End-to-end integration tests.

Require the full stack running and are skipped unless RUN_INTEGRATION=1:

    docker compose up -d
    pip install -e ".[ai,dev]"
    RUN_INTEGRATION=1 pytest

The agent test additionally needs a model and makes live calls (cents): ANTHROPIC_API_KEY for
the default Claude model, or INSTACLUSTR_SDK_AGENT_MODEL plus that provider's key.
scripts/smoke_test.sh runs all of this against a fresh stack.
"""
import os
import time
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="integration test; start the stack and set RUN_INTEGRATION=1",
)


def _unique_entity() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


def test_sync_find_anomalies_detects_spike():
    import instaclustr_sdk.stream as stream
    import instaclustr_sdk.search as search
    from instaclustr_sdk import Event

    stream.setup()
    search.setup()

    entity = _unique_entity()
    events = [Event(entity=entity, metric="m", value=10.0 + (i % 3) * 0.1) for i in range(100)]
    spike = Event(entity=entity, metric="m", value=500.0)
    events.append(spike)

    wm = stream.publish(events)
    assert wm.count == len(events)

    anomalies = search.find_anomalies(wait_for=wm, entity=entity)
    detected_ids = {a.event_id for a in anomalies}
    assert spike.event_id in detected_ids


def test_async_anomaly_reaches_kafka_topic():
    import instaclustr_sdk.stream as stream
    import instaclustr_sdk.search as search
    from instaclustr_sdk import Event

    stream.setup()
    search.setup()

    entity = _unique_entity()
    hits = []

    sub = search.on_anomaly(
        lambda a: hits.append(a) if a.entity == entity else None,
        from_beginning=False,
    )
    try:
        events = [Event(entity=entity, metric="m", value=10.0) for _ in range(100)]
        events.append(Event(entity=entity, metric="m", value=500.0))
        stream.publish(events)

        # refreshable MV runs every 5s, then republishes to Kafka; allow generous slack.
        deadline = time.time() + 30
        while time.time() < deadline and not hits:
            time.sleep(1)

        assert hits, "no anomaly received on the 'anomalies' topic within 30s"
    finally:
        sub.stop()


@pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("INSTACLUSTR_SDK_AGENT_MODEL")),
    reason="live agent test; needs ANTHROPIC_API_KEY, or INSTACLUSTR_SDK_AGENT_MODEL plus that "
    "provider's key (makes real model calls)",
)
def test_agent_returns_typed_verdicts_and_remembers_them():
    pytest.importorskip("pydantic_ai")
    import instaclustr_sdk.agent as agent
    import instaclustr_sdk.rag as rag
    import instaclustr_sdk.search as search
    import instaclustr_sdk.stream as stream
    from instaclustr_sdk import Event

    stream.setup()
    search.setup()
    rag.setup()
    agent.setup()

    entity = _unique_entity()
    events = [Event(entity=entity, metric="m", value=10.0 + (i % 3) * 0.1) for i in range(100)]
    spike = Event(entity=entity, metric="m", value=500.0)
    events.append(spike)
    anomalies = search.find_anomalies(wait_for=stream.publish(events), entity=entity)
    anomaly = next((a for a in anomalies if a.event_id == spike.event_id), None)
    assert anomaly is not None

    explained = agent.explain_anomaly(anomaly, remember=True)
    investigated = agent.investigate_anomaly(anomaly)

    for verdict in (explained, investigated):
        assert verdict.verdict in ("genuine", "benign", "uncertain")
        assert verdict.cause and verdict.action
    findings = rag.retrieve(entity, kind="finding", entity=entity)
    assert any(f"Verdict: {explained.verdict}." in d.text for d in findings)
